# Raspberry Pi 4 Mock Server (PBL6 Assistive Monitor)

Bộ giả lập phần cứng Raspberry Pi 4 phục vụ phát triển và kiểm thử ứng dụng Flutter giám sát hỗ trợ người khiếm thị. Công cụ cung cấp luồng telemetry định kỳ, phát cảnh báo chướng ngại vật nguy hiểm, truyền luồng video WebRTC thời gian thực (webcam hoặc radar HUD giả lập) và nhận luồng âm thanh micro Push-to-Talk (PTT) từ điện thoại phát ra loa máy tính.

---

## 1. Yêu cầu hệ thống và cài đặt

### Yêu cầu tiên quyết
- Python 3.10 trở lên (đã kiểm thử tương thích hoàn toàn trên Python 3.14).
- Kết nối Internet tới MQTT broker (mặc định EMQX public broker `broker.emqx.io` port 1883) và Google STUN server (UDP port 19302).
- Webcam và loa máy tính (tùy chọn, mock server tự động chuyển sang chế độ giả lập nếu thiếu phần cứng).

### Cài đặt thư viện
Chạy lệnh cài đặt từ thư mục gốc của dự án:

```powershell
pip install -r tools/mock_pi/requirements.txt
```

Các thư viện chính:
- `paho-mqtt>=1.6.1`: Giao tiếp MQTT client, hỗ trợ cả API v1 và v2.
- `aiortc>=1.6.0`: Ngăn xếp giao thức WebRTC P2P và xử lý luồng media.
- `opencv-python>=4.8.0`: Thu nhận khung hình webcam và vẽ canvas radar HUD giả lập.
- `numpy>=1.24.0`: Xử lý mảng ma trận pixel và tín hiệu âm thanh PCM.
- `sounddevice>=0.4.6`: Phát âm thanh đàm thoại PTT ra loa với cơ chế fallback tự động.
- `av>=10.0.0`: Mã hóa giải mã khung hình video và audio.

---

## 2. Hướng dẫn khởi chạy

### Chạy ở chế độ mặc định (tự động nhận diện webcam)
Mã nguồn tự động dò tìm camera USB qua chuẩn V4L2 (ưu tiên index 1 `/dev/video1`, index 0 `/dev/video0`) với định dạng MJPG 640x480 và bộ đệm 1 khung hình. Chỉ khi không tìm thấy camera vật lý mới tự động chuyển sang radar HUD giả lập.
```powershell
python tools/mock_pi/mock_pi_server.py
```
Hoặc trên Raspberry Pi dùng `uv`:
```bash
uv run mock_pi_server.py
```

### Chạy chế độ radar HUD giả lập (không dùng webcam)
```powershell
python tools/mock_pi/mock_pi_server.py --synthetic
```

### Chạy chế độ headless (chạy ngầm, không nhận phím từ terminal)
Phù hợp cho môi trường CI/CD hoặc chạy nền:
```powershell
python tools/mock_pi/mock_pi_server.py --headless --synthetic
```

### Tùy chỉnh Device ID và MQTT Broker
```powershell
python tools/mock_pi/mock_pi_server.py --device-id pi4_test_01 --broker broker.emqx.io --port 1883 --interval 3.0
```

---

## 3. Danh sách tham số dòng lệnh (CLI Parameters)

| Tham số | Giá trị mặc định | Giải thích |
|---|---|---|
| `--device-id` | `pi4_01` | Mã định danh thiết bị, quyết định tiền tố topic MQTT `pbl6/{device_id}/...`. |
| `--broker` | `broker.emqx.io` | Địa chỉ máy chủ MQTT broker. |
| `--port` | `1883` | Cổng kết nối MQTT broker. |
| `--camera-index` | `0` | Chỉ số webcam vật lý của hệ thống. |
| `--synthetic` | `False` | Ép buộc sử dụng radar HUD đồ họa thay vì mở webcam vật lý. |
| `--headless` | `False` | Tắt vòng lặp đọc lệnh từ console terminal. |
| `--interval` | `3.0` | Chu kỳ phát bản tin telemetry tính theo giây. |
| `--mock-sensor` | `False` | Bật chế độ giả lập số liệu ngẫu nhiên khi chưa cắm phần cứng cảm biến. |
| `--trig-pin` | `23` | Chân GPIO Trigger của cảm biến khoảng cách HC-SR04. |
| `--echo-pin` | `24` | Chân GPIO Echo của cảm biến khoảng cách HC-SR04. |

---

## 4. Bảng lệnh điều khiển tương tác qua Console

Khi chạy không kèm cờ `--headless`, người dùng có thể nhập trực tiếp các lệnh sau vào terminal:

| Lệnh | Mô tả |
|---|---|
| `a` hoặc `alert` | Kích hoạt ngay lập tức một bản tin cảnh báo nguy hiểm tới topic alert. |
| `d <cm>` | Cố định khoảng cách siêu âm mô phỏng, ví dụ `d 25` để kích hoạt vùng nguy hiểm hoặc `d 160` để an toàn. |
| `d auto` | Trả cảm biến về chế độ đọc tự động từ phần cứng GPIO HC-SR04. |
| `b <pct>` | Cố định phần trăm pin mô phỏng, ví dụ `b 15`. |
| `t <c>` | Cố định nhiệt độ CPU mô phỏng, ví dụ `t 62.5`. |
| `reboot` | Giả lập quá trình khởi động lại thiết bị: chuyển offline 3 giây rồi online trở lại. |
| `mute` | Tắt âm lượng loa của thiết bị về 0. |
| `unmute` | Khôi phục âm lượng loa về mức trước khi tắt. |
| `status` | In thông số cảm biến hiện tại ra màn hình console. |
| `h` hoặc `help` | Hiển thị bảng trợ giúp danh sách lệnh. |
| `q` hoặc `quit` | Dừng an toàn mock server, gửi thông điệp offline và ngắt kết nối. |

---

## 5. Đặc tả giao thức MQTT Topics và JSON Schemas

Toàn bộ topic sử dụng tiền tố `pbl6/{device_id}/` (mặc định `{device_id}` là `pi4_01`).

### 5.1. Trạng thái thiết bị và LWT (`status`)
- Topic: `pbl6/{device_id}/status`
- Hướng: Pi -> App, QoS 1, Retain: True
- Nội dung:
```json
{
  "status": "online",
  "timestamp": 1732312000
}
```
Khi mock server mất kết nối đột ngột, broker tự động phát bản tin Last Will and Testament với nội dung `"status": "offline"`.

### 5.2. Telemetry định kỳ (`telemetry`)
- Topic: `pbl6/{device_id}/telemetry`
- Hướng: Pi -> App, định kỳ 3.0 giây, QoS 0
- Nội dung:
```json
{
  "device_id": "pi4_01",
  "timestamp": 1732312000,
  "battery_percentage": 85,
  "temperature_celsius": 48.5,
  "cpu_usage": 32.0,
  "ultrasonic_distance_cm": 145.2,
  "camera_active": true,
  "speaker_volume": 80
}
```

### 5.3. Cảnh báo nguy hiểm (`alert`)
- Topic: `pbl6/{device_id}/alert`
- Hướng: Pi -> App, QoS 1
- Kích hoạt: Tự động khi `ultrasonic_distance_cm < distance_threshold_cm` (có debounce theo `alert_frequency_ms`) hoặc kích hoạt thủ công.
- Nội dung:
```json
{
  "event_id": "evt_9981",
  "timestamp": 1732312015,
  "alert_type": "OBSTACLE_DANGER",
  "level": "CRITICAL",
  "distance_cm": 25.0,
  "detected_objects": ["stairs_down", "obstacle"],
  "message": "Phát hiện chướng ngại vật ở cự ly gần: 25.0 cm!"
}
```

### 5.4. Cấu hình thông số (`config`)
- Topic: `pbl6/{device_id}/config`
- Hướng: App -> Pi, QoS 1
- Nội dung:
```json
{
  "distance_threshold_cm": 80.0,
  "speaker_volume": 90,
  "alert_frequency_ms": 1500,
  "detection_fps": 15
}
```

### 5.5. Lệnh điều khiển thiết bị (`command`)
- Topic: `pbl6/{device_id}/command`
- Hướng: App -> Pi, QoS 1
- Nội dung:
```json
{
  "command": "REBOOT"
}
```
Các lệnh hỗ trợ: `REBOOT`, `RESTART_SERVICE`, `MUTE`, `UNMUTE`, `TRIGGER_BUZZER`.

---

## 6. Giao thức WebRTC Signaling qua MQTT

### 6.1. Luồng thiết lập kết nối (Handshake)
1. Ứng dụng Flutter gửi SDP Offer tới topic: `pbl6/{device_id}/webrtc/offer`.
2. Mock server nhận offer, tạo `RTCPeerConnection` với Google STUN `stun:stun.l.google.com:19302`, đính kèm track video và lắng nghe track audio.
3. Mock server sinh SDP Answer và gửi về topic: `pbl6/{device_id}/webrtc/answer`.
4. Hai bên trao đổi ICE candidate qua topic: `pbl6/{device_id}/webrtc/ice_candidate`.

### 6.2. Cấu trúc thông điệp Signaling
- **Offer**:
```json
{
  "sdp": "v=0\r\no=...",
  "type": "offer",
  "caller": "app_client"
}
```

- **Answer**:
```json
{
  "sdp": "v=0\r\no=...",
  "type": "answer",
  "callee": "pi4_01"
}
```

- **ICE Candidate**:
```json
{
  "candidate": "candidate:1 1 UDP ...",
  "sdpMid": "0",
  "sdpMLineIndex": 0,
  "sender": "app"
}
```

---

## 7. Cơ chế hoạt động của Video và Audio

### Video Stream
- Nếu có webcam và không bật `--synthetic`, server mở `cv2.VideoCapture(camera_index)`, chụp khung hình 640x480 và chèn thông số telemetry lên góc dưới khung hình. Khi có cảnh báo khoảng cách nguy hiểm, viền đỏ cảnh báo nhấp nháy trên khung hình.
- Nếu không có webcam hoặc bật `--synthetic`, server sinh radar HUD 640x480: hiển thị các vòng tròn cự ly 50cm, 100cm, 150cm, 200cm, vệt quét radar quay liên tục 360 độ và điểm chấm biểu diễn chướng ngại vật nhấp nháy đỏ khi trong cự ly nguy hiểm.

### Audio Sink (Push-to-Talk)
- Nhận luồng âm thanh Opus giải mã thành dữ liệu PCM 48000 Hz.
- Dữ liệu được đưa vào luồng xuất của thư viện `sounddevice` để phát trực tiếp ra loa máy tính.
- Nếu môi trường chạy không có loa hoặc thiếu driver PortAudio, server tự động chuyển sang bộ ghi log RMS mô phỏng, ghi nhận lưu lượng âm thanh nhận được mà không gây lỗi dừng chương trình.

---

## 8. Xử lý sự cố thường gặp (Troubleshooting)

1. **Không kết nối được MQTT Broker**:
   - Kiểm tra kết nối mạng tới cổng 1883 của `broker.hivemq.com`.
   - Nếu mạng trường học hoặc công ty chặn cổng 1883, chỉ định broker cục bộ bằng cờ `--broker localhost`.

2. **Xung đột Device ID trên HiveMQ công cộng**:
   - Do `broker.hivemq.com` là máy chủ công cộng, nếu nhiều người cùng kiểm thử với ID mặc định `pi4_01`, thông điệp có thể bị ghi đè.
   - Luôn sử dụng `--device-id <tên_riêng>` khi kiểm thử thực tế.

3. **Lỗi mở Webcam**:
   - Kiểm tra quyền truy cập camera trong cài đặt hệ điều hành hoặc sử dụng cờ `--synthetic` để chuyển sang màn hình radar đồ họa.
