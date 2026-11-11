# ---- Build stage: cài thư viện + Chromium ----
FROM python:3.13-slim AS builder

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
    && python -m playwright install --with-deps chromium

# ---- Runtime stage ----
FROM python:3.13-slim

# Thư viện runtime (nhẹ hơn build stage)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
        libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
        # Font Times New Roman (mẫu PDF) — metric-compatible fallback
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Tạo user không phải root (bảo mật)
RUN groupadd --gid 1000 appuser && useradd --uid 1000 --gid appuser --shell /bin/bash appuser

WORKDIR /app

# Copy Python packages + Playwright browsers từ builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache/ms-playwright /home/appuser/.cache/ms-playwright

# Copy mã nguồn
COPY . .

# Tạo thư mục data (output + logs) thuộc appuser
RUN mkdir -p data/output data/logs \
    && chown -R appuser:appuser /app /home/appuser

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

