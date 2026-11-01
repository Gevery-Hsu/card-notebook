"""Markdown is the source of truth; the in-memory index is disposable."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime, date, timezone, timedelta
from pathlib import Path

import yaml
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

TZ = timezone(timedelta(hours=8))
DEFAULT_CATEGORIES = ["随笔", "灵感", "书摘", "其他"]
CATEGORY_ICONS = {"file-text", "lightbulb", "book-open", "ellipsis", "bookmark", "leaf", "coffee", "compass"}
DEFAULT_ICONS = {"随笔": "file-text", "灵感": "lightbulb", "书摘": "book-open", "其他": "ellipsis"}


def now() -> str:
    return datetime.now(TZ).isoformat(timespec="microseconds")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def atomic_write(path: Path, raw: bytes) -> None:
    fd, temp = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class NoteInput(BaseModel):
    title: str = Field(default="", max_length=500)
    body: str = Field(min_length=1, max_length=2_000_000)
    category: str = Field(default="其他", min_length=1, max_length=80)
    tags: list[str] = Field(default_factory=list, max_length=100)
    source: str = Field(default="", max_length=2000)
    source_url: str = Field(default="", max_length=4000)
    created_date: date | None = None

    @field_validator("title", "category", "source", "source_url")
    @classmethod
    def trim(cls, value):
        return value.strip()

    @field_validator("body")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("请先写下笔记内容")
        return value

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, tags):
        result = list(dict.fromkeys(t.strip() for t in tags if t.strip()))
        if any(len(t) > 80 for t in result):
            raise ValueError("标签最多 80 个字符")
        return result

    @field_validator("source_url")
    @classmethod
    def safe_url(cls, value):
        from urllib.parse import urlsplit
        if value:
            parsed = urlsplit(value)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("来源链接需要以 http:// 或 https:// 开头")
        return value


class NoteUpdate(NoteInput):
    version: str


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.notes_dir = self.root / "notes"
        self.trash_dir = self.root / "trash"
        for folder in (self.notes_dir, self.trash_dir):
            folder.mkdir(exist_ok=True)
            if folder.is_symlink() or folder.resolve().parent != self.root:
                raise ValueError("数据目录不能是链接或指向目录外")
        self.config = self.root / "categories.json"
        self.lock = threading.RLock()
        self.cache: dict[Path, tuple[str, dict]] = {}
        self.notes: dict[str, dict] = {}
        self.errors: list[dict] = []
        self.config_error = ""
        if not self.config.exists():
            self._write_categories(DEFAULT_CATEGORIES)
        self.refresh()

    def _safe(self, path: Path):
        if path.is_symlink() or path.resolve().parent not in (self.notes_dir, self.trash_dir):
            raise ValueError("不读取链接或数据目录以外的文件")

    def _categories(self) -> list[str]:
        if self.config.is_symlink() or self.config.resolve().parent != self.root:
            raise ValueError("分类配置不能指向目录外")
        raw = self.config.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
        icons = {}
        if isinstance(data, dict):
            icons = data.get("icons", {})
            data = data.get("categories")
        if not isinstance(icons, dict) or any(not isinstance(k, str) or not isinstance(v, str) or v not in CATEGORY_ICONS for k, v in icons.items()):
            raise ValueError("分类图标配置无效")
        if not isinstance(data, list) or any(not isinstance(x, str) or not x.strip() or len(x) > 80 for x in data):
            raise ValueError("分类配置需要为非空字符串数组")
        self.category_icons = icons
        self.category_version = digest(raw)
        return list(dict.fromkeys([*data, "其他"]))

    def _write_categories(self, categories, icons=None):
        if self.config.is_symlink():
            raise ValueError("分类配置不能为链接")
        payload = categories if icons is None else {"categories": categories, "icons": icons}
        atomic_write(self.config, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))

    def _parse(self, path: Path, raw: bytes, trashed: bool):
        text = raw.decode("utf-8-sig").replace("\r\n", "\n")
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            raise ValueError("缺少 YAML 文件头；请保留 id、created_at、updated_at 等元信息")
        head, body = text[4:].split("\n---\n", 1)
        meta = yaml.safe_load(head)
        if not isinstance(meta, dict):
            raise ValueError("YAML 文件头必须为对象")
        note_id = str(uuid.UUID(str(meta["id"])))
        for key in ("created_at", "updated_at"):
            dt = datetime.fromisoformat(str(meta[key]))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)
            meta[key] = dt.isoformat()
        values = NoteInput.model_validate({**meta, "body": body}).model_dump()
        return {**values, "created_date": datetime.fromisoformat(meta["created_at"]).astimezone(TZ).date().isoformat(), "id": note_id, "created_at": meta["created_at"], "updated_at": meta["updated_at"],
                "version": digest(raw), "trashed": trashed, "filename": path.name, "_path": path, "_meta": meta}

    def refresh(self):
        with self.lock:
            self.errors = []
            try:
                categories = self._categories()
                self.config_error = ""
            except (ValueError, OSError) as exc:
                categories = DEFAULT_CATEGORIES.copy()
                self.category_icons = {}
                self.category_version = ""
                self.config_error = str(exc)
                self.errors.append({"file": "categories.json", "message": str(exc)})
            indexed, cached, duplicate_ids = {}, {}, set()
            for folder, trashed in ((self.notes_dir, False), (self.trash_dir, True)):
                for path in sorted(folder.glob("*.md")):
                    try:
                        self._safe(path)
                        raw = path.read_bytes()
                        version = digest(raw)
                        old = self.cache.get(path)
                        item = old[1] if old and old[0] == version else self._parse(path, raw, trashed)
                        cached[path] = (version, item)
                        if item["id"] in indexed:
                            duplicate_ids.add(item["id"])
                            self.errors.append({"file": path.name, "message": "笔记 ID 重复；重复项均暂不展示，请检查复制的文件"})
                        else:
                            indexed[item["id"]] = item
                    except Exception as exc:
                        self.errors.append({"file": f"{folder.name}/{path.name}", "message": str(exc)})
            for note_id in duplicate_ids:
                indexed.pop(note_id, None)
            self.notes = indexed
            self.cache = cached
            self.categories = list(dict.fromkeys([*categories, *(x["category"] for x in indexed.values())]))
            self.category_icons = {c: self.category_icons.get(c, DEFAULT_ICONS.get(c, "file-text")) for c in self.categories}

    @staticmethod
    def public(note):
        return {k: v for k, v in note.items() if not k.startswith("_")}

    def read_raw(self, item):
        self._safe(item["_path"])
        return item["_path"].read_bytes()

    def get(self, note_id):
        if note_id not in self.notes:
            raise HTTPException(404, "笔记不存在或文件无法解析，请刷新列表")
        return self.notes[note_id]

    def check_version(self, note, version):
        self._safe(note["_path"])
        try:
            current = digest(note["_path"].read_bytes())
        except OSError:
            raise HTTPException(409, "文件已移动或删除，草稿已保留，请刷新后查看")
        if current != version or note["version"] != version:
            raise HTTPException(409, "这条笔记已在其他窗口或文件中修改。草稿已保留，请查看最新版本或另存为新笔记")

    def _serialize(self, values, meta):
        details = {**meta, **{k: v for k, v in values.items() if k not in ("body", "created_date")}}
        details.pop("created_date", None)
        details.pop("version", None)
        return ("---\n" + yaml.safe_dump(details, allow_unicode=True, sort_keys=False).strip() + "\n---\n" + values["body"]).encode("utf-8")

    def create(self, data: NoteInput):
        with self.lock:
            self.refresh()
            if data.category not in self.categories:
                raise HTTPException(422, "分类不存在，请先添加分类")
            note_id, stamp = str(uuid.uuid4()), now()
            created = datetime.combine(data.created_date, datetime.min.time(), TZ).isoformat() if data.created_date else stamp
            path = self.notes_dir / f"{datetime.now(TZ):%Y%m%d-%H%M%S}-{note_id}.md"
            raw = self._serialize(data.model_dump(), {"id": note_id, "created_at": created, "updated_at": stamp})
            atomic_write(path, raw)
            self.refresh()
            return self.public(self.get(note_id))

    def update(self, note_id, data: NoteUpdate):
        with self.lock:
            self.refresh()
            item = self.get(note_id)
            if item["trashed"]:
                raise HTTPException(409, "请先从回收站恢复笔记")
            if data.category not in self.categories:
                raise HTTPException(422, "分类不存在，请先添加分类")
            created = item["created_at"]
            if data.created_date and data.created_date.isoformat() != item["created_date"]:
                created = datetime.combine(data.created_date, datetime.min.time(), TZ).isoformat()
            raw = self._serialize(data.model_dump(exclude={"version"}), {**item["_meta"], "created_at": created, "updated_at": now()})
            self.check_version(item, data.version)
            atomic_write(item["_path"], raw)
            self.refresh()
            return self.public(self.get(note_id))

    def move(self, note_id, version, restore=False):
        with self.lock:
            self.refresh()
            item = self.get(note_id)
            self.check_version(item, version)
            if item["trashed"] == (not restore):
                raise HTTPException(409, "笔记位置已经改变，请刷新")
            target = (self.notes_dir if restore else self.trash_dir) / item["filename"]
            if target.exists():
                raise HTTPException(409, "目标位置存在同名文件，未覆盖")
            item["_path"].rename(target)
            self.refresh()
            return self.public(self.get(note_id))

    def query(self, q="", category="", tags=None, start=None, end=None, date_field="created_at", order="desc", trash=False):
        words = q.casefold().split()
        results = []
        for item in self.notes.values():
            if item["trashed"] != trash or (category and item["category"] != category):
                continue
            if tags and not set(tags).issubset(item["tags"]):
                continue
            searchable = "\n".join([item["title"], item["body"], *item["tags"], item["source"], item["source_url"]]).casefold()
            if not all(word in searchable for word in words):
                continue
            day = datetime.fromisoformat(item[date_field]).astimezone(TZ).date()
            if (start and day < start) or (end and day > end):
                continue
            results.append(item)
        return sorted(results, key=lambda x: (datetime.fromisoformat(x[date_field]), x["id"]), reverse=order == "desc")

    def metadata(self):
        with self.lock:
            self.refresh()
            active = [x for x in self.notes.values() if not x["trashed"]]
            return {"categories": self.categories, "category_icons": self.category_icons, "category_version": self.category_version, "tags": sorted({t for x in active for t in x["tags"]}),
                    "total": len(active), "trash_total": len(self.notes) - len(active), "errors": self.errors}

    def _check_category_version(self, version=None):
        if self.config_error:
            raise HTTPException(409, "分类配置无法读取，请先修复文件")
        if (version is not None and version != self.category_version) or digest(self.config.read_bytes()) != self.category_version:
            raise HTTPException(409, "分类已在其他窗口或文件中修改，请刷新后重试")

    def reorder_categories(self, categories, version):
        with self.lock:
            self.refresh()
            self._check_category_version(version)
            if len(categories) != len(self.categories) or set(categories) != set(self.categories):
                raise HTTPException(409, "分类列表已变化，请刷新后重新排序")
            self._write_categories(categories, self.category_icons)
            return self.metadata()

    def change_category(self, old=None, new=None, icon=None, version=None):
        with self.lock:
            self.refresh()
            if self.errors:
                raise HTTPException(409, "请先修复文件读取问题，再调整分类，以免遗漏笔记")
            self._check_category_version(version)
            if icon is not None and icon not in CATEGORY_ICONS:
                raise HTTPException(422, "请选择提供的分类图标")
            if new is not None:
                new = new.strip()
                if not new or len(new) > 80:
                    raise HTTPException(422, "分类名需要 1–80 个字符")
                if new in self.categories and new != old:
                    raise HTTPException(409, "分类已存在")
            if old is not None and (old not in self.categories or (old == "其他" and new != old)):
                raise HTTPException(422, "分类不存在或为保留分类“其他”")
            replacements = []
            for item in self.notes.values():
                if old and old != new and item["category"] == old:
                    self.check_version(item, item["version"])
                    values = {k: item[k] for k in NoteInput.model_fields}
                    values["category"] = new or "其他"
                    replacements.append((item["_path"], item["_path"].read_bytes(), self._serialize(values, {**item["_meta"], "updated_at": now()})))
            cats = [new if c == old and new else c for c in self.categories if c != old or new]
            if old is None and new:
                cats.append(new)
            icons = dict(self.category_icons)
            if old:
                previous_icon = icons.pop(old)
                if new:
                    icons[new] = icon or previous_icon
            elif new:
                icons[new] = icon or DEFAULT_ICONS.get(new, "file-text")
            written = []
            try:
                for path, original, replacement in replacements:
                    if digest(path.read_bytes()) != digest(original):
                        raise HTTPException(409, "调整期间文件发生变化，请刷新后重试")
                    atomic_write(path, replacement)
                    written.append((path, original, replacement))
                self._check_category_version(version)
                self._write_categories(cats, icons)
            except Exception:
                for path, original, replacement in reversed(written):
                    if path.read_bytes() == replacement:
                        atomic_write(path, original)
                raise
            self.refresh()
            return self.metadata()

    def export_zip(self, items):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in items:
                self._safe(item["_path"])
                archive.writestr("notes/" + item["filename"], item["_path"].read_bytes())
            archive.writestr("categories.json", json.dumps({"categories": self.categories, "icons": self.category_icons}, ensure_ascii=False, indent=2))
        return out.getvalue()
