# Raspberry Pi 4 Edge Hardware Service (PBL6)

Service chính thức chạy trực tiếp trên phần cứng thật Raspberry Pi 4. Service đảm nhiệm đọc các cảm biến vật lý, truyền luồng hình ảnh thời gian thực từ USB Webcam, phát âm thanh đàm thoại 2 chiều qua loa thật và giao tiếp hai chiều với ứng dụng Flutter qua giao thức MQTT và WebRTC.

## 1. Yêu cầu phần cứng
- Bo mạch Raspberry Pi 4 (khuyên dùng hệ điều hành Raspberry Pi OS 64-bit Debian Bookworm).
- Camera USB (nhận diện tại `/dev/video1` hoặc `/dev/video0`).
- Cảm biến siêu âm HC-SR04:
  - VCC nối chân Pin 2 hoặc Pin 4 (5V).
  - GND nối chân Pin 6 hoặc Pin 9 (GND).
  - Trig nối chân GPIO 23 (Pin 16 vật lý).
  - Echo nối chân GPIO 24 (Pin 18 vật lý) qua cầu phân áp trở (1k / 2k) để hạ áp về 3.3V bảo vệ cổng GPIO của Pi.
- Loa máy tính hoặc loa USB/3.5mm cắm vào Raspberry Pi để phát âm thanh đàm thoại Push-to-Talk.

## 2. Cài đặt môi trường trên Raspberry Pi
Chuyển vào thư mục làm việc trên Raspberry Pi:
```bash
cd /home/admin/Documents/pbl6/tools

# Cài đặt thư viện bằng uv
uv pip install -r requirements.txt

# Hoặc cài đặt vào môi trường ảo Python
/home/admin/Documents/pbl6/.venv/bin/pip install -r requirements.txt
```

## 3. Khởi chạy Service
```bash
# Chạy trực tiếp qua uv
uv run pi_server.py

# Hoặc chạy bằng Python trong venv
/home/admin/Documents/pbl6/.venv/bin/python3 pi_server.py
```

### Chạy ngầm khi đóng phiên SSH
```bash
cd /home/admin/Documents/pbl6/tools
nohup uv run pi_server.py > pi_service.log 2>&1 &
```

Hoặc qua tmux:
```bash
tmux new -s pbl6 "cd /home/admin/Documents/pbl6/tools && uv run pi_server.py"
# Bấm Ctrl+B rồi bấm D để tách phiên mà tiến trình vẫn chạy ngầm
```

## 4. Danh sách tham số dòng lệnh
| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--device-id` | `pi4_01` | Mã định danh thiết bị, quyết định topic MQTT `pbl6/{device_id}/...`. |
| `--broker` | `broker.emqx.io` | Máy chủ MQTT broker. |
| `--port` | `1883` | Cổng kết nối MQTT. |
| `--camera-index` | `1` | Chỉ số webcam USB vật lý (ưu tiên /dev/video1). |
| `--interval` | `3.0` | Chu kỳ phát bản tin telemetry phần cứng (giây). |
| `--trig-pin` | `23` | Chân GPIO Trigger của HC-SR04. |
| `--echo-pin` | `24` | Chân GPIO Echo của HC-SR04. |

## 5. Hành vi phát hiện phần cứng
- **Khi chưa cắm cảm biến khoảng cách**: Telemetry gửi `ultrasonic_distance_cm: -1.0`. Giao diện Flutter hiển thị "Chưa kết nối cảm biến" (`--`), không có cảnh báo nguy hiểm giả.
- **Khi webcam chưa cắm hoặc bị chiếm dụng**: Truyền khung hình thông báo trạng thái "CAMERA KHONG KHA DUNG (CHUA CAM HOAC DANG BAN)" kèm timestamp, không sinh hình ảnh radar giả.
- **Nhiệt độ CPU và tải CPU**: Đo đạc trực tiếp từ nhân Linux (`/sys/class/thermal/thermal_zone0/temp` và `/proc/stat`).
