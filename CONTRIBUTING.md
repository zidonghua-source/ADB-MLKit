# Contributing and publishing

## Local checks

```text
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
# After building Android:
python scripts/prepare_package.py
python -m build
python scripts/smoke_install.py dist/adb_mlkit-0.1.0-py3-none-any.whl
```

Android checks (from `android/`; use `gradlew.bat` on Windows):

```text
./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

Use the toolchain in `android/README.md`. Do not commit `local.properties`, signing keys, APK binaries, `.venv`, caches, private images or result files. Keep Gradle wrapper files in source control, including `gradle-wrapper.jar`.

## Device smoke test

The unit suite and a successful APK build do not prove device behavior. Use an authorized test device and a **synthetic non-sensitive image** for integration checks:

1. Build and explicitly install the helper with `adb-mlkit install ...`.
2. Use `adb-mlkit info` to verify device/helper setup.
3. Recognize the same synthetic image with `--file` and `--device-file` after manually copying it to a readable shared folder. Compare text, dimensions, ROI and rotated geometry.
4. Use a screen containing synthetic text for `--screenshot`; use optional `[ui]` dependencies for XPath.
5. Test each script with corresponding synthetic text. Record device model/API, source image resolution and first/warm/end-to-end timing separately.
6. Include invalid-image, out-of-bounds ROI, permission-denied, disconnected-device and multiple-device tests. Verify error messages and request cleanup.

Never use production bank/customer images in CI or public issues. Do not infer multilingual accuracy from a single Latin image.

## API changes

Update Python result models, Android serialization, protocol documentation and tests together. Incompatible wire-format changes require a new schema version. Do not change coordinate semantics silently. Preserve error codes and avoid fabricating confidence values.

## Publishing this repository

The project is prepared locally; nothing is automatically pushed or published. Review all files and the license before creating a remote. Replace example paths/serials only in your local commands, not with real private data in documentation.

The configured repository is https://github.com/zidonghua-source/ADB-MLKit. Commit and push only after reviewing `git status` and `git diff --cached`. Forks should update the project URLs and Trusted Publisher configuration for their own repository.

GitHub Actions run tests/builds and produce artifacts. A separate **manual-only** PyPI/TestPyPI workflow is documented in [PUBLISHING.md](docs/PUBLISHING.md); configure protected environments and Trusted Publishing before using it. Nothing publishes automatically on push. Review permissions and current third-party dependency terms before distributing an APK. Debug signing on CI is ephemeral, so a CI APK may not update a locally signed installation without a signature conflict; use one controlled signing key for stable releases and never commit it. Do not uninstall an existing helper blindly to resolve a conflict if it contains data you need.

## Scope

ADB-MLKit is an OCR SDK/CLI and helper, not a general phone automation framework. Additional features should preserve offline execution, explicit device selection and least privilege. HTTP services, persistent Android daemons and cross-process request queues require separate threat-model and protocol design.
