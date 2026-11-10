"""Bước 1: gửi CV gốc cho OpenAI và nhận về JSON hồ sơ ứng viên.

Hàm chính: extract_cv(file_bytes, filename, project, position, today) -> dict

Chạy thử từ dòng lệnh:
    python -m services.ai.extract "duong/dan/cv.pdf" --project "Message Coffee"   (chạy ở thư mục gốc dự án)
"""
import base64
import io
import json
import os
import logging
import re
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from infra.settings import DUOI_ANH, THU_MUC_PROMPT, doc_prompt
from services.ai.models import CVData

load_dotenv()  # đọc OPENAI_API_KEY, OPENAI_MODEL... từ file .env (nếu có)

log = logging.getLogger("extract")

SYSTEM_PROMPT = (THU_MUC_PROMPT / "system_prompt.txt").read_text(encoding="utf-8")
SCHEMA = json.loads((THU_MUC_PROMPT / "schema.json").read_text(encoding="utf-8"))

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "8000"))
SO_LAN_THU_LAI = 2   # thử lại tối đa 2 lần nếu JSON hỏng / sai cấu trúc


def _so_nguyen_env(ten: str, mac_dinh: int, cho_phep_0: bool = False) -> int:
    """Đọc số nguyên dương từ .env; trống/sai/âm (hoặc 0 khi không cho phép) -> giá trị mặc định."""
    try:
        gia_tri = int(os.getenv(ten, ""))
    except ValueError:
        return mac_dinh
    return gia_tri if gia_tri > 0 or (cho_phep_0 and gia_tri == 0) else mac_dinh


# R1: giới hạn thời gian gọi OpenAI. Trước đây 180 s x (1 + 2 lần SDK tự thử lại) = tới 9 phút treo giao diện.
OPENAI_TIMEOUT = _so_nguyen_env("OPENAI_TIMEOUT", 90)                          # giây, cho mỗi lần gọi
OPENAI_MAX_RETRIES = _so_nguyen_env("OPENAI_MAX_RETRIES", 1, cho_phep_0=True)  # SDK tự thử lại khi lỗi mạng/5xx
OPENAI_TOTAL_DEADLINE = _so_nguyen_env("OPENAI_TOTAL_DEADLINE", 180)           # giây, hạn tổng cho 1 CV
# Có để OpenAI lưu phản hồi không. Mặc định "1" = như trước (API mặc định store=true) và cho phép
# sửa JSON bằng previous_response_id (không gửi lại file). "0" = không lưu, sửa JSON bằng cách gửi lại toàn bộ.
OPENAI_STORE = os.getenv("OPENAI_STORE", "1").strip() != "0"


# S7: dung lượng tối đa của file tải lên (MB). Phải khớp server.maxUploadSize trong .streamlit/config.toml.
MAX_UPLOAD_MB = _so_nguyen_env("MAX_UPLOAD_MB", 20)


class ExtractError(Exception):
    """Lỗi có thông báo thân thiện, hiển thị thẳng cho người dùng."""


def kiem_tra_file(file_bytes: bytes, filename: str) -> None:
    """Chặn file quá lớn hoặc rỗng trước khi xử lý (S7). Lỗi -> ExtractError có thông báo dễ hiểu."""
    if not file_bytes:
        raise ExtractError(f"File '{Path(filename).name}' trống.")
    so_mb = len(file_bytes) / (1024 * 1024)
    if so_mb > MAX_UPLOAD_MB:
        raise ExtractError(f"File nặng {so_mb:.1f} MB, vượt giới hạn {MAX_UPLOAD_MB} MB. "
                           "Hãy nén hoặc xuất lại file nhẹ hơn rồi gửi lại.")


# ---------------------------------------------------------------------------
# Chuẩn bị nội dung gửi đi
# ---------------------------------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _docx_to_text(file_bytes: bytes) -> tuple[str, bool]:
    """Trích văn bản từ DOCX (cả đoạn văn lẫn bảng). Trả (văn bản, có_ảnh)."""
    import docx  # python-docx

    doc = docx.Document(io.BytesIO(file_bytes))
    dong = [p.text for p in doc.paragraphs if p.text.strip()]
    for bang in doc.tables:
        for hang in bang.rows:
            o = []
            for cell in hang.cells:
                t = cell.text.strip()
                if t and (not o or o[-1] != t):  # bỏ ô bị gộp lặp lại
                    o.append(t)
            if o:
                dong.append(" | ".join(o))
    co_anh = len(doc.inline_shapes) > 0
    return "\n".join(dong), co_anh


def _build_file_part(file_bytes: bytes, filename: str) -> tuple[dict, list[str]]:
    """Tạo phần nội dung chứa CV theo loại file. Trả (part, ghi_chú)."""
    duoi = Path(filename).suffix.lower()
    ghi_chu: list[str] = []

    if duoi == ".pdf":
        part = {
            "type": "input_file",
            "filename": filename,
            "file_data": f"data:application/pdf;base64,{_b64(file_bytes)}",
        }
    elif duoi in DUOI_ANH:
        mime = "image/png" if duoi == ".png" else "image/jpeg"
        part = {"type": "input_image", "image_url": f"data:{mime};base64,{_b64(file_bytes)}"}
    elif duoi == ".docx":
        van_ban, co_anh = _docx_to_text(file_bytes)
        if not van_ban.strip():
            raise ExtractError("File DOCX không có nội dung chữ để đọc.")
        if not co_anh:
            ghi_chu.append("DOCX không có ảnh chân dung")
        part = {"type": "input_text", "text": f"Nội dung CV (trích từ file DOCX):\n\n{van_ban}"}
    else:
        raise ExtractError(f"Chưa hỗ trợ loại file '{duoi}'. Hãy dùng PDF, PNG, JPG hoặc DOCX.")
    return part, ghi_chu


def _mau_user() -> tuple[str, dict[str, str]]:
    """prompts/user.txt: phần trên '---' là mẫu câu, phần dưới là chữ thay thế khi người dùng để trống."""
    mau, _, phu = doc_prompt("user.txt").partition("\n---\n")
    thay = {}
    for dong in phu.splitlines():
        if "=" in dong and not dong.lstrip().startswith("#"):
            k, v = dong.split("=", 1)
            thay[k.strip()] = v.strip()
    return mau, thay


def _user_text(project: str, position: str, today: date) -> str:
    mau, thay = _mau_user()
    return mau.format(hom_nay=f"{today:%d/%m/%Y}",
                      du_an=project or thay["khong_co_du_an"],
                      vi_tri=position or thay["khong_co_vi_tri"])


# ---------------------------------------------------------------------------
# Đọc và kiểm tra JSON trả về
# ---------------------------------------------------------------------------

def parse_json_text(text: str) -> dict:
    """Đọc JSON từ chuỗi; tự bóc ```json ... ``` nếu model lỡ thêm vào."""
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", t, flags=re.DOTALL)
    if m:
        t = m.group(1)
    return json.loads(t)


def validate(data: dict) -> dict:
    """Kiểm tra bằng pydantic, trả dict đã chuẩn hoá."""
    return CVData.model_validate(data).model_dump()


# ---------------------------------------------------------------------------
# Gọi API
# ---------------------------------------------------------------------------

def _client():
    from openai import OpenAI

    if not os.getenv("OPENAI_API_KEY"):
        raise ExtractError("Chưa cấu hình OPENAI_API_KEY (xem README).")
    return OpenAI(timeout=OPENAI_TIMEOUT, max_retries=OPENAI_MAX_RETRIES)


def _call_api(client, input_: list, previous_response_id: str | None = None,
              timeout: float | None = None) -> tuple[str, str | None]:
    """Gọi OpenAI một lần, đổi các lỗi kỹ thuật thành thông báo dễ hiểu. Trả (văn bản, response id)."""
    import openai

    tham_so = dict(
        model=MODEL,
        instructions=SYSTEM_PROMPT,     # instructions không được kế thừa qua previous_response_id -> luôn gửi
        input=input_,
        max_output_tokens=MAX_TOKENS,
        text={"format": {"type": "json_schema", "name": "ho_so_ung_vien", "schema": SCHEMA, "strict": True}},
        store=OPENAI_STORE,
    )
    if previous_response_id:
        tham_so["previous_response_id"] = previous_response_id
    if timeout is not None:
        tham_so["timeout"] = timeout
    t0 = time.monotonic()
    try:
        resp = client.responses.create(**tham_so)
    except openai.APIError as e:
        log.warning("OpenAI lỗi sau %.1f giây: %s", time.monotonic() - t0, type(e).__name__)
        _doi_loi_openai(e, timeout)

    log.info("OpenAI trả lời sau %.1f giây (trạng thái %s)", time.monotonic() - t0, resp.status)
    if resp.status == "incomplete":
        ly_do = getattr(resp.incomplete_details, "reason", "")
        if ly_do == "max_output_tokens":
            raise ExtractError("CV quá dài, kết quả bị cắt giữa chừng. Tăng OPENAI_MAX_TOKENS rồi thử lại.")
        raise ExtractError(f"OpenAI trả về kết quả chưa đầy đủ ({ly_do}).")
    return resp.output_text, getattr(resp, "id", None)


def _doi_loi_openai(e: Exception, timeout: float | None) -> None:
    """Đổi lỗi của SDK OpenAI thành ExtractError có câu thông báo tiếng Việt."""
    import openai

    try:
        raise e
    except openai.AuthenticationError:
        raise ExtractError("API key OpenAI không hợp lệ hoặc đã bị thu hồi. Báo người quản trị kiểm tra.")
    except openai.RateLimitError as e:
        if "insufficient_quota" in str(e):
            raise ExtractError("Tài khoản OpenAI đã hết hạn mức/tiền. Báo người quản trị nạp thêm.")
        raise ExtractError("Hệ thống đang quá tải (giới hạn tốc độ). Vui lòng thử lại sau 1 phút.")
    except openai.APITimeoutError:
        cho = f" (đã chờ quá {timeout:.0f} giây)" if timeout else ""
        raise ExtractError(f"Hết thời gian chờ phản hồi từ OpenAI{cho}. Vui lòng gửi lại sau ít phút.")
    except openai.APIConnectionError:
        raise ExtractError("Không kết nối được tới OpenAI. Kiểm tra mạng rồi thử lại.")
    except openai.BadRequestError as e:
        raise ExtractError(f"OpenAI từ chối yêu cầu: {getattr(e, 'message', e)}")
    except openai.APIError as e2:
        raise ExtractError(f"Lỗi từ OpenAI: {getattr(e2, 'message', e2)}")


def extract_cv(file_bytes: bytes, filename: str, project: str = "",
               position: str = "", today: date | None = None) -> dict:
    """Trích xuất CV thành dict đúng schema. Lỗi -> ExtractError (thông báo thân thiện)."""
    if today is None:
        from services.pdf.render import hom_nay_vn   # Q7: ngày theo giờ Việt Nam, không theo giờ máy
        today = hom_nay_vn()
    kiem_tra_file(file_bytes, filename)
    file_part, ghi_chu = _build_file_part(file_bytes, filename)
    client = _client()

    messages: list = [{"role": "user", "content": [file_part,
                       {"type": "input_text", "text": _user_text(project, position, today)}]}]
    input_, prev_id = messages, None

    bat_dau = time.monotonic()
    loi_cuoi = ""
    for lan in range(1 + SO_LAN_THU_LAI):
        con_lai = OPENAI_TOTAL_DEADLINE - (time.monotonic() - bat_dau)
        if con_lai < 5:
            raise ExtractError(f"Quá {OPENAI_TOTAL_DEADLINE} giây mà AI vẫn chưa trả về kết quả hợp lệ. "
                               "Vui lòng gửi lại sau ít phút.")
        # Chia thời gian còn lại cho cả các lần SDK tự thử lại -> tổng không vượt hạn
        moi_lan = min(OPENAI_TIMEOUT, con_lai / (1 + OPENAI_MAX_RETRIES))
        raw, resp_id = _call_api(client, input_, prev_id, timeout=moi_lan)
        try:
            data = validate(parse_json_text(raw))
        except (json.JSONDecodeError, ValidationError) as e:
            loi_cuoi = str(e)
            log.warning("JSON lần %d không hợp lệ (%s), yêu cầu AI sửa", lan + 1, type(e).__name__)
            sua = {"role": "user", "content": doc_prompt("fix_json.txt").format(loi=loi_cuoi[:2000])}
            if OPENAI_STORE and resp_id:
                # R1: OpenAI đã lưu lượt trước -> chỉ gửi câu yêu cầu sửa, không gửi lại cả file CV
                input_, prev_id = [sua], resp_id
            else:
                messages += [{"role": "assistant", "content": raw}, sua]
                input_, prev_id = messages, None
            continue
        data["model_notes"]["other"] += ghi_chu
        return data

    raise ExtractError(f"AI trả về dữ liệu sai cấu trúc sau {1 + SO_LAN_THU_LAI} lần thử. Chi tiết: {loi_cuoi[:500]}")


# ---------------------------------------------------------------------------
# Chạy thử từ dòng lệnh
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import sys
    import time

    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Trích xuất thử một CV ra JSON")
    ap.add_argument("file")
    ap.add_argument("--project", default="")
    ap.add_argument("--position", default="")
    ap.add_argument("--out", default="data/thu_extract.json")
    args = ap.parse_args()

    p = Path(args.file)
    t0 = time.time()
    try:
        ket_qua = extract_cv(p.read_bytes(), p.name, args.project, args.position)
    except ExtractError as e:
        print("LỖI:", e)
        sys.exit(1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Xong sau {time.time() - t0:.0f}s -> {args.out}")
    print(json.dumps(ket_qua["model_notes"], ensure_ascii=False, indent=2))
    print("Lương mong muốn:", ket_qua["expected_salary"])
    print("Ô số liệu:", [(s["value"], s["label"]) for s in ket_qua["stats"]])
