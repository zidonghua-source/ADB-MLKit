"""Verify distributable contents; no device or network access."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile


def main():
    path = Path(sys.argv[1])
    with zipfile.ZipFile(path) as wheel:
        apk = wheel.read("adb_mlkit/assets/adb-mlkit.apk")
        manifest = json.loads(wheel.read("adb_mlkit/assets/helper.json"))
        if hashlib.sha256(apk).hexdigest() != manifest["sha256"]:
            raise SystemExit("Bundled APK checksum mismatch")
        metadata_name = next(n for n in wheel.namelist() if n.endswith(".dist-info/METADATA"))
        metadata = wheel.read(metadata_name).decode("utf-8")
        if f"Version: {manifest['version']}" not in metadata.splitlines():
            raise SystemExit("Wheel and APK versions differ")
        if len(apk) < 1024:
            raise SystemExit("APK unexpectedly small")
    print(f"Verified {path.name}: bundled helper {manifest['version']}, {len(apk)} bytes")


if __name__ == "__main__":
    main()
