# Server Starlette cho FillCV Light Human
"""Khởi tạo và cấu hình ứng dụng Starlette API server.

Cấu hình các tuyến đường (routes), CORS middleware, quản lý vòng đời ứng dụng (lifespan)
và phục vụ file tĩnh web/dist khi chạy production.
"""
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from api import routes
from infra import logging_setup, settings, storage

log = logging.getLogger("app")


# Quản lý vòng đời khởi động và kết thúc của server
@asynccontextmanager
async def lifespan(app: Starlette):
    logging_setup.setup_logging()
    deleted = storage.delete_expired_files(settings.output_dir(), storage.retention_days())
    log.info("Khởi động FillCV API Server (đã dọn %d file hết hạn trong %s)", len(deleted), settings.output_dir())
    yield
    log.info("Dừng FillCV API Server.")


# Danh sách các tuyến đường API
api_routes = [
    Route("/health", routes.health, methods=["GET"]),
    Route("/api/config", routes.get_config, methods=["GET"]),
    Route("/api/cv/extract", routes.extract_cv, methods=["POST"]),
    Route("/api/cv/validate", routes.validate_cv, methods=["POST"]),
    Route("/api/pdf/build", routes.build_pdf, methods=["POST"]),
    Route("/api/pdf/status", routes.get_pdf_status, methods=["POST"]),
    Route("/api/preview/original/{run_id}/info", routes.preview_original_info, methods=["GET"]),
    Route("/api/preview/original/{run_id}/{page:int}", routes.preview_original_page, methods=["GET"]),
    Route("/api/preview/pdf/{run_id}/info", routes.preview_pdf_info, methods=["GET"]),
    Route("/api/preview/pdf/{run_id}/{page:int}", routes.preview_pdf_page, methods=["GET"]),
    Route("/api/pdf/download/{run_id}", routes.download_pdf, methods=["GET"]),
    Route("/api/photo/crop", routes.crop_photo, methods=["POST"]),
    Route("/api/photo/preview/{run_id}", routes.preview_photo, methods=["GET"]),
    Route("/api/photo/{run_id}", routes.delete_photo, methods=["DELETE"]),
]

# Kiểm tra thư mục web/dist để serve file tĩnh khi production
web_dist = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
if not web_dist.exists():
    web_dist = Path("web/dist")

all_routes = list(api_routes)
if web_dist.exists() and web_dist.is_dir():
    all_routes.append(Mount("/", app=StaticFiles(directory=str(web_dist), html=True), name="static"))

# Middleware CORS cho môi trường dev
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    ),
]

# Ứng dụng Starlette duy nhất
app = Starlette(
    debug=False,
    routes=all_routes,
    middleware=middleware,
    lifespan=lifespan,
)


# Chạy trực tiếp server qua uvicorn
def run() -> None:
    """Chạy server bằng Uvicorn với 1 worker."""
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("api.server:app", host=host, port=port, reload=False, workers=1)


if __name__ == "__main__":
    run()
