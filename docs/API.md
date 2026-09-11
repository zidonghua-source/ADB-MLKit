# Python API and CLI

## Client

```python
from adb_mlkit import ADBMLKit
client = ADBMLKit(serial=None, adb_path=None, timeout=30, script="latin")
```

Construction/import does not contact a device. Without `serial`, exactly one authorized device must be connected. ADB is resolved from the explicit argument, `ADB_PATH`, then PATH. The client remembers the selected serial. `timeout` applies to ordinary ADB operations; instrumentation allows at least `60 + 35 * runs` seconds.

| Method | Input / output |
|---|---|
| `devices()` | All discovered `Device(serial, state, details)` records, including unauthorized devices |
| `info()` | Selected device model/API, helper installed flag and supported script list |
| `install(apk)` | Explicitly install/update a local APK, returning installation confirmation |
| `recognize_bytes(data, **options)` | Encoded image bytes; returns `OCRResult` |
| `recognize_file(path, **options)` | Local file; returns `OCRResult` |
| `recognize_device_file(path, **options)` | Absolute Android path readable by shell; returns `OCRResult` |
| `recognize_screenshot(**options)` | Capture current display using ADB screencap; returns `OCRResult` |
| `recognize_xpath(xpath, xpath_timeout=10, **options)` | Optional uiautomator2 lookup supplies screenshot ROI; returns `OCRResult` |
| `batch_files(paths, **options)` | Sequential list of local files; returns list of results, stops on first error |

Every successful recognition deletes its own temporary request directory on the device. Cleanup is also attempted after errors; failures generate a warning without replacing the original error. Process termination/disconnection may leave residual data.

## Common recognition options

- `script=None`: one of `latin`, `chinese`, `devanagari`, `japanese`, `korean`; defaults to client setting.
- `language=None`: convenience alias such as `vi`, `en`, `zh`, `ja`, `ko`, `hi`. Cannot combine with `script`. Use `script_for_language()` or `LANGUAGES` to inspect aliases.
- `roi=None`: four integer pixels `(left, top, right, bottom)` before rotation. Must fit inside the image. Cannot combine with XPath's derived ROI.
- `rotation=0`: clockwise degrees, one of 0/90/180/270.
- `runs=1`: 1–30 repeated recognitions on the same image. Final run supplies output text.

These options do not request translation or linguistic correction. Model choice is script-based.

## Result

`OCRResult` provides:

- `id`, `schema_version`, `ok`, `text`, `script`.
- `image`: original width/height, output width/height, rotation and ROI metadata.
- `timing`: Android `decode_ms`, `init_ms`, `runs_ms`.
- `host_timing`: host `load_ms`, `transfer_ms`, `instrumentation_ms`, `result_ms`, `cleanup_ms`, `total_ms`. Host instrumentation time includes all runs plus process and ADB overhead. Timers overlap conceptually: do not add Android OCR times to host total.
- `blocks`: `TextBlock` objects with text, geometry, language and `lines`.
- `lines`: `TextLine` objects with nullable confidence and `elements`.
- `elements`: `TextElement` objects with text, geometry, recognized language and nullable confidence.
- `to_dict()` and `to_json(indent=2)` for export.

Geometry: `bounds` may be null; otherwise `[left, top, right, bottom]`. `corner_points` contains `[x, y]` pairs. Coordinates belong to the cropped, rotated output image. Confidence is not fabricated when unavailable. Recognized language may be empty/undetermined.

## Errors

`ADBMLKitError` covers missing ADB, authorization/selection errors, command timeouts, invalid helper responses and Android OCR failures. Invalid arguments raise `ValueError`; unreadable local files may raise `OSError`. The JSON error categories from Android are documented in [PROTOCOL.md](PROTOCOL.md).

```python
from adb_mlkit import ADBMLKit, ADBMLKitError
try:
    result = ADBMLKit().recognize_screenshot(language="vi")
except (ADBMLKitError, ValueError, OSError) as error:
    print(f"OCR failed: {error}")
```

## CLI

```text
adb-mlkit [--serial SERIAL] [--adb-path PATH] [--timeout SECONDS] COMMAND

COMMAND:
  devices
  info
  languages
  install APK
  recognize (--file PATH | --device-file PATH | --screenshot | --xpath XPATH)
  batch FILE [FILE ...]

Recognition options:
  --script SCRIPT | --language ALIAS
  --roi LEFT TOP RIGHT BOTTOM
  --rotation 0|90|180|270
  --runs N
  --json
  --output PATH
  --overwrite
```

`--json` produces structured output only on stdout; normal text output puts timing diagnostics on stderr. `--output` saves the chosen representation to UTF-8 instead of stdout. Existing output files require explicit `--overwrite`. Batch JSON is an array in the input order. Ordinary operational errors return exit code 1; argparse usage errors return 2. No command silently installs the helper except explicit `install`.
