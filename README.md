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

### Phương án A: Chạy bộ giả lập Mock Pi trên máy tính

Dự án tích hợp sẵn bộ giả lập phần cứng hoàn chỉnh tại [tools/mock_pi/mock_pi_server.py](file:///c:/Users/khiem_ssxdm6v/Documents/GitHub/PBL6-app-web/tools/mock_pi/mock_pi_server.py) phục vụ phát triển độc lập mà không cần mạch phần cứng thật.

1. **Cài đặt thư viện Python**:
   ```powershell
   pip install -r tools/mock_pi/requirements.txt
   ```

2. **Khởi chạy Mock Pi Server**:
   - Sử dụng webcam máy tính:
     ```powershell
     python tools/mock_pi/mock_pi_server.py
     ```
   - Sử dụng radar HUD giả lập không cần webcam:
     ```powershell
     python tools/mock_pi/mock_pi_server.py --synthetic
     ```
   - Tùy chỉnh mã thiết bị hoặc broker riêng:
     ```powershell
     python tools/mock_pi/mock_pi_server.py --device-id pi4_01 --broker broker.emqx.io --port 1883
     ```

Khi khởi chạy, server sẽ phát dữ liệu cảm biến định kỳ và lắng nghe lệnh điều khiển hoặc yêu cầu xem video từ ứng dụng.

---

### Phương án B: Cài đặt và kết nối trực tiếp với Raspberry Pi 4 thật

#### 1. Đấu nối phần cứng
- **Camera**: Kết nối Pi Camera qua cáp dẹt CSI hoặc cắm Webcam chuẩn USB vào cổng USB 3.0.
- **Cảm biến khoảng cách siêu âm HC-SR04**:
  - `VCC`: Chân 5V (Pin 2 hoặc Pin 4).
  - `GND`: Chân GND (Pin 6).
  - `TRIG`: Chân GPIO 23 (Pin 16).
  - `ECHO`: Chân GPIO 24 (Pin 18) qua cầu phân áp trở (1kΩ và 2kΩ để hạ mức tín hiệu từ 5V xuống 3.3V an toàn cho chân Pi).
- **Âm thanh**: Cắm tai nghe hoặc loa mini qua cổng 3.5mm hoặc cổng USB.

#### 2. Cài đặt môi trường trên Raspberry Pi OS
Mở terminal trên Raspberry Pi và chạy các lệnh:
```bash
sudo apt update
sudo apt install -y python3-pip python3-opencv libportaudio2 git
pip3 install paho-mqtt aiortc sounddevice numpy av RPi.GPIO
```

#### 3. Chạy service kết nối trên Raspberry Pi
Không cần sao chép toàn bộ mã nguồn Flutter. Bạn chỉ cần đưa thư mục `tools/` vào thư mục làm việc `/home/admin/Documents/pbl6/tools` trên Raspberry Pi (bằng lệnh SCP hoặc tải trực tiếp):

```bash
# Cách 1: Sao chép từ máy tính sang Pi qua SSH alias
scp -r tools/mock_pi/* pbl6:/home/admin/Documents/pbl6/tools/

# Cách 2: Tải trực tiếp 2 file từ GitHub trên terminal của Pi
mkdir -p /home/admin/Documents/pbl6/tools && cd /home/admin/Documents/pbl6/tools
curl -O https://raw.githubusercontent.com/nck345/PBL6-app-web/main/tools/mock_pi/requirements.txt
curl -O https://raw.githubusercontent.com/nck345/PBL6-app-web/main/tools/mock_pi/mock_pi_server.py
```

Trên Raspberry Pi, chuyển vào thư mục `/home/admin/Documents/pbl6/tools` và khởi chạy service:
```bash
cd /home/admin/Documents/pbl6/tools

# Chạy qua uv
uv run mock_pi_server.py

# Hoặc chạy trực tiếp qua môi trường ảo Python
/home/admin/Documents/pbl6/.venv/bin/python3 mock_pi_server.py
```

Mã nguồn đã tích hợp cơ chế tự động dò tìm webcam USB qua chuẩn V4L2 (ưu tiên `/dev/video1`, `/dev/video0`) với định dạng MJPG 640x480 và bộ đệm 1 khung hình chống trễ. Đồng thời tích hợp driver cảm biến khoảng cách HC-SR04 trên chân GPIO 23 (Trigger) và GPIO 24 (Echo).

Khi chưa cắm cảm biến khoảng cách, hệ thống tự động gán giá trị `-1.0` và hiển thị trạng thái "Chưa kết nối cảm biến" trên màn hình Dashboard và Camera POV mà không phát sinh cảnh báo giả. Nếu muốn bật chế độ giả lập số liệu ngẫu nhiên để thử nghiệm khi không có phần cứng:

```bash
# Bật giả lập số liệu khoảng cách khi chưa cắm cảm biến
uv run mock_pi_server.py --mock-sensor

# Chỉ định cổng camera USB cụ thể
python3 mock_pi_server.py --camera-index 1

# Ép buộc dùng radar HUD đồ họa khi không cắm webcam
python3 mock_pi_server.py --synthetic
```

#### 4. Duy trì service chạy ngầm khi ngắt kết nối SSH
Khi kết nối remote SSH qua Cloudflare Tunnel hoặc mạng ngoài, bạn nên cho service chạy ngầm để không bị tắt khi đóng cửa sổ terminal:

```bash
# Chạy ngầm bằng nohup tại thư mục /home/admin/Documents/pbl6/tools
cd /home/admin/Documents/pbl6/tools
nohup uv run mock_pi_server.py > pbl6.log 2>&1 &

# Hoặc chạy trong phiên làm việc tmux
tmux new -s pbl6 "cd /home/admin/Documents/pbl6/tools && uv run mock_pi_server.py"
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
