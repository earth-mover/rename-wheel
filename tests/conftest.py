"""Shared fixtures for wheel-rename tests."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


def create_test_wheel(
    tmp_path: Path,
    pkg_name: str,
    version: str,
    *,
    with_submodule: bool = True,
) -> Path:
    """Create a test wheel with version-specific identifiers.

    The wheel has cross-module imports that will need to be renamed:
    - __init__.py imports from core
    - core.py imports from utils
    - sub/feature.py imports from core

    Each module has functions that return version identifiers.
    """
    wheel_name = f"{pkg_name}-{version}-py3-none-any.whl"
    wheel_path = tmp_path / wheel_name

    with zipfile.ZipFile(wheel_path, "w") as zf:
        # __init__.py - imports core and exposes version
        init_content = f'''"""Test package {pkg_name} version {version}."""

from {pkg_name}.core import main_func

__version__ = "{version}"

def get_version():
    """Return the package version."""
    return __version__
'''
        zf.writestr(f"{pkg_name}/__init__.py", init_content)

        # core.py - imports utils, provides version chain verification
        core_content = f'''"""Core module for {pkg_name}."""

from {pkg_name}.utils import helper, get_utils_version

VERSION_TAG = "{version}"

def main_func():
    """Main function."""
    return f"main_func from {{VERSION_TAG}}"

def get_helper_version():
    """Get version from the helper module."""
    return get_utils_version()

def get_core_version():
    """Get this module's version tag."""
    return VERSION_TAG
'''
        zf.writestr(f"{pkg_name}/core.py", core_content)

        # utils.py - no imports, provides version identifier
        utils_content = f'''"""Utilities module for {pkg_name}."""

VERSION_TAG = "{version}"

def helper():
    """Helper function."""
    return f"helper from {{VERSION_TAG}}"

def get_utils_version():
    """Return this module's version tag."""
    return VERSION_TAG
'''
        zf.writestr(f"{pkg_name}/utils.py", utils_content)

        if with_submodule:
            # sub/__init__.py - imports feature
            sub_init_content = f'''"""Submodule for {pkg_name}."""

from {pkg_name}.sub.feature import Feature
'''
            zf.writestr(f"{pkg_name}/sub/__init__.py", sub_init_content)

            # sub/feature.py - imports from parent core module
            feature_content = f'''"""Feature module in subpackage."""

from {pkg_name}.core import get_core_version

VERSION_TAG = "{version}"

class Feature:
    """A feature class."""

    def __init__(self):
        self.version = VERSION_TAG

def core_version():
    """Get version from the core module (tests cross-module imports)."""
    return get_core_version()

def get_feature_version():
    """Get this module's version tag."""
    return VERSION_TAG
'''
            zf.writestr(f"{pkg_name}/sub/feature.py", feature_content)

        # dist-info
        metadata = f"""Metadata-Version: 2.1
Name: {pkg_name}
Version: {version}
"""
        zf.writestr(f"{pkg_name}-{version}.dist-info/METADATA", metadata)

        wheel_info = """Wheel-Version: 1.0
Generator: test
Root-Is-Purelib: true
Tag: py3-none-any
"""
        zf.writestr(f"{pkg_name}-{version}.dist-info/WHEEL", wheel_info)

        # Empty RECORD (not validating hashes in tests)
        zf.writestr(f"{pkg_name}-{version}.dist-info/RECORD", "")

    return wheel_path


@pytest.fixture
def create_wheel() -> Callable[[Path, str, str, bool], Path]:
    """Fixture that returns the create_test_wheel function."""
    return create_test_wheel


@pytest.fixture
def dual_install_venv(tmp_path: Path) -> Path:
    """Create a fresh venv for dual-install testing.

    Returns the venv directory path. Use run_in_venv() to execute code.
    """
    venv_dir = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        capture_output=True,
    )
    return venv_dir


def get_venv_python(venv_dir: Path) -> Path:
    """Get the Python executable path for a venv."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def get_venv_pip(venv_dir: Path) -> Path:
    """Get the pip executable path for a venv."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"


def run_in_venv(venv_dir: Path, code: str) -> subprocess.CompletedProcess[str]:
    """Execute Python code in the venv and return the result.

    Args:
        venv_dir: Path to the venv directory
        code: Python code to execute

    Returns:
        CompletedProcess with stdout/stderr
    """
    python = get_venv_python(venv_dir)
    return subprocess.run(
        [str(python), "-c", code],
        capture_output=True,
        text=True,
    )


def install_wheel_in_venv(venv_dir: Path, wheel_path: Path) -> None:
    """Install a wheel in the venv."""
    pip = get_venv_pip(venv_dir)
    result = subprocess.run(
        [str(pip), "install", str(wheel_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to install {wheel_path}: {result.stderr}")
