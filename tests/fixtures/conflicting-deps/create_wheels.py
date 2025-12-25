#!/usr/bin/env python3
"""Create test wheels with conflicting dependencies.

Scenario:
- mypkg v1.0.0 requires mydep<2
- mypkg v2.0.0 requires mydep>=2
- mydep v1.0.0 and v2.0.0 exist

Goal: Rename mypkg v1 -> mypkg_v1 AND mydep v1 -> mydep_v1,
      updating mypkg_v1's dependency to require mydep_v1 instead.
"""

import zipfile
from pathlib import Path


def create_wheel(
    output_dir: Path,
    name: str,
    version: str,
    dependencies: list[str] | None = None,
    code: str = "",
) -> Path:
    """Create a minimal wheel file."""
    wheel_name = f"{name}-{version}-py3-none-any.whl"
    wheel_path = output_dir / wheel_name

    deps_metadata = ""
    if dependencies:
        deps_metadata = "\n".join(f"Requires-Dist: {dep}" for dep in dependencies)
        deps_metadata = "\n" + deps_metadata

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
Version: {version}{deps_metadata}
"""
        zf.writestr(f"{name}-{version}.dist-info/METADATA", metadata)

        # WHEEL
        wheel_content = """Wheel-Version: 1.0
Generator: test
Root-Is-Purelib: true
Tag: py3-none-any
"""
        zf.writestr(f"{name}-{version}.dist-info/WHEEL", wheel_content)

        # Empty RECORD (will be regenerated on rename)
        zf.writestr(f"{name}-{version}.dist-info/RECORD", "")

    return wheel_path


def main():
    output_dir = Path(__file__).parent / "wheels"
    output_dir.mkdir(exist_ok=True)

    # Clean existing wheels
    for whl in output_dir.glob("*.whl"):
        whl.unlink()

    # Create mydep v1 and v2
    create_wheel(
        output_dir,
        "mydep",
        "1.0.0",
        code='def get_value(): return "mydep v1"',
    )
    create_wheel(
        output_dir,
        "mydep",
        "2.0.0",
        code='def get_value(): return "mydep v2"',
    )

    # Create mypkg v1 (requires mydep<2)
    create_wheel(
        output_dir,
        "mypkg",
        "1.0.0",
        dependencies=["mydep<2"],
        code="""
from mydep import get_value

def run():
    return f"mypkg v1 using {get_value()}"
""",
    )

    # Create mypkg v2 (requires mydep>=2)
    create_wheel(
        output_dir,
        "mypkg",
        "2.0.0",
        dependencies=["mydep>=2"],
        code="""
from mydep import get_value

def run():
    return f"mypkg v2 using {get_value()}"
""",
    )

    print("Created wheels:")
    for whl in sorted(output_dir.glob("*.whl")):
        print(f"  {whl.name}")


if __name__ == "__main__":
    main()
