# Dịch máy offline (vi → en)

Tính năng "Dịch sang tiếng Anh" ở trang Chỉnh sửa nội dung (`/edit`) dùng **dịch máy chạy ngay trên máy chủ**:
CTranslate2 (bộ chạy mô hình, CPU, int8) + Opus-MT `vi-en` (mô hình). CV không gửi ra ngoài, không cần internet khi chạy.

Code: `system/services/translation/nmt.py`, endpoint `POST /api/cv/translate` (xem [api.md](api.md) mục 3.2).

## Cách hoạt động

1. Nhân viên bấm **Dịch sang tiếng Anh** ở trang `/edit` (nút chỉ hiện khi máy chủ đã cài mô hình).
2. Máy chủ dọn hồ sơ, rồi với từng đoạn chữ tự do:
   - đoạn không có dấu tiếng Việt → bỏ qua (đã là tiếng Anh hoặc gõ không dấu);
   - thuật ngữ có trong bảng cố định (`config/pdf_labels.toml`, bằng cấp) → tra bảng;
   - còn lại → dịch máy, sau đó **kiểm tra**: không rỗng, độ dài hợp lý, **số liệu giữ nguyên**. Không đạt → giữ tiếng Việt.
3. Kết quả thay vào form. Ngôn ngữ xuất PDF tự chuyển sang English; ô "Đã kiểm tra các mục hệ thống tự lập" bị bỏ tick
   (vì `model_notes.self_created` có thêm dòng "Dịch máy ... cần đọc lại").
4. Nhân viên đọc, sửa, bấm **Lưu & cập nhật PDF**. Muốn bỏ bản dịch: **Về bản đọc ban đầu**.

**Không đưa vào dịch máy:** họ tên, tên công ty, tên trường, người tham chiếu (tên/công ty), thời gian.
**Chỉ tra bảng thuật ngữ** (`config/translation_glossary.toml` + `pdf_labels.toml`, không có trong bảng thì giữ nguyên): giới tính, nhãn và giá trị dòng thông tin ("Mong muốn"), giá trị ô số liệu, thẻ kỹ năng, tiêu đề mục. Nhãn ô số liệu (câu ngắn) thì được dịch máy.
Dấu in đậm `**...**` trong đoạn đã dịch máy bị mất (mô hình làm hỏng ký hiệu này).

Bản dịch máy chỉ là **bản nháp**. Quy tắc riêng tư giữ nguyên: log không ghi nội dung đoạn dịch, báo cáo chỉ có đường dẫn trường + lý do.

## Cài đặt trên máy chủ

Thư viện `ctranslate2` và `sentencepiece` đã nằm trong `system/requirements.txt` (có sẵn trong image Docker).
**Mô hình không nằm trong image**, đặt ở `data/models/opus-mt-vi-en/` (thư mục `data/` không commit, đã mount vào container):

```
data/models/opus-mt-vi-en/
  model.bin  source.spm  target.spm  (+ config.json, shared_vocabulary...)
```

Tạo mô hình (một lần, trên máy dev; cần thêm `transformers` và `torch`, **không** cần trên máy chủ). Nếu máy dev chặn
DLL của `torch`/`ctranslate2` (chính sách Application Control của Windows), chạy lệnh này trong container Linux
(`docker run --rm -v "<repo>:/work" -w /work/system python:3.13-slim ...`):

```powershell
cd system
python -m pip install transformers torch
python scripts/convert_opus_mt.py                    # Opus-MT: data/models/opus-mt-vi-en (int8, ~75 MB)
python scripts/convert_opus_mt.py --preset vinai     # VinAI:   data/models/vinai-vi2en  (int8, ~0,4 GB)
```

App tự nhận loại mô hình theo file trong thư mục (`source.spm` + `target.spm` = Opus-MT; `sentencepiece.bpe.model` = VinAI).
Chọn mô hình bằng `TRANSLATE_MODEL_DIR` (mặc định `data/models/opus-mt-vi-en`), ví dụ `TRANSLATE_MODEL_DIR=data/models/vinai-vi2en`.

Rồi chép thư mục `opus-mt-vi-en` lên VPS vào `/opt/fillcv-lighthuman/data/models/` và khởi động lại container:

```bash
scp -r data/models/opus-mt-vi-en root@<IP-VPS>:/opt/fillcv-lighthuman/data/models/
chown -R 1000:1000 /opt/fillcv-lighthuman/data/models     # appuser của container
docker compose restart app
```

Kiểm tra: `GET /api/config` có `"translation": {"available": true, ...}`. Tắt hẳn: đặt `CV_TRANSLATOR=none`.

Mô hình được **nạp sẵn ở nền ngay khi app khởi động** (lần dịch đầu không phải chờ nạp 15-45 giây, tránh Cloudflare Tunnel cắt kết nối ở 100 giây); đặt `TRANSLATE_PRELOAD=0` để tắt (tiết kiệm ~0,7 GB RAM với VinAI). Khi đang dịch, giao diện hiện thanh tiến độ + số giây đã chờ.

Biến môi trường: `CV_TRANSLATOR`, `TRANSLATE_PRELOAD`, `TRANSLATE_MODEL_DIR`, `TRANSLATE_MAX_CONCURRENT` (mặc định 1), `TRANSLATE_QUEUE_TIMEOUT`,
`TRANSLATE_THREADS` (mặc định 2, chừa CPU cho Chromium) — bảng đầy đủ ở [README](../README.md).

## Kết quả thử nghiệm (23/11/2026)

Đo bằng chính code của app trong container Linux Python 3.13, giới hạn **2 CPU / 3 GB RAM, 2 luồng dịch** (mô phỏng VPS),
trên 2 hồ sơ **giả** (khoảng 70 đoạn chữ mỗi hồ sơ). Chất lượng do người viết code đọc, **chưa phải đánh giá của nhân viên**.

| | Opus-MT `vi-en` | VinAI `vi2en-v2` |
|---|---|---|
| Thời gian dịch một CV | 0,8 giây | 3,5 giây (lần nạp mô hình đầu: ~15 giây) |
| RAM tăng thêm | ~180 MB | ~700 MB |
| Dung lượng mô hình (int8) | 75 MB | 414 MB |
| Đoạn bị loại bởi bước kiểm tra | 2/68 | 0/68 |
| Chất lượng đọc thử | **Kém**: khoảng 1/3 đoạn dùng được, nhiều câu sai nghĩa ("Cử nhân Kế toán" → "Organize Accounting", "hạch toán" → "fusion", "Excel" → "OSL"), từng đổi "800 tỷ đồng" thành "$800 billion" | **Tốt**: gần hết đoạn dùng được; lỗi còn lại nhỏ ("Quản lý tài chính" → "Financial management services") |
| Giấy phép | CC-BY 4.0 | **AGPL-3.0** (theo thông tin trên trang mô hình) |

Kết luận tạm thời: **Opus-MT không đủ chất lượng** cho hồ sơ gửi khách; **VinAI đủ nhanh, đủ nhẹ và dịch tốt**, nhưng cần
**duyệt giấy phép AGPL-3.0** (và điều khoản bộ dữ liệu PhoMT, chưa kiểm tra) trước khi dùng thật.

Hai lỗi đã gặp và sửa trong quá trình thử (ghi lại để khỏi lặp lại):

- Opus-MT: câu đầu vào **bắt buộc** có `</s>` cuối câu, thiếu thì dịch lặp từ đến hết độ dài tối đa (sai và chậm gấp 30 lần).
- Bước kiểm tra số liệu không bắt được lỗi đổi tiền tệ (chữ số vẫn đúng) nên đã thêm kiểm tra riêng (đồng ↔ ngoại tệ).

Dịch máy dù tốt vẫn có thể sai nghĩa mà qua được mọi kiểm tra tự động: **luôn cần người đọc lại**.

## Đánh giá chất lượng trước khi dùng rộng

Script `system/scripts/benchmark_translation.py` đo thời gian, RAM và xuất bảng đối chiếu để người đọc chấm
(dùng ngay / sửa nhẹ / dịch lại):

```powershell
cd system
$env:PYTHONPATH='.'
python scripts/benchmark_translation.py data/benchmark/*.json --dump data/benchmark/review.tsv
```

CV thật chỉ để trong `data/` (không commit). Ngưỡng đề xuất để duyệt dùng chính thức:

- ít nhất 80% đoạn ở mức "dùng ngay" hoặc "sửa nhẹ";
- không có lỗi nào làm sai số hoặc ngày;
- dịch cả CV dưới 15 giây trên cấu hình giống VPS (4 vCPU);
- RAM tăng thêm dưới 1 GB.

## Giấy phép

- Opus-MT: CC-BY 4.0 (cần ghi công Helsinki-NLP).
- VinAI Translate (huấn luyện trên PhoMT): **AGPL-3.0** theo thông tin trên trang mô hình HuggingFace. AGPL có điều khoản về
  cung cấp mã nguồn cho người dùng truy cập qua mạng; áp dụng thế nào cho một công cụ nội bộ chạy mô hình này, và điều khoản
  của bộ dữ liệu PhoMT, cần **người có chuyên môn pháp lý duyệt** trước khi dùng thật. Chưa có kết luận trong tài liệu này.
