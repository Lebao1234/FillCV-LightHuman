import os
import sys
from pathlib import Path

# Cho phép test import các package của dự án (core, ui, services, infra) từ thư mục gốc
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Test chạy app.py (AppTest) -> KHÔNG để bước tự xoá PDF hết hạn đụng vào data/output thật
os.environ["OUTPUT_RETENTION_DAYS"] = "0"

# Log của phiên test ghi vào thư mục tạm, không lẫn vào data/logs thật
os.environ["LOG_DIR"] = __import__("tempfile").mkdtemp(prefix="fillcv-log-")
