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

## 2. Hướng dẫn chạy bộ giả lập Mock Pi trên máy tính

Mã nguồn dịch vụ chạy trực tiếp trên phần cứng Raspberry Pi được quản lý độc lập tại repository phần cứng riêng. Repository này cung cấp sẵn bộ giả lập Mock Pi tại thư mục `tools/mock_pi` giúp lập trình viên phát triển và kiểm thử toàn bộ tính năng của ứng dụng giám sát mà không cần thiết bị Raspberry Pi vật lý.

### 1. Cài đặt thư viện Python cho Mock Pi
Từ thư mục gốc của dự án, cài đặt các thư viện cần thiết:
```powershell
pip install -r tools/mock_pi/requirements.txt
```

### 2. Khởi chạy Mock Pi Server
- **Sử dụng webcam máy tính làm camera góc nhìn thứ nhất (POV)**:
  ```powershell
  python tools/mock_pi/mock_pi_server.py
  ```
- **Sử dụng radar HUD đồ họa mô phỏng (không cần webcam)**:
  ```powershell
  python tools/mock_pi/mock_pi_server.py --synthetic
  ```
- **Chạy chế độ ngầm (headless)**:
  ```powershell
  python tools/mock_pi/mock_pi_server.py --headless --synthetic
  ```
- **Tùy chỉnh mã thiết bị hoặc MQTT broker**:
  ```powershell
  python tools/mock_pi/mock_pi_server.py --device-id pi4_01 --broker broker.emqx.io --port 1883
  ```

### 3. Điều khiển số liệu mô phỏng qua Console
Khi chạy ở chế độ tương tác (không có `--headless`), bạn có thể nhập trực tiếp các lệnh sau vào terminal:
- `d <cm>`: Đổi khoảng cách cảm biến siêu âm (ví dụ: `d 25` để kiểm thử cảnh báo nguy hiểm, `d 150` để kiểm thử vùng an toàn, `d -1` để giả lập mất cảm biến).
- `b <pct>`: Đổi phần trăm pin (ví dụ: `b 15` để kiểm thử cảnh báo pin yếu).
- `t <c>`: Đổi nhiệt độ CPU (ví dụ: `t 75` để kiểm thử cảnh báo quá nhiệt).
- `a`: Bắn ngay lập tức một bản tin cảnh báo khẩn cấp tới ứng dụng.
- `reboot`: Giả lập chu kỳ khởi động lại (chuyển offline 3 giây rồi online trở lại).
- `q`: Dừng mock server an toàn.

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
