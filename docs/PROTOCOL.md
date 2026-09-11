# Host–Android protocol v1

This is a local file protocol carried over an authorized ADB connection, not an HTTP API.

- Package: `io.github.adbmlkit.helper`
- Instrumentation: `io.github.adbmlkit.helper/.OcrInstrumentation`
- Request ID: UUID represented by 32 hexadecimal characters.
- Private request directory: `files/requests/<id>/`.
- Files: `request.json`, `input.png`, `result.json`. The image is decoded from its contents; the staging filename is not an image-format restriction.

The host stages image bytes and UTF-8 JSON using Base64 through `run-as`, avoiding binary-stdin corruption seen with some Windows ADB transports. The helper must never execute JSON content as shell commands.

```text
adb -s SERIAL shell am instrument -w -e request_id ID io.github.adbmlkit.helper/.OcrInstrumentation
```

## Request

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

`script` is `latin`, `chinese`, `devanagari`, `japanese`, or `korean`. `rotation` is clockwise in degrees and must be 0, 90, 180, or 270. `runs` is 1–30 and repeats recognition on the same decoded image/recognizer, not fresh screenshots. Input is limited to 32 MiB and 32 million decoded pixels.

`roi` is null or `[left, top, right, bottom]` in the **unrotated source image**, with exclusive right/bottom boundaries. Crop happens before rotation. Returned coordinates refer to the **cropped, rotated image**; they are not automatically screen coordinates. Use zero rotation and no crop if original pixel coordinates are needed without conversion. EXIF orientation is not an implicit coordinate contract; normalize images beforehand or use the explicit rotation option.

## Success response

```json
{
  "schema_version": 1,
  "id": "0123456789abcdef0123456789abcdef",
  "ok": true,
  "text": "Hello",
  "script": "latin",
  "image": {
    "source_width": 100,
    "source_height": 80,
    "width": 100,
    "height": 80,
    "rotation": 0,
    "roi": null
  },
  "timing": {"decode_ms": 1.0, "init_ms": 2.0, "runs_ms": [100.0]},
  "blocks": []
}
```

Numbers above are illustrative, not benchmarks. Blocks contain `text`, nullable `bounds`, `corner_points`, `recognized_language`, and `lines`. Lines contain the same geometry/text fields, nullable `confidence`, and `elements`. Elements have no children. Confidence is engine-provided where available; it is not a calibrated promise of correctness.

The response file is atomically published. Clients must validate response version and request ID, not just parse JSON. The Python layer may enrich output with host timing information.

## Error response

```json
{
  "schema_version": 1,
  "id": "0123456789abcdef0123456789abcdef",
  "ok": false,
  "error": {"code": "DECODE_FAILED", "message": "Cannot decode input image"}
}
```

Error categories: `INVALID_REQUEST`, `DECODE_FAILED`, `OCR_FAILED`, `TIMEOUT`, and `INTERNAL_ERROR`. A process crash or inaccessible storage can prevent any result from being written; clients must also handle instrumentation/transport failure.

## Lifetime and concurrency

The host deletes only its own request directory in a `finally` path. Android instrumentation starts a fresh helper process; warm measurements apply within a single invocation. Serializing requests to one device is required: unique paths prevent accidental file reuse but do not make simultaneous instrumentation sessions safe. Parallel requests on different devices are independent.
