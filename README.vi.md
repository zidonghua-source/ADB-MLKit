# ADB-MLKit — OCR trên Android từ Python

Project độc lập gồm **SDK/CLI Python** và **APK Android không có giao diện**, dùng Google ML Kit Text Recognition v2. Đây không phải sản phẩm chính thức của Google.

## Có gì?

- Đọc ảnh trên máy tính, bytes ảnh, ảnh có sẵn trong điện thoại và ảnh chụp màn hình.
- Lấy vùng bằng XPath tùy chọn; XPath chỉ lấy tọa độ, không lấy text từ UI.
- Năm bộ chữ: Latin (có tiếng Việt), Trung, Nhật, Hàn, Devanagari.
- Cắt vùng, xoay ảnh, text theo block/dòng/từ, tọa độ và confidence khi engine cung cấp.
- Đo riêng thời gian OCR và tổng thời gian xử lý; xuất JSON, đọc nhiều ảnh tuần tự.
- Không gửi ảnh lên cloud; không cần API key hay root.

## Cài đặt

### 1. Cài package

```powershell
python -m pip install adb-mlkit
```

Package đã chứa APK Android, cả 5 model và hỗ trợ XPath (uiautomator2 và Pillow), không cần tự build Android, không cần Java/Gradle/Android Studio. ADB/platform-tools vẫn phải cài riêng.

### 2. Kết nối điện thoại

Bật USB debugging trên điện thoại, cắm máy (hoặc kết nối TCP) và cấp quyền ADB:

```powershell
adb devices
```

Thiết bị phải hiện với trạng thái `device`.

### 3. Đọc văn bản

Lệnh đọc văn bản và API Python sẽ **tự kiểm tra và cài APK đi kèm** (đã xác minh checksum) nếu điện thoại chưa có. Không cần chạy `adb-mlkit install` trước:

```powershell
adb-mlkit recognize --screenshot --language vi --json
```

Nếu APK đã có thì không tự cài lại hay cập nhật. Vẫn có thể dùng `adb-mlkit install` để cài/cập nhật thủ công, hoặc `adb-mlkit install path/to/custom.apk` để chọn APK khác. Nếu cài thất bại, OCR dừng và báo lỗi; SDK không tự gỡ APK hiện có để xử lý xung đột.

## Sử dụng

**Đọc ảnh nằm trong điện thoại:**

```powershell
adb-mlkit recognize --device-file "/sdcard/Download/anh.png" --language vi --json
```

ADB phải có quyền đọc đường dẫn đó. Ảnh được đọc về host rồi chuyển vào vùng lưu trữ riêng của APK, không phải xử lý trực tiếp không qua truyền ảnh. Không đọc được thư mục riêng của app khác nếu Android không cho phép.

**Đọc ảnh máy tính, Nhật/Hàn/Trung:**

```powershell
adb-mlkit recognize --file anh.png --language vi
adb-mlkit recognize --file japanese.png --script japanese --json
adb-mlkit recognize --file korean.png --script korean --json
adb-mlkit recognize --file chinese.png --script chinese --json
```

**Đọc bằng XPath:**

```powershell
adb-mlkit recognize --xpath '//*[@resource-id="com.example:id/dialog"]/..' --language vi --runs 3
```

Thay XPath bằng phần tử trên app của bạn. Màn hình thay đổi giữa lúc lấy XPath và chụp ảnh có thể làm vùng không còn khớp.

**Quản lý thiết bị:**

```powershell
adb-mlkit devices           # Liệt kê thiết bị đang kết nối
adb-mlkit info              # Model, API level, trạng thái APK helper
adb-mlkit install           # Cài hoặc cập nhật APK helper
adb-mlkit languages         # Liệt kê bộ chữ và bí danh ngôn ngữ
```

## API Python

```python
from adb_mlkit import ADBMLKit

ocr = ADBMLKit()  # Chỉ tự chọn khi có đúng một thiết bị đã được cấp quyền ADB
result = ocr.recognize_device_file("/sdcard/Download/anh.png", language="vi")
print(result.text)
print(result.to_json())

result = ocr.recognize_screenshot(roi=(60, 100, 1000, 700), runs=5)
print(result.timing)
print(result.host_timing)
```

Chọn thiết bị cụ thể: `ADBMLKit(serial="SERIAL")` hoặc `adb-mlkit --serial SERIAL recognize ...`.

## Lưu ý quan trọng

- `language="vi"` chọn model Latin, không dịch hoặc ép đầu ra thành tiếng Việt. Không hỗ trợ mọi bộ chữ trên thế giới.
- `runs=5` đọc **cùng một ảnh** 5 lần. Các lần sau đo model đã nạp; tổng thời gian thật còn có chụp ảnh, truyền ADB và khởi chạy APK. `host_timing.setup_ms` đo kiểm tra/cài APK; `total_ms` bao gồm cả bước này nên lần đầu có thể lâu hơn.
- ROI là tọa độ ảnh gốc trước xoay; kết quả là tọa độ sau cắt và xoay, không mặc định là tọa độ màn hình.
- Giới hạn ảnh 32 MiB/32 triệu pixel. Chất lượng phụ thuộc ảnh, bộ chữ và thiết bị.
- Một phiên nhận dạng tại một thời điểm cho mỗi điện thoại. Các process riêng phải tự điều phối.
- APK debug không xin quyền mạng, không bỏ qua `FLAG_SECURE` hay cơ chế bảo vệ của Android.
- Dữ liệu tạm được cố gắng xóa sau mỗi request; mất kết nối hoặc dừng process đột ngột có thể để lại file.

## Phát triển từ source

Clone repo và build từ source. Cần JDK 25, Android SDK (API 37) và bộ công cụ trong [android/README.md](android/README.md):

```powershell
git clone https://github.com/zidonghua-source/ADB-MLKit.git
cd ADB-MLKit

python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v

# Build APK helper trước
cd android
.\gradlew.bat :app:assembleDebug
cd ..

python scripts/prepare_package.py
python -m build
python scripts/verify_wheel.py dist/adb_mlkit-0.1.0-py3-none-any.whl
```

Source checkout cài bằng `pip install .` mà chưa chạy bước chuẩn bị tài nguyên sẽ chỉ có Python, không có APK đi kèm; lúc đó OCR báo thiếu APK. Có thể cung cấp APK tùy chỉnh hoặc cài từ PyPI.

## Tài liệu

- [Hướng dẫn đầy đủ](README.md)
- [API và CLI](docs/API.md)
- [Giao thức Python–Android](docs/PROTOCOL.md)
- [Build APK](android/README.md)
- [Bảo mật](SECURITY.md)
- [Đóng góp và đưa lên GitHub](CONTRIBUTING.md)

Mã project dùng MIT. Thư viện/model Google giữ điều khoản riêng. Không cam kết độ chính xác hay thời gian cố định khi chưa benchmark trên ảnh thực tế.