# PBL6 Assistive Monitor

Ứng dụng giám sát và hỗ trợ người khiếm thị thời gian thực đa nền tảng (Flutter Android & Web), kết nối đồng bộ với thiết bị đeo Raspberry Pi 4 hoặc bộ giả lập máy tính Mock Pi.

---

## 1. Kiến trúc kết nối hệ thống

Hệ thống hoạt động theo mô hình Edge - Cloud - Mobile phân tán. Điện thoại và thiết bị đeo Raspberry Pi không cần kết nối cùng mạng Wi-Fi cục bộ hay cắm dây trực tiếp mà giao tiếp thông qua hạ tầng đám mây:

- **Kênh điều phối MQTT**: Quản lý trạng thái thiết bị, đồng bộ telemetry chu kỳ 3 giây, đẩy cảnh báo khẩn cấp và truyền nhận tín hiệu báo hiệu (Signaling) cho WebRTC.
- **Kênh truyền thông WebRTC P2P**: Bắt tay qua STUN server của Google để truyền luồng video góc nhìn thứ nhất (POV) từ camera về ứng dụng và truyền giọng nói Push-to-Talk (PTT) từ micro ứng dụng ra loa của thiết bị.

### Bảng thông số kết nối mặc định

| Tham số | Giá trị mặc định | Mô tả |
|---|---|---|
| MQTT Broker | `broker.emqx.io` | Máy chủ điều phối trung tâm |
| Cổng TCP (Native / Pi / Mobile) | `1883` | Kết nối socket chuẩn cho Raspberry Pi và Android |
| Cổng WebSocket (Web App) | `8083` | Kết nối WebSocket bảo đảm tương thích trình duyệt |
| Mã thiết bị (Device ID) | `pi4_01` | Tiền tố topic nhận diện thiết bị `pbl6/{device_id}/...` |
| STUN Server | `stun:stun.l.google.com:19302` | Máy chủ duyệt NAT thiết lập P2P WebRTC |

---

## 2. Hướng dẫn thiết lập và kết nối Raspberry Pi

### Phương án A: Giả lập phần cứng trên máy tính phát triển (Mock Simulator)

Phù hợp cho lập trình viên frontend muốn kiểm thử ứng dụng Flutter mà không cần bo mạch Raspberry Pi vật lý.

1. **Cài đặt thư viện Python**:
   ```powershell
   cd tools/mock_pi
   pip install -r requirements.txt
   ```

2. **Khởi chạy Mock Pi Server**:
   - Sử dụng webcam máy tính:
     ```powershell
     python mock_pi_server.py
     ```
   - Sử dụng radar HUD giả lập không cần webcam:
     ```powershell
     python mock_pi_server.py --synthetic
     ```
   - Tùy chỉnh mã thiết bị hoặc broker riêng:
     ```powershell
     python mock_pi_server.py --device-id pi4_01 --broker broker.emqx.io --port 1883
     ```

Trong quá trình chạy, bạn có thể gõ các phím lệnh vào terminal (`d <cm>`, `b <pct>`, `t <c>`, `a`, `reboot`, `q`) để kiểm thử các trạng thái ứng dụng.

---

### Phương án B: Cài đặt và vận hành trên Raspberry Pi 4 thật (Hardware Service)

Dành riêng cho thiết bị Raspberry Pi 4 thật có gắn camera USB và cảm biến vật lý. Toàn bộ mã nguồn service phần cứng nằm độc lập tại thư mục `tools/pi_edge/`.

#### 1. Đấu nối phần cứng
- **Camera**: Cắm USB Webcam vào cổng USB 3.0 (hoặc USB 2.0) của Pi.
- **Cảm biến khoảng cách siêu âm HC-SR04**:
  - `VCC`: Chân 5V (Pin 2 hoặc Pin 4).
  - `GND`: Chân GND (Pin 6).
  - `TRIG`: Chân GPIO 23 (Pin 16 vật lý).
  - `ECHO`: Chân GPIO 24 (Pin 18 vật lý) qua cầu phân áp trở (1kΩ và 2kΩ để hạ mức tín hiệu từ 5V xuống 3.3V bảo vệ chân GPIO của Pi).
- **Âm thanh**: Cắm loa mini hoặc tai nghe qua cổng 3.5mm hoặc cổng USB để nghe giọng nói đàm thoại 2 chiều.

#### 2. Sao chép và cài đặt trên Raspberry Pi
Không cần sao chép toàn bộ dự án Flutter lên Pi. Bạn chỉ cần đưa thư mục `tools/pi_edge/` vào thư mục làm việc `/home/admin/Documents/pbl6/tools` trên Raspberry Pi:

```bash
# Cách 1: Sao chép từ máy tính sang Pi qua SSH alias
scp -r tools/pi_edge/* pbl6:/home/admin/Documents/pbl6/tools/

# Cách 2: Tải trực tiếp 2 file từ GitHub trên terminal của Pi
mkdir -p /home/admin/Documents/pbl6/tools && cd /home/admin/Documents/pbl6/tools
curl -O https://raw.githubusercontent.com/nck345/PBL6-app-web/main/tools/pi_edge/requirements.txt
curl -O https://raw.githubusercontent.com/nck345/PBL6-app-web/main/tools/pi_edge/pi_server.py
```

#### 3. Khởi chạy service trên Raspberry Pi
Trên Raspberry Pi, chuyển vào thư mục `/home/admin/Documents/pbl6/tools`:
```bash
cd /home/admin/Documents/pbl6/tools

# Cài đặt thư viện nếu cần
uv pip install -r requirements.txt

# Khởi chạy service phần cứng
uv run pi_server.py

# Hoặc chạy trực tiếp qua môi trường ảo Python
/home/admin/Documents/pbl6/.venv/bin/python3 pi_server.py
```

Service phần cứng sẽ tự động:
- Đọc webcam USB thật qua chuẩn V4L2 (`/dev/video1`, `/dev/video0`). Nếu webcam chưa cắm hoặc đang bận do tiến trình AI chiếm dụng, service sẽ phát khung hình thông báo trạng thái mà không sinh hình ảnh radar giả.
- Đọc cảm biến siêu âm HC-SR04 thật. Nếu chưa cắm cảm biến, telemetry trả về `-1.0` để app hiển thị "Chưa kết nối cảm biến" (`--`), không báo nguy hiểm giả.
- Đo nhiệt độ CPU và tải CPU thực tế từ nhân Linux (`/sys/class/thermal/thermal_zone0/temp` và `/proc/stat`).
- Phát âm thanh micro từ điện thoại ra loa ngoài của Pi.

#### 4. Duy trì service chạy ngầm khi ngắt kết nối SSH
Khi kết nối remote SSH qua Cloudflare Tunnel, bạn nên cho service chạy ngầm để không bị tắt khi đóng cửa sổ terminal:

```bash
# Chạy ngầm bằng nohup tại thư mục /home/admin/Documents/pbl6/tools
cd /home/admin/Documents/pbl6/tools
nohup uv run pi_server.py > pi_service.log 2>&1 &

# Hoặc chạy trong phiên làm việc tmux
tmux new -s pbl6 "cd /home/admin/Documents/pbl6/tools && uv run pi_server.py"
# Bấm Ctrl + B rồi bấm D để thoát ra ngoài mà tiến trình vẫn chạy
```

Khi chạy thành công, Pi sẽ tự động:
- Tự động nhận diện và mở luồng hình ảnh từ webcam USB thật.
- Gửi bản tin trực tuyến lên topic `pbl6/pi4_01/status` với cờ `retain=True`.
- Đẩy số liệu pin, nhiệt độ, khoảng cách cảm biến định kỳ lên `pbl6/pi4_01/telemetry`.
- Tự động bắt tay WebRTC khi người thân mở màn hình Camera trên điện thoại hoặc trình duyệt web.

---

## 3. Hướng dẫn khởi chạy ứng dụng giám sát Flutter

Ứng dụng sử dụng một mã nguồn duy nhất và tự động thích ứng theo môi trường thực thi (Mobile hoặc Web).

### Cài đặt thư viện
```powershell
flutter pub get
```

### Chạy chế độ phát triển
- **Chạy trên Web (Google Chrome)**:
  ```powershell
  flutter run -d chrome
  ```
- **Chạy trên Web (Microsoft Edge)**:
  ```powershell
  flutter run -d edge
  ```
- **Chạy trên điện thoại hoặc máy ảo Android**:
  ```powershell
  flutter run -d android
  ```

### Đóng gói sản phẩm phát hành
- **Xuất bản cài đặt Android (.apk)**:
  ```powershell
  flutter build apk --release
  ```
  File cài đặt nằm tại: `build/app/outputs/flutter-apk/app-release.apk`
- **Xuất bản web tĩnh để đưa lên hosting**:
  ```powershell
  flutter build web --release
  ```
  Toàn bộ gói web sẵn sàng đưa lên hosting nằm tại thư mục: `build/web/`

---

## 4. Kiểm thử chất lượng mã nguồn

- **Kiểm tra phân tích tĩnh**:
  ```powershell
  flutter analyze
  ```
- **Chạy toàn bộ 130 bài kiểm thử đơn vị và giao diện Flutter**:
  ```powershell
  flutter test
  ```
- **Chạy kiểm thử tích hợp E2E tự động**:
  ```powershell
  pytest test/e2e
  ```

---

## 5. Cấu trúc thư mục mã nguồn

```
PBL6-app-web/
├── lib/
│   ├── main.dart                          # Khởi tạo DI, BLoCs và giao diện
│   ├── core/
│   │   ├── constants/app_constants.dart   # Cấu hình Broker, Topics và Port
│   │   ├── services/                      # Dịch vụ thông báo nổi và hệ thống
│   │   └── theme/                         # Cấu hình màu sắc, theme sáng tối
│   ├── data/
│   │   ├── datasources/                   # Kết nối MQTT TCP/WebSocket và WebRTC
│   │   ├── models/                        # Parser JSON Telemetry, Alert, Config
│   │   └── repositories/                  # Triển khai Repository từ Domain
│   ├── domain/                            # Thực thể nghiệp vụ và Repository contracts
│   └── presentation/
│       ├── bloc/                          # Quản lý trạng thái BLoC
│       ├── screens/                       # Dashboard, Camera POV, Cảnh báo, Cài đặt
│       └── widgets/                       # Nút Push-to-Talk, biểu đồ, thẻ chỉ số
├── tools/
│   └── mock_pi/                           # Bộ giả lập Raspberry Pi 4 bằng Python
├── docs/
│   └── ARCHITECTURE.md                    # Tài liệu kiến trúc và đặc tả chi tiết
└── test/                                  # 130 bài Unit, Widget và E2E tests
```
