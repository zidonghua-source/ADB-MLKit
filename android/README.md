# ADB-MLKit Android helper

Offline, file-only OCR companion for the public ADB-MLKit host SDK. Application ID
`io.github.adbmlkit.helper`; runner `io.github.adbmlkit.helper/.OcrInstrumentation`.
This is a deliberately **debuggable** helper so an authorized ADB host can use
`run-as`. It has no Activity and requests **no permissions**, including network
and storage permissions. The merged non-exported ML Kit initialization provider
initializes the SDK when Android launches the self-instrumented application.
No Google Play services model download is required.

## Build

Prerequisites:

- JDK/JBR 25 (used for this build); Java source/bytecode level 17.
- Android SDK platform **stable API 37** (`platforms/android-37.0` in the verified
  installation, Android 17, `PreviewSdkInt=0`) and build tools **36.0.0**.
- Gradle **9.3.1**, Android Gradle Plugin **9.1.1**. The generated, portable Gradle
  wrapper is included; no separately installed Gradle is required by consumers.
- `JAVA_HOME` and `ANDROID_HOME` set to your JDK and SDK respectively, with no
  machine-specific paths in tracked configuration. Alternatively create your
  own ignored `local.properties` with `sdk.dir`; do not commit that file.

SDK-manager package IDs verified from the installed platform metadata:

```text
sdkmanager "platforms;android-37.0" "build-tools;36.0.0"
```

From this directory on Windows:

```powershell
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug
```

On macOS/Linux use `sh ./gradlew` with the same tasks (or make it executable).
The APK is `app/build/outputs/apk/debug/app-debug.apk`; it is signed with the
local Android debug key. Debug signing identity therefore varies by machine.
This is not a production signing/release configuration.

The wrapper was generated using installed Gradle, not hand-written. Its official
`https://services.gradle.org/distributions/gradle-9.3.1-bin.zip` distribution is
pinned to SHA-256
`b266d5ff6b90eada6dc3b20cb090e3731302e553a27c5d3e4df1f0d76beaff06`.
Dependency resolution/build may need network access; the helper itself does not.
All five bundled dependencies are pinned to **16.0.1**:

- `com.google.mlkit:text-recognition` (Latin)
- `com.google.mlkit:text-recognition-chinese`
- `com.google.mlkit:text-recognition-devanagari`
- `com.google.mlkit:text-recognition-japanese`
- `com.google.mlkit:text-recognition-korean`

Official setup/version reference:
<https://developers.google.com/ml-kit/vision/text-recognition/v2/android>.

## Version-one request transport

The host generates a fresh UUID as **32 lowercase hexadecimal characters**, with
no hyphens, and creates `files/requests/<id>/` relative to the package's private
working directory under `run-as io.github.adbmlkit.helper`. The host streams
base64-encoded bytes through ADB and decodes them into private `request.json`
and `input.png`. Complete both writes **before** invoking instrumentation; do
not modify request files while the operation is in progress. Use a new ID per
invocation; do not run concurrent instrumentations for this package.

A JSON request (UTF-8, at most 16 KiB):

```json
{
  "schema_version": 1,
  "id": "0123456789abcdef0123456789abcdef",
  "script": "latin",
  "source": {
    "type": "private",
    "path": "files/requests/0123456789abcdef0123456789abcdef/input.png"
  },
  "rotation": 0,
  "roi": null,
  "runs": 1
}
```

Required fields: `schema_version`, `id`, `source.type`, `source.path`, `runs`.
`script` defaults to `latin` when omitted; its exact case-sensitive values are
`latin`, `chinese`, `devanagari`, `japanese`, `korean`. `rotation` defaults to 0;
valid values are integer 0/90/180/270, clockwise. Omitted or null `roi` means the
whole source. `runs` is a required integer in 1..30. Numeric strings, booleans,
null for required/defaulted fields, and fractional numeric values are rejected.
Unknown fields are ignored for forward compatibility; callers must send valid
JSON without duplicate keys (the platform JSON parser may accept nonstandard
JSON syntax, which is not part of this contract).

Only the **exact** source path shown for this request's ID is accepted. Absolute
paths, another ID's namespace, traversal, and symbolic-link aliases are rejected.
For a device external path, the **Python host** reads it using an ADB `cat` stream
and stages those bytes in private storage. Android never opens external paths
or requests storage permissions. Caller access controls still apply to the host
stream. Host cleanup removes completed request directories; the helper does not
clean up other requests or retain a request history outside those directories.

Invocation (documentation only; not performed during build verification):

```text
adb shell am instrument -w -e request_id 0123456789abcdef0123456789abcdef io.github.adbmlkit.helper/.OcrInstrumentation
adb exec-out run-as io.github.adbmlkit.helper cat files/requests/0123456789abcdef0123456789abcdef/result.json
```

Treat `result.json` as authoritative, not ADB's process exit status. The runner
returns instrumentation code **0** on successfully published OCR success, **-1**
on failure, plus `ok` and `result_file` status fields when available. On failure,
`response` contains the error envelope, including when an invalid ID or filesystem
failure makes a safe result path unavailable. There is no capabilities action;
the host may use the static five-script list above. Allow a host timeout larger
than `runs * 30 seconds`, plus startup/decoding/serialization overhead.

## Success response and coordinates

```json
{
  "schema_version": 1,
  "id": "0123456789abcdef0123456789abcdef",
  "ok": true,
  "text": "Example",
  "script": "latin",
  "image": {
    "source_width": 640,
    "source_height": 480,
    "width": 640,
    "height": 480,
    "rotation": 0,
    "roi": null
  },
  "timing": {
    "decode_ms": 3.5,
    "init_ms": 1.2,
    "runs_ms": [42.0]
  },
  "blocks": [
    {
      "text": "Example",
      "bounds": [10, 20, 100, 40],
      "corner_points": [[10, 20], [100, 20], [100, 40], [10, 40]],
      "recognized_language": "en",
      "lines": [
        {
          "text": "Example",
          "bounds": [10, 20, 100, 40],
          "corner_points": [[10, 20], [100, 20], [100, 40], [10, 40]],
          "recognized_language": "en",
          "confidence": null,
          "elements": [
            {
              "text": "Example",
              "bounds": [10, 20, 100, 40],
              "corner_points": [[10, 20], [100, 20], [100, 40], [10, 40]],
              "recognized_language": "en",
              "confidence": null
            }
          ]
        }
      ]
    }
  ]
}
```

The example's timings/geometry are illustrative, not a recognition fixture.
Empty recognition is successful: `text` is empty and `blocks` is `[]`.

- Source dimensions describe the decoded source raster. EXIF orientation is not
  applied; `rotation` is the caller's explicit orientation instruction.
- ROI is `[left, top, right, bottom]` in **source pixels before rotation**. Right
  and bottom are exclusive. Require `0 <= left < right <= source_width` and
  `0 <= top < bottom <= source_height`; clipping is not performed.
- The helper physically crops first and rotates second, then supplies ML Kit an
  image with rotation 0. All returned bounds and corner points are in this final
  **cropped + rotated image** coordinate system, origin top-left, x right/y down.
- With cropped dimensions `cw` and `ch`, result dimensions are `cw x ch` at 0/180
  degrees and `ch x cw` at 90/270 degrees. No resizing/downsampling occurs.
- To map boundary coordinates back to the source, first invert the clockwise
  rotation: 0 `(x,y)`; 90 `(y,ch-x)`; 180 `(cw-x,ch-y)`;
  270 `(cw-y,x)`. Then add ROI left/top (zero for a full image). Transform all
  corners when mapping a bounding rectangle, then compute its source envelope.
- Bounds are `[l,t,r,b]` or null. Corner points preserve SDK order, or `[]` if
  unavailable. SDK language values are preserved (including undetermined codes).
- Lines and elements expose real SDK `getConfidence()` values, compiled against
  bundled 16.0.1. These are finite floats in 0..1; unavailable/nonfinite/out-of-range
  values are null. No confidence is synthesized. Blocks have no confidence field.
- `decode_ms` includes header validation, memory checks, decode, crop, and rotation.
  `init_ms` includes input-image/recognizer creation. `runs_ms` has exactly `runs`
  entries, each including submission and waiting; model warmup is in the first
  run. One recognizer is reused, the final run supplies the text hierarchy, and
  the recognizer is closed even on error. Each run waits off the main thread for
  at most 30 seconds. A timeout does not imply underlying native work was canceled.

## Limits and errors

Input is at most **32 MiB** (33,554,432 bytes), dimensions at most **16,384** on
either side, and at most **32,000,000 source pixels**. Header-only bounds decode
checks dimensions before allocating a full bitmap. Oversized sources are refused,
even if ROI is small; never silently downsample. An additional conservative heap
budget check may reject smaller images on low-memory runtimes. PNG is the host
transport convention; any raster the Android decoder can decode is accepted.

```json
{
  "schema_version": 1,
  "id": "0123456789abcdef0123456789abcdef",
  "ok": false,
  "error": {"code": "INVALID_REQUEST", "message": "runs must be from 1 to 30"}
}
```

| Code | Meaning |
| --- | --- |
| `INVALID_REQUEST` | Invalid/missing request JSON or fields, wrong namespace, symlink, source byte/dimension limit, invalid/out-of-bounds ROI. |
| `DECODE_FAILED` | Missing/empty/undecodable image, decode/transform allocation failure, insufficient estimated heap budget. |
| `OCR_FAILED` | Recognizer creation/submission/processing failure. |
| `TIMEOUT` | Any individual OCR run exceeded 30 seconds. |
| `INTERNAL_ERROR` | Unexpected runner failure, interruption, or inability to publish a result. |

Results are UTF-8, written to a temporary file **in the same request directory**,
flushed with file-descriptor sync, and atomically renamed over `result.json`.
This avoids partial JSON visibility; directory-entry power-loss durability is not
promised. With invalid/missing `request_id`, no private result path can safely be
chosen; instrumentation `response` carries the error and missing IDs use null.
A killed process/device or exhausted memory can prevent any response; the host
must handle missing files/transport failures and never trust stale files from an
old ID. This helper assumes the authorized host does not mutate the private
namespace during processing; it is not a sandbox against an adversarial ADB host.

## Verification scope

Local JVM tests cover request defaults, all scripts/rotations, strict field types,
run bounds, namespace/UUID validation, ROI validation, dimension limits and integer
overflow. `assembleDebug` compiles the actual ML Kit line/element confidence APIs;
`lintDebug` checks Android code and resources. APK inspection can verify signing,
merged manifest (no permissions/activities; correct runner/provider/debuggable
flag), and assets for all five bundled models. No device installation or runtime
OCR testing is required or performed by these build tasks. Runtime model behavior,
rotation geometry and instrumentation startup still need later authorized device
integration tests.
