# Hướng dẫn triển khai: Cloudflare Tunnel + Access

> Mục tiêu: app chạy trên máy nội bộ, nhân viên truy cập qua domain (vd `cv.lighthuman.vn`) với đăng nhập email công ty. Không cần mở port, không cần IP tĩnh, HTTPS tự động.

---

## Yêu cầu

- Máy chạy app: Windows 10/11, ≥ 8 GB RAM (4 GB trống cho app), Python 3.13+, mạng internet ổn định
- Tài khoản Cloudflare (miễn phí) với domain đã trỏ nameserver về Cloudflare
- (Khuyến nghị) Google Workspace hoặc Microsoft 365 của công ty — để đăng nhập bằng email công ty

---

## Bước 1 — Cài app và kiểm tra chạy được trên máy

```powershell
cd E:\FillCV-LightHuman

# Cài thư viện (chạy 1 lần)
python -m pip install -r requirements.txt
python -m playwright install chromium

# Chạy thử
python -m streamlit run app.py
```

Mở `http://localhost:8501` — nếu thấy giao diện là OK. Tắt app (Ctrl+C).

---

## Bước 2 — Cài Cloudflare Tunnel (`cloudflared`)

### Cách 1: Dùng winget (Windows 11)

```powershell
winget install Cloudflare.cloudflared
```

### Cách 2: Tải trực tiếp

Tải `cloudflared-windows-amd64.msi` từ https://github.com/cloudflare/cloudflared/releases/latest → cài đặt.

Kiểm tra:

```powershell
cloudflared --version
```

---

## Bước 3 — Tạo Tunnel trên Cloudflare Dashboard

1. Vào https://one.dash.cloudflare.com → **Networks** → **Tunnels**
2. Bấm **Create a tunnel**
3. Chọn **Cloudflared** → đặt tên tunnel, vd `fillcv-lighthuman`
4. Cloudflare hiện lệnh cài connector — **copy token** (chuỗi dài sau `--token`), lưu lại
5. Cấu hình **Public Hostname**:
   - **Subdomain**: `cv` (hoặc tên bạn muốn)
   - **Domain**: chọn domain của bạn (vd `lighthuman.vn`)
   - **Service**: `http://localhost:8501`
6. Bấm **Save tunnel**

Kết quả: domain `cv.lighthuman.vn` sẽ trỏ về `localhost:8501` trên máy bạn.

---

## Bước 4 — Chạy Tunnel trên máy Windows

### Chạy thử (xem log để debug)

```powershell
cloudflared tunnel run --token <TOKEN_CỦA_BẠN>
```

### Cài thành Windows Service (chạy tự động khi mở máy)

```powershell
# Chạy PowerShell với quyền Administrator
cloudflared service install <TOKEN_CỦA_BẠN>
```

Kiểm tra service:

```powershell
Get-Service cloudflared
```

Trạng thái `Running` là OK. Từ giờ tunnel tự chạy khi máy khởi động.

---

## Bước 5 — Bật Cloudflare Access (đăng nhập bắt buộc)

> [!CAUTION]
> **BẮT BUỘC LÀM BƯỚC NÀY.** App không có đăng nhập riêng — bỏ qua bước này = ai biết URL đều xem được CV.

1. Vào https://one.dash.cloudflare.com → **Access** → **Applications**
2. Bấm **Add an application** → **Self-hosted**
3. Điền:
   - **Application name**: `Hồ sơ ứng viên`
   - **Session duration**: `24 hours` (hoặc tuỳ chọn)
   - **Application domain**: `cv.lighthuman.vn` (khớp với bước 3)
4. **Add a policy** (ai được vào):
   - **Policy name**: `Nhân viên Light Human`
   - **Action**: `Allow`
   - **Include rule**: chọn **Emails ending in** → nhập `lighthuman.vn`
   - (Hoặc chọn **Login Methods** → **Google** nếu công ty dùng Google Workspace)
5. **Authentication** → chọn phương thức đăng nhập:
   - **One-time PIN** (đơn giản nhất): Cloudflare gửi mã OTP qua email → nhân viên nhập mã
   - **Google**: đăng nhập bằng tài khoản Google công ty (nếu dùng Google Workspace)
   - **Microsoft**: đăng nhập bằng Microsoft 365
6. Bấm **Save**

Kết quả: truy cập `cv.lighthuman.vn` → Cloudflare yêu cầu đăng nhập → chỉ email `@lighthuman.vn` mới vào được → app Streamlit hiển thị.

---

## Bước 6 — Chạy app tự động khi khởi động máy

Tạo script khởi động:

```powershell
# Tạo file start-app.ps1 trong thư mục dự án
@"
Set-Location E:\FillCV-LightHuman
python -m streamlit run app.py --server.address=localhost --server.port=8501
"@ | Out-File -FilePath "E:\FillCV-LightHuman\start-app.ps1" -Encoding utf8
```

Đăng ký vào Task Scheduler:

```powershell
# Chạy PowerShell với quyền Administrator
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File E:\FillCV-LightHuman\start-app.ps1"

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName "FillCV-LightHuman" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Hồ sơ ứng viên Light Human - Streamlit app" `
    -RunLevel Highest
```

Từ giờ: **mở máy → tunnel tự chạy → app tự chạy → nhân viên truy cập qua domain được ngay**.

---

## Bước 7 — Kiểm tra

| Kiểm tra | Cách | Kết quả đúng |
|---|---|---|
| App chạy trên máy | Mở `http://localhost:8501` | Thấy giao diện |
| Tunnel hoạt động | Mở `https://cv.lighthuman.vn` | Thấy trang đăng nhập Cloudflare Access |
| Access chặn người lạ | Mở bằng email cá nhân (gmail) | Bị từ chối |
| Access cho nhân viên | Đăng nhập bằng email `@lighthuman.vn` | Thấy giao diện app |
| Upload CV | Gửi 1 file PDF thử | PDF hồ sơ xuất ra OK |
| Tự khởi động | Restart máy, chờ 1-2 phút | App + tunnel tự chạy lại |

---

## Sự cố thường gặp

| Lỗi | Nguyên nhân | Cách xử lý |
|---|---|---|
| `502 Bad Gateway` trên domain | App chưa chạy hoặc đang khởi động | Chờ 30s; kiểm tra `localhost:8501` |
| Tunnel `ERR_CONNECTION_REFUSED` | Port sai hoặc app bind sai address | Đảm bảo app chạy trên `localhost:8501` |
| Đăng nhập xong vẫn bị chặn | Email không thuộc domain cho phép | Kiểm tra policy trong Access |
| App chạy chậm qua tunnel | Băng thông upload máy thấp | Bình thường — PDF chỉ ~200-500KB |
| `cloudflared` service không chạy | Token hết hạn hoặc sai | Gỡ service, cài lại với token mới |

### Gỡ service cloudflared (nếu cần cài lại)

```powershell
# PowerShell Administrator
cloudflared service uninstall
```

### Xem log tunnel

```powershell
cloudflared tunnel run --token <TOKEN> --loglevel debug
```

---

## Chi phí

| Thành phần | Chi phí |
|---|---|
| Cloudflare Tunnel | **Miễn phí** |
| Cloudflare Access (≤ 50 users) | **Miễn phí** |
| Domain `.vn` | ~350.000₫/năm |
| SSL/HTTPS | **Miễn phí** (Cloudflare cấp) |
| Máy chạy app | Máy hiện có (hoặc mini PC ~3-5 triệu) |
| **Tổng** | **~350.000₫/năm** (chỉ tiền domain) |

---

## Nâng cấp sau này (tuỳ chọn)

| Việc | Khi nào cần | Công sức |
|---|---|---|
| Chuyển sang VPS + Docker | Máy nội bộ không ổn định, hay mất điện/mạng | 1-2 ngày |
| Thêm `st.login` trong app | Cần biết **ai** làm hồ sơ nào (audit log) | 0.5-1 ngày |
| CI tự chạy test | Repo lên GitHub, nhiều người sửa code | 2 giờ |
| Monitoring (uptime check) | Cần biết app có đang chạy không mà không kiểm tra thủ công | 1 giờ |

