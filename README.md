# Hồ sơ ứng viên – Light Human

Web app nội bộ của **Light Human** (công ty tuyển dụng nhân sự): tải CV gốc lên, bộ trích xuất chạy **ngay trên máy chủ** dựng hồ sơ, nhân viên duyệt và sửa, rồi xuất PDF "Hồ sơ ứng viên" theo mẫu thương hiệu, đã bỏ thông tin liên hệ của ứng viên.

**Dữ liệu CV không rời máy chủ.** App không gọi bất kỳ dịch vụ AI hay API bên ngoài nào. Khi dịch sang tiếng Anh, app dùng bảng dịch cố định và dịch máy offline chạy ngay trên máy chủ (xem [docs/dich-may-offline.md](docs/dich-may-offline.md)).

---

## Mục lục

- [Tính năng](#tính-năng)
- [Kiến trúc triển khai](#kiến-trúc-triển-khai)
- [Chạy trên máy để phát triển](#chạy-trên-máy-để-phát-triển)
- [Cách dùng](#cách-dùng)
- [Triển khai chính thức trên VPS](#triển-khai-chính-thức-trên-vps)
  - [1. Tạo khoá SSH](#1-tạo-khoá-ssh)
  - [2. Chuẩn bị VPS](#2-chuẩn-bị-vps)
  - [3. Cài và chạy app bằng Docker](#3-cài-và-chạy-app-bằng-docker)
  - [4. Cloudflare: domain, Tunnel, Access](#4-cloudflare-domain-tunnel-access)
  - [5. Nối tunnel từ VPS](#5-nối-tunnel-từ-vps)
  - [6. Kiểm tra sau khi triển khai](#6-kiểm-tra-sau-khi-triển-khai)
- [Vận hành hằng ngày](#vận-hành-hằng-ngày)
- [Cấu hình](#cấu-hình)
- [Cấu trúc mã nguồn](#cấu-trúc-mã-nguồn)
- [Chạy test](#chạy-test)
- [Bảo mật](#bảo-mật)
- [Log](#log)
- [Sự cố thường gặp](#sự-cố-thường-gặp)
- [Tài liệu liên quan](#tài-liệu-liên-quan)
- [Công nghệ](#công-nghệ)

---

## Tính năng

- **Trích xuất tự động**: bộ đọc PDF theo luật (`rules`) đọc chữ, cỡ chữ và in đậm, tách mục, tách kinh nghiệm/học vấn, lọc thông tin nhạy cảm, lập ô số liệu và lưu ý tuyển dụng.
- **Bảo vệ thông tin ứng viên**: tự xoá SĐT, email, địa chỉ, link cá nhân, nơi sinh, tình trạng hôn nhân; chỉ giữ năm sinh; lương mong muốn chỉ ghi nội bộ, không đưa vào PDF.
- **PDF chuẩn thương hiệu**: header Light Human, font Times New Roman, ảnh chân dung cắt tự động (nhận diện khuôn mặt bằng OpenCV), tự chọn cỡ chữ vừa trang. Xuất được bản Tiếng Việt hoặc English.
- **Kiểm tra trước khi tải**: khoá nút **Tải PDF** khi còn sót thông tin nhạy cảm (quét cả dữ liệu lẫn file PDF), và chỉ ra chỗ cần sửa.
- **Hàng đợi**: giới hạn số lượt dựng PDF và đọc CV chạy cùng lúc; người tới sau tự xếp hàng.
- **Tự dọn dẹp**: PDF đã xuất tự xoá sau 30 ngày (đổi được).

---

## Kiến trúc triển khai

```
Nhân viên (trình duyệt)
   │  https://<domain>
   ▼
Cloudflare ── Access: bắt đăng nhập bằng mã OTP gửi qua email, chỉ email trong danh sách mới vào được
   │
   │  Cloudflare Tunnel (kết nối đi RA từ VPS, VPS không mở cổng web nào)
   ▼
VPS Ubuntu ── cloudflared (systemd)
   │            │
   │            ▼
   │         nginx  (Docker, chỉ nghe 127.0.0.1:80)
   │            │
   │            ▼
   │         app Starlette + React build  (Docker, cổng 8000 chỉ trong mạng Docker)
   │
   └── data/output (PDF + JSON đã xuất), data/logs
```

- App **không có đăng nhập riêng**. Lớp bảo vệ là **Cloudflare Access**; nếu bỏ Access thì ai biết địa chỉ cũng xem được CV.
- Tường lửa VPS chỉ mở cổng SSH. Truy cập web đi duy nhất qua tunnel.

---

## Chạy trên máy để phát triển

**Yêu cầu:** Python 3.13+, Node.js 20+, Windows hoặc Linux.

### Cài đặt

```powershell
# Backend (thư mục system/)
cd system
python -m pip install -r requirements-dev.txt   # thư viện app + test
python -m playwright install chromium            # bắt buộc: PDF được dựng bằng Chromium

# Frontend (thư mục web/)
cd ..\web
npm install
```

Không dùng `opencv-python-headless` bản 5.x: bản này đã bỏ bộ nhận diện khuôn mặt Haar cascade mà app dùng để cắt ảnh chân dung (đã ghim `<5` trong `requirements.txt`).

### Chạy chế độ phát triển

Mở 2 terminal:

```powershell
# Terminal 1: backend API, cổng 8000
cd system
python -m api.server

# Terminal 2: frontend Vite, cổng 5173 (tự chuyển /api sang 8000)
cd web
npm run dev
```

Mở `http://localhost:5173`.

### Chạy bằng Docker trên máy

```powershell
# Từ thư mục gốc repo
docker compose up -d --build
```

Mở `http://localhost` (nginx, chỉ mở cho chính máy này). PDF đã xuất và log nằm ở `data/` của thư mục gốc.

---

## Cách dùng

1. **Nạp CV** (cột trái, khung *Trạng thái bóc tách CV*): kéo thả hoặc bấm để chọn file CV (PDF, DOCX, PNG, JPG, tối đa 20 MB). Nhập *Tên dự án*, *Vị trí ứng tuyển* (không bắt buộc), chọn *Ngôn ngữ xuất hồ sơ*, rồi bấm **Bắt đầu bóc tách CV**.
   - Thanh tiến trình hiện các bước đang chạy thật. Xong sẽ có các thẻ: ứng viên đã nhận diện, thông tin đã loại bỏ, lương mong muốn (chỉ nội bộ), mục hệ thống tự lập, lưu ý tuyển dụng, mục cần xem lại, và **tin nhắn tóm tắt** để sao chép.
   - Bộ trích xuất mặc định là `rules` (không AI, không mạng). Hiện chỉ đọc tự động **PDF có lớp chữ** (chưa OCR). DOCX, ảnh, PDF scan hoặc PDF lỗi font sẽ ra **khung trống để nhập tay** kèm lý do.
2. **Xem và sửa** (cột phải, khung *Hồ sơ PDF*):
   - Tab **Bản PDF**: xem trước PDF, checklist chất lượng, đổi ngôn ngữ.
   - Tab **Chỉnh sửa nội dung**: sửa từng mục, thay hoặc bỏ ảnh. Phần không chắc chắn có nhãn **Cần xem**. Sửa xong bấm **Cập nhật PDF**.
   - Tab **CV gốc**: đối chiếu với file gốc.
3. **Tải PDF**: tick 2 ô xác nhận, bấm **Tải PDF**. Một bản sao PDF và file `.json` hồ sơ cùng tên được lưu vào `data/output`; trùng tên thì thêm hậu tố giờ, không ghi đè.

**Nút Tải PDF bị khoá khi** còn số điện thoại, email, link hoặc ngày sinh (trong nội dung, tên dự án, vị trí hay trong chính file PDF), hồ sơ chưa hợp lệ, hoặc PDF chưa cập nhật theo nội dung mới. Lý do hiện ngay dưới các nút.

Tên file PDF theo chuẩn `LH - CV <Vị trí> - <Họ tên> - <ddmmyyyy>.pdf`; bản tiếng Anh thêm ` - EN`.

---

## Triển khai chính thức trên VPS

Cấu hình khuyên dùng: **Ubuntu (24.04 trở lên), ảo hoá KVM, 2–4 vCPU, 4 GB RAM, 40 GB SSD trở lên**. Không nên dùng VPS Windows: riêng hệ điều hành đã chiếm 1,5–2 GB RAM, và Docker thường không chạy được.

Trong hướng dẫn: `<IP-VPS>` là IP của VPS, `<domain>` là tên miền dùng cho app.

### 1. Tạo khoá SSH

Dùng khoá SSH thay cho mật khẩu: an toàn hơn và không bị bot dò mật khẩu. **Khoá riêng (private key) không bao giờ gửi cho ai, không commit lên git.** Chỉ khoá công khai (`.pub`) được chép lên VPS.

#### Cách A: OpenSSH (PowerShell hoặc Git Bash, có sẵn trên Windows 10/11)

```powershell
# Tạo cặp khoá ed25519. Khi được hỏi passphrase, nên đặt một mật khẩu cho khoá.
ssh-keygen -t ed25519 -C "ten-may-hoac-ten-nguoi" -f $env:USERPROFILE\.ssh\id_ed25519_fillcv

# Xem khoá công khai (dòng bắt đầu bằng ssh-ed25519 ...)
type $env:USERPROFILE\.ssh\id_ed25519_fillcv.pub
```

Chép khoá công khai lên VPS. Lần đầu sẽ phải nhập **mật khẩu root** của VPS; ký tự không hiện khi gõ, đó là bình thường:

```powershell
type $env:USERPROFILE\.ssh\id_ed25519_fillcv.pub | ssh root@<IP-VPS> "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys && echo DA_THEM_KHOA"
```

Từ lần sau, đăng nhập bằng khoá:

```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519_fillcv root@<IP-VPS>
```

#### Cách B: PuTTY và PuTTYgen

1. Mở **PuTTYgen**. Ở *Type of key*, chọn **EdDSA** (Ed25519), bấm **Generate** và rê chuột trong ô trống cho tới khi tạo xong.
2. Nhập **Key passphrase** (mật khẩu cho khoá) hai lần.
3. Copy toàn bộ nội dung ô *Public key for pasting into OpenSSH authorized_keys file* (một dòng `ssh-ed25519 ...`).
4. Bấm **Save private key**, lưu file `.ppk` ở nơi an toàn (ví dụ `Documents\ssh\fillcv.ppk`).
5. Đăng nhập VPS bằng PuTTY (mật khẩu) hoặc console web của nhà cung cấp. Dán lệnh sau, thay `<khoá công khai>` bằng dòng vừa copy (trong PuTTY, **bấm chuột phải** để dán):
   ```bash
   mkdir -p ~/.ssh && echo "<khoá công khai>" >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys && echo DA_THEM_KHOA
   ```
6. Trong PuTTY: **Session**, nhập `<IP-VPS>`. Vào **Connection → Data**, ô *Auto-login username* nhập `root`. Vào **Connection → SSH → Auth → Credentials**, mục *Private key file for authentication*, chọn file `.ppk`. Quay lại **Session**, đặt tên ở *Saved Sessions*, bấm **Save**. Từ giờ chỉ cần chọn session đã lưu rồi **Open**.

Có file khoá OpenSSH từ Cách A mà muốn dùng trong PuTTY: mở PuTTYgen, **Conversions → Import key**, chọn file khoá riêng, rồi **Save private key** ra `.ppk`.

#### Tắt đăng nhập bằng mật khẩu (làm sau khi khoá đã chạy)

**Mở sẵn một phiên SSH bằng khoá và giữ nguyên.** Chạy lệnh dưới trong phiên đó, rồi **mở thêm một phiên mới** để thử. Chỉ đóng phiên cũ khi phiên mới vào được.

```bash
cat > /etc/ssh/sshd_config.d/00-fillcv-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
sshd -t && systemctl reload ssh
```

File được đặt tên `00-...` để đứng trước `50-cloud-init.conf`: file cloud-init này trên nhiều VPS bật lại `PasswordAuthentication yes`, mà sshd lấy giá trị **đầu tiên** nó đọc được. Nếu bị khoá ngoài, vào **console web của nhà cung cấp VPS** rồi xoá file trên.

### 2. Chuẩn bị VPS

```bash
# Cập nhật hệ thống, cài tường lửa, chống dò mật khẩu, git
apt-get update && apt-get -y upgrade
apt-get -y install ufw fail2ban ca-certificates curl git

# Tường lửa: CHỈ mở SSH. Không mở 80/443, vì web đi qua Cloudflare Tunnel
ufw allow OpenSSH
ufw --force enable
systemctl enable --now fail2ban

# Swap 2 GB (đỡ cho lúc nhiều người dựng PDF cùng lúc)
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf && sysctl -p /etc/sysctl.d/99-swappiness.conf

# Docker Engine + Compose từ kho chính thức của Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" > /etc/apt/sources.list.d/docker.list
apt-get update && apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker run --rm hello-world
```

### 3. Cài và chạy app bằng Docker

```bash
cd /opt
git clone --branch main https://github.com/Lebao1234/FillCV-LightHuman.git fillcv-lighthuman
cd fillcv-lighthuman

# Giới hạn RAM của app cho VPS 4 GB (chừa RAM cho hệ điều hành và cloudflared).
# File override này chỉ nằm trên VPS, không commit.
cat > docker-compose.override.yml <<'EOF'
services:
  app:
    mem_limit: 3g
EOF
echo "docker-compose.override.yml" >> .git/info/exclude

# Build và chạy (lần đầu 5–10 phút)
docker compose up -d --build

# BẮT BUỘC trên Linux: container chạy bằng user appuser (UID 1000), không phải root.
# Thiếu bước này app không ghi được log và dừng ngay khi khởi động (PermissionError ở data/logs/app.log).
chown -R 1000:1000 data/output data/logs
chmod 750 data/output data/logs
docker compose up -d

docker compose ps                        # cả hai container phải "healthy"
curl -s http://127.0.0.1/health          # {"status":"ok"}
```

nginx chỉ nghe ở `127.0.0.1:80`, nên từ internet không vào thẳng được. Cổng 8000 của app chỉ mở trong mạng Docker.

### 4. Cloudflare: domain, Tunnel, Access

**4.1. Đưa domain lên Cloudflare.** Thêm domain vào tài khoản Cloudflare (gói Free là đủ), rồi ở trang quản lý domain của nhà đăng ký, **thay** nameserver cũ bằng 2 nameserver Cloudflare cấp. Không trộn nameserver cũ và mới. Đợi trạng thái **Active**.

**4.2. Tạo Tunnel.** Vào https://one.dash.cloudflare.com, mục **Networks → Tunnels → Create a tunnel → Cloudflared**, đặt tên (ví dụ `FillCV-LightHuman`). Lưu lại **token** của tunnel ở nơi an toàn; không commit, không gửi qua chat.

**4.3. Trỏ hostname vào app.** Trong tunnel, mục **Public hostname** (hoặc *Published application routes*):
- Hostname: `<domain>`
- Service: `http://localhost:80` (nginx trên VPS)

Cloudflare tự tạo bản ghi DNS CNAME trỏ `<domain>` vào tunnel. Xoá các bản ghi A cũ của domain nếu còn.

**4.4. Bật Cloudflare Access. Bắt buộc, phải làm trước khi nối tunnel.**
1. Lần đầu dùng Zero Trust: đặt *team name*, chọn gói **Free** (miễn phí đến 50 người dùng).
2. **Settings → Authentication → Login methods**: thêm **One-time PIN** (mã OTP gửi qua email).
3. **Access controls → Applications → Add an application → Self-hosted**:
   - Name: `FillCV - Hồ sơ ứng viên`; Domain: `<domain>`; Session duration: `24 hours`.
   - Policy: tên `FillCV - Nhân viên được phép`, Action **Allow**, Include **Emails**, nhập từng email được phép.
   - Login methods: chỉ **One-time PIN**.

**4.5. HTTPS.** Ở dashboard của domain, **SSL/TLS → Edge Certificates**: bật **Always Use HTTPS**, đặt **Minimum TLS Version = 1.2**.

### 5. Nối tunnel từ VPS

Chỉ làm sau khi Access đã được tạo ở bước 4.4.

```bash
# Cài cloudflared
curl -fsSL -o /tmp/cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
dpkg -i /tmp/cloudflared.deb && rm /tmp/cloudflared.deb

# Lưu token vào file chỉ root đọc được. Lệnh read không hiện token khi dán.
install -d -m 700 /etc/cloudflared
read -rs -p "Dán token tunnel: " T && printf '%s' "$T" > /etc/cloudflared/tunnel-token && unset T && echo
chmod 600 /etc/cloudflared/tunnel-token

# Service systemd đọc token từ file (token không lộ trong danh sách tiến trình)
cat > /etc/systemd/system/cloudflared.service <<'EOF'
[Unit]
Description=Cloudflare Tunnel - FillCV
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/bin/cloudflared --no-autoupdate tunnel run --token-file /etc/cloudflared/tunnel-token
Restart=on-failure
RestartSec=5s
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now cloudflared
journalctl -u cloudflared -n 20 --no-pager | grep "Registered tunnel connection"
```

Mỗi tunnel chỉ nên chạy ở **một máy**. Nếu trước đó từng chạy `cloudflared` cho cùng tunnel ở máy khác (ví dụ máy Windows trong công ty), phải tắt ở máy đó. Trên Windows, chạy PowerShell bằng quyền Administrator: `Stop-Service cloudflared; Set-Service cloudflared -StartupType Disabled`. Nếu không tắt, Cloudflare chia truy cập ngẫu nhiên giữa hai máy: PDF dựng ở máy này nhưng lúc tải lại hỏi máy kia, nên báo "không tìm thấy".

### 6. Kiểm tra sau khi triển khai

| Kiểm tra | Cách làm | Kết quả đúng |
|---|---|---|
| Access chặn người lạ | `curl -I https://<domain>/` | `302` chuyển tới `...cloudflareaccess.com/.../login` |
| Chuyển sang HTTPS | `curl -I http://<domain>/` | `301` tới `https://` |
| VPS không lộ cổng web | Từ máy khác: thử kết nối `<IP-VPS>` cổng 80, 443, 8000 | Đều bị từ chối, chỉ cổng 22 mở |
| Email ngoài danh sách | Tab ẩn danh, nhập email khác | Không vào được |
| Luồng đầy đủ | Đăng nhập bằng OTP, upload CV thử, dựng PDF, tải PDF | Chạy hết, thanh tiến trình chạy liên tục |
| Request vào đúng VPS | `docker logs --since 10m fillcv-nginx` | Thấy request với **IP thật** của người dùng |
| Tự chạy lại sau khi khởi động | `reboot`, đợi 1–2 phút, mở lại `<domain>` | App vào được, không cần làm gì |

---

## Vận hành hằng ngày

Mọi lệnh chạy trên VPS, trong thư mục `/opt/fillcv-lighthuman`.

| Việc | Lệnh / cách làm |
|---|---|
| Cập nhật code mới từ GitHub | `git pull && docker compose up -d --build && docker image prune -f` |
| Xem trạng thái | `docker compose ps` · `systemctl status cloudflared` |
| Xem log app | `tail -f data/logs/app.log` · `docker logs -f fillcv-lighthuman` |
| Xem log tunnel | `journalctl -u cloudflared -f` |
| Xem RAM và CPU | `docker stats` · `free -h` |
| Khởi động lại app | `docker compose restart` |
| Thêm hoặc bớt người được vào | Cloudflare Zero Trust, **Access controls → Policies →** `FillCV - Nhân viên được phép` → sửa danh sách **Emails**. Không cần đụng tới VPS |
| Đổi token tunnel | Tạo lại token trên dashboard, ghi đè `/etc/cloudflared/tunnel-token`, chạy `systemctl restart cloudflared` |
| Sao lưu PDF đã xuất | `tar czf /root/fillcv-output-$(date +%F).tar.gz -C /opt/fillcv-lighthuman data/output`, rồi tải về máy khác bằng `scp`. Có thể đặt cron chạy hằng ngày |

**Tắt máy Windows trong công ty không ảnh hưởng tới app.** App, nginx và tunnel đều chạy trên VPS và tự khởi động lại khi VPS khởi động: Docker và cloudflared đều được bật cùng hệ thống, các container có `restart: unless-stopped`.

---

## Cấu hình

### File cấu hình

Đường dẫn tính từ thư mục `system/`.

| File | Nội dung |
|---|---|
| `config/company.toml` | Tên, địa chỉ, SĐT, email, website Light Human, câu footer, ghi chú người tham chiếu. **Nguồn duy nhất**: header PDF, footer và bộ lọc thông tin nhạy cảm cùng đọc từ đây |
| `config/extraction_rules.toml` | Bảng từ khoá của bộ đọc theo luật (viết không dấu): tiêu đề mục, nhãn thông tin nhạy cảm cần bỏ, nhãn dòng phụ, từ nhận ra công ty/chức danh/văn bằng. Muốn nhận thêm một cách viết thì thêm vào đây |
| `config/pdf_labels.toml` | Nhãn cố định của PDF bằng tiếng Việt và tiếng Anh |
| `prompts/schema.json` | Cấu trúc JSON hồ sơ (phải khớp `services/ai/models.py`) |
| `infra/tokens.py` | Màu, chữ, khoảng cách, lề trang PDF, dùng chung cho web, mẫu PDF và footer. Sinh `web/src/tokens.css` bằng `python -m infra.tokens --write`. Xem [`docs/design-system.md`](docs/design-system.md) |

Trong Docker, `system/config` và `system/assets` được mount chỉ-đọc vào container: sửa file rồi `docker compose restart` là áp dụng, không cần build lại.

### Biến môi trường

Không đặt thì dùng mặc định. Dự án **không đọc** file `.env`; với Docker, đặt trong `docker-compose.yml` hoặc `docker-compose.override.yml`.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `HOST` | `127.0.0.1` | Địa chỉ bind của backend (trong Docker là `0.0.0.0`, chỉ trong mạng Docker) |
| `PORT` | `8000` | Cổng HTTP |
| `CV_EXTRACTOR` | `rules` | `rules` (đọc PDF theo luật) hoặc `manual` (luôn khung trống nhập tay) |
| `EXTRACT_MAX_CONCURRENT` | `2` | Số lượt đọc CV chạy cùng lúc; người tới sau xếp hàng |
| `EXTRACT_QUEUE_TIMEOUT` | `300` | Giây chờ tối đa khi xếp hàng đọc CV |
| `MAX_UPLOAD_MB` | `20` | Dung lượng tối đa file tải lên; **phải khớp** `client_max_body_size` trong `nginx/conf.d/fillcv.conf` |
| `MAX_CV_PAGES` | `20` | Số trang tối đa được đọc tự động và xem trước |
| `OUTPUT_RETENTION_DAYS` | `30` | Số ngày giữ PDF + JSON đã xuất (`0` = không tự xoá) |
| `OUTPUT_DIR` | `data/output` | Thư mục lưu PDF + JSON |
| `LOG_DIR` | `data/logs` | Thư mục log |
| `LOGO_PATH` | `assets/logo.png` | Logo trong PDF |
| `LOGO_HEADER_PATH` | `Logo.png` | Logo header (không có thì dùng logo PDF) |
| `COMPANY_CONFIG` | `config/company.toml` | File thông tin công ty |
| `RENDER_TIMEOUT` | `120` | Giây tối đa cho một lần Chromium dựng PDF |
| `RENDER_MAX_CONCURRENT` | `2` | Số lượt dựng PDF cùng lúc (mỗi lượt khoảng 300–400 MB RAM) |
| `RENDER_QUEUE_TIMEOUT` | `300` | Giây tối đa chờ tới lượt dựng PDF |
| `CV_TRANSLATOR` | `nmt` | `none` = tắt dịch máy offline (giao diện ẩn nút dịch). Dịch máy chỉ dùng được khi đã cài mô hình |
| `TRANSLATE_MODEL_DIR` | `data/models/opus-mt-vi-en` | Thư mục mô hình dịch (`model.bin`, `source.spm`, `target.spm`) |
| `TRANSLATE_MAX_CONCURRENT` | `1` | Số lượt dịch cùng lúc |
| `TRANSLATE_QUEUE_TIMEOUT` | `120` | Giây tối đa chờ tới lượt dịch |
| `TRANSLATE_THREADS` | `2` | Số luồng CPU của bộ dịch |
| `TRANSLATE_PRELOAD` | `1` | Nạp sẵn mô hình dịch khi khởi động (`0` = chỉ nạp khi có người dịch lần đầu) |
| `CHROMIUM_NO_SANDBOX` | *(trống)* | Chỉ đặt `1` khi chạy trong Docker hoặc bằng root (Dockerfile đã đặt sẵn) |

---

## Cấu trúc mã nguồn

```
README.md  CLAUDE.md  .gitignore  .dockerignore
Dockerfile              Dockerfile duy nhất (multi-stage: build web/ bằng Node, rồi Python + Chromium)
docker-compose.yml      app + nginx
nginx/conf.d/           cấu hình nginx (tắt đệm cho SSE, giới hạn upload, IP thật từ Cloudflare)
.github/                CI/CD + dependabot
docs/                   SKILL.md (quy chuẩn PDF), api.md (hợp đồng API), design-system.md, ...
data/                   PDF đã xuất + log khi chạy (không đưa lên git)
web/                    frontend React + Vite + Tailwind CSS v4 (JavaScript/JSX)
system/                 backend Starlette API, core, services, infra, tests
```

- **Frontend (`web/`)**: `src/api/client.js` là module **duy nhất** gọi API. `src/components/` chứa Header, ExtractionPanel, PdfPanel, StatusBar, StageScreen, OriginalCvPreview, Field; `src/components/profile/` chứa form chỉnh sửa hồ sơ. `src/tokens.css` được sinh tự động từ `system/infra/tokens.py`.
- **Backend (`system/`)**: `api/` là lớp API mỏng (`server.py`, `routes.py`, `state.py`, có stream tiến độ bằng SSE); `core/` chứa luồng nghiệp vụ (`pipeline.py`, `pdf_status.py`); `services/` gồm trích xuất (`extraction/rules/`), dựng PDF bằng Playwright (`pdf/`), quét thông tin nhạy cảm (`privacy/`); `infra/` chứa cấu hình, token, log, lưu trữ; `tests/` là test backend.

---

## Chạy test

### Backend

```powershell
cd system
python -m pytest -q                               # toàn bộ (có dựng PDF bằng Chromium thật)
python -m pytest -q -m "not slow"                 # bỏ các test chạy Chromium, nhanh hơn
python -m pytest -q tests/test_api_contract.py    # hợp đồng API theo docs/api.md
python -m coverage run -m pytest -q; python -m coverage report   # độ phủ từng module
ruff check --isolated --select E4,E7,E9,F api tests
```

### Frontend

```powershell
cd web
npm run lint     # ESLint
npm run test     # Vitest: component, client API, kiểm tra CSS/token
npm run build    # build ra web/dist
```

- Test chỉ dùng hồ sơ giả (`system/tests/fixtures/fake_candidate.json`). **Không bao giờ** dùng CV thật trong test, fixture hay commit.
- Đo bộ đọc trên một CV mà chỉ in **con số**, không in nội dung (để file CV **ngoài** thư mục dự án):
  ```powershell
  cd system
  python -m services.extraction.rules.measure "D:\cv\mot_cv.pdf"
  python -m services.extraction.rules.measure "cv_gia.pdf" --expect "tests\fixtures\fake_candidate.json"
  ```

---

## Bảo mật

| Biện pháp | Chi tiết |
|---|---|
| **Đăng nhập trước khi vào app** | Cloudflare Access, mã OTP qua email, chỉ email trong danh sách được vào |
| **Không mở cổng web** | Tường lửa VPS chỉ mở SSH; web đi qua Cloudflare Tunnel (kết nối đi ra). nginx chỉ nghe `127.0.0.1`, app chỉ trong mạng Docker |
| **SSH bằng khoá** | Tắt đăng nhập bằng mật khẩu; fail2ban chặn IP dò mật khẩu |
| **HTTPS bắt buộc** | Always Use HTTPS, TLS tối thiểu 1.2 |
| **Không gọi API bên ngoài** | CV được đọc hoàn toàn trên máy chủ |
| **Chặn xuất khi còn thông tin nhạy cảm** | Quét cả dữ liệu lẫn file PDF trước khi cho tải |
| **Log không chứa thông tin ứng viên** | Không ghi nội dung CV, họ tên; tên file gốc ghi dạng mã băm `pdf#1a2b3c4d` |
| **Giới hạn tài nguyên** | Upload tối đa 20 MB; tối đa 2 lượt dựng PDF song song; giới hạn tần suất đọc CV theo IP thật của từng người |
| **Tự xoá PDF cũ** | Mặc định sau 30 ngày |
| **Bí mật không nằm trong repo** | Token tunnel chỉ ở `/etc/cloudflared/tunnel-token` (quyền 600) trên VPS. Repo public nên **không** commit IP, token, khoá SSH hay danh sách email |

Chính sách xử lý dữ liệu cá nhân: [`docs/data-privacy-policy.md`](docs/data-privacy-policy.md).

---

## Log

- `data/logs/app.log` (app) và `data/logs/render_worker.log` (tiến trình dựng PDF), xoay vòng 1 MB × 5 file.
- Mỗi lần gửi CV có một mã `run_id` 8 ký tự, ví dụ `[a1b2c3d4]`. Tìm mã này trong cả hai file để xem trọn một lượt xử lý.
- Log nginx: `docker logs fillcv-nginx`. Log tunnel: `journalctl -u cloudflared`.

---

## Sự cố thường gặp

| Lỗi | Cách xử lý |
|---|---|
| Container app khởi động lại liên tục, log báo `PermissionError: ... data/logs/app.log` | Thư mục `data/` trên Linux thuộc root. Chạy `chown -R 1000:1000 data/output data/logs`, rồi `docker compose up -d` |
| Trang báo lỗi **1033** | Tunnel không có kết nối: `systemctl status cloudflared`, xem `journalctl -u cloudflared` |
| Trang báo **502** | nginx hoặc app chưa chạy: `docker compose ps`, `curl http://127.0.0.1/health` |
| Lúc dựng được PDF, lúc báo "không tìm thấy" | Cùng một tunnel đang chạy ở **hai máy**. Tắt `cloudflared` ở máy không dùng |
| Không nhận được mã OTP | Kiểm tra thư mục Spam; kiểm tra email có trong policy Access không |
| Đăng nhập xong vẫn bị chặn | Email không nằm trong policy `FillCV - Nhân viên được phép` |
| Nhiều người cùng bị lỗi 429 khi đọc CV dù mỗi người chỉ gửi vài lần | nginx không lấy được IP thật: kiểm tra các dòng `real_ip_header CF-Connecting-IP` trong `nginx/conf.d/fillcv.conf` |
| Hồ sơ ra khung trống "nhập tay" | CV là DOCX, ảnh, PDF scan hoặc PDF lỗi font. Xuất lại thành PDF có chữ chọn được, hoặc nhập tay |
| Bộ đọc bỏ sót hoặc nhận sai tiêu đề mục | Thêm cách viết đó (không dấu) vào `config/extraction_rules.toml` |
| `Trình dựng PDF (Chromium) gặp lỗi` | Chạy trên máy: `python -m playwright install chromium`. Trong Docker: build lại image. Xem `data/logs/` |
| App không khởi động sau khi sửa `config/company.toml` | File sai cú pháp TOML: kiểm tra dấu ngoặc kép và dấu `=` |
| `DLL load failed ... Application Control policy` (Windows) | Smart App Control chặn thư viện; app không dùng tới tính năng đó |

---

## Tài liệu liên quan

| Tài liệu | Mô tả |
|---|---|
| [`docs/SKILL.md`](docs/SKILL.md) | Quy chuẩn hồ sơ PDF: bố cục, thông tin bỏ/giữ, đặt tên file, checklist |
| [`docs/api.md`](docs/api.md) | Hợp đồng API giữa backend và frontend |
| [`docs/design-system.md`](docs/design-system.md) | Hệ thống giao diện: design token, Tailwind, quy tắc accessibility |
| [`docs/deployment-cloudflare-tunnel.md`](docs/deployment-cloudflare-tunnel.md) | Phương án dự phòng: chạy trên máy Windows nội bộ + Cloudflare Tunnel |
| [`docs/data-privacy-policy.md`](docs/data-privacy-policy.md) | Chính sách xử lý dữ liệu cá nhân ứng viên (bản nháp, chờ pháp chế) |
| [`docs/proposals.md`](docs/proposals.md) | Đề xuất dài hạn: đăng nhập/phân quyền, CI, cải tiến khác |

---

## Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Backend API | [Starlette](https://www.starlette.io/) + [Uvicorn](https://www.uvicorn.org/) |
| Frontend | [React 19](https://react.dev/) + [Vite](https://vitejs.dev/) + [Tailwind CSS v4](https://tailwindcss.com/), font Be Vietnam Pro tự host |
| Kiểm thử frontend | [Vitest](https://vitest.dev/) + [React Testing Library](https://testing-library.com/) |
| Đọc PDF | [PyMuPDF](https://pymupdf.readthedocs.io/) |
| Cấu trúc dữ liệu | [Pydantic](https://docs.pydantic.dev/) |
| Template PDF | [Jinja2](https://jinja.palletsprojects.com/) |
| Dựng PDF | [Playwright](https://playwright.dev/python/) (Chromium) |
| Xử lý ảnh | [Pillow](https://pillow.readthedocs.io/) + [OpenCV](https://opencv.org/) |
| Triển khai | Docker Compose + nginx trên VPS Ubuntu, Cloudflare Tunnel + Access |
