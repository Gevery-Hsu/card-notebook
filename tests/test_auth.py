import io
import zipfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.auth import COOKIE, Sessions, hash_key


@pytest.fixture
def protected(tmp_path, monkeypatch):
    monkeypatch.setenv("NOTEBOOK_KEY_HASH", hash_key("a-test-only-key-123456"))
    monkeypatch.setenv("NOTEBOOK_AUTH_DB", str(tmp_path / "auth.sqlite3"))
    return TestClient(create_app(tmp_path / "data"))


def unlock(client):
    return client.post('/api/auth/unlock', json={'key': 'a-test-only-key-123456'})


def test_all_note_endpoints_protected_and_cookie(protected):
    for path in ['/api/meta', '/api/notes', '/api/export.zip', '/api/backup.zip', '/api/notes/abc/export']:
        result = protected.get(path)
        assert result.status_code == 401
        assert result.headers['cache-control'] == 'no-store'
    assert protected.post('/api/notes', json={'body': 'x'}).status_code == 401
    assert protected.get('/api/auth/status').json() == {'required': True, 'authenticated': False}
    result = unlock(protected)
    assert result.status_code == 200
    assert 'HttpOnly' in result.headers['set-cookie'] and 'SameSite=strict' in result.headers['set-cookie']
    assert 'a-test-only' not in result.headers['set-cookie']
    assert protected.get('/api/meta').status_code == 200
    assert 'data_dir' not in protected.get('/api/health').json()


def test_sessions_survive_restart_and_revoke_all(protected):
    unlock(protected)
    second = TestClient(protected.app)
    unlock(second)
    old_token = protected.cookies.get(COOKIE)
    restarted = Sessions(protected.app.state.sessions.key_hash, sqlite_path=protected.app.state.sessions.sqlite_path)
    assert restarted.authenticated(old_token)
    assert protected.post('/api/auth/logout?all_devices=true').status_code == 200
    assert second.get('/api/meta').status_code == 401
    assert not restarted.authenticated(old_token)


def test_key_rotation_expiry_and_wrong_key_limit(protected):
    assert protected.post('/api/auth/unlock', json={'key': 'wrong'}).status_code == 401
    unlock(protected)
    sessions = protected.app.state.sessions
    token = protected.cookies.get(COOKIE)
    rotated = Sessions(hash_key('another-key'), sqlite_path=sessions.sqlite_path)
    assert not rotated.authenticated(token)
    with patch('backend.auth.time.time', return_value=9999999999):
        assert not sessions.authenticated(token)
    for _ in range(28):
        assert protected.post('/api/auth/unlock', json={'key': 'wrong'}).status_code == 401
    assert unlock(protected).status_code == 429


def test_cross_origin_unlock_and_backup(protected):
    assert protected.post('/api/auth/unlock', json={'key': 'a-test-only-key-123456'}, headers={'Origin': 'https://evil.example'}).status_code == 403
    unlock(protected)
    n = protected.post('/api/notes', json={'body': '含回收站的完整备份'}).json()
    protected.post(f'/api/notes/{n["id"]}/trash', json={'version': n['version']})
    with zipfile.ZipFile(io.BytesIO(protected.get('/api/backup.zip').content)) as archive:
        assert 'trash/' + n['filename'] in archive.namelist()
        assert 'categories.json' in archive.namelist()
    protected.post('/api/auth/logout')
    assert protected.get('/api/backup.zip').status_code == 401


def test_cloud_fails_closed_without_auth(monkeypatch):
    monkeypatch.setenv('NOTEBOOK_STORAGE', 'postgres')
    monkeypatch.delenv('NOTEBOOK_KEY_HASH', raising=False)
    with pytest.raises(RuntimeError):
        create_app()
    monkeypatch.delenv('NOTEBOOK_STORAGE')
    monkeypatch.setenv('VERCEL', '1')
    with pytest.raises(RuntimeError):
        create_app()
