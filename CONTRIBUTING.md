# Contributing

Use Python 3.13 and Node.js 24. Install with the lockfiles, run the tests and production build, and keep changes focused.

For backend development, run `python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8765`. Run `npm run dev` in a second terminal and set `NOTEBOOK_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173` on the backend. Use an isolated `NOTEBOOK_DATA_DIR` for tests.

Do not attach personal notes or real credentials to issues, commits, logs, screenshots, or pull requests. New deployments should start with an empty database; demonstration content, if needed, must be synthetic and explicitly marked.

Keep `requirements.txt` and `requirements.lock.txt` identical. The duplication supports Vercel's Python dependency parser. Do not run destructive dependency updates as a routine cleanup step.

The Chinese and English deployment guides should describe the same behavior. Update both when configuration changes. The application UI currently remains Chinese.

Contributions are provided under this repository's MIT License.
