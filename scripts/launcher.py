"""One local server per project and port, with explicit ownership checks."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent.parent


def health(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
            return json.load(response)
    except Exception:
        return None


def expected(info):
    return info and info.get("app") == "private-card-notebook" and Path(info.get("instance", "")).resolve() == ROOT and Path(info.get("data_dir", "")).resolve() == Path(os.environ.get("NOTEBOOK_DATA_DIR", ROOT / 'data')).resolve()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    info = health(args.port)
    if args.action == 'stop':
        if not expected(info):
            print("没有找到本项目运行中的服务；未停止其他进程。")
            return
        os.kill(info["pid"], signal.SIGTERM)
        print("私人卡片本已停止。")
        return
    if info and not expected(info):
        raise RuntimeError(f"端口 {args.port} 正由其他服务或笔记目录使用，请先检查。")
    if not info:
        if not (ROOT / 'dist' / 'index.html').exists():
            raise RuntimeError("界面尚未构建，请先运行安装.cmd。")
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', args.port)) == 0:
                raise RuntimeError(f"端口 {args.port} 已被其他程序占用，未启动或停止任何程序。")
        runtime = ROOT / '.runtime'
        runtime.mkdir(exist_ok=True)
        env = {**os.environ, "PYTHONUTF8": "1"}
        flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else 0
        with open(runtime / f'server-{args.port}.log', 'a', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.app:create_app', '--factory', '--host', '127.0.0.1', '--port', str(args.port)], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags, start_new_session=os.name != 'nt')
        for _ in range(80):
            info = health(args.port)
            if expected(info):
                break
            if process.poll() is not None:
                raise RuntimeError(f"启动失败，请查看 .runtime/server-{args.port}.log。")
            time.sleep(.15)
        else:
            raise RuntimeError("启动尚未就绪，请查看日志；未反复启动服务。")
    url = f'http://127.0.0.1:{args.port}'
    print(f"私人卡片本：{url}")
    if not args.no_browser:
        webbrowser.open(url)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
