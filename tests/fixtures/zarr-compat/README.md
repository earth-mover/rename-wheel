# Zarr Compatibility Test

This fixture demonstrates installing two different versions of zarr (v2 and v3)
in the same environment using spare-tire's dependency renaming feature.

## What it tests

- Downloads zarr v2 from PyPI and renames it to `zarr_v2`
- Creates test packages (`myreader` v1 and v2) with different zarr dependencies
- Renames `myreader` v1 to `myreader_v1` with `--rename-dep zarr=zarr_v2`
- Installs all packages in the same environment
- Verifies both versions can read the same Zarr format 2 data

## Running the test

```bash
# From the repository root
uv run python tests/fixtures/zarr-compat/test_zarr_compat.py
```

## Expected output

The test installs:

- `zarr` 3.x (latest)
- `zarr_v2` 2.x (renamed)
- `myreader` 2.0.0 (uses zarr v3)
- `myreader_v1` 1.0.0 (uses zarr_v2)

Both `myreader` and `myreader_v1` successfully read the same Zarr format 2 array,
demonstrating that the dependency renaming works correctly.

## Files

- `create_wheels.py` - Creates the test wheels for myreader v1 and v2
- `test_zarr_compat.py` - The main test script
- `wheels/` - Generated test wheels (created by running create_wheels.py)
- `renamed/` - Downloaded and renamed wheels (created by test)
