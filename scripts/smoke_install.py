"""Install wheel in disposable venv, outside source; never contact a device."""
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def main():
    wheel = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="adb-mlkit-pip-") as tmp:
        root = Path(tmp)
        env = root / "env"
        venv.EnvBuilder(with_pip=True).create(env)
        python = env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        def run(*args):
            subprocess.run([str(python), *args], cwd=root, check=True)
        run("-m", "pip", "install", "--no-deps", str(wheel))
        run("-m", "adb_mlkit", "install", "--help")
        run("-c", "from adb_mlkit.helper import bundled_apk; from adb_mlkit import __version__; "
            "c=bundled_apk(); p=c.__enter__(); assert p.is_file(); "
            "print('PASS: installed version',__version__,'bundled APK bytes',p.stat().st_size); "
            "c.__exit__(None,None,None)")
    print("PASS: isolated wheel install, CLI and helper checksum; no ADB/device access")


if __name__ == "__main__":
    main()
