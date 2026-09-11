# ADB-MLKit

**Read text on Android from Python, using Google's on-device ML Kit models over ADB.**

ADB-MLKit consists of a Python SDK/CLI and a small, headless Android instrumentation helper. It is an independent community project, not an official Google product. No OCR cloud account or API key is required.

[Tiếng Việt](README.vi.md) · [API reference](docs/API.md) · [Protocol](docs/PROTOCOL.md) · [Security](SECURITY.md)

## Features

- Read a local image, encoded image bytes, an image already on Android, or a screenshot.
- Optional XPath-to-region lookup with uiautomator2; recognized text always comes from OCR.
- Five bundled script models: **Latin (including Vietnamese), Chinese, Japanese, Korean and Devanagari**.
- Crop ROI, clockwise rotation, block/line/element text and geometry, engine-provided confidence where available.
- Multiple devices via explicit serial selection; sequential batch images.
- Cold/first invocation and repeated-same-image OCR timings, plus host transfer/startup/cleanup timings.
- Request-isolated temporary storage and best-effort cleanup; Base64-safe ADB input transport.
- Structured JSON output, typed Python results, unit tests and GitHub Actions build configuration.

## Requirements

- Python 3.10+, Android platform-tools (`adb`) on PATH, and an authorized USB/TCP device.
- Android 6.0 / API 23 or newer.
- A distribution wheel includes the version-matched Android helper APK. End users do not need Java/Gradle/Android Studio.
- ADB/platform-tools remains a separate prerequisite; pip never installs an APK on your phone automatically.
- Optional XPath support: install the `[ui]` extra.

This does **not** bypass Android screen-capture restrictions or private-storage permissions. Avoid enabling ADB on untrusted networks.

## Quick start

Install the built wheel (available locally in `dist/`; publication is a separate maintainer step):

```powershell
python -m pip install ./dist/adb_mlkit-0.1.0-py3-none-any.whl
adb-mlkit devices
```

After the maintainer publishes this project to PyPI, installation by name becomes:

```text
python -m pip install adb-mlkit
python -m pip install "adb-mlkit[ui]"
```

These package-index commands require an actual release; preparing this repository does not publish one. See [PyPI publishing](docs/PUBLISHING.md).

Explicitly install the bundled, checksum-verified helper on the selected phone:

```powershell
adb-mlkit install
adb-mlkit info
adb-mlkit recognize --screenshot --language vi --runs 3 --json
```

The new helper package is **`io.github.adbmlkit.helper`**, separate from the earlier `com.example.mlkitocrtest` prototype. The prototype APK cannot serve this protocol.

### Images on Android

```powershell
adb-mlkit recognize --device-file "/sdcard/Download/example.png" --language vi --json
```

The Android shell must already be allowed to read the path. The host reads the encoded bytes over ADB and stages them in helper-private storage; this is not zero-copy device-only ingestion and does not require broad storage permissions.

### Local images, crop and other scripts

```powershell
adb-mlkit recognize --file image.png --language vi --roi 60 100 1000 700 --runs 5
adb-mlkit recognize --file japanese.png --script japanese --json
adb-mlkit recognize --file rotated.jpg --rotation 90 --json --output result.json
adb-mlkit batch first.png second.png --language vi --json --output batch.json
adb-mlkit --serial DEVICE_SERIAL recognize --screenshot --script latin
```

Existing output files are protected unless `--overwrite` is given. Global options (`--serial`, `--adb-path`, `--timeout`) go **before** the subcommand. `python -m adb_mlkit` is equivalent to `adb-mlkit`.

### Python API

```python
from adb_mlkit import ADBMLKit

ocr = ADBMLKit(serial="DEVICE_SERIAL")
result = ocr.recognize_device_file("/sdcard/Download/example.png", language="vi", runs=3)
print(result.text)
print(result.timing)       # Android decode/init/recognition durations
print(result.host_timing)  # Host load/transfer/instrumentation/result/cleanup/total

for block in result.blocks:
    for line in block.lines:
        print(line.text, line.bounds, line.confidence)
```

See [API reference](docs/API.md) and [examples](examples/) for all entry points.

## Languages versus scripts

`--language vi` selects the **Latin model**, not a Vietnamese-only model. It does not translate, force output into Vietnamese, or provide a recognition hint. The SDK maps a documented set of aliases to the five supported scripts; `adb-mlkit languages` lists them. The alias list is not Google's exhaustive language list. Unsupported scripts (for example Arabic or Thai) are not automatically recognized by this integration.

ML Kit may recognize mixed-script text supported by a selected model, but this project does not run all five recognizers automatically or promise arbitrary multilingual detection. For mixed documents, select and benchmark an appropriate model or process the image separately with multiple models.

## Coordinate and timing semantics

ROI is `[left, top, right, bottom]` in the original unrotated source image, with exclusive right/bottom edges. Crop precedes rotation. Output geometry uses the cropped, rotated image coordinate system, **not necessarily screen coordinates**. Explicit rotation is used; normalize EXIF orientation yourself when needed.

`runs=N` recognizes **one image N times** using one recognizer in one invocation. The first run can include lazy model initialization; later values measure warm recognition. Each API call starts instrumentation again. Warm OCR time is not end-to-end latency. The host total includes image loading/capture, transfers and cleanup, but not APK installation. No fixed speed or accuracy guarantee is made.

## Development and verification

```powershell
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
# Build Android first: see android/README.md
python scripts/prepare_package.py
python -m build
python scripts/verify_wheel.py dist/adb_mlkit-0.1.0-py3-none-any.whl
```

Python unit tests mock ADB; they do not establish on-device accuracy. Build the Android helper separately. See [CONTRIBUTING.md](CONTRIBUTING.md) for synthetic-image device tests and publication notes. No device credentials or private images are included.

## Limitations

- One instrumentation invocation at a time per device. Use one client per device; separate processes must coordinate themselves.
- No always-running HTTP daemon, streaming camera service, translation API or cloud fallback.
- Image input limit: 32 MiB; decoded dimensions: at most 32 million pixels. Large input can still be memory-intensive.
- Same-device screenshot and XPath lookup are sequential, not an atomic UI snapshot. Changing UI may move the target.
- Debug APK is a developer tool, not a hardened Play Store app. Model libraries make the all-script APK substantially larger than a Latin-only helper.
- ML Kit models/libraries have their own terms. This repository provides integration source, not source code for Google's recognition models.

## License and upstream

Project code: [MIT](LICENSE). See [third-party notices](THIRD_PARTY_NOTICES.md).

- [Google ML Kit Android setup](https://developers.google.com/ml-kit/vision/text-recognition/v2/android)
- [Supported languages](https://developers.google.com/ml-kit/vision/text-recognition/v2/languages)
- [Official sample source](https://github.com/googlesamples/mlkit)
