import base64
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

from adb_mlkit import ADBMLKit, ADBMLKitError, OCRResult, script_for_language
from adb_mlkit.cli import main
from adb_mlkit.client import PACKAGE

RID = "a" * 32
PNG = b"\x89PNG\r\n\x1a\n\x00\xff"


def response(**updates):
    data = dict(schema_version=1, id=RID, ok=True, text="Tiếng Việt", script="latin",
                image={"width": 100, "height": 80}, timing={"runs_ms": [100, 20]}, blocks=[])
    data.update(updates)
    return data


class SDKTests(unittest.TestCase):
    def setUp(self):
        self.client = ADBMLKit(serial="test-device")

    def test_import_construction_has_no_device_io(self):
        with patch("subprocess.run") as run:
            ADBMLKit()
        run.assert_not_called()

    def test_language_aliases(self):
        for alias, script in (("vi", "latin"), ("zh_Hant", "chinese"), ("ja", "japanese"),
                              ("ko", "korean"), ("hi", "devanagari")):
            self.assertEqual(script_for_language(alias), script)
        with self.assertRaises(ValueError):
            script_for_language("ar")

    def test_devices_and_selection(self):
        with patch.object(self.client, "_adb", return_value=b"List of devices attached\na device model:One\nb unauthorized\n"):
            self.assertEqual(self.client.devices()[1].state, "unauthorized")
            self.client.serial = None
            self.assertEqual(self.client._select_device(), "a")
        with patch.object(self.client, "devices", return_value=[]):
            with self.assertRaises(ADBMLKitError):
                self.client._select_device()

    def test_adb_errors(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(ADBMLKitError, "ADB not found"):
                self.client._adb(["version"])
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("adb", 30)):
            with self.assertRaisesRegex(ADBMLKitError, "timed out"):
                self.client._adb(["version"])
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, b"", b"denied")):
            with self.assertRaisesRegex(ADBMLKitError, "denied"):
                self.client._adb(["version"])

    def test_remote_paths_quoted(self):
        with patch.object(self.client, "_adb", return_value=b"image") as adb:
            self.client._exec("cat", "/sdcard/a'; touch oops; '.png")
        import shlex
        remote = adb.call_args.args[0][1]
        self.assertEqual(shlex.split(remote), ["cat", "/sdcard/a'; touch oops; '.png"])

    def test_invalid_options_before_device_access(self):
        invalid = [dict(runs=0), dict(runs=True), dict(rotation=12), dict(roi=[0, 0, 0, 2]),
                   dict(script="arabic"), dict(script="latin", language="vi")]
        with patch.object(self.client, "_select_device") as select:
            for options in invalid:
                with self.assertRaises(ValueError):
                    self.client.recognize_bytes(PNG, **options)
        select.assert_not_called()

    def test_success_base64_unique_directory_cleanup(self):
        with patch.object(self.client, "_select_device"), \
                patch("adb_mlkit.client.uuid.uuid4", return_value=Mock(hex=RID)), \
                patch.object(self.client, "_shell", return_value=f"package:{PACKAGE}\r\n".encode()) as shell, \
                patch.object(self.client, "_exec", return_value=json.dumps(response()).encode()):
            result = self.client.recognize_bytes(PNG, language="vi", runs=2)
        transfers = [call for call in shell.call_args_list if "payload" in call.kwargs]
        self.assertEqual(base64.b64decode(transfers[0].kwargs["payload"]), PNG)
        request = json.loads(base64.b64decode(transfers[1].kwargs["payload"]))
        self.assertEqual(request["source"]["path"], f"files/requests/{RID}/input.png")
        self.assertEqual(request["runs"], 2)
        self.assertEqual(shell.call_args.args[-2:], ("-rf", f"files/requests/{RID}"))
        self.assertEqual(result.text, "Tiếng Việt")
        self.assertIn("total_ms", result.host_timing)
        self.assertIn("cleanup_ms", result.host_timing)

    def test_failure_cleanup_preserves_original_error(self):
        with patch.object(self.client, "_select_device"), \
                patch.object(self.client, "_shell", side_effect=[f"package:{PACKAGE}\n".encode(), b"",
                                                              ADBMLKitError("upload"), ADBMLKitError("cleanup")]):
            with self.assertWarns(RuntimeWarning), self.assertRaisesRegex(ADBMLKitError, "upload"):
                self.client.recognize_bytes(PNG)

    def test_helper_presence_exact_match(self):
        for output, installed in ((b"", False),
                                  (f"package:{PACKAGE}.other\n".encode(), False),
                                  (f"package:{PACKAGE}\r\n".encode(), True)):
            with self.subTest(output=output), \
                    patch.object(self.client, "_shell", return_value=output) as shell, \
                    patch.object(self.client, "install") as install:
                self.client._ensure_helper()
                shell.assert_called_once_with("pm", "list", "packages", PACKAGE)
                if installed:
                    install.assert_not_called()
                else:
                    install.assert_called_once_with()

    def test_auto_install_before_staging_and_recheck_each_recognition(self):
        installed = False

        def install_helper():
            nonlocal installed
            installed = True
            return "Success"

        def shell_command(*args, **kwargs):
            if args[:3] == ("pm", "list", "packages"):
                return f"package:{PACKAGE}\n".encode() if installed else b""
            self.assertTrue(installed, "Helper must be installed before staging or OCR")
            return b""

        with patch.object(self.client, "_select_device"), \
                patch("adb_mlkit.client.uuid.uuid4", return_value=Mock(hex=RID)), \
                patch.object(self.client, "_shell", side_effect=shell_command) as shell, \
                patch.object(self.client, "install", side_effect=install_helper) as install, \
                patch.object(self.client, "_exec", return_value=json.dumps(response()).encode()):
            for _ in range(2):
                result = self.client.recognize_bytes(PNG)
                self.assertIn("setup_ms", result.host_timing)
                self.assertGreaterEqual(result.host_timing["total_ms"], result.host_timing["setup_ms"])
            install.assert_called_once_with()
            installed = False
            self.client.recognize_bytes(PNG)
            self.assertEqual(install.call_count, 2)
        checks = [c for c in shell.call_args_list if c.args[:3] == ("pm", "list", "packages")]
        self.assertEqual(len(checks), 3)

    def test_helper_check_error_does_not_install_or_stage(self):
        with patch.object(self.client, "_select_device"), \
                patch.object(self.client, "_shell", side_effect=ADBMLKitError("device offline")) as shell, \
                patch.object(self.client, "install") as install, \
                patch.object(self.client, "_exec") as execute:
            with self.assertRaisesRegex(ADBMLKitError, "device offline"):
                self.client.recognize_bytes(PNG)
        shell.assert_called_once_with("pm", "list", "packages", PACKAGE)
        install.assert_not_called()
        execute.assert_not_called()

    def test_auto_install_failure_does_not_stage(self):
        with patch.object(self.client, "_select_device"), \
                patch.object(self.client, "_shell", return_value=b"") as shell, \
                patch.object(self.client, "install", side_effect=ADBMLKitError("install denied")), \
                patch.object(self.client, "_exec") as execute:
            with self.assertRaisesRegex(ADBMLKitError, "install denied"):
                self.client.recognize_bytes(PNG)
        shell.assert_called_once_with("pm", "list", "packages", PACKAGE)
        execute.assert_not_called()

    def test_device_selection_failure_does_not_install(self):
        with patch.object(self.client, "devices", return_value=[]), \
                patch.object(self.client, "install") as install, \
                patch.object(self.client, "_shell") as shell:
            with self.assertRaisesRegex(ADBMLKitError, "not connected/authorized"):
                self.client.recognize_bytes(PNG)
        install.assert_not_called()
        shell.assert_not_called()

    def test_info_does_not_install_missing_helper(self):
        with patch.object(self.client, "_select_device"), \
                patch.object(self.client, "_shell", side_effect=[b"23", b"test", b""]), \
                patch.object(self.client, "install") as install:
            self.assertFalse(self.client.info()["helper_installed"])
        install.assert_not_called()

    def test_cli_json_with_auto_install(self):
        output = StringIO()
        with patch("adb_mlkit.cli.ADBMLKit", return_value=self.client), \
                patch.object(self.client, "_select_device"), \
                patch("adb_mlkit.client.uuid.uuid4", return_value=Mock(hex=RID)), \
                patch.object(self.client, "_shell", return_value=b""), \
                patch.object(self.client, "install", return_value="Success") as install, \
                patch.object(self.client, "_exec", side_effect=[PNG, json.dumps(response()).encode()]), \
                redirect_stdout(output):
            self.assertEqual(main(["recognize", "--screenshot", "--json"]), 0)
        install.assert_called_once_with()
        self.assertEqual(json.loads(output.getvalue())["text"], "Tiếng Việt")

    def test_result_validation(self):
        for data in (response(id="wrong"), response(schema_version=2), response(schema_version=True),
                     response(ok=None), response(text=5), response(blocks=[{}]),
                     response(ok=False, error="invalid")):
            with self.assertRaises(ADBMLKitError):
                OCRResult.from_dict(data, RID)
        with self.assertRaisesRegex(ADBMLKitError, "DECODE_FAILED"):
            OCRResult.from_dict(response(ok=False, error={"code": "DECODE_FAILED", "message": "bad image"}), RID)

    def test_nested_result_roundtrip(self):
        data = response(blocks=[{"text": "Hi", "lines": [{"text": "Hi", "confidence": None,
                                    "elements": [{"text": "Hi", "bounds": [0, 0, 10, 20]}]}]}])
        result = OCRResult.from_dict(data, RID)
        self.assertEqual(result.blocks[0].lines[0].elements[0].bounds, [0, 0, 10, 20])
        self.assertEqual(json.loads(result.to_json())["text"], "Tiếng Việt")

    def test_source_loaders(self):
        with patch.object(self.client, "_recognize", side_effect=lambda loader, **kw: loader()), \
                patch.object(self.client, "_exec", return_value=PNG) as execute:
            self.assertEqual(self.client.recognize_device_file("/sdcard/abc.png"), (PNG, None))
            execute.assert_called_with("cat", "/sdcard/abc.png")
            self.client.recognize_screenshot()
            execute.assert_called_with("screencap", "-p")
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "image.png"
                path.write_bytes(PNG)
                self.assertEqual(self.client.recognize_file(path), (PNG, None))
        for path in ("relative.png", "/sdcard/bad\x00.png"):
            with self.assertRaises(ValueError):
                self.client.recognize_device_file(path)

    def test_batch(self):
        with patch.object(self.client, "recognize_file", side_effect=[1, 2]) as recognize:
            self.assertEqual(self.client.batch_files(["a", "b"], language="vi"), [1, 2])
        self.assertEqual(recognize.call_count, 2)

    def test_request_matches_android_schema(self):
        with patch.object(self.client, "_select_device"), \
                patch("adb_mlkit.client.uuid.uuid4", return_value=Mock(hex=RID)), \
                patch.object(self.client, "_shell", return_value=f"package:{PACKAGE}\n".encode()) as shell, \
                patch.object(self.client, "_exec", return_value=json.dumps(response(script="japanese")).encode()):
            self.client.recognize_bytes(PNG, script="japanese", roi=(1, 2, 50, 60), rotation=90)
        transfers = [c for c in shell.call_args_list if "payload" in c.kwargs]
        request = json.loads(base64.b64decode(transfers[1].kwargs["payload"]))
        self.assertEqual(request["roi"], [1, 2, 50, 60])
        self.assertEqual(request["rotation"], 90)
        self.assertEqual(request["schema_version"], 1)
        self.assertEqual(request["script"], "japanese")

    def test_invalid_json_cleans_request(self):
        with patch.object(self.client, "_select_device"), \
                patch.object(self.client, "_shell", return_value=f"package:{PACKAGE}\n".encode()) as shell, \
                patch.object(self.client, "_exec", return_value=b"not json"):
            with self.assertRaisesRegex(ADBMLKitError, "invalid UTF-8 JSON"):
                self.client.recognize_bytes(PNG)
        self.assertEqual(shell.call_args.args[-2], "-rf")

    def test_empty_image_not_staged(self):
        with patch.object(self.client, "_select_device"), patch.object(self.client, "_shell") as shell:
            with self.assertRaises(ValueError):
                self.client.recognize_bytes(b"")
        shell.assert_not_called()

    def test_xpath_roi_rejected_without_optional_import(self):
        with self.assertRaises(ValueError):
            self.client.recognize_xpath("//*", roi=[0, 0, 10, 10])

    def test_cli_json(self):
        output = StringIO()
        with patch("adb_mlkit.cli.ADBMLKit") as client, redirect_stdout(output):
            client.return_value.recognize_screenshot.return_value = OCRResult.from_dict(response(), RID)
            self.assertEqual(main(["recognize", "--screenshot", "--language", "vi", "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["text"], "Tiếng Việt")

    def test_cli_protects_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text("original")
            with patch("adb_mlkit.cli.ADBMLKit") as client, redirect_stderr(StringIO()):
                self.assertEqual(main(["recognize", "--screenshot", "--output", str(path)]), 1)
            client.assert_not_called()
            self.assertEqual(path.read_text(), "original")

    def test_cli_sources_exclusive(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            main(["recognize", "--screenshot", "--file", "image.png"])

    def test_languages_no_adb(self):
        with patch("adb_mlkit.cli.ADBMLKit") as client, redirect_stdout(StringIO()):
            self.assertEqual(main(["languages"]), 0)
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
