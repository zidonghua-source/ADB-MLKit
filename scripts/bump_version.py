"""Bump SemVer version in pyproject.toml, __init__.py, and build.gradle."""
import argparse
import re
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src" / "adb_mlkit" / "__init__.py"
GRADLE = ROOT / "android" / "app" / "build.gradle"


def parse_version(text: str) -> tuple[int, int, int]:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    if not m:
        sys.exit("Cannot find semver string in version files")
    return int(m[1]), int(m[2]), int(m[3])


def bump(version: tuple[int, int, int], kind: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if kind == "major":
        return major + 1, 0, 0
    if kind == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def replace_version(text: str, new: str) -> str:
    """Replace the first semver-like string in *text*."""
    return re.sub(r"\d+\.\d+\.\d+", new, text, count=1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bump-type", choices=["major", "minor", "patch"], default="patch")
    parser.add_argument("--dry-run", action="store_true", help="Print new version without writing files")
    args = parser.parse_args()

    current = parse_version(PYPROJECT.read_text(encoding="utf-8"))
    new = bump(current, args.bump_type)
    new_str = f"{new[0]}.{new[1]}.{new[2]}"
    old_str = f"{current[0]}.{current[1]}.{current[2]}"

    if new == current:
        print(new_str)
        return

    files = [PYPROJECT, INIT, GRADLE]
    for path in files:
        content = path.read_text(encoding="utf-8")
        if old_str not in content:
            sys.exit(f"Version {old_str} not found in {path}")
        if not args.dry_run:
            path.write_text(replace_version(content, new_str), encoding="utf-8")

    if not args.dry_run:
        # Increment versionCode in build.gradle
        content = GRADLE.read_text(encoding="utf-8")
        m = re.search(r"versionCode\s*=\s*(\d+)", content)
        if m:
            old_code = int(m[1])
            content = content.replace(f"versionCode = {old_code}", f"versionCode = {old_code + 1}", 1)
            GRADLE.write_text(content, encoding="utf-8")

    print(new_str)


if __name__ == "__main__":
    main()
