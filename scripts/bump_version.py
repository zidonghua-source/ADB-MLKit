"""Bump SemVer version in pyproject.toml, __init__.py, and build.gradle."""
import argparse
import re
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src" / "adb_mlkit" / "__init__.py"
GRADLE = ROOT / "android" / "app" / "build.gradle"

PYPROJECT_RE = re.compile(r'^version = "([^"]+)"', re.M)
INIT_RE = re.compile(r'__version__ = "([^"]+)"')
GRADLE_NAME_RE = re.compile(r"versionName\s*=\s*'([^']+)'")
GRADLE_CODE_RE = re.compile(r"versionCode\s*=\s*(\d+)")


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


def current_str(version: tuple[int, int, int]) -> str:
    return f"{version[0]}.{version[1]}.{version[2]}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bump-type", choices=["major", "minor", "patch"], default="patch")
    parser.add_argument("--dry-run", action="store_true", help="Print new version without writing files")
    args = parser.parse_args()

    pyproject = PYPROJECT.read_text(encoding="utf-8")
    current = parse_version(pyproject)
    old_str = current_str(current)
    new = bump(current, args.bump_type)
    new_str = current_str(new)

    if new == current:
        print(new_str)
        return

    # pyproject.toml: version = "x.y.z"
    m = PYPROJECT_RE.search(pyproject)
    if not m or m.group(1) != old_str:
        sys.exit(f"Expected version {old_str} in {PYPROJECT}")
    if not args.dry_run:
        PYPROJECT.write_text(PYPROJECT_RE.sub(f'version = "{new_str}"', pyproject, count=1),
                             encoding="utf-8")

    # src/adb_mlkit/__init__.py: __version__ = "x.y.z"
    init = INIT.read_text(encoding="utf-8")
    m = INIT_RE.search(init)
    if not m or m.group(1) != old_str:
        sys.exit(f"Expected version {old_str} in {INIT}")
    if not args.dry_run:
        INIT.write_text(INIT_RE.sub(f'__version__ = "{new_str}"', init, count=1), encoding="utf-8")

    # android/app/build.gradle: versionName = 'x.y.z' and versionCode = N
    gradle = GRADLE.read_text(encoding="utf-8")
    m = GRADLE_NAME_RE.search(gradle)
    if not m or m.group(1) != old_str:
        sys.exit(f"Expected versionName {old_str} in {GRADLE}")
    if not args.dry_run:
        gradle = GRADLE_NAME_RE.sub(f"versionName = '{new_str}'", gradle, count=1)
        code = GRADLE_CODE_RE.search(gradle)
        if code:
            gradle = GRADLE_CODE_RE.sub(lambda mm: f"versionCode = {int(mm.group(1)) + 1}",
                                        gradle, count=1)
        GRADLE.write_text(gradle, encoding="utf-8")

    # Verify all three files now agree on the new version.
    if not args.dry_run:
        for path, pattern in ((PYPROJECT, PYPROJECT_RE), (INIT, INIT_RE), (GRADLE, GRADLE_NAME_RE)):
            content = path.read_text(encoding="utf-8")
            if not pattern.search(content) or pattern.search(content).group(1) != new_str:
                sys.exit(f"Version sync failed: {path} does not contain {new_str}")

    print(new_str)


if __name__ == "__main__":
    main()