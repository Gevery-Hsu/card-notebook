import io
import json
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.store import Store, NoteInput, NoteUpdate


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "data"))


def create(client, **fields):
    result = client.post("/api/notes", json={"body": "一句中文灵感", **fields})
    assert result.status_code == 201, result.text
    return result.json()


def test_markdown_roundtrip_and_restart(client):
    body = "# 标题\n\n**粗体**与*斜体*\n\n> 引用\n\n- 项目一\n- [链接](https://example.com)\n\n" + "长篇中文。" * 5000
    n = create(client, body=body, title="长文", tags=["写作", "阅读"], source="书籍第 32 页", source_url="https://example.com")
    root = client.app.state.store.root
    raw = (root / "notes" / n["filename"]).read_text(encoding="utf-8")
    assert "tags:" in raw and "阅读" in raw and body in raw
    restarted = TestClient(create_app(root))
    got = restarted.get(f'/api/notes/{n["id"]}').json()
    assert got["body"] == body and got["tags"] == n["tags"]
    assert restarted.get(f'/api/notes/{n["id"]}/export').content.decode("utf-8") == raw


def test_filter_chinese_multi_tags_source_dates(client):
    a = create(client, body="傍晚散步", category="随笔", tags=["生活", "观察"], source="某本书的第32页")
    create(client, body="散步", category="灵感", tags=["生活"])
    assert client.get("/api/notes", params={"q": "傍晚 散步", "category": "随笔", "tags": ["生活", "观察"]}).json()["total"] == 1
    assert client.get("/api/notes", params={"q": "第32页"}).json()["total"] == 1
    day = a["created_at"][:10]
    assert client.get("/api/notes", params={"start": day, "end": day}).json()["total"] == 2
    assert client.get("/api/notes", params={"start": "2099-01-01"}).json()["total"] == 0
    assert client.get("/api/notes", params={"start": "2026-12-01", "end": "2026-01-01"}).status_code == 422
    assert client.get("/api/notes", params={"date_field": "__class__"}).status_code == 422


def test_external_edit_conflict_delete_and_bad_file(client):
    n = create(client)
    path = client.app.state.store.notes_dir / n["filename"]
    path.write_text(path.read_text(encoding="utf-8").replace("一句中文灵感", "外部编辑保留"), encoding="utf-8")
    assert client.put(f'/api/notes/{n["id"]}', json={**n, "body": "旧窗口覆盖"}).status_code == 409
    assert client.post(f'/api/notes/{n["id"]}/trash', json={"version": n["version"]}).status_code == 409
    assert "外部编辑保留" in path.read_text(encoding="utf-8")
    broken = path.parent / "bad.md"
    broken.write_text("这是普通文本", encoding="utf-8")
    meta = client.get("/api/meta").json()
    assert meta["errors"] and meta["total"] == 1 and broken.read_text(encoding="utf-8") == "这是普通文本"
    assert client.get("/api/export.zip").status_code == 409


def test_two_windows_only_one_update_wins(client):
    n = create(client)
    store = client.app.state.store
    def save(body):
        try:
            return store.update(n["id"], NoteUpdate(**{**n, "body": body}))["body"]
        except Exception as exc:
            return exc.status_code
    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(save, ["窗口 A", "窗口 B"]))
    assert outcomes.count(409) == 1


def test_trash_restore_and_no_overwrite(client):
    n = create(client)
    moved = client.post(f'/api/notes/{n["id"]}/trash', json={"version": n["version"]})
    assert moved.status_code == 200
    assert client.get("/api/notes").json()["total"] == 0
    assert client.get("/api/notes?trash=true").json()["total"] == 1
    root = client.app.state.store.notes_dir
    target = root / n["filename"]
    target.write_text("不可覆盖", encoding="utf-8")
    assert client.post(f'/api/notes/{n["id"]}/restore', json={"version": n["version"]}).status_code == 409
    assert target.read_text(encoding="utf-8") == "不可覆盖"
    target.unlink()
    assert client.post(f'/api/notes/{n["id"]}/restore', json={"version": n["version"]}).status_code == 200


def test_category_rename_delete_including_trash(client):
    assert client.post("/api/categories", json={"name": "旅行"}).status_code == 200
    a = create(client, category="旅行")
    b = create(client, category="旅行")
    client.post(f'/api/notes/{b["id"]}/trash', json={"version": b["version"]})
    assert client.put("/api/categories/旅行", json={"name": "远行"}).status_code == 200
    assert client.get(f'/api/notes/{b["id"]}').json()["category"] == "远行"
    assert client.delete("/api/categories/远行").status_code == 200
    assert client.get(f'/api/notes/{a["id"]}').json()["category"] == "其他"
    assert client.delete("/api/categories/其他").status_code == 422
    assert client.post("/api/categories", json={"name": "随笔"}).status_code == 409


def test_export_selection_and_migration(client, tmp_path):
    n = create(client, category="书摘", source="示例书", tags=["阅读"])
    create(client, category="灵感")
    content = client.get("/api/export.zip?category=书摘").content
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert len([p for p in archive.namelist() if p.endswith('.md')]) == 1
        target = tmp_path / "migrated"
        archive.extractall(target)
    migrated = Store(target)
    assert migrated.get(n["id"])["source"] == "示例书"
    assert migrated.get(n["id"])["tags"] == ["阅读"]


def test_write_failure_preserves_original(client):
    n = create(client)
    with patch("backend.store.os.replace", side_effect=PermissionError("read-only")):
        assert client.put(f'/api/notes/{n["id"]}', json={**n, "body": "不会写入"}).status_code == 503
    assert client.get(f'/api/notes/{n["id"]}').json()["body"] == n["body"]
    assert not list(client.app.state.store.notes_dir.glob('.writing-*'))


def test_validation_and_origin(client):
    assert client.post('/api/notes', json={"body": "  "}).status_code == 422
    assert client.post('/api/notes', json={"body": "x", "source_url": "javascript:alert(1)"}).status_code == 422
    assert client.post('/api/notes', json={"body": "x"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post('/api/notes', json={"body": "x"}, headers={"Origin": "http://testserver"}).status_code == 201
    assert client.get('/api/notes', headers={"Host": "evil.example"}).status_code == 400
    assert client.get('/api/notes/../../categories.json').status_code == 404


def test_duplicate_ids_and_invalid_config_are_preserved(client):
    n = create(client)
    store = client.app.state.store
    shutil.copyfile(store.notes_dir / n["filename"], store.notes_dir / "duplicate.md")
    assert client.get('/api/notes').json()["total"] == 0
    assert client.get('/api/meta').json()["errors"]
    store.config.write_text("[invalid]", encoding="utf-8")
    assert client.post('/api/categories', json={"name": "new"}).status_code == 409
    assert store.config.read_text(encoding="utf-8") == "[invalid]"


def test_unknown_frontmatter_preserved_and_stable_filename(client):
    n = create(client)
    path = client.app.state.store.notes_dir / n["filename"]
    path.write_text(path.read_text(encoding="utf-8").replace("---\n", "---\ncustom_field: 我的备注\n", 1), encoding="utf-8")
    latest = client.get(f'/api/notes/{n["id"]}').json()
    updated = client.put(f'/api/notes/{n["id"]}', json={**latest, "title": "换个标题", "category": "随笔"}).json()
    assert updated["filename"] == n["filename"]
    assert "custom_field: 我的备注" in path.read_text(encoding="utf-8")


def test_symlink_outside_not_read(client, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("private outside content", encoding="utf-8")
    link = client.app.state.store.notes_dir / "link.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    assert client.get('/api/meta').json()["errors"]
    assert outside.read_text(encoding="utf-8") == "private outside content"


def test_category_with_slash_and_pagination(client):
    assert client.post('/api/categories', json={'name': '书籍/电影'}).status_code == 200
    create(client, category='书籍/电影')
    assert client.put('/api/categories/书籍%2F电影', json={'name': '文化'}).status_code == 200
    assert client.get('/api/notes?category=文化').json()['total'] == 1
    for i in range(5):
        create(client, body=f'分页笔记 {i}')
    first = client.get('/api/notes?limit=3&order=asc').json()
    second = client.get('/api/notes?limit=3&offset=3&order=asc').json()
    assert first['total'] == 6 and second['total'] == 6
    assert not ({x['id'] for x in first['items']} & {x['id'] for x in second['items']})


def test_backdated_note_edit_export_and_sort(client):
    old = create(client, created_date='2009-03-04', body='补录旧笔记')
    recent = create(client)
    assert old['created_date'] == '2009-03-04'
    assert old['created_at'] == '2009-03-04T00:00:00+08:00'
    assert client.get('/api/notes').json()['items'][0]['id'] == recent['id']
    assert client.get('/api/notes?order=asc').json()['items'][0]['id'] == old['id']
    edited = client.put(f"/api/notes/{old['id']}", json={**old, 'created_date': '2008-02-29'}).json()
    assert edited['created_date'] == '2008-02-29' and edited['filename'] == old['filename']
    assert client.put(f"/api/notes/{old['id']}", json={**old, 'created_date': '2007-01-01'}).status_code == 409
    unchanged = client.put(f"/api/notes/{old['id']}", json={'body': '只改正文', 'version': edited['version']}).json()
    assert unchanged['created_date'] == '2008-02-29'
    exported = client.get(f"/api/notes/{old['id']}/export").text
    assert '2008-02-29T00:00:00+08:00' in exported
    restarted = TestClient(create_app(client.app.state.store.root))
    assert restarted.get(f"/api/notes/{old['id']}").json()['created_date'] == '2008-02-29'
    assert client.post('/api/notes', json={'body': 'x', 'created_date': '2025-02-29'}).status_code == 422


def test_default_date_uses_beijing_and_legacy_timestamp_preserved(client):
    with patch('backend.store.now', return_value='2026-10-11T00:01:00+08:00'):
        note = create(client)
    assert note['created_date'] == '2026-10-11'
    edited = client.put(f"/api/notes/{note['id']}", json={**note, 'body': '修改内容'}).json()
    assert edited['created_at'] == note['created_at']
    path = client.app.state.store.notes_dir / note['filename']
    path.write_text(path.read_text(encoding='utf-8').replace(note['created_at'], '2026-10-10T16:01:00+00:00'), encoding='utf-8')
    assert client.get(f"/api/notes/{note['id']}").json()['created_date'] == '2026-10-11'


def test_category_order_icons_legacy_migration_and_export(client, tmp_path):
    store = client.app.state.store
    original = store.config.read_bytes()
    meta = client.get('/api/meta').json()
    assert meta['category_icons']['灵感'] == 'lightbulb'
    assert store.config.read_bytes() == original  # Opening legacy config does not rewrite it.
    note = create(client, category='随笔')
    note_path = store.notes_dir / note['filename']
    raw = note_path.read_bytes()
    order = ['其他', '书摘', '灵感', '随笔']
    result = client.put('/api/category-order', json={'categories': order, 'version': meta['category_version']})
    assert result.status_code == 200
    meta = result.json()
    assert meta['categories'] == order
    changed = client.put('/api/categories/随笔', json={'name': '随笔', 'icon': 'leaf', 'version': meta['category_version']})
    assert changed.status_code == 200 and changed.json()['category_icons']['随笔'] == 'leaf'
    assert note_path.read_bytes() == raw
    assert client.put('/api/categories/其他', json={'name': '其他', 'icon': 'compass'}).status_code == 200
    assert client.put('/api/categories/其他', json={'name': '杂项'}).status_code == 422
    with zipfile.ZipFile(io.BytesIO(client.get('/api/export.zip').content)) as archive:
        migrated = tmp_path / 'category-migration'
        archive.extractall(migrated)
    metadata = Store(migrated).metadata()
    assert metadata['categories'] == order
    assert metadata['category_icons']['随笔'] == 'leaf'
    assert metadata['category_icons']['其他'] == 'compass'


def test_category_icon_rename_delete_conflict_and_validation(client):
    result = client.post('/api/categories', json={'name': '旅行', 'icon': 'compass'})
    assert result.status_code == 200
    version = result.json()['category_version']
    renamed = client.put('/api/categories/旅行', json={'name': '远行', 'version': version})
    assert renamed.json()['category_icons']['远行'] == 'compass'
    assert '旅行' not in renamed.json()['category_icons']
    assert client.put('/api/category-order', json={'categories': renamed.json()['categories'], 'version': version}).status_code == 409
    meta = renamed.json()
    assert client.put('/api/category-order', json={'categories': ['其他'] * len(meta['categories']), 'version': meta['category_version']}).status_code == 409
    assert client.post('/api/categories', json={'name': '错误图标', 'icon': 'unknown'}).status_code == 422
    assert client.delete('/api/categories/远行').status_code == 200
    assert '远行' not in client.get('/api/meta').json()['category_icons']
    store = client.app.state.store
    original = store.config.read_bytes()
    meta = client.get('/api/meta').json()
    with patch('backend.store.os.replace', side_effect=PermissionError('read-only')):
        assert client.put('/api/category-order', json={'categories': list(reversed(meta['categories'])), 'version': meta['category_version']}).status_code == 503
    assert store.config.read_bytes() == original
    store.config.write_text('{"categories":["其他"],"icons":{"其他":[]}}', encoding='utf-8')
    assert client.get('/api/meta').json()['errors']
    assert client.put('/api/category-order', json={'categories': ['其他'], 'version': meta['category_version']}).status_code == 409
