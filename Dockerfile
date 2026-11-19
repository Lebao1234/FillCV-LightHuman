# Dockerfile cho nền tảng chạy MỘT container từ thư mục gốc repo (snapdeploy, Render, Railway…).
# - Build context = thư mục gốc repo, mã nguồn lấy từ system/ và web/.
# - Không có nginx/đăng nhập: app mở công khai -> CHỈ dùng để xem thử với CV GIẢ.
# - Chạy thật (VPS/máy nội bộ) dùng docker-compose.yml (có nginx + đăng nhập basic auth).

# ---- Stage 1: Build React web app ----
FROM node:22-alpine AS web-builder
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- Stage 2: Cài thư viện Python + Chromium ----
FROM python:3.13-slim AS python-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY system/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps --only-shell chromium

# ---- Stage 3: Runtime stage ----
FROM python:3.13-slim

RUN groupadd --gid 1000 appuser && useradd --uid 1000 --gid appuser --shell /bin/bash appuser

WORKDIR /app

COPY --from=python-builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin

RUN apt-get update \
    && python -m playwright install-deps chromium \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
COPY --from=python-builder --chown=appuser:appuser /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright

# Mã nguồn backend (data/, tests, tài liệu… bị loại bởi .dockerignore ở thư mục gốc)
COPY system/ .
# Bản build web frontend
COPY --from=web-builder /web/dist /web/dist

RUN mkdir -p data/output data/logs \
    && chown -R appuser:appuser /app/data \
    && chown appuser:appuser /home/appuser

USER appuser

ENV CHROMIUM_NO_SANDBOX=1
# Gói nhỏ (512 MB RAM): mỗi lúc chỉ 1 Chromium dựng PDF, 1 lượt đọc CV. Nền tảng có thể ghi đè.
ENV RENDER_MAX_CONCURRENT=1
ENV EXTRACT_MAX_CONCURRENT=1
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\", \"8000\")}/health')" || exit 1

CMD ["sh", "-c", "exec uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
