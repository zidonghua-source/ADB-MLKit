# Pip distributions and PyPI publishing

## What is ready

The wheel and source distribution include the version-matched five-script Android APK plus a SHA-256 manifest. Recognition commands and Python recognition methods automatically install this bundled helper on the selected device if it is missing; `adb-mlkit install` or `ADBMLKit().install()` remains available for explicit installation/updates or a custom APK path. Pip installation itself has no ADB/device side effects and requires no Android build tooling for wheel users.

ADB/platform-tools must already be installed. The Python core is standard-library-only; uiautomator2 and Pillow are bundled for XPath support. A bundled APK makes the wheel tens of megabytes; check current PyPI per-file limits and redistribution terms before publishing. The checksum detects corrupted/mismatched package resources; it is not independent publisher authentication.

## Build locally

From the repository root, first build Android using the toolchain in `android/README.md`, then:

```powershell
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python scripts/prepare_package.py
python -m build
python scripts/verify_wheel.py dist/adb_mlkit-0.1.0-py3-none-any.whl
python -m twine check dist/*
```

`prepare_package.py` checks Android output metadata, source version agreement and all five model assets. It stages generated resources under `src/adb_mlkit/assets/`; these are ignored by Git but included in built distributions. Keep the APK and Gradle `output-metadata.json` together. A bare source checkout installed with `pip install .` without this staging step installs Python only; recognition then reports a missing bundled helper. It does not secretly download/build an APK. You can supply a custom APK explicitly instead.

Install the distributable into any environment:

```powershell
python -m pip install ./dist/adb_mlkit-0.1.0-py3-none-any.whl
adb-mlkit recognize --screenshot --language vi --json
```

The source distribution also carries the staged binary so pip can build a wheel without Android SDK. To modify/rebuild Android itself, clone the GitHub repository; the Python sdist is not the complete Android source distribution.

## Stable signing

Android rejects updates signed with a different key. For publication, use the **same controlled signing key** for every helper APK. The supplied workflow restores a repository secret `HELPER_DEBUG_KEYSTORE_BASE64` into the standard Android debug-keystore location before building. It must be a valid Android debug keystore (`androiddebugkey` alias, standard `android` store/key passwords); do not place its Base64 value in source code, logs or issues. This remains a debuggable developer helper, not a production Play Store signing design.

An existing locally signed installation only updates when its certificate matches. Do not automatically uninstall it or discard device data to resolve a signature mismatch. Initial CI artifact builds may use ephemeral debug keys; do not confuse those test artifacts with stable published artifacts.

## Publish with GitHub Trusted Publishing

Publishing is **automatic on push to `main`**. The release workflow bumps the SemVer version, creates a git tag and GitHub Release, which triggers the publish workflow to build and upload to PyPI via OIDC Trusted Publishing.

### How it works

```
push to main → release.yml → bump version → git tag v* → GitHub Release → publish.yml → PyPI
```

1. **`release.yml`** runs on every push to `main`:
   - Determines bump type from the latest commit message (default: patch).
   - Runs `scripts/bump_version.py` to update `pyproject.toml`, `src/adb_mlkit/__init__.py`, and `android/app/build.gradle` (versionName + versionCode).
   - Commits with `[skip ci]` to prevent re-triggering, creates tag `v{new_version}`, and pushes.
   - Creates a GitHub Release with auto-generated notes.

2. **`publish.yml`** is triggered by the tag push:
   - Verifies the tag version matches `pyproject.toml`.
   - Builds the Android helper APK, stages it with `prepare_package.py`, builds the wheel, and verifies it.
   - Publishes to PyPI using OIDC Trusted Publishing.

### Commit message conventions

| Commit message | Bump type | Example |
|---|---|---|
| Any (default) | **patch** | 0.1.0 → 0.1.1 |
| `... [minor]` at end | **minor** | 0.1.0 → 0.2.0 |
| `... [major]` at end | **major** | 0.1.0 → 1.0.0 |
| Starts with `[skip ci]` | skipped | release commit → no re-trigger |

### Manual publish

`workflow_dispatch` is still available to re-publish or target TestPyPI:

1. Dispatch **Publish Python package**, target `testpypi`, on any branch.
2. After validation, dispatch target `pypi` and approve the protected environment.

### Owner setup required

1. Create accounts at PyPI and TestPyPI; verify you may register/use `adb-mlkit`. This repository does not establish ownership or name availability.
2. Configure a Trusted Publisher/pending publisher on each index:
   - Owner: `zidonghua-source`
   - Repository: `ADB-MLKit`
   - Workflow: `publish.yml`
   - Environment: `testpypi` or `pypi`, respectively.
3. Create corresponding GitHub environments and configure **required reviewers** for publication. Environment protection is a GitHub setting; YAML alone does not enforce human approval.
4. Add the stable helper-keystore repository secret `HELPER_DEBUG_KEYSTORE_BASE64`. Restrict who can dispatch workflows/change repository code; build jobs run repository code with access to that signing key.
5. Review Google's redistribution terms and the complete generated package. PyPI release files cannot be overwritten.

After a real PyPI release:

```text
python -m pip install adb-mlkit
adb-mlkit recognize --screenshot --language vi --json
```

The helper APK is installed automatically on the device during the first OCR call. To install or update it explicitly, use `adb-mlkit install`.

For TestPyPI, test the core with `--no-deps --index-url https://test.pypi.org/simple/`; normal dependencies generally live on PyPI. Avoid casually mixing public indexes with `--extra-index-url` because name collisions can select unintended packages.
