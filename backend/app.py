from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .store import Store, NoteInput, NoteUpdate
from .auth import Sessions, COOKIE, SESSION_SECONDS

PROJECT = Path(__file__).resolve().parent.parent


class Version(BaseModel):
    version: str


class Category(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    icon: Literal["file-text", "lightbulb", "book-open", "ellipsis", "bookmark", "leaf", "coffee", "compass"] | None = None
    version: str | None = None


class CategoryOrder(BaseModel):
    categories: list[str] = Field(min_length=1)
    version: str


class Unlock(BaseModel):
    key: str = Field(min_length=1, max_length=1024)


def create_app(data_dir: Path | None = None, *, store_override=None):
    app = FastAPI(title="私人卡片本", docs_url=None, redoc_url=None, openapi_url=None)
    cloud = os.environ.get("NOTEBOOK_STORAGE") == "postgres"
    if os.environ.get("VERCEL") and not cloud:
        raise RuntimeError("Vercel 必须使用 PostgreSQL 存储，不能回退到临时文件目录")
    if cloud and not os.environ.get("NOTEBOOK_KEY_HASH"):
        raise RuntimeError("云端必须配置 NOTEBOOK_KEY_HASH")
    if store_override is not None:
        store = store_override
    elif cloud:
        from .postgres import PostgresStore
        store = PostgresStore(os.environ["DATABASE_URL"])
    else:
        store = Store(data_dir or Path(os.environ.get("NOTEBOOK_DATA_DIR", PROJECT / "data")))
    app.state.store = store
    if cloud:
        import psycopg
        @app.exception_handler(psycopg.Error)
        async def database_failure(request, exc):
            return JSONResponse({"detail": "数据库暂时不可用，尚未确认保存的内容请保留草稿后重试"}, status_code=503, headers={"Cache-Control": "no-store"})
    sessions = Sessions(os.environ["NOTEBOOK_KEY_HASH"], getattr(store, "url", None),
                        os.environ.get("NOTEBOOK_AUTH_DB", str(PROJECT / ".runtime" / "auth.sqlite3"))) if os.environ.get("NOTEBOOK_KEY_HASH") else None
    app.state.sessions = sessions
    hosts = os.environ.get("NOTEBOOK_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",")
    if os.environ.get("VERCEL"):
        hosts += list(filter(None, (os.environ.get("VERCEL_URL"), os.environ.get("VERCEL_PROJECT_PRODUCTION_URL"))))
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        def protected_error(detail, status):
            return JSONResponse({"detail": detail}, status_code=status, headers={"Cache-Control": "no-store"})
        if sessions and request.url.path.startswith("/api/") and request.url.path not in ("/api/auth/status", "/api/auth/unlock", "/api/health"):
            # Synchronous database calls run in the thread pool, never on the event loop.
            from starlette.concurrency import run_in_threadpool
            try:
                authorized = await run_in_threadpool(sessions.authenticated, request.cookies.get(COOKIE))
            except Exception:
                return protected_error("暂时无法验证设备，请稍后重试；草稿仍会保留", 503)
            if not authorized:
                return protected_error("请先输入访问密钥解锁卡片本", 401)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            allowed = {str(request.base_url).rstrip("/"), *filter(None, os.environ.get("NOTEBOOK_ALLOWED_ORIGINS", "").split(","))}
            if origin and origin not in allowed:
                return JSONResponse({"detail": "拒绝来自其他网站的写入请求"}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "拒绝跨站写入请求"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/auth/status")
    def auth_status(request: Request):
        return {"required": bool(sessions), "authenticated": not sessions or sessions.authenticated(request.cookies.get(COOKIE))}

    @app.post("/api/auth/unlock")
    def unlock(data: Unlock, request: Request):
        if not sessions:
            raise HTTPException(404, "本地版未启用密钥")
        token = sessions.login(data.key)
        # Re-authentication replaces this browser's previous session.
        sessions.revoke(request.cookies.get(COOKIE))
        response = JSONResponse({"authenticated": True})
        response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS, httponly=True,
                            secure=cloud or request.url.scheme == "https", samesite="strict", path="/")
        return response

    @app.post("/api/auth/logout")
    def logout(request: Request, all_devices: bool = False):
        if sessions:
            sessions.revoke(request.cookies.get(COOKIE), all_devices)
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(COOKIE, path="/")
        return response

    @app.exception_handler(OSError)
    async def io_failure(request, exc):
        return JSONResponse({"detail": "文件读写失败，请检查数据目录权限及磁盘空间。尚未确认保存的内容请保留草稿。"}, status_code=503)

    @app.get("/api/health")
    def health():
        if cloud or sessions:
            return {"app": "private-card-notebook", "version": "2.0.0", "storage": "postgres" if cloud else "markdown"}
        return {"app": "private-card-notebook", "version": "1.0.0", "instance": str(PROJECT), "data_dir": str(store.root), "pid": os.getpid()}

    @app.get("/api/meta")
    def metadata():
        return store.metadata()

    def selected(q="", category="", tags=None, start=None, end=None, date_field="created_at", order="desc", trash=False):
        if start and end and start > end:
            raise HTTPException(422, "开始日期不能晚于结束日期")
        store.refresh()
        return store.query(q, category, tags, start, end, date_field, order, trash)

    @app.get("/api/notes")
    def notes(q: str = "", category: str = "", tags: list[str] = Query(default=[]), start: date | None = None,
              end: date | None = None, date_field: Literal["created_at", "updated_at"] = "created_at",
              order: Literal["asc", "desc"] = "desc", trash: bool = False, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
        with store.lock:
            items = selected(q, category, tags, start, end, date_field, order, trash)
            return {"items": [store.public(x) for x in items[offset:offset + limit]], "total": len(items), "errors": store.errors}

    @app.get("/api/export.zip")
    def export(q: str = "", category: str = "", tags: list[str] = Query(default=[]), start: date | None = None,
               end: date | None = None, date_field: Literal["created_at", "updated_at"] = "created_at", order: Literal["asc", "desc"] = "desc"):
        with store.lock:
            items = selected(q, category, tags, start, end, date_field, order)
            if store.errors:
                raise HTTPException(409, "有文件无法读取，请先修复问题，或直接备份整个数据目录")
            return Response(store.export_zip(items), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="notebook-export.zip"'})

    @app.get("/api/notes/{note_id}/export")
    def export_one(note_id: str):
        with store.lock:
            store.refresh()
            item = store.get(note_id)
            return Response(store.read_raw(item), media_type="text/markdown; charset=utf-8",
                            headers={"Content-Disposition": f'attachment; filename="{item["filename"]}"'})

    @app.get("/api/notes/{note_id}")
    def note(note_id: str):
        with store.lock:
            store.refresh()
            return store.public(store.get(note_id))

    @app.get("/api/backup.zip")
    def backup():
        with store.lock:
            store.refresh()
            if store.errors:
                raise HTTPException(409, "有文件无法读取，请直接备份整个数据目录")
            if cloud:
                content = store.export_zip(store.query() + store.query(trash=True), include_trash=True)
            else:
                import io, zipfile
                out = io.BytesIO()
                with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
                    for item in store.notes.values():
                        archive.writestr(("trash/" if item["trashed"] else "notes/") + item["filename"], store.read_raw(item))
                    archive.writestr("categories.json", store.config.read_bytes())
                content = out.getvalue()
            return Response(content, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="notebook-backup.zip"'})

    @app.post("/api/notes", status_code=201)
    def create(data: NoteInput):
        return store.create(data)

    @app.put("/api/notes/{note_id}")
    def update(note_id: str, data: NoteUpdate):
        return store.update(note_id, data)

    @app.post("/api/notes/{note_id}/trash")
    def trash(note_id: str, data: Version):
        return store.move(note_id, data.version)

    @app.post("/api/notes/{note_id}/restore")
    def restore(note_id: str, data: Version):
        return store.move(note_id, data.version, restore=True)

    @app.post("/api/categories")
    def add_category(data: Category):
        return store.change_category(new=data.name, icon=data.icon, version=data.version)

    @app.put("/api/category-order")
    def reorder_categories(data: CategoryOrder):
        return store.reorder_categories(data.categories, data.version)

    @app.put("/api/categories/{name:path}")
    def rename_category(name: str, data: Category):
        return store.change_category(old=name, new=data.name, icon=data.icon, version=data.version)

    @app.delete("/api/categories/{name:path}")
    def delete_category(name: str):
        return store.change_category(old=name)

    # The application only needs a root route, so no catch-all can expose files.
    dist = PROJECT / "dist"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/notebook.svg")
    def icon():
        return FileResponse(PROJECT / "public" / "notebook.svg")

    @app.get("/")
    def index():
        if not (dist / "index.html").is_file():
            return Response("请先运行安装脚本以构建界面。", status_code=503)
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return app
