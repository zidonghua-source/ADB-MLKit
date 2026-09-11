# Local verification — 2026-09-11

This report describes checks actually performed, not a compatibility guarantee.

## Passed

- Python 3.14 local isolated environment: **20 unit tests** passed. Tests mock ADB; cover device selection, command errors, remote quoting, Base64 preservation, request construction, response validation, cleanup, source loaders, batch and CLI output protection.
- Editable SDK installation and CLI help succeeded.
- Python wheel and source distribution built successfully using setuptools 84.0.0. Core SDK has no mandatory Python runtime dependency beyond the standard library.
- Android wrapper build with JBR 25.0.2, Gradle 9.3.1, AGP 9.1.1, SDK `platforms;android-37.0`, Build Tools 36.0.0: **BUILD SUCCESSFUL**.
- Android JVM request-validation suite: **8 tests**, zero failures/errors/skips.
- Android lint: zero errors, three warnings (newer build-tool/dependency versions available and intentionally missing application icon for a no-Activity helper).
- Final APK version `0.1.0`, package `io.github.adbmlkit.helper`.
- APK signing verification passed v1 and v2; all five script model assets were present; no requested permissions or launchable Activity were found in packaged metadata.

## Build artifact

Path: `android/app/build/outputs/apk/debug/app-debug.apk`

- Size: 49,023,576 bytes.
- SHA-256: `d26ec2cafd0140fe2ddbb6e13d8196ea3ddfdea652733afb05dde348b6b937b0`.

Rebuilding can change the binary/hash and uses the local debug signing key. APKs and build caches are ignored by Git; distribute an APK deliberately as a release asset, not by removing ignore rules wholesale.

## Warnings and untested areas

- `apksigner` reports legacy v1 META-INF-entry warnings and a JBR native-access warning; the overall signature verification succeeds, including whole-APK v2 verification.
- The SDK has **not been installed/run on a phone as part of this new-project verification**. Real OCR accuracy, storage permissions, startup behavior and multilingual runtime performance remain unverified here.
- Linux/macOS and Python 3.10 runtime checks were not run locally. CI is configured for Windows/Linux and Python 3.10/3.14 but has not run on GitHub.
- Optional uiautomator2 XPath integration was not exercised on a device.
- Git was not available on PATH or at standard checked Windows installation paths. No `.git` repository, commit, remote or push was created.
- Neither PyPI package-name availability nor ownership of the GitHub repository name was checked. Nothing has been published.
