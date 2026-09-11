# Security and privacy

Use ADB-MLKit only with devices and images you are authorized to access.

## Trust boundaries

- The Android helper is a **debuggable developer tool**, not a hardened consumer app. An authorized ADB connection can access its private files through `run-as`.
- Protect USB debugging authorization, your workstation, and any ADB TCP connection. Do not expose ADB or wrap this SDK in an unauthenticated public HTTP service.
- The helper uses bundled ML Kit models and does not request network permissions. Images are processed on the selected Android device, not submitted to an OCR cloud endpoint.
- Build tooling downloads Gradle, Maven libraries, and SDK components. Offline OCR does not mean an initial build is offline.
- Google ML Kit and other dependencies retain their respective licenses and terms; the repository's MIT license covers this project's code, not Google's models.

## Image handling

Each request uses a unique helper-private directory. The Python client attempts to remove that directory after success and failure. Cleanup is not secure erasure, and a disconnected device, killed process, or power failure can leave data behind. Results printed to a terminal or explicitly written to a file remain there.

Images already on a device are read with the shell user's existing permissions. Access to another app's private directory is not granted by this tool. It does not root devices, defeat `FLAG_SECURE`, or bypass Android storage restrictions. Device image bytes travel to the host before being staged in helper-private storage.

Do not commit personal screenshots, financial data, APK signing secrets, device identifiers, or output JSON to a public repository. The ignore rules are a convenience, not a data-loss prevention system.

## Reporting issues

Before publishing, the repository owner should enable GitHub private vulnerability reporting. Use that mechanism when available. Do not post secrets, private screenshots, or exploitable details in a public issue; provide a synthetic reproduction and affected versions instead.
