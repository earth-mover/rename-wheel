#!/usr/bin/env python3
"""Create test wheels that use different zarr versions.

Creates two packages:
- myreader v1: uses zarr<3 API (zarr.open(), array[:])
- myreader v2: uses zarr>=3 API (zarr.open_array(), array[:])

Both should be able to read the same Zarr format 2 data.
"""

import zipfile
from pathlib import Path


def create_wheel(
    output_dir: Path,
    name: str,
    version: str,
    dependencies: list[str],
    code: str,
) -> Path:
    """Create a minimal wheel file."""
    wheel_name = f"{name}-{version}-py3-none-any.whl"
    wheel_path = output_dir / wheel_name

    deps_metadata = "\n".join(f"Requires-Dist: {dep}" for dep in dependencies)

    with zipfile.ZipFile(wheel_path, "w") as zf:
        # Package __init__.py
        init_code = f'''"""Package {name} version {version}."""
__version__ = "{version}"
{code}
'''
        zf.writestr(f"{name}/__init__.py", init_code)

        # METADATA
        metadata = f"""Metadata-Version: 2.1
Name: {name}
Version: {version}
{deps_metadata}
"""
        zf.writestr(f"{name}-{version}.dist-info/METADATA", metadata)

        # WHEEL
        wheel_content = """Wheel-Version: 1.0
Generator: test
Root-Is-Purelib: true
Tag: py3-none-any
"""
        zf.writestr(f"{name}-{version}.dist-info/WHEEL", wheel_content)

        # Empty RECORD
        zf.writestr(f"{name}-{version}.dist-info/RECORD", "")

    return wheel_path


def main():
    output_dir = Path(__file__).parent / "wheels"
    output_dir.mkdir(exist_ok=True)

    # Clean existing wheels
    for whl in output_dir.glob("*.whl"):
        whl.unlink()

    # myreader v1 - uses zarr v2 API
    # zarr v2 API: zarr.open() returns array directly for simple cases
    create_wheel(
        output_dir,
        "myreader",
        "1.0.0",
        dependencies=["zarr>=2.0,<3"],
        code='''
import zarr

def read_data(path: str):
    """Read data using zarr v2 API."""
    # zarr v2: open() can return array or group
    store = zarr.open(path, mode="r")
    if hasattr(store, "shape"):
        # It's an array
        return store[:]
    else:
        # It's a group, get the "data" array
        return store["data"][:]

def get_zarr_version():
    """Return the zarr version being used."""
    return zarr.__version__
''',
    )

    # myreader v2 - uses zarr v3 API
    # zarr v3 API: zarr.open() returns Group, use open_array for arrays
    create_wheel(
        output_dir,
        "myreader",
        "2.0.0",
        dependencies=["zarr>=3"],
        code='''
import zarr

def read_data(path: str):
    """Read data using zarr v3 API."""
    # zarr v3: open_group() for groups, open_array() for arrays
    # But we can still use open() which returns appropriate type
    store = zarr.open(path, mode="r")
    if hasattr(store, "shape"):
        # It's an array
        return store[:]
    else:
        # It's a group, get the "data" array
        return store["data"][:]

def get_zarr_version():
    """Return the zarr version being used."""
    return zarr.__version__
''',
    )

    print("Created wheels:")
    for whl in sorted(output_dir.glob("*.whl")):
        print(f"  {whl.name}")


if __name__ == "__main__":
    main()
