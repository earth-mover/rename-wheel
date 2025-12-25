#!/usr/bin/env python3
"""Test that two different zarr versions can coexist and read the same data.

This test:
1. Creates test wheels (myreader v1 uses zarr<3, myreader v2 uses zarr>=3)
2. Renames myreader v1 -> myreader_v1 with zarr -> zarr_v2 dependency rename
3. Downloads zarr v2 and renames it to zarr_v2
4. Creates a virtual environment with both versions installed
5. Creates Zarr format 2 data and verifies both can read it

This demonstrates that spare-tire's --rename-dep feature enables
multi-version coexistence of packages with conflicting dependencies.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from spare_tire.rename import rename_wheel


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, **kwargs)


def main():
    fixture_dir = Path(__file__).parent
    wheels_dir = fixture_dir / "wheels"
    renamed_dir = fixture_dir / "renamed"

    # Clean up
    renamed_dir.mkdir(exist_ok=True)
    for whl in renamed_dir.glob("*.whl"):
        whl.unlink()

    print("=" * 70)
    print("STEP 1: Create test wheels")
    print("=" * 70)

    # Create the test wheels
    run([sys.executable, str(fixture_dir / "create_wheels.py")], check=True)

    print("\n" + "=" * 70)
    print("STEP 2: Download zarr v2 and rename to zarr_v2")
    print("=" * 70)

    # Download zarr v2
    result = run(
        [
            sys.executable,
            "-m",
            "spare_tire.cli",
            "download",
            "zarr",
            "--version",
            ">=2,<3",
            "--python-version",
            f"{sys.version_info.major}.{sys.version_info.minor}",
            "-o",
            str(renamed_dir),
        ],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"Failed to download zarr v2: {result.stderr}")
        return 1

    # Find the downloaded zarr wheel
    zarr_v2_wheels = list(renamed_dir.glob("zarr-2*.whl"))
    if not zarr_v2_wheels:
        print("No zarr v2 wheel found!")
        return 1

    zarr_v2_wheel = zarr_v2_wheels[0]
    print(f"Downloaded: {zarr_v2_wheel.name}")

    # Rename zarr -> zarr_v2
    zarr_v2_renamed = rename_wheel(zarr_v2_wheel, "zarr_v2", output_dir=renamed_dir)
    zarr_v2_wheel.unlink()  # Remove original
    print(f"Renamed to: {zarr_v2_renamed.name}")

    print("\n" + "=" * 70)
    print("STEP 3: Rename myreader v1 -> myreader_v1 with zarr -> zarr_v2")
    print("=" * 70)

    myreader_v1_renamed = rename_wheel(
        wheels_dir / "myreader-1.0.0-py3-none-any.whl",
        "myreader_v1",
        output_dir=renamed_dir,
        rename_deps={"zarr": "zarr_v2"},
    )
    print(f"Created: {myreader_v1_renamed.name}")

    # Show the metadata
    import zipfile

    with zipfile.ZipFile(myreader_v1_renamed) as zf:
        for name in zf.namelist():
            if name.endswith("/METADATA"):
                print("\nMETADATA:")
                print(zf.read(name).decode())
                break

    print("=" * 70)
    print("STEP 4: Create test environment and install both versions")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        venv_path = tmpdir / "venv"
        data_path = tmpdir / "test_data.zarr"

        # Create venv
        run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        pip = str(venv_path / "bin" / "pip")
        python = str(venv_path / "bin" / "python")

        # Upgrade pip to avoid warnings
        run([pip, "install", "--upgrade", "pip"], capture_output=True)

        print("\n1. Installing zarr v3 and myreader v2...")
        result = run(
            [pip, "install", "zarr>=3", str(wheels_dir / "myreader-2.0.0-py3-none-any.whl")],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Failed: {result.stderr}")
            return 1
        print("   ✓ myreader v2 (uses zarr>=3) installed")

        print("\n2. Installing zarr_v2 and myreader_v1...")
        result = run(
            [pip, "install", str(zarr_v2_renamed), str(myreader_v1_renamed)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Failed: {result.stderr}")
            return 1
        print("   ✓ myreader_v1 (uses zarr_v2<3) installed")

        print("\n3. Showing installed packages...")
        result = run([pip, "list"], capture_output=True, text=True)
        for line in result.stdout.split("\n"):
            if "zarr" in line.lower() or "myreader" in line.lower():
                print(f"   {line}")

        print("\n" + "=" * 70)
        print("STEP 5: Create Zarr format 2 data with zarr v3")
        print("=" * 70)

        # Create test data using zarr v3 (in format 2 for compatibility)
        create_data_script = f'''
import numpy as np
import zarr

# Create a simple array in Zarr format 2
data = np.arange(100).reshape(10, 10)
zarr.save("{data_path}", data, zarr_format=2)
print(f"Created Zarr format 2 array with shape {{data.shape}}")
print(f"Data sum: {{data.sum()}}")
'''
        result = run([python, "-c", create_data_script], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"Failed to create data: {result.stderr}")
            return 1

        print("=" * 70)
        print("STEP 6: Read data with both myreader versions")
        print("=" * 70)

        # Read with myreader v2 (zarr v3)
        read_v2_script = f'''
import myreader
import numpy as np

print(f"myreader version: {{myreader.__version__}}")
print(f"zarr version: {{myreader.get_zarr_version()}}")

data = myreader.read_data("{data_path}")
print(f"Read array with shape {{data.shape}}")
print(f"Data sum: {{data.sum()}}")
assert data.sum() == 4950, f"Expected sum 4950, got {{data.sum()}}"
print("✓ Data verified correctly!")
'''
        print("\nReading with myreader v2 (zarr v3):")
        result = run([python, "-c", read_v2_script], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"Failed: {result.stderr}")
            return 1

        # Read with myreader_v1 (zarr_v2)
        read_v1_script = f'''
import myreader_v1
import numpy as np

print(f"myreader_v1 version: {{myreader_v1.__version__}}")
print(f"zarr_v2 version: {{myreader_v1.get_zarr_version()}}")

data = myreader_v1.read_data("{data_path}")
print(f"Read array with shape {{data.shape}}")
print(f"Data sum: {{data.sum()}}")
assert data.sum() == 4950, f"Expected sum 4950, got {{data.sum()}}"
print("✓ Data verified correctly!")
'''
        print("\nReading with myreader_v1 (zarr_v2):")
        result = run([python, "-c", read_v1_script], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"Failed: {result.stderr}")
            return 1

        # Final verification - both in same script
        print("\n" + "=" * 70)
        print("STEP 7: Verify both versions work in the same Python session")
        print("=" * 70)

        both_script = f'''
import myreader
import myreader_v1

print(f"myreader v2 using zarr {{myreader.get_zarr_version()}}")
print(f"myreader_v1 using zarr_v2 {{myreader_v1.get_zarr_version()}}")

data_v2 = myreader.read_data("{data_path}")
data_v1 = myreader_v1.read_data("{data_path}")

import numpy as np
assert np.array_equal(data_v1, data_v2), "Data mismatch!"
print(f"\\n✓ Both versions read identical data (shape={{data_v1.shape}}, sum={{data_v1.sum()}})")
'''
        result = run([python, "-c", both_script], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"Failed: {result.stderr}")
            return 1

        print("\n" + "=" * 70)
        print("✅ SUCCESS: Both zarr versions coexist and read the same data!")
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
