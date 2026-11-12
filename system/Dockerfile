# ---- Build stage: cài thư viện + Chromium ----
FROM python:3.15-slim AS builder

# Thư viện hệ thống cần cho opencv-python-headless, PyMuPDF, Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps --only-shell chromium

# ---- Runtime stage ----
FROM python:3.15-slim

# Tạo user không phải root (bảo mật)
RUN groupadd --gid 1000 appuser && useradd --uid 1000 --gid appuser --shell /bin/bash appuser

WORKDIR /app

# Copy Python packages + Playwright browsers từ builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Thư viện hệ thống: Chromium (playwright install-deps cài đúng bộ cho bản đã ghim — liệt kê tay từng thiếu
# libXfixes) + opencv (libgl1, libglib2.0-0) + font Times New Roman thay thế (metric-compatible)
RUN apt-get update \
    && python -m playwright install-deps chromium \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder --chown=appuser:appuser /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright

# Copy mã nguồn
COPY . .

# Tạo thư mục data (output + logs) thuộc appuser. Chỉ gán quyền chỗ cần ghi
# (chown -R cả /home/appuser sẽ nhân đôi Chromium trong image)
RUN mkdir -p data/output data/logs \
    && chown -R appuser:appuser /app/data \
    && chown appuser:appuser /home/appuser

USER appuser

# Chromium trong Docker cần --no-sandbox (user không phải root)
ENV CHROMIUM_NO_SANDBOX=1
# Streamlit không mở trình duyệt tự động
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_HEADLESS=true

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["python", "-m", "streamlit", "run", "app.py", \
            "--server.address=0.0.0.0", \
            "--server.port=8501", \
            "--server.maxUploadSize=20"]

