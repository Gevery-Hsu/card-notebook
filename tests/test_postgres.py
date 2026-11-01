"""Real PostgreSQL acceptance; restricted to a disposable loopback notebook_qa database."""
import io
import json
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from unittest.mock import patch

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.auth import hash_key
from backend.postgres import PostgresStore
from backend.store import NoteInput, NoteUpdate, Store
from scripts.cloud import initialize, migrate


@pytest.fixture
def cloud(monkeypatch):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to disposable loopback notebook_qa database')
    parsed = urlsplit(url)
    assert parsed.hostname in ('127.0.0.1', 'localhost') and parsed.path == '/notebook_qa'
    initialize(url)
    with psycopg.connect(url) as db:
        db.execute('TRUNCATE notebook_notes,notebook_sessions,notebook_login_limits,notebook_settings')
    initialize(url)
    monkeypatch.setenv('NOTEBOOK_STORAGE', 'postgres')
    monkeypatch.setenv('DATABASE_URL', url)
    monkeypatch.setenv('NOTEBOOK_KEY_HASH', hash_key('postgres-qa-only-key'))
    client = TestClient(create_app(), base_url='https://testserver')
    assert client.post('/api/auth/unlock', json={'key': 'postgres-qa-only-key'}).status_code == 200
    return client, url


def new(client, **extra):
    result = client.post('/api/notes', json={'body': '中文散步的灵感', **extra})
    assert result.status_code == 201, result.text
    return result.json()


def test_cloud_crud_search_export_and_restart(cloud):
    c, url = cloud
    n = new(c, created_date='2008-02-29', tags=['生活', '观察'], source='书籍第32页')
    new(c, category='随笔', body='其他')
    assert c.get('/api/notes', params={'q': '中文 散步', 'tags': ['生活', '观察']}).json()['total'] == 1
    assert c.get('/api/notes', params={'q': '第32页', 'start': '2008-02-29', 'end': '2008-02-29'}).json()['total'] == 1
    assert c.get('/api/notes', params={'q': '%_'}).json()['total'] == 0
    updated = c.put(f'/api/notes/{n["id"]}', json={**n, 'created_date': '2009-03-04', 'body': '# 标题\n\n**粗体**与*斜体*\n\n> 引用\n\n- 列表\n\n' + '长篇中文。'*5000}).json()
    restarted = PostgresStore(url)
    with restarted.lock:
        assert restarted.get(n['id'])['body'] == updated['body']
    exported = c.get(f'/api/notes/{n["id"]}/export').content
    assert updated['body'].encode() in exported and b'2009-03-04' in exported
    with zipfile.ZipFile(io.BytesIO(c.get('/api/export.zip').content)) as archive:
        assert len(archive.namelist()) == 3


def test_cloud_conflicts_between_instances_and_trash(cloud):
    c, url = cloud
    n = new(c)
    def save(body):
        try:
            return PostgresStore(url).update(n['id'], NoteUpdate(**{**n, 'body': body}))['body']
        except Exception as exc:
            return exc.status_code
    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(save, ['窗口A', '窗口B'])).count(409) == 1
    latest = c.get(f'/api/notes/{n["id"]}').json()
    moved = c.post(f'/api/notes/{n["id"]}/trash', json={'version': latest['version']}).json()
    assert c.post(f'/api/notes/{n["id"]}/restore', json={'version': latest['version']}).status_code == 409
    assert c.get('/api/notes?trash=true').json()['total'] == 1
    with zipfile.ZipFile(io.BytesIO(c.get('/api/backup.zip').content)) as archive:
        assert 'trash/' + n['filename'] in archive.namelist()
    assert c.post(f'/api/notes/{n["id"]}/restore', json={'version': moved['version']}).status_code == 200


def test_cloud_category_transactions_icons_and_raw_preservation(cloud):
    c, _ = cloud
    c.post('/api/categories', json={'name': '旅行', 'icon': 'compass'})
    n = new(c, category='旅行')
    raw = c.get(f'/api/notes/{n["id"]}/export').content
    meta = c.get('/api/meta').json()
    reordered = c.put('/api/category-order', json={'categories': list(reversed(meta['categories'])), 'version': meta['category_version']}).json()
    assert c.get(f'/api/notes/{n["id"]}/export').content == raw
    assert c.put('/api/category-order', json={'categories': meta['categories'], 'version': meta['category_version']}).status_code == 409
    renamed = c.put('/api/categories/旅行', json={'name': '远行', 'version': reordered['category_version']}).json()
    assert renamed['category_icons']['远行'] == 'compass'
    c.delete('/api/categories/远行')
    assert c.get(f'/api/notes/{n["id"]}').json()['category'] == '其他'


def test_import_exact_bytes_unknown_metadata_and_idempotence(cloud, tmp_path):
    _, url = cloud
    local = Store(tmp_path / 'source')
    n = local.create(NoteInput(body='迁移正文\n\n', created_date='2001-01-01'))
    path = local.notes_dir / n['filename']
    raw = path.read_bytes().replace(b'---\n', b'---\nunknown: [1, 2]\n', 1)
    path.write_bytes(raw)
    assert migrate(url, local.root)['verified']
    assert migrate(url, local.root)['already_imported']
    remote = PostgresStore(url)
    with remote.lock:
        imported = remote.get(n['id'])
        assert remote.read_raw(imported) == raw
        updated = remote.update(n['id'], NoteUpdate(**{**imported, 'title': '修改标题'}))
        assert updated['filename'] == n['filename']
        assert b'unknown:' in remote.read_raw(updated)
    with pytest.raises(ValueError):
        migrate(url, local.root)


def test_failed_import_rolls_back_all_content(cloud, tmp_path):
    _, url = cloud
    local = Store(tmp_path / 'source')
    local.create(NoteInput(body='第一条')); local.create(NoteInput(body='第二条'))
    original = PostgresStore.put_raw
    count = 0
    def fail_second(self, *args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError('simulated failure')
        return original(self, *args, **kwargs)
    with patch.object(PostgresStore, 'put_raw', fail_second), pytest.raises(RuntimeError):
        migrate(url, local.root)
    remote = PostgresStore(url)
    assert remote.metadata()['total'] == 0


def test_cloud_auth_persistence_and_revocation(cloud):
    c, _ = cloud
    second = TestClient(create_app(), base_url='https://testserver')
    assert second.get('/api/meta').status_code == 401
    assert second.post('/api/auth/unlock', json={'key': 'postgres-qa-only-key'}).status_code == 200
    assert c.post('/api/auth/logout?all_devices=true').status_code == 200
    assert second.get('/api/backup.zip').status_code == 401
