# ADB-MLKit — OCR trên Android từ Python

Project độc lập gồm **SDK/CLI Python** và **APK Android không có giao diện**, dùng Google ML Kit Text Recognition v2. Đây không phải sản phẩm chính thức của Google.

## Có gì?

- Đọc ảnh trên máy tính, bytes ảnh, ảnh có sẵn trong điện thoại và ảnh chụp màn hình.
- Lấy vùng bằng XPath tùy chọn; XPath chỉ lấy tọa độ, không lấy text từ UI.
- Năm bộ chữ: Latin (có tiếng Việt), Trung, Nhật, Hàn, Devanagari.
- Cắt vùng, xoay ảnh, text theo block/dòng/từ, tọa độ và confidence khi engine cung cấp.
- Đo riêng thời gian OCR và tổng thời gian xử lý; xuất JSON, đọc nhiều ảnh tuần tự.
- Không gửi ảnh lên cloud; không cần API key hay root.

## Chạy nhanh trên Windows

```powershell
cd D:\Github\ADB-MLKit
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Build APK theo [hướng dẫn Android](android/README.md). Khi APK đã có:

```powershell
adb-mlkit devices
adb-mlkit install android/app/build/outputs/apk/debug/app-debug.apk
adb-mlkit recognize --screenshot --language vi --runs 3 --json
```

Package mới là `io.github.adbmlkit.helper`, không dùng chung APK prototype `com.example.mlkitocrtest`.

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
python -m pip install -e ".[ui]"
adb-mlkit recognize --xpath '//*[@resource-id="com.example:id/dialog"]/..' --language vi --runs 3
```

Thay XPath bằng phần tử trên app của bạn. Màn hình thay đổi giữa lúc lấy XPath và chụp ảnh có thể làm vùng không còn khớp.

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
- `runs=5` đọc **cùng một ảnh** 5 lần. Các lần sau đo model đã nạp; tổng thời gian thật còn có chụp ảnh, truyền ADB và khởi chạy APK.
- ROI là tọa độ ảnh gốc trước xoay; kết quả là tọa độ sau cắt và xoay, không mặc định là tọa độ màn hình.
- Giới hạn ảnh 32 MiB/32 triệu pixel. Chất lượng phụ thuộc ảnh, bộ chữ và thiết bị.
- Một phiên nhận dạng tại một thời điểm cho mỗi điện thoại. Các process riêng phải tự điều phối.
- APK debug không xin quyền mạng, không bỏ qua `FLAG_SECURE` hay cơ chế bảo vệ của Android.
- Dữ liệu tạm được cố gắng xóa sau mỗi request; mất kết nối hoặc dừng process đột ngột có thể để lại file.

## Tài liệu

- [Hướng dẫn đầy đủ](README.md)
- [API và CLI](docs/API.md)
- [Giao thức Python–Android](docs/PROTOCOL.md)
- [Build APK](android/README.md)
- [Bảo mật](SECURITY.md)
- [Đóng góp và đưa lên GitHub](CONTRIBUTING.md)

Mã project dùng MIT. Thư viện/model Google giữ điều khoản riêng. Không cam kết độ chính xác hay thời gian cố định khi chưa benchmark trên ảnh thực tế.
