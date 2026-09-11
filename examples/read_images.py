"""Run manually with an authorized device and installed helper."""
from adb_mlkit import ADBMLKit


def main():
    client = ADBMLKit()
    result = client.recognize_device_file("/sdcard/Download/example.png", language="vi", runs=3)
    print(result.to_json())


if __name__ == "__main__":
    main()
