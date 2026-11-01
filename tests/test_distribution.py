"""A fresh clone is empty and custom domains come from configuration."""
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.auth import hash_key


def test_fresh_install_is_empty_and_exports_defaults(tmp_path):
    client = TestClient(create_app(tmp_path / 'new-notebook'))
    meta = client.get('/api/meta').json()
    assert meta['total'] == 0 and meta['trash_total'] == 0
    assert '其他' in meta['categories']
    assert list((tmp_path / 'new-notebook' / 'notes').iterdir()) == []


def test_cloud_hostname_config_and_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('VERCEL_URL', 'preview.example.vercel.app')
    monkeypatch.setenv('VERCEL_PROJECT_PRODUCTION_URL', 'notebook.example.vercel.app')
    monkeypatch.setenv('NOTEBOOK_STORAGE', 'postgres')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://invalid.invalid/not-used')
    monkeypatch.setenv('NOTEBOOK_KEY_HASH', hash_key('distribution-test-only-key'))
    monkeypatch.setenv('NOTEBOOK_ALLOWED_HOSTS', 'notes.example.com')
    for host in ['notes.example.com', 'preview.example.vercel.app', 'notebook.example.vercel.app']:
        client = TestClient(create_app(), base_url='https://' + host)
        assert client.get('/api/health').status_code == 200
        assert client.get('/api/notes').status_code == 401
    assert TestClient(create_app(), base_url='https://unlisted.example.com').get('/api/health').status_code == 400
