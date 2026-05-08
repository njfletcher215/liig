"""Tests for liig-carousel.py — pool helpers, CLI validation, and iteration modes."""

import csv as csv_mod
import importlib.util
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

TESTS_DIR   = Path(__file__).parent
CAROUSEL_PY = TESTS_DIR.parent / "liig-carousel.py"
TEST_CONFIG = TESTS_DIR / "default-config.toml"
TEST_CSV    = TESTS_DIR / "input" / "tests-labels.csv"


# ── Module loading ─────────────────────────────────────────────────────────────

def _load_carousel():
    """Import liig-carousel.py as a module (importlib because of the hyphen in name)."""
    spec = importlib.util.spec_from_file_location("liig_carousel", CAROUSEL_PY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def carousel():
    """Carousel module with globals pointed at the test CSV."""
    m = _load_carousel()
    m.LABELS_CSV = TEST_CSV
    m.CSV_HEADER = ""
    m.CSV_FILE_COLUMN = "FILE"
    return m


# ── Unit tests — pool helpers ─────────────────────────────────────────────────

def test_row_count(carousel):
    assert carousel._row_count(None) == 9


def test_row_count_explicit_header():
    """Explicit fieldnames cause every line to be counted as a data row."""
    m = _load_carousel()
    m.LABELS_CSV = TESTS_DIR / "input" / "tests-labels-no-header.csv"
    m.CSV_FILE_COLUMN = "FILE"
    header = "ID\tFILE\tAUTHOR\tBORN-DIED\tTITLE\tDATE\tTECHNIQUE\tLOCATION\tFORM\tTYPE\tSCHOOL\tTIMELINE\tURL"
    fieldnames = next(csv_mod.reader([header], delimiter="\t"))
    assert m._row_count(fieldnames) == 9


def test_build_pool_by_column_single_value(carousel):
    pool = carousel._build_pool_by_column("SCHOOL", ["German"], None)
    assert pool == [0, 1, 2, 3, 4]


def test_build_pool_by_column_multiple_values(carousel):
    """Values are returned grouped in the order given."""
    pool = carousel._build_pool_by_column("SCHOOL", ["Danish", "Spanish"], None)
    assert pool == [5, 6, 7]


def test_build_pool_by_column_no_match(carousel):
    assert carousel._build_pool_by_column("SCHOOL", ["NONEXISTENT"], None) == []


def test_build_pool_by_query_single_row(carousel):
    assert carousel._build_pool_by_query("ID = '1'", None) == [0]


def test_build_pool_by_query_multiple_rows(carousel):
    assert carousel._build_pool_by_query("SCHOOL = 'Danish'", None) == [5, 6]


def test_parse_index_args_single(carousel):
    assert carousel._parse_index_args(["3"], 9) == [3]


def test_parse_index_args_range(carousel):
    assert carousel._parse_index_args(["1-3"], 9) == [1, 2, 3]


def test_parse_index_args_comma_separated(carousel):
    assert carousel._parse_index_args(["0,2,4"], 9) == [0, 2, 4]


def test_parse_index_args_mixed(carousel):
    assert carousel._parse_index_args(["0-1", "5"], 9) == [0, 1, 5]


def test_parse_index_args_out_of_range(carousel):
    with pytest.raises(SystemExit):
        carousel._parse_index_args(["100"], 9)


# ── CLI error tests ───────────────────────────────────────────────────────────

def _cli(*args):
    return subprocess.run(
        [sys.executable, str(CAROUSEL_PY), "--config", str(TEST_CONFIG)] + list(args),
        capture_output=True, text=True,
    )


def test_cli_invalid_mode():
    """argparse rejects unknown carousel-mode values."""
    result = _cli("--carousel-mode", "badmode")
    assert result.returncode != 0


def test_cli_query_with_positional_arg():
    """--query and positional index args are mutually exclusive."""
    result = _cli("--query", "ID = '1'", "0")
    assert result.returncode != 0
    assert "--query does not take positional" in result.stdout + result.stderr


def test_cli_no_matching_rows_by():
    """--by with a value that matches no rows exits with an error."""
    result = _cli("--by", "SCHOOL", "NONEXISTENT_SCHOOL")
    assert result.returncode != 0
    assert "no rows matched" in result.stdout + result.stderr


def test_cli_no_matching_rows_query():
    """--query that matches no rows exits with an error."""
    result = _cli("--query", "SCHOOL = 'NONEXISTENT_SCHOOL'")
    assert result.returncode != 0
    assert "no rows matched" in result.stdout + result.stderr


def test_cli_invalid_sql_query():
    """Syntactically invalid SQL WHERE clause exits with an error."""
    result = _cli("--query", "INVALID @@@ SYNTAX")
    assert result.returncode != 0
    assert "invalid query" in result.stdout + result.stderr


# ── Integration tests — carousel iteration ────────────────────────────────────

def _collect_picks(cmd, n, timeout=120):
    """Start carousel subprocess, collect n 'picking index X' lines, then terminate.

    Returns the list of collected indices (may be shorter than n on timeout).
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    picks = []
    done = threading.Event()

    def reader():
        for line in proc.stdout:
            m = re.search(r"picking index (\d+)", line)
            if m:
                picks.append(int(m.group(1)))
            if len(picks) >= n:
                done.set()
                return
        done.set()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    done.wait(timeout=timeout)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    t.join(timeout=2)
    return picks


def _carousel_cmd(tmp_path, *extra):
    return [
        sys.executable, str(CAROUSEL_PY),
        "--config",                str(TEST_CONFIG),
        "--generation-interval-s", "0",
        "--output-file",           str(tmp_path / "output.png"),
    ] + list(extra)


def test_normal_mode_sequential(tmp_path):
    """Normal mode visits the pool in sequential order starting from index 0."""
    picks = _collect_picks(_carousel_cmd(tmp_path, "--carousel-mode", "normal"), n=3)
    assert picks == [0, 1, 2]


def test_shuffle_mode_in_pool(tmp_path):
    """Shuffle mode only picks indices that are within the pool."""
    picks = _collect_picks(_carousel_cmd(tmp_path, "--carousel-mode", "shuffle"), n=6)
    assert len(picks) == 6
    assert all(0 <= p <= 8 for p in picks)


def test_by_filter_restricts_pool(tmp_path):
    """--by filters the pool to rows where the column matches the given value."""
    picks = _collect_picks(
        _carousel_cmd(tmp_path, "--by", "SCHOOL", "German"),
        n=3,
    )
    german_indices = {0, 1, 2, 3, 4}
    assert len(picks) == 3
    assert all(p in german_indices for p in picks)


def test_query_filter_restricts_pool(tmp_path):
    """--query filters the pool using a SQL WHERE clause."""
    picks = _collect_picks(
        _carousel_cmd(tmp_path, "--query", "SCHOOL = 'Danish'"),
        n=3,
    )
    danish_indices = {5, 6}
    assert len(picks) == 3
    assert all(p in danish_indices for p in picks)
