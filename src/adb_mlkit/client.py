"""ADB transport and synchronous OCR API. No device access at import time."""
import base64
from contextlib import contextmanager
from io import BytesIO
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import threading
from time import perf_counter
import uuid
import warnings

from .models import ADBMLKitError, Device, OCRResult, SCRIPTS, script_for_language

PACKAGE = "io.github.adbmlkit.helper"
RUNNER = f"{PACKAGE}/.OcrInstrumentation"
MAX_INPUT_BYTES = 32 * 1024 * 1024


class ADBMLKit:
    """One client serializes its requests; use one client per device.

    timeout controls ordinary ADB calls. Recognition allows at least
    60 + runs * 35 seconds for Android process startup and engine timeouts.
    Independent clients/processes must not invoke instrumentation concurrently
    on the same device.
    """
    def __init__(self, serial=None, adb_path=None, timeout=30, script="latin"):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if script not in SCRIPTS:
            raise ValueError(f"script must be one of {SCRIPTS}")
        self.serial = serial
        self.adb_path = str(adb_path or os.environ.get("ADB_PATH") or shutil.which("adb") or "adb")
        self.timeout = timeout
        self.script = script
        self._lock = threading.RLock()

    def _adb(self, args, payload=None, timeout=None, selected=True):
        command = [self.adb_path]
        if selected:
            if not self.serial:
                self._select_device()
            command += ["-s", self.serial]
        try:
            result = subprocess.run(command + list(args), input=payload, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=timeout or self.timeout, check=False)
        except FileNotFoundError as exc:
            raise ADBMLKitError("ADB not found. Install Android platform-tools or set ADB_PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise ADBMLKitError(f"ADB timed out after {exc.timeout}s") from exc
        if result.returncode:
            message = (result.stderr + result.stdout).decode("utf-8", errors="replace").strip()
            raise ADBMLKitError(f"ADB exit {result.returncode}: {message}")
        return result.stdout

    def _shell(self, *args, payload=None, timeout=None):
        return self._adb(["shell", " ".join(shlex.quote(str(arg)) for arg in args)], payload, timeout)

    def _exec(self, *args):
        return self._adb(["exec-out", " ".join(shlex.quote(str(arg)) for arg in args)])

    def devices(self):
        output = self._adb(["devices", "-l"], selected=False).decode("utf-8", errors="replace")
        result = []
        for line in output.splitlines():
            if not line.strip() or line.startswith(("List of devices", "*")):
                continue
            parts = line.split(maxsplit=2)
            if len(parts) >= 2:
                result.append(Device(parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
        return result

    def _select_device(self):
        devices = self.devices()
        available = [d.serial for d in devices if d.state == "device"]
        if self.serial:
            if self.serial not in available:
                raise ADBMLKitError(f"Device {self.serial!r} is not connected/authorized")
        elif len(available) == 1:
            self.serial = available[0]
        else:
            raise ADBMLKitError(f"Expected one authorized device, found {available}; specify serial")
        return self.serial

    def _helper_installed(self):
        packages = self._shell("pm", "list", "packages", PACKAGE).splitlines()
        return f"package:{PACKAGE}".encode() in packages

    def _ensure_helper(self):
        if not self._helper_installed():
            self.install()

    def info(self):
        with self._lock:
            self._select_device()
            return {"serial": self.serial,
                    "android_api": self._shell("getprop", "ro.build.version.sdk").decode().strip(),
                    "model": self._shell("getprop", "ro.product.model").decode().strip(),
                    "helper_installed": self._helper_installed(),
                    "package": PACKAGE, "scripts": list(SCRIPTS), "protocol_version": 1}

    def install(self, apk=None):
        """Explicitly install the bundled helper, or a caller-supplied APK."""
        if apk is None:
            from .helper import bundled_apk
            with bundled_apk() as path:
                return self.install(path)
        path = Path(apk).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        with self._lock:
            self._select_device()
            output = self._adb(["install", "-r", str(path)], timeout=max(180, self.timeout)).decode(errors="replace")
            if "Success" not in output:
                raise ADBMLKitError(f"APK installation not confirmed: {output}")
            return output.strip()

    @staticmethod
    def _options(script, language, default_script, roi, rotation, runs):
        if script is not None and language is not None:
            raise ValueError("Choose script or language, not both")
        script = script_for_language(language) if language else (script or default_script)
        if script not in SCRIPTS:
            raise ValueError(f"script must be one of {SCRIPTS}")
        if type(rotation) is not int or rotation not in (0, 90, 180, 270):
            raise ValueError("rotation must be 0, 90, 180 or 270")
        if type(runs) is not int or not 1 <= runs <= 30:
            raise ValueError("runs must be an integer from 1 to 30")
        if roi is not None:
            if len(roi) != 4 or any(type(v) is not int for v in roi):
                raise ValueError("roi must contain four integer pixel coordinates")
            l, t, r, b = roi
            if not (0 <= l < r and 0 <= t < b):
                raise ValueError("roi must be a nonempty positive rectangle")
            roi = list(roi)
        return script, roi

    @contextmanager
    def _stage(self, timings, name):
        start = perf_counter()
        try:
            yield
        finally:
            timings[name] = (perf_counter() - start) * 1000

    def _recognize(self, loader, *, script=None, language=None, roi=None, rotation=0, runs=1):
        script, roi = self._options(script, language, self.script, roi, rotation, runs)
        with self._lock:
            started = perf_counter()
            timing = {}
            self._select_device()
            request_id = uuid.uuid4().hex
            directory = f"files/requests/{request_id}"
            image_path = f"{directory}/input.png"
            result = None
            staged = False
            try:
                with self._stage(timing, "load_ms"):
                    image, source_roi = loader()
                    if source_roi is not None:
                        if roi is not None:
                            raise ValueError("An explicit ROI cannot be combined with XPath bounds")
                        roi = list(source_roi)
                    if not isinstance(image, bytes) or not 0 < len(image) <= MAX_INPUT_BYTES:
                        raise ValueError("Input must contain 1..32 MiB of encoded image bytes")
                with self._stage(timing, "setup_ms"):
                    self._ensure_helper()
                request = {"schema_version": 1, "id": request_id, "script": script,
                           "source": {"type": "private", "path": image_path},
                           "rotation": rotation, "roi": roi, "runs": runs}
                with self._stage(timing, "transfer_ms"):
                    self._shell("run-as", PACKAGE, "mkdir", "-p", directory)
                    staged = True
                    for path, data in ((image_path, image),
                                       (f"{directory}/request.json", json.dumps(request).encode("utf-8"))):
                        # ASCII transport avoids Windows binary-stdin conversion/truncation.
                        self._shell("run-as", PACKAGE, "sh", "-c", f"base64 -d > {path}",
                                    payload=base64.b64encode(data))
                with self._stage(timing, "instrumentation_ms"):
                    output = self._shell("am", "instrument", "-w", "-e", "request_id", request_id,
                                         RUNNER, timeout=max(self.timeout, 60 + 35 * runs))
                with self._stage(timing, "result_ms"):
                    try:
                        raw = self._exec("run-as", PACKAGE, "cat", f"{directory}/result.json")
                    except ADBMLKitError as exc:
                        raise ADBMLKitError("No result from helper: " + output.decode("utf-8", errors="replace")) from exc
                    try:
                        data = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise ADBMLKitError("Helper returned invalid UTF-8 JSON") from exc
                    result = OCRResult.from_dict(data, request_id)
            finally:
                if staged:
                    with self._stage(timing, "cleanup_ms"):
                        try:
                            self._shell("run-as", PACKAGE, "rm", "-rf", directory)
                        except ADBMLKitError as exc:
                            warnings.warn(f"Could not remove own request {request_id}: {exc}", RuntimeWarning)
                timing["total_ms"] = (perf_counter() - started) * 1000
            result.host_timing = timing
            return result

    def recognize_bytes(self, data: bytes, **options) -> OCRResult:
        return self._recognize(lambda: (data, None), **options)

    def recognize_file(self, path, **options) -> OCRResult:
        def load():
            with Path(path).open("rb") as stream:
                return stream.read(MAX_INPUT_BYTES + 1), None
        return self._recognize(load, **options)

    def recognize_device_file(self, path: str, **options) -> OCRResult:
        if not isinstance(path, str) or not path.startswith("/") or "\x00" in path:
            raise ValueError("device path must be an absolute Android path without NUL")
        return self._recognize(lambda: (self._exec("cat", path), None), **options)

    def recognize_screenshot(self, **options) -> OCRResult:
        return self._recognize(lambda: (self._exec("screencap", "-p"), None), **options)

    def recognize_xpath(self, xpath: str, xpath_timeout=10, **options) -> OCRResult:
        if not xpath or xpath_timeout <= 0:
            raise ValueError("xpath and a positive xpath_timeout are required")
        if options.get("roi") is not None:
            raise ValueError("XPath supplies its own ROI")
        def load():
            try:
                import uiautomator2 as u2
            except ImportError as exc:
                raise ADBMLKitError('Install optional UI support: pip install "adb-mlkit[ui]"') from exc
            device = u2.connect(self.serial)
            bounds = tuple(device.xpath(xpath).get(timeout=xpath_timeout).bounds)
            image = device.screenshot().convert("RGB")
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue(), bounds
        return self._recognize(load, **options)

    def batch_files(self, paths, **options):
        """Sequential fail-fast batch; each image has its own invocation/timing."""
        return [self.recognize_file(path, **options) for path in paths]
