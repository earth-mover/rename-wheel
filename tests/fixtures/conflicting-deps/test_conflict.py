#!/usr/bin/env python3
"""Test that demonstrates and resolves dependency conflicts.

This script:
1. Shows the conflict when trying to install both mypkg v1 and v2
2. Renames mypkg v1 -> mypkg_v1 and mydep v1 -> mydep_v1
3. Updates mypkg_v1's dependency to require mydep_v1 (using rename_deps)
4. Installs both versions successfully
"""

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# Add src to path for importing spare_tire
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from spare_tire.rename import rename_wheel


def show_metadata(wheel_path: Path, label: str = "") -> None:
    """Print the METADATA from a wheel."""
    print(f"\n{'=' * 60}")
    print(f"METADATA for {label or wheel_path.name}")
    print("=" * 60)
    with zipfile.ZipFile(wheel_path) as zf:
        for name in zf.namelist():
            if name.endswith("/METADATA"):
                print(zf.read(name).decode())
                break


def show_init(wheel_path: Path, label: str = "") -> None:
    """Print the __init__.py from a wheel."""
    print(f"\n{'=' * 60}")
    print(f"__init__.py for {label or wheel_path.name}")
    print("=" * 60)
    with zipfile.ZipFile(wheel_path) as zf:
        for name in zf.namelist():
            if name.endswith("__init__.py"):
                print(zf.read(name).decode())
                break


def main():
    wheels_dir = Path(__file__).parent / "wheels"
    renamed_dir = Path(__file__).parent / "renamed"
    renamed_dir.mkdir(exist_ok=True)

    # Clean renamed directory
    for whl in renamed_dir.glob("*.whl"):
        whl.unlink()

    print("\n" + "=" * 60)
    print("STEP 1: Show original wheels")
    print("=" * 60)

    show_metadata(wheels_dir / "mypkg-1.0.0-py3-none-any.whl", "mypkg v1 (original)")
    show_metadata(wheels_dir / "mypkg-2.0.0-py3-none-any.whl", "mypkg v2 (original)")

    print("\n" + "=" * 60)
    print("STEP 2: Rename mydep v1 -> mydep_v1")
    print("=" * 60)

    mydep_v1 = rename_wheel(
        wheels_dir / "mydep-1.0.0-py3-none-any.whl",
        "mydep_v1",
        output_dir=renamed_dir,
    )
    print(f"Created: {mydep_v1.name}")
    show_metadata(mydep_v1, "mydep_v1 (renamed)")

    print("\n" + "=" * 60)
    print("STEP 3: Rename mypkg v1 -> mypkg_v1 WITH dependency renaming")
    print("=" * 60)

    mypkg_v1 = rename_wheel(
        wheels_dir / "mypkg-1.0.0-py3-none-any.whl",
        "mypkg_v1",
        output_dir=renamed_dir,
        rename_deps={"mydep": "mydep_v1"},  # <-- NEW: rename the dependency too!
    )
    print(f"Created: {mypkg_v1.name}")
    show_metadata(mypkg_v1, "mypkg_v1 (renamed with dep rename)")
    show_init(mypkg_v1, "mypkg_v1 (renamed with dep rename)")

    print("\n" + "=" * 60)
    print("STEP 4: Test installation in isolated venv")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_path = Path(tmpdir) / "venv"

        # Create venv
        subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        pip = venv_path / "bin" / "pip"
        python = venv_path / "bin" / "python"

        print("\n1. Installing mypkg v2 (requires mydep>=2)...")
        subprocess.run(
            [str(pip), "install", str(wheels_dir / "mydep-2.0.0-py3-none-any.whl")],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [str(pip), "install", str(wheels_dir / "mypkg-2.0.0-py3-none-any.whl")],
            check=True,
            capture_output=True,
        )
        print("   ✓ mypkg v2 installed successfully")

        print("\n2. Installing mypkg_v1 (now requires mydep_v1)...")
        subprocess.run(
            [str(pip), "install", str(mydep_v1)],
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            [str(pip), "install", str(mypkg_v1)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print("   ❌ Installation failed!")
            print(result.stderr)
            return 1

        print("   ✓ mypkg_v1 installed successfully")

        print("\n3. Verifying both versions work...")

        # Test v2
        result = subprocess.run(
            [str(python), "-c", "from mypkg import run; print(run())"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"   ✓ mypkg v2: {result.stdout.strip()}")
        else:
            print(f"   ❌ mypkg v2 failed: {result.stderr}")
            return 1

        # Test v1
        result = subprocess.run(
            [str(python), "-c", "from mypkg_v1 import run; print(run())"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"   ✓ mypkg_v1: {result.stdout.strip()}")
        else:
            print(f"   ❌ mypkg_v1 failed: {result.stderr}")
            return 1

        print("\n4. Showing installed packages...")
        result = subprocess.run(
            [str(pip), "list"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.split("\n"):
            if "mypkg" in line.lower() or "mydep" in line.lower():
                print(f"   {line}")

        print("\n" + "=" * 60)
        print("✅ SUCCESS: Both mypkg v1 and v2 installed and working!")
        print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
