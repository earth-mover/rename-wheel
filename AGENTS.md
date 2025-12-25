# Agent Instructions for spare-tire

This document provides context and guidance for AI assistants working on the spare-tire project.

## Project Overview

**spare-tire** is a tool to rename Python wheel packages for multi-version installation. The primary use case is regression testing where you need both `icechunk` (v2) and `icechunk_v1` (renamed v1) installed simultaneously.

## Key Technical Concepts

### Wheel File Format (PEP 427)

- Wheels are ZIP files with `.whl` extension
- Structure: `{package}/`, `{package}-{version}.dist-info/`
- METADATA file contains package name, version, dependencies
- RECORD file contains SHA256 hashes of all files
- WHEEL file contains wheel metadata (generator, tags)

### Compiled Extensions Challenge

- `.so`/`.pyd` files contain `PyInit_{name}` symbol baked into binary
- This symbol MUST match the filename for Python to load the extension
- **Workaround**: If extension uses underscore prefix (e.g., `_icechunk_python.cpython-*.so`), parent directory can be renamed while keeping the `.so` filename unchanged
- Python imports `icechunk_v1._icechunk_python` and finds `PyInit__icechunk_python` correctly

### PEP 503 Simple Repository API

- Package indexes use this standard (PyPI, Anaconda.org)
- Root endpoint `/simple/` lists all projects
- Project endpoint `/simple/{project}/` lists all wheels
- Supports JSON variant (PEP 691) but HTML is most common

## Codebase Structure

```text
src/spare_tire/
├── __init__.py      # Package exports
├── cli.py           # Click-based CLI with rich output
├── download.py      # PEP 503 index client using pypi-simple
├── rename.py        # Core wheel manipulation logic
└── server/          # Proxy server for on-the-fly renaming
    ├── __init__.py
    ├── app.py       # FastAPI application with PEP 503 endpoints
    ├── config.py    # Configuration (TOML + CLI) with name normalization
    ├── html.py      # PEP 503 HTML generation
    ├── stream.py    # Wheel streaming and on-the-fly renaming
    └── upstream.py  # Async HTTP client for upstream indexes

tests/
├── conftest.py              # Shared fixtures for venv creation
├── test_rename.py           # Unit tests for rename functions
├── test_integration.py      # Import rewriting tests
├── test_dual_install.py     # Multi-package isolation tests
├── test_icechunk_integration.py  # Real icechunk wheel tests
└── fixtures/
    ├── dual-install/        # Example project for multi-version install
    │   ├── pyproject.toml   # uv config with both icechunk versions
    │   └── README.md        # Usage documentation
    └── conflicting-deps/    # Test case for dependency conflicts
        ├── create_wheels.py # Creates test wheels with conflicting deps
        ├── test_conflict.py # Demonstrates --rename-dep solution
        └── wheels/          # Generated test wheels
```

## Important Functions

### `rename.py`

- `rename_wheel(wheel_path, new_name, output_dir, update_imports, rename_deps)` - Main entry point
  - `rename_deps`: Optional dict mapping old dep names to new names (e.g., `{"mydep": "mydep_v1"}`)
- `_update_python_imports(content, old_name, new_name)` - Regex-based import rewriting
- `_update_metadata(content, old_name, new_name, rename_deps)` - Update METADATA including Requires-Dist
- `inspect_wheel(wheel_path)` - Analyze wheel structure, detect extensions
- `_compute_record_hash(data)` - SHA256 for RECORD file

### `download.py`

- `download_compatible_wheel(package, output_dir, index_url, version, python_version)` - Download best match
  - `python_version`: Optional target Python version (e.g., "3.12") for cross-version downloads
- `best_wheel(packages, compatible_tags)` - Select most compatible wheel
- `parse_wheel_tags(filename)` - Extract platform tags from wheel name
- `get_compatible_tags(python_version)` - Get platform tags, optionally for a specific Python version

### `cli.py`

- Explicit subcommands: `rename`, `download`, `inspect`, `serve`
- Rich console output with 🛞 and 🔧 emojis for theming

## Testing Patterns

### Dual-Install Tests

Tests create isolated venvs and install both original and renamed packages to verify:

1. Both packages import without errors
2. Module `__file__` paths are distinct
3. Internal import chains stay within each package
4. No `sys.modules` contamination
5. No leaked references to old package name in renamed package

### Test Wheel Creation

Use `conftest.create_test_wheel()` to create synthetic wheels with version-tagged functions:

```python
v1_wheel = create_test_wheel(tmp_path, "mypkg", "1.0.0")
v1_renamed = rename_wheel(v1_wheel, "mypkg_v1", output_dir=tmp_path)
```

### Running Tests

```bash
uv run pytest tests/                     # All tests
uv run pytest tests/test_rename.py       # Unit tests only
uv run pytest -m integration             # Integration tests (slower, network)
```

## Common Tasks

### Adding a New CLI Command

1. Add function in `cli.py` with `@main.command()` decorator
2. Use Click options/arguments
3. Use `console.print()` for output, `err_console.print()` for errors
4. Handle exceptions and call `sys.exit(1)` on error

### Modifying Import Rewriting

The regex patterns in `_update_python_imports()` handle:

- `from pkg import x`
- `from pkg.submodule import x`
- `import pkg`
- `import pkg as alias`

Be careful with word boundaries (`\b`) to avoid partial matches.

### Adding Test Coverage

- Unit tests go in `test_rename.py`
- Import rewriting tests go in `test_integration.py`
- Multi-package isolation tests go in `test_dual_install.py`
- Real wheel tests go in `test_icechunk_integration.py` with `@pytest.mark.integration`

## Dependencies

Core:

- `click` - CLI framework
- `packaging` - Version parsing, platform tags
- `pypi-simple` - PEP 503 index client
- `rich` - Pretty terminal output

Server (optional):

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `httpx` - Async HTTP client

## Proxy Server

The proxy server enables `uv sync` to install renamed packages without manual wheel downloading.

### How It Works

1. Start proxy: `spare-tire serve -u <upstream> -r "pkg=pkg_v1:<version>"`
2. Proxy serves `/simple/pkg_v1/` endpoint with renamed wheel links
3. When uv requests the wheel, proxy downloads from upstream, renames on-the-fly, serves renamed wheel
4. uv installs `pkg_v1` as a normal package

### Server Modules

- `config.py`: Loads TOML config or CLI args, handles PEP 503 name normalization
- `app.py`: FastAPI routes for `/simple/`, `/simple/{project}/`, `/simple/{project}/{filename}`
- `upstream.py`: Async client to fetch packages from upstream indexes
- `stream.py`: Downloads wheel, calls `rename_wheel_from_bytes()`, returns renamed bytes
- `html.py`: Generates PEP 503 HTML with rewritten filenames

### Configuration Options

```toml
[tool.uv]
extra-index-url = ["http://127.0.0.1:8123/simple/"]
prerelease = "allow"
index-strategy = "unsafe-best-match"  # Required for mixing indexes
resolution = "highest"
```

## Implementing Multi-Version Install in a New Repo

To set up a project that installs both `icechunk` (v2) and `icechunk_v1` (v1):

### Step 1: Install spare-tire with server extras

```bash
pip install spare-tire[server]
# or
uvx --with spare-tire[server] spare-tire serve --help
```

### Step 2: Start the proxy server

```bash
spare-tire serve \
    -u https://pypi.anaconda.org/scientific-python-nightly-wheels/simple \
    -r "icechunk=icechunk_v1:<2" \
    --port 8123
```

### Step 3: Configure pyproject.toml

```toml
[project]
name = "my-project"
requires-python = ">=3.12"
dependencies = [
    "icechunk>=2.0.0.dev0",  # v2 from nightly
    "icechunk_v1",            # v1 renamed, from proxy
]

[tool.uv]
extra-index-url = [
    "https://pypi.anaconda.org/scientific-python-nightly-wheels/simple",
    "http://127.0.0.1:8123/simple/",
]
prerelease = "allow"
index-strategy = "unsafe-best-match"
resolution = "highest"
```

### Step 4: Install with uv sync

```bash
uv sync
```

### Step 5: Use both versions

```python
import icechunk      # v2
import icechunk_v1   # v1

# Both are fully isolated and functional
```

### Reference Implementation

See `tests/fixtures/dual-install/` for a complete working example with:

- `pyproject.toml` - Full uv configuration
- `README.md` - Detailed usage instructions

## Git Workflow

- `main` branch has core rename/download/inspect functionality
- `feature/proxy-index` branch has the proxy server implementation
- Run `uv run ruff check src tests` before committing
- Pre-commit hooks handle formatting

## Environment

- Python 3.11+ required
- Use `uv` for environment management: `uv sync`, `uv run pytest`
- Ruff for linting and formatting
- Pyright for type checking (strict mode)

## Gotchas

1. **Anaconda.org doesn't provide digests** - Use `verify=False` when downloading
2. **Version specifiers with .dev releases** - Use `>=2.0.0.dev0` not `>=2.0.0a0` for dev releases
3. **pytest.skip() in fixtures** - Use assertions instead to avoid hiding failures
4. **pypi-simple is sync** - For async proxy, need to wrap or use httpx directly
5. **Wheel filenames must match internal metadata** - After renaming, filename, directory name, and METADATA Name must all match

## Useful Commands

```bash
# List available wheels for a package
uv run spare-tire download icechunk --list -i https://pypi.anaconda.org/scientific-python-nightly-wheels/simple

# Inspect a wheel
uv run spare-tire inspect ./icechunk-*.whl

# Rename a wheel
uv run spare-tire rename ./icechunk-*.whl icechunk_v1 -o ./renamed/

# Download and rename in one step
uv run spare-tire download icechunk \
    -i https://pypi.anaconda.org/scientific-python-nightly-wheels/simple \
    --version "<2" \
    --rename icechunk_v1 \
    -o ./wheels/
```
