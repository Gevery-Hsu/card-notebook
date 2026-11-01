"""Run from the project root: python -m scripts.cloud --help. Never logs secrets."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path

from backend.auth import hash_key
from backend.store import Store, DEFAULT_CATEGORIES

ROOT = Path(__file__).resolve().parent.parent


def source_snapshot(path):
    path = path.resolve()
    for name in ("notes", "trash", "categories.json"):
        if not (path / name).exists():
            raise ValueError(f"原数据缺少 {name}，停止迁移")
    store = Store(path)
    if store.errors:
        raise ValueError("原数据存在解析问题，停止迁移：" + json.dumps(store.errors, ensure_ascii=False))
    items = [(item, store.read_raw(item)) for item in store.notes.values()]
    hashes = {("trash/" if n["trashed"] else "notes/") + n["filename"]: hashlib.sha256(raw).hexdigest() for n, raw in items}
    hashes["categories.json"] = hashlib.sha256(store.config.read_bytes()).hexdigest()
    return store, items, hashes


def initialize(url):
    import psycopg
    with psycopg.connect(url, connect_timeout=10) as db:
        db.execute("SELECT pg_advisory_xact_lock(731876501)")
        db.execute((ROOT / "backend/schema.sql").read_text(encoding="utf-8"))
        db.execute("INSERT INTO notebook_settings(id,categories) VALUES (1,%s) ON CONFLICT (id) DO NOTHING", (json.dumps(DEFAULT_CATEGORIES, ensure_ascii=False).encode(),))


def migrate(url, source, verify=False):
    from backend.postgres import PostgresStore
    local, items, hashes = source_snapshot(source)
    cloud = PostgresStore(url)
    with cloud.lock:
        existing = cloud.query() + cloud.query(trash=True)
        remote = {("trash/" if n["trashed"] else "notes/") + n["filename"]: hashlib.sha256(cloud.read_raw(n)).hexdigest() for n in existing}
        remote["categories.json"] = hashlib.sha256(cloud.config()[0]).hexdigest()
        if remote == hashes:
            return {"verified": True, "files": len(hashes), "already_imported": True}
        if verify:
            raise ValueError("云端与本地文件哈希或文件清单不一致")
        if existing:
            raise ValueError("云端已有不同内容，停止导入；不覆盖、不合并")
        remote_config = cloud.config()[0]
        if remote_config != local.config.read_bytes() and json.loads(remote_config) != DEFAULT_CATEGORIES:
            raise ValueError("云端已有不同的分类配置，停止导入；不覆盖")
        for item, raw in items:
            cloud.put_raw(raw, item["filename"], item["trashed"], insert=True)
        cloud.conn.execute("UPDATE notebook_settings SET categories=%s WHERE id=1", (local.config.read_bytes(),))
    # A new connection confirms the committed data, not just transaction-local writes.
    return migrate(url, source, verify=True)


def main():
    parser = argparse.ArgumentParser(description="初始化、只读核对及迁移私人卡片本；连接串从 DATABASE_URL 环境变量读取")
    parser.add_argument("command", choices=["inspect", "init", "import", "verify", "key"])
    parser.add_argument("--source", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    if args.command == "key":
        key = getpass.getpass("设置访问密钥（至少 16 个字符，不回显）：")
        if len(key) < 16 or key != getpass.getpass("再次输入："):
            raise ValueError("密钥太短或两次输入不一致")
        # Only the salted hash is printed; the access key is never written to disk.
        print("NOTEBOOK_KEY_HASH=" + hash_key(key))
    elif args.command == "inspect":
        store, items, hashes = source_snapshot(args.source)
        print(json.dumps({"notes": sum(not n["trashed"] for n, _ in items), "trash": sum(n["trashed"] for n, _ in items), "categories": len(store.categories), "hashes": hashes}, ensure_ascii=False, indent=2))
    else:
        url = os.environ.get("DATABASE_URL_UNPOOLED") or os.environ.get("DATABASE_URL")
        if not url:
            raise ValueError("缺少 DATABASE_URL；请在本地终端安全设置，不要粘贴到聊天")
        if args.command == "init":
            initialize(url)
            print("数据库结构初始化完成，现有笔记未被修改")
        else:
            print(json.dumps(migrate(url, args.source, args.command == "verify"), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Database driver errors can contain connection details. Keep them out of logs.
        print(str(exc) if isinstance(exc, ValueError) else "云端操作失败，请检查连接、数据库结构和权限；未自动重试")
        raise SystemExit(1)
