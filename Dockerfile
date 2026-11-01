FROM node:24-slim AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
COPY public ./public
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY backend ./backend
COPY public ./public
COPY --from=frontend /app/dist ./dist
ENV NOTEBOOK_DATA_DIR=/data PYTHONUTF8=1
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765", "--workers", "1"]
