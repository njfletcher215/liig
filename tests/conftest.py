"""pytest configuration and shared fixtures for liig tests."""

import os
import subprocess
from pathlib import Path

import pytest

TESTS_DIR    = Path(__file__).parent
LIIG         = TESTS_DIR.parent / "liig.sh"
INPUT_DIR    = TESTS_DIR / "input"
OUTPUT_DIR   = TESTS_DIR / "output"
EXPECTED_DIR = TESTS_DIR / "expected"

GENERATE = os.environ.get("LIIG_GENERATE_EXPECTED") == "1"


@pytest.fixture(scope="session", autouse=True)
def clear_output_dir():
    """Delete all output images before the test session so stale files don't linger."""
    if OUTPUT_DIR.exists():
        import shutil
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _pixels_match(a: Path, b: Path) -> bool:
    """Return True if images a and b are pixel-identical (metadata ignored)."""
    result = subprocess.run(
        ["magick", "compare", "-metric", "AE", str(a), str(b), "/dev/null"],
        capture_output=True, text=True,
    )
    # AE reports differing-pixel count on stderr as "N" or "N (normalised)"
    return result.stderr.split()[0] == "0"


def _test_subdir(request) -> str:
    """Subdirectory name derived from the test function name (strip 'test_' prefix)."""
    return request.node.function.__name__.removeprefix("test_")


def _liig_batch_cmd(out_dir: Path, extra_args) -> list[str]:
    return (
        [str(LIIG),
         "--config",     str(TESTS_DIR / "default-config.toml"),
         "--output-dir", str(out_dir)]
        + (extra_args or [])
    )


def _liig_cmd(out_file: Path, extra_args, index: int) -> list[str]:
    return (
        [str(LIIG),
         "--config",      str(TESTS_DIR / "default-config.toml"),
         "--output-file", str(out_file)]
        + (extra_args or [])
        + [str(index)]
    )


@pytest.fixture
def run(request):
    """Return a callable that runs liig with the default config and compares output.

    The output image is written to output/<test_name>/<name>.png.
    The expected image is read from expected/<test_name>/<name>.png.

    Usage:
        def test_foo(run):
            run("bar", extra_args=["--some-flag", "value"], index=0)
    """
    def _run(name: str, extra_args: list[str] | None = None, index: int = 0) -> None:
        subdir   = _test_subdir(request)
        out_file = OUTPUT_DIR / subdir / f"{name}.png"
        out_file.parent.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(_liig_cmd(out_file, extra_args, index),
                                capture_output=True, text=True)
        assert result.returncode == 0, (
            f"liig exited with code {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out_file.exists(), "liig did not produce an output file"

        expected = EXPECTED_DIR / subdir / f"{name}.png"
        if GENERATE:
            expected.parent.mkdir(parents=True, exist_ok=True)
            expected.write_bytes(out_file.read_bytes())
            return

        assert expected.exists(), (
            f"No expected image for '{subdir}/{name}'. "
            "Run with LIIG_GENERATE_EXPECTED=1 to generate it."
        )
        assert _pixels_match(out_file, expected), \
            f"Pixel mismatch for '{subdir}/{name}'"

    return _run


@pytest.fixture
def run_batch(tmp_path):
    """Return a callable that runs liig in batch mode and returns the output directory."""
    def _run(extra_args=None) -> Path:
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        result = subprocess.run(
            _liig_batch_cmd(out_dir, extra_args),
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"liig batch exited with code {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        return out_dir
    return _run


@pytest.fixture
def run_expect_skip(request):
    """Return a callable that runs liig and asserts generation was skipped (exit 1)."""
    def _run(extra_args: list[str] | None = None, index: int = 0) -> None:
        subdir   = _test_subdir(request)
        out_file = OUTPUT_DIR / subdir / "skip.png"
        out_file.parent.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(_liig_cmd(out_file, extra_args, index),
                                capture_output=True, text=True)
        assert result.returncode == 1, (
            f"Expected liig to skip generation (exit 1) but got exit {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "no room for label" in result.stderr, (
            f"Expected 'no room for label' in stderr, got: {result.stderr!r}"
        )

    return _run
