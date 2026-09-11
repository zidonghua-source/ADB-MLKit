from contextlib import contextmanager, redirect_stdout
from io import StringIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adb_mlkit import ADBMLKit, ADBMLKitError, __version__
from adb_mlkit.cli import main
from adb_mlkit.helper import bundled_apk


class PackagingTests(unittest.TestCase):
    def assets(self, directory, content=b"test apk", digest=None, version=__version__):
        assets = Path(directory) / "assets"
        assets.mkdir()
        (assets / "adb-mlkit.apk").write_bytes(content)
        (assets / "helper.json").write_text(json.dumps({
            "package": "io.github.adbmlkit.helper", "version": version,
            "sha256": digest or hashlib.sha256(content).hexdigest(),
        }))

    def test_verify_resource(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assets(tmp)
            with patch("adb_mlkit.helper.files", return_value=Path(tmp)):
                with bundled_apk() as apk:
                    self.assertEqual(apk.read_bytes(), b"test apk")

    def test_missing_resource(self):
        with tempfile.TemporaryDirectory() as tmp, patch("adb_mlkit.helper.files", return_value=Path(tmp)):
            with self.assertRaisesRegex(ADBMLKitError, "missing"):
                with bundled_apk():
                    pass

    def test_modified_resource_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assets(tmp, digest="bad")
            with patch("adb_mlkit.helper.files", return_value=Path(tmp)):
                with self.assertRaisesRegex(ADBMLKitError, "checksum"):
                    with bundled_apk():
                        pass

    def test_version_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assets(tmp, version="0.0.0")
            with patch("adb_mlkit.helper.files", return_value=Path(tmp)):
                with self.assertRaisesRegex(ADBMLKitError, "version mismatch"):
                    with bundled_apk():
                        pass

    def test_default_install_only_explicit(self):
        client = ADBMLKit(serial="test")
        with tempfile.TemporaryDirectory() as tmp:
            self.assets(tmp)
            with patch("adb_mlkit.helper.files", return_value=Path(tmp)), \
                    patch.object(client, "_select_device"), \
                    patch.object(client, "_adb", return_value=b"Success") as adb:
                self.assertEqual(client.install(), "Success")
            self.assertEqual(adb.call_args.args[0][:2], ["install", "-r"])

    def test_cli_optional_apk(self):
        with patch("adb_mlkit.cli.ADBMLKit") as client, redirect_stdout(StringIO()):
            self.assertEqual(main(["install"]), 0)
        client.return_value.install.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()
