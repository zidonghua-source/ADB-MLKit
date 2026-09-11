"""Stage a built Android helper for wheel/sdist packaging; never installs it."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, default=ROOT / "android/app/build/outputs/apk/debug/app-debug.apk")
    args = parser.parse_args()
    apk = args.apk.resolve()
    if not apk.is_file():
        parser.error(f"APK not found: {apk}. Build the Android helper first.")
    config = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', config, re.M).group(1)
    android = (ROOT / "android/app/build.gradle").read_text(encoding="utf-8")
    android_version = re.search(r"versionName\s*=\s*'([^']+)'", android).group(1)
    if version != android_version:
        parser.error("Python and Android source versions differ")
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        if "AndroidManifest.xml" not in names or "classes.dex" not in names:
            parser.error("Not a valid Android APK archive")
        for script in ("Latn", "Hani", "Deva", "Jpan", "Kore"):
            if not any(f"/{script}_ctc/" in name for name in names):
                parser.error(f"APK is missing the {script} model")
    output_metadata = apk.parent / "output-metadata.json"
    if not output_metadata.is_file():
        parser.error("Build output-metadata.json must accompany APK to verify application/version")
    metadata = json.loads(output_metadata.read_text(encoding="utf-8"))
    if metadata.get("applicationId") != "io.github.adbmlkit.helper":
        parser.error("Wrong APK application ID")
    elements = [e for e in metadata["elements"] if e["outputFile"] == apk.name]
    if len(elements) != 1 or elements[0]["versionName"] != version:
        parser.error("Built APK version does not match Python package")
    assets = ROOT / "src/adb_mlkit/assets"
    assets.mkdir(parents=True, exist_ok=True)
    destination = assets / "adb-mlkit.apk"
    shutil.copyfile(apk, destination)
    manifest = {"package": metadata["applicationId"], "version": version,
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
    (assets / "helper.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Staged helper {version}: {destination.stat().st_size} bytes, SHA-256 {manifest['sha256']}")


if __name__ == "__main__":
    main()
