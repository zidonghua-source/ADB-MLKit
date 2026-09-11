"""Version-matched Android helper resource. No network or device side effects."""
from contextlib import contextmanager
import hashlib
from importlib.resources import as_file, files
import json

from .models import ADBMLKitError


@contextmanager
def bundled_apk():
    """Yield a verified filesystem path, including from zip-based installations."""
    root = files("adb_mlkit").joinpath("assets")
    apk = root.joinpath("adb-mlkit.apk")
    manifest = root.joinpath("helper.json")
    if not apk.is_file() or not manifest.is_file():
        raise ADBMLKitError(
            "Bundled helper APK is missing. Install an official wheel, or build Android "
            "and run scripts/prepare_package.py before packaging. "
            "You can also use adb-mlkit install /path/to/helper.apk."
        )
    try:
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        from . import __version__
        if metadata["package"] != "io.github.adbmlkit.helper" or metadata["version"] != __version__:
            raise ValueError("helper/package version mismatch")
        with as_file(apk) as path:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != metadata["sha256"]:
                raise ValueError("helper APK checksum mismatch")
            yield path
    except (KeyError, ValueError, OSError) as exc:
        raise ADBMLKitError(f"Cannot verify bundled helper: {exc}") from exc
