# Server Starlette cho FillCV Light Human
"""Khởi tạo và cấu hình ứng dụng Starlette API server.

Cấu hình các tuyến đường (routes), CORS middleware, quản lý vòng đời ứng dụng (lifespan)
và phục vụ file tĩnh web/dist khi chạy production.
"""
import asyncio
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from api import routes
from infra import logging_setup, settings, storage
from services.translation import nmt

log = logging.getLogger("app")


# Quản lý vòng đời khởi động và kết thúc của server
@asynccontextmanager
async def lifespan(app: Starlette):
    logging_setup.setup_logging()
    deleted = storage.delete_expired_files(settings.output_dir(), storage.retention_days())
    log.info("Khởi động FillCV API Server (đã dọn %d file hết hạn trong %s)", len(deleted), settings.output_dir())
    if settings.translate_preload() and nmt.is_available():
        # Nạp mô hình dịch ở luồng nền: app nhận request ngay, lần dịch đầu không phải chờ nạp
        asyncio.get_running_loop().run_in_executor(None, nmt.preload)
    yield
    log.info("Dừng FillCV API Server.")


# Danh sách các tuyến đường API
api_routes = [
    Route("/health", routes.health, methods=["GET"]),
    Route("/api/config", routes.get_config, methods=["GET"]),
    Route("/api/cv/extract", routes.extract_cv, methods=["POST"]),
    Route("/api/cv/validate", routes.validate_cv, methods=["POST"]),
    Route("/api/cv/translate", routes.translate_cv, methods=["POST"]),
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

# File tĩnh kèm fallback cho SPA: đường dẫn trang (vd /edit) trả index.html để React Router tự xử lý
class SpaStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            # Chỉ cho đường dẫn "kiểu trang": không có đuôi file và không thuộc /api (để file thiếu và API sai vẫn 404)
            norm = path.replace("\\", "/")  # Windows đưa đường dẫn dạng api\x
            is_page = "." not in Path(norm).name and not norm.startswith("api/")
            if exc.status_code == 404 and is_page:
                return await super().get_response("index.html", scope)
            raise


# Kiểm tra thư mục web/dist để serve file tĩnh khi production
possible_dirs = [
    Path(__file__).resolve().parent.parent.parent / "web" / "dist",
    Path("web/dist"),
    Path("/web/dist"),
    Path("/app/web/dist"),
]
web_dist = next((p for p in possible_dirs if p.exists() and p.is_dir()), None)

all_routes = list(api_routes)
if web_dist:
    all_routes.append(Mount("/", app=SpaStaticFiles(directory=str(web_dist), html=True), name="static"))

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
