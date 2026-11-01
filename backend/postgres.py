"""Cloud persistence. Each operation is a database transaction, never a local file write."""
from __future__ import annotations

import io
import json
import threading
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException

from .store import Store, NoteInput, NoteUpdate, TZ, DEFAULT_CATEGORIES, DEFAULT_ICONS, CATEGORY_ICONS, digest, now


class PostgresStore:
    public = staticmethod(Store.public)
    _parse = Store._parse
    _serialize = Store._serialize
    errors: list = []

    def __init__(self, url: str):
        self.url = url
        self.local = threading.local()

    @contextmanager
    def transaction(self):
        if getattr(self.local, "connection", None) is not None:
            yield self.local.connection
            return
        with psycopg.connect(self.url, row_factory=dict_row, connect_timeout=10) as conn:
            self.local.connection = conn
            try:
                # All mutations use this row lock, including imports and category changes.
                # Safe across Vercel instances; no process-local lock or index is authoritative.
                row = conn.execute("SELECT id FROM notebook_settings WHERE id = 1 FOR UPDATE").fetchone()
                if row is None:
                    raise RuntimeError("数据库尚未初始化，请先运行云端初始化工具")
                yield conn
            finally:
                self.local.connection = None

    @property
    def lock(self):
        return self.transaction()

    @property
    def conn(self):
        return self.local.connection

    def refresh(self):
        # Reads always query Postgres in the current transaction.
        pass

    def config(self):
        raw = bytes(self.conn.execute("SELECT categories FROM notebook_settings WHERE id=1").fetchone()["categories"])
        payload = json.loads(raw.decode("utf-8-sig"))
        cats = payload if isinstance(payload, list) else payload["categories"]
        cats = list(dict.fromkeys([*cats, "其他", *(r["category"] for r in self.conn.execute("SELECT DISTINCT category FROM notebook_notes ORDER BY category").fetchall())]))
        icons = {} if isinstance(payload, list) else payload.get("icons", {})
        return raw, cats, {c: icons.get(c, DEFAULT_ICONS.get(c, "file-text")) for c in cats}

    def write_config(self, cats, icons):
        raw, _, _ = self.config()
        payload = json.loads(raw.decode("utf-8-sig"))
        payload = {**(payload if isinstance(payload, dict) else {}), "categories": cats, "icons": icons}
        self.conn.execute("UPDATE notebook_settings SET categories=%s WHERE id=1", (json.dumps(payload, ensure_ascii=False, indent=2).encode(),))

    def parsed(self, row):
        note = self._parse(Path(row["filename"]), bytes(row["raw"]), row["trashed"])
        note["version"] = str(row["version"])
        return note

    def get(self, note_id):
        try:
            note_id = uuid.UUID(note_id)
        except ValueError:
            raise HTTPException(404, "笔记不存在")
        row = self.conn.execute("SELECT * FROM notebook_notes WHERE id=%s", (note_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "笔记不存在")
        return self.parsed(row)

    def read_raw(self, item):
        return bytes(self.conn.execute("SELECT raw FROM notebook_notes WHERE id=%s", (uuid.UUID(item["id"]),)).fetchone()["raw"])

    def put_raw(self, raw, filename, trashed=False, insert=False):
        if Path(filename).name != filename or "/" in filename or "\\" in filename or not filename.endswith(".md"):
            raise ValueError("无效的 Markdown 文件名")
        n = self._parse(Path(filename), raw, trashed)
        values = (uuid.UUID(n["id"]), filename, raw, n["title"], n["body"], n["category"], n["tags"],
                  n["source"], n["source_url"], n["created_at"], n["updated_at"], trashed, uuid.uuid4())
        self.conn.execute("""INSERT INTO notebook_notes
            (id,filename,raw,title,body,category,tags,source,source_url,created_at,updated_at,trashed,version)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""" + ("" if insert else """
            ON CONFLICT (id) DO UPDATE SET raw=EXCLUDED.raw,title=EXCLUDED.title,body=EXCLUDED.body,
            category=EXCLUDED.category,tags=EXCLUDED.tags,source=EXCLUDED.source,source_url=EXCLUDED.source_url,
            created_at=EXCLUDED.created_at,updated_at=EXCLUDED.updated_at,trashed=EXCLUDED.trashed,version=EXCLUDED.version"""), values)
        return self.public(self.get(n["id"]))

    def check_version(self, note, version):
        if note["version"] != version:
            raise HTTPException(409, "这条笔记已在其他窗口修改。草稿已保留，请查看最新版本或另存为新笔记")

    def create(self, data: NoteInput):
        with self.lock:
            if data.category not in self.config()[1]:
                raise HTTPException(422, "分类不存在，请先添加分类")
            note_id, stamp = str(uuid.uuid4()), now()
            created = datetime.combine(data.created_date, datetime.min.time(), TZ).isoformat() if data.created_date else stamp
            raw = self._serialize(data.model_dump(), {"id": note_id, "created_at": created, "updated_at": stamp})
            return self.put_raw(raw, f"{datetime.now(TZ):%Y%m%d-%H%M%S}-{note_id}.md", insert=True)

    def update(self, note_id, data: NoteUpdate):
        with self.lock:
            item = self.get(note_id)
            self.check_version(item, data.version)
            if item["trashed"]:
                raise HTTPException(409, "请先从回收站恢复笔记")
            if data.category not in self.config()[1]:
                raise HTTPException(422, "分类不存在，请先添加分类")
            created = item["created_at"]
            if data.created_date and data.created_date.isoformat() != item["created_date"]:
                created = datetime.combine(data.created_date, datetime.min.time(), TZ).isoformat()
            raw = self._serialize(data.model_dump(exclude={"version"}), {**item["_meta"], "created_at": created, "updated_at": now()})
            return self.put_raw(raw, item["filename"])

    def move(self, note_id, version, restore=False):
        with self.lock:
            item = self.get(note_id)
            self.check_version(item, version)
            if item["trashed"] == (not restore):
                raise HTTPException(409, "笔记位置已经改变，请刷新")
            self.conn.execute("UPDATE notebook_notes SET trashed=%s,version=%s WHERE id=%s", (not restore, uuid.uuid4(), uuid.UUID(note_id)))
            return self.public(self.get(note_id))

    def query(self, q="", category="", tags=None, start=None, end=None, date_field="created_at", order="desc", trash=False):
        clauses, params = ["trashed=%s"], [trash]
        if category:
            clauses.append("category=%s"); params.append(category)
        if tags:
            clauses.append("tags @> %s::text[]"); params.append(tags)
        for word in q.split():
            clauses.append("strpos(lower(title || E'\\n' || body || E'\\n' || array_to_string(tags,E'\\n') || E'\\n' || source || E'\\n' || source_url), lower(%s)) > 0")
            params.append(word)
        field = "updated_at" if date_field == "updated_at" else "created_at"
        for value, op in ((start, ">="), (end, "<=")):
            if value:
                clauses.append(f"({field} AT TIME ZONE 'Asia/Shanghai')::date {op} %s"); params.append(value)
        direction = "ASC" if order == "asc" else "DESC"
        rows = self.conn.execute(f"SELECT * FROM notebook_notes WHERE {' AND '.join(clauses)} ORDER BY {field} {direction}, id {direction}", params).fetchall()
        return [self.parsed(row) for row in rows]

    def metadata(self):
        with self.lock:
            raw, cats, icons = self.config()
            rows = self.conn.execute("SELECT tags,trashed FROM notebook_notes").fetchall()
            active = [r for r in rows if not r["trashed"]]
            return {"categories": cats, "category_icons": icons, "category_version": digest(raw),
                    "tags": sorted({t for r in active for t in r["tags"]}), "total": len(active), "trash_total": len(rows)-len(active), "errors": []}

    def check_category_version(self, version):
        if version is not None and version != digest(self.config()[0]):
            raise HTTPException(409, "分类已在其他窗口修改，请刷新后重试")

    def reorder_categories(self, categories, version):
        with self.lock:
            self.check_category_version(version)
            _, cats, icons = self.config()
            if len(categories) != len(cats) or set(categories) != set(cats):
                raise HTTPException(409, "分类列表已变化，请刷新后重新排序")
            self.write_config(categories, icons)
            return self.metadata()

    def change_category(self, old=None, new=None, icon=None, version=None):
        with self.lock:
            self.check_category_version(version)
            _, cats, icons = self.config()
            if icon is not None and icon not in CATEGORY_ICONS:
                raise HTTPException(422, "请选择提供的分类图标")
            if new is not None:
                new = new.strip()
                if not new or len(new) > 80:
                    raise HTTPException(422, "分类名需要 1–80 个字符")
                if new in cats and new != old:
                    raise HTTPException(409, "分类已存在")
            if old is not None and (old not in cats or (old == "其他" and new != old)):
                raise HTTPException(422, "分类不存在或为保留分类“其他”")
            if old and old != new:
                for row in self.conn.execute("SELECT * FROM notebook_notes WHERE category=%s", (old,)).fetchall():
                    item = self.parsed(row)
                    values = {k: item[k] for k in NoteInput.model_fields}
                    values["category"] = new or "其他"
                    self.put_raw(self._serialize(values, {**item["_meta"], "updated_at": now()}), item["filename"], item["trashed"])
            cats = [new if c == old and new else c for c in cats if c != old or new]
            if old is None and new:
                cats.append(new)
            if old:
                previous = icons.pop(old)
                if new:
                    icons[new] = icon or previous
            elif new:
                icons[new] = icon or DEFAULT_ICONS.get(new, "file-text")
            self.write_config(cats, icons)
            return self.metadata()

    def export_zip(self, items, include_trash=False):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in items:
                prefix = "trash/" if item["trashed"] else "notes/"
                archive.writestr(prefix + item["filename"], self.read_raw(item))
            archive.writestr("categories.json", self.config()[0])
        return out.getvalue()
