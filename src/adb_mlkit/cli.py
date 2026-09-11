"""Command-line interface; JSON goes to stdout, diagnostics to stderr."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .client import ADBMLKit
from .models import ADBMLKitError, LANGUAGES, SCRIPTS


def parser():
    root = argparse.ArgumentParser(prog="adb-mlkit", description="Offline Android OCR over ADB")
    root.add_argument("--serial", help="Device serial; required if multiple devices are authorized")
    root.add_argument("--adb-path", help="ADB executable (otherwise ADB_PATH or PATH)")
    root.add_argument("--timeout", type=float, default=30)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("devices", help="List attached devices and authorization states")
    commands.add_parser("info", help="Inspect selected device and helper installation")
    commands.add_parser("languages", help="List scripts and convenience language aliases")
    install = commands.add_parser("install", help="Explicitly install bundled helper or a custom APK")
    install.add_argument("apk", type=Path, nargs="?", help="Optional custom APK; default is the bundled helper")
    for name in ("recognize", "batch"):
        command = commands.add_parser(name, description="Read text; automatically install the bundled helper if missing")
        if name == "recognize":
            source = command.add_mutually_exclusive_group(required=True)
            source.add_argument("--file", type=Path)
            source.add_argument("--device-file", help="Absolute path readable by Android shell")
            source.add_argument("--screenshot", action="store_true")
            source.add_argument("--xpath", help="Optional uiautomator2 lookup; OCR reads the text")
        else:
            command.add_argument("files", type=Path, nargs="+")
        selection = command.add_mutually_exclusive_group()
        selection.add_argument("--script", choices=SCRIPTS)
        selection.add_argument("--language", choices=sorted(LANGUAGES))
        command.add_argument("--roi", nargs=4, type=int, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
        command.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=0)
        command.add_argument("--runs", type=int, choices=range(1, 31), default=1, metavar="1..30")
        command.add_argument("--json", action="store_true", help="Structured result; human timing stays off stdout")
        command.add_argument("--output", type=Path, help="Save result locally instead of stdout")
        command.add_argument("--overwrite", action="store_true", help="Allow replacing an existing output file")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "languages":
            print(json.dumps({"scripts": SCRIPTS, "language_aliases": LANGUAGES}, indent=2))
            return 0
        if getattr(args, "output", None) and args.output.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists: {args.output}; choose another path or --overwrite")
        client = ADBMLKit(serial=args.serial, adb_path=args.adb_path, timeout=args.timeout)
        if args.command == "devices":
            print(json.dumps([asdict(d) for d in client.devices()], ensure_ascii=False, indent=2))
            return 0
        if args.command == "info":
            print(json.dumps(client.info(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "install":
            print(client.install(args.apk))
            return 0
        options = dict(script=args.script, language=args.language, roi=args.roi,
                       rotation=args.rotation, runs=args.runs)
        if args.command == "batch":
            results = client.batch_files(args.files, **options)
        elif args.file:
            results = [client.recognize_file(args.file, **options)]
        elif args.device_file:
            results = [client.recognize_device_file(args.device_file, **options)]
        elif args.screenshot:
            results = [client.recognize_screenshot(**options)]
        else:
            results = [client.recognize_xpath(args.xpath, **options)]
        if args.json:
            data = [r.to_dict() for r in results]
            text = json.dumps(data if args.command == "batch" else data[0], ensure_ascii=False, indent=2)
        else:
            text = "\n\n".join(r.text for r in results)
            for result in results:
                print(json.dumps({"id": result.id, "android_timing": result.timing,
                                  "host_timing": result.host_timing}), file=sys.stderr)
        if args.output:
            mode = "w" if args.overwrite else "x"
            with args.output.open(mode, encoding="utf-8") as stream:
                stream.write(text + "\n")
        else:
            print(text)
        return 0
    except (ADBMLKitError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
