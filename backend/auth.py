"""One owner, opaque revocable device sessions, and persistent login throttling."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

COOKIE = "notebook_session"
SESSION_SECONDS = 365 * 24 * 60 * 60


def hash_key(key: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(key.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f"scrypt:{salt}:{value}"


def valid_hash(value):
    try:
        kind, salt, hashed = value.split(":")
        return kind == "scrypt" and len(bytes.fromhex(salt)) == 16 and len(bytes.fromhex(hashed)) == 64
    except (ValueError, AttributeError):
        return False


class Sessions:
    def __init__(self, key_hash, database_url=None, sqlite_path=None):
        if not valid_hash(key_hash):
            raise ValueError("NOTEBOOK_KEY_HASH 无效，请使用密钥配置工具生成")
        self.key_hash = key_hash
        self.key_id = hashlib.sha256(key_hash.encode()).hexdigest()
        self.database_url = database_url
        self.sqlite_path = sqlite_path
        if not database_url:
            Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            with self.connection() as db:
                db.execute("CREATE TABLE IF NOT EXISTS notebook_sessions (token_hash TEXT PRIMARY KEY,key_id TEXT NOT NULL,expires BIGINT NOT NULL,created BIGINT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS notebook_login_limits (bucket TEXT PRIMARY KEY,attempts INTEGER NOT NULL,reset_at BIGINT NOT NULL)")

    @contextmanager
    def connection(self):
        if self.database_url:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=10) as db:
                yield db
        else:
            with sqlite3.connect(self.sqlite_path, timeout=15) as db:
                db.row_factory = sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                yield db

    def execute(self, db, sql, values=()):
        return db.execute(sql.replace("?", "%s") if self.database_url else sql, values)

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def authenticated(self, token):
        if not token or len(token) > 200:
            return False
        with self.connection() as db:
            row = self.execute(db, "SELECT key_id,expires FROM notebook_sessions WHERE token_hash=?", (self.token_hash(token),)).fetchone()
            return bool(row and row["expires"] > int(time.time()) and hmac.compare_digest(row["key_id"], self.key_id))

    def login(self, key):
        from fastapi import HTTPException
        current = int(time.time())
        # Reserve an attempt atomically before expensive password verification.
        # Global for this private app: not bypassable by forged IP headers or new instances.
        with self.connection() as db:
            self.execute(db, "INSERT INTO notebook_login_limits(bucket,attempts,reset_at) VALUES ('owner',0,?) ON CONFLICT (bucket) DO NOTHING", (current+900,))
            sql = "SELECT * FROM notebook_login_limits WHERE bucket='owner'" + (" FOR UPDATE" if self.database_url else "")
            row = self.execute(db, sql).fetchone()
            attempts = row["attempts"] if row["reset_at"] > current else 0
            if attempts >= 30:
                raise HTTPException(429, "尝试次数过多，请 15 分钟后重试")
            self.execute(db, "UPDATE notebook_login_limits SET attempts=?,reset_at=? WHERE bucket='owner'", (attempts+1, row["reset_at"] if row["reset_at"] > current else current+900))
        candidate = hash_key(key, self.key_hash.split(":")[1])
        if not hmac.compare_digest(candidate, self.key_hash):
            raise HTTPException(401, "访问密钥不正确")
        token = secrets.token_urlsafe(48)
        with self.connection() as db:
            self.execute(db, "DELETE FROM notebook_sessions WHERE expires<=? OR key_id<>?", (current, self.key_id))
            self.execute(db, "INSERT INTO notebook_sessions(token_hash,key_id,expires,created) VALUES (?,?,?,?)", (self.token_hash(token), self.key_id, current+SESSION_SECONDS, current))
        return token

    def revoke(self, token, all_devices=False):
        with self.connection() as db:
            if all_devices:
                self.execute(db, "DELETE FROM notebook_sessions")
            elif token:
                self.execute(db, "DELETE FROM notebook_sessions WHERE token_hash=?", (self.token_hash(token),))
