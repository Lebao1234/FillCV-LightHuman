# Dockerfile cho nền tảng chạy MỘT container từ thư mục gốc repo (snapdeploy, Render, Railway…).
# - Build context = thư mục gốc repo, mã nguồn lấy từ system/.
# - Không có nginx/đăng nhập: app mở công khai -> CHỈ dùng để xem thử với CV GIẢ.
# - Chạy thật (VPS/máy nội bộ) dùng docker-compose.yml (build system/Dockerfile, có nginx + đăng nhập).
# Giữ đồng bộ phần cài đặt với system/Dockerfile khi sửa một trong hai file.

# ---- Build stage: cài thư viện + Chromium ----
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY system/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps --only-shell chromium

# ---- Runtime stage ----
FROM python:3.13-slim

RUN groupadd --gid 1000 appuser && useradd --uid 1000 --gid appuser --shell /bin/bash appuser

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Thư viện hệ thống: Chromium (playwright install-deps cài đúng bộ cho bản đã ghim — liệt kê tay từng thiếu
# libXfixes) + opencv (libgl1, libglib2.0-0) + font thay Times New Roman
RUN apt-get update \
    && python -m playwright install-deps chromium \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder --chown=appuser:appuser /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright

# Mã nguồn (data/, tests, tài liệu… bị loại bởi .dockerignore ở thư mục gốc)
COPY system/ .

# Chỉ gán quyền chỗ cần ghi (chown -R cả /home/appuser sẽ nhân đôi Chromium trong image)
RUN mkdir -p data/output data/logs \
    && chown -R appuser:appuser /app/data \
    && chown appuser:appuser /home/appuser

USER appuser

ENV CHROMIUM_NO_SANDBOX=1
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_HEADLESS=true
# Gói nhỏ (512 MB RAM): mỗi lúc chỉ 1 Chromium dựng PDF, 1 lượt đọc CV. Nền tảng có thể ghi đè.
ENV RENDER_MAX_CONCURRENT=1
ENV EXTRACT_MAX_CONCURRENT=1

EXPOSE 8501

# Nền tảng cấp cổng qua biến PORT; không có thì dùng 8501
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\", \"8501\")}/_stcore/health')" || exit 1

CMD ["sh", "-c", "exec python -m streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.maxUploadSize=20"]
