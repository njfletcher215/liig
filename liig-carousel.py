#!/usr/bin/env python3
"""liig-carousel — random-rotation driver for liig

Reads LABELS_CSV (via the same config as liig), picks a random row index
every GENERATION_INTERVAL_S seconds, and calls liig with that index.

Send SIGUSR1 to skip the current sleep and advance immediately:
  kill -USR1 $(cat /tmp/liig-rotate.pid)
or, if using systemd:
  systemctl --user kill --signal=SIGUSR1 liig-rotate.service
"""

import argparse
import collections
import csv
import os
import random
import re
import signal
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

# ── Locate liig ──────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
LIIG: Path = next(
    p for p in (SCRIPT_DIR / "liig", SCRIPT_DIR / "liig.sh") if p.is_file()
)

# ── Config ────────────────────────────────────────────────────────────────────

CONFIG_FILE = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    / "liig" / "config.toml"
)

INPUT_DIR: str = ""
LABELS_CSV: Path | None = None
CSV_HEADER: str = ""
CSV_FILE_COLUMN: str = "FILE"
CSV_DELIMITER: str = ""
LABEL_FORMAT: str = ""
GENERATION_INTERVAL_S: int = 300
CAROUSEL_MODE: str = "normal"


def _load_config(path: Path) -> None:
    global INPUT_DIR, LABELS_CSV, CSV_HEADER, CSV_FILE_COLUMN, CSV_DELIMITER, LABEL_FORMAT, GENERATION_INTERVAL_S, CAROUSEL_MODE
    if not path.exists():
        return
    import tomllib
    with open(path, "rb") as f:
        data = tomllib.load(f)
    if "INPUT_DIR"             in data and data["INPUT_DIR"]:    INPUT_DIR  = str(data["INPUT_DIR"])
    if "LABELS_CSV"            in data and data["LABELS_CSV"]:  LABELS_CSV = Path(str(data["LABELS_CSV"]))
    if "CSV_HEADER"            in data: CSV_HEADER            = str(data["CSV_HEADER"])
    if "CSV_FILE_COLUMN"       in data: CSV_FILE_COLUMN       = str(data["CSV_FILE_COLUMN"])
    if "CSV_DELIMITER"         in data: CSV_DELIMITER         = str(data["CSV_DELIMITER"])
    if "LABEL_FORMAT"          in data and data["LABEL_FORMAT"]: LABEL_FORMAT = str(data["LABEL_FORMAT"])
    if "GENERATION_INTERVAL_S" in data: GENERATION_INTERVAL_S = int(data["GENERATION_INTERVAL_S"])
    if "CAROUSEL_MODE"         in data:
        mode = str(data["CAROUSEL_MODE"])
        if mode not in ("normal", "shuffle", "smart-shuffle"):
            sys.exit(f"liig-carousel: invalid CAROUSEL_MODE '{mode}' (expected normal, shuffle, or smart-shuffle)")
        CAROUSEL_MODE = mode


# ── Liig CLI arg definitions ─────────────────────────────────────────────────
# Each entry: (argparse dest, CLI flag, help text)
# _SHARED_ARGS affect carousel internals AND are forwarded to liig.sh.
# _LIIG_ARGS are forwarded to liig.sh only.

_SHARED_ARGS: list[tuple[str, str, str]] = [
    ("labels_csv",      "--labels-csv",      "path to the CSV file"),
    ("csv_file_column", "--csv-file-column", "CSV column containing image file paths"),
    ("csv_header",      "--csv-header",      "explicit CSV header (for headerless files)"),
    ("csv_delimiter",   "--csv-delimiter",   "field delimiter character (default: auto-detect)"),
]

_LIIG_ARGS: list[tuple[str, str, str]] = [
    ("input_dir",              "--input-dir",              "source images directory"),
    ("output_dir",             "--output-dir",             "batch output directory"),
    ("output_file",            "--output-file",            "single-mode output file"),
    ("canvas_width_px",        "--canvas-width-px",        "canvas width in pixels"),
    ("canvas_height_px",       "--canvas-height-px",       "canvas height in pixels"),
    ("canvas_color",           "--canvas-color",           "canvas background color"),
    ("image_position",         "--image-position",         "image placement position"),
    ("scale_images",           "--scale-images",           "scale images up to fill max dimensions (true/false)"),
    ("image_max_width_px",     "--image-max-width-px",     "max image width in pixels"),
    ("image_max_height_px",    "--image-max-height-px",    "max image height in pixels"),
    ("label_position",         "--label-position",         "label placement position"),
    ("label_margins_px",       "--label-margins-px",       "label margins in pixels"),
    ("label_alignment",        "--label-alignment",        "label text alignment: left | center | right"),
    ("label_justify",          "--label-justify",          "stretch full lines to fill the label box width (true/false)"),
    ("label_color",            "--label-color",            "label text color"),
    ("label_font",             "--label-font",             "label font (Pango font description)"),
    ("label_background_color", "--label-background-color", "label background color"),
    ("label_padding_px",       "--label-padding-px",       "inner spacing between label border and text content"),
    ("label_max_width_px",     "--label-max-width-px",     "max label text box width in pixels"),
    ("label_format",           "--label-format",           "label format string with {COLUMN_NAME} placeholders"),
]

# ── CSV helpers ───────────────────────────────────────────────────────────────

def _csv_delimiter() -> str:
    """Return the field delimiter to use: explicit CSV_DELIMITER or auto-detected."""
    if CSV_DELIMITER:
        return CSV_DELIMITER
    with open(LABELS_CSV, newline="") as f:
        sample = f.readline()
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t,;|").delimiter
    except csv.Error:
        return "\t"


def _get_fieldnames() -> list | None:
    """Return explicit fieldnames from CSV_HEADER if configured, else None.

    When None, csv.DictReader will infer fieldnames from the first row of the file.
    """
    if not CSV_HEADER:
        return None
    return next(csv.reader([CSV_HEADER], delimiter=_csv_delimiter()))


def _row_count(fieldnames: list | None) -> int:
    with open(LABELS_CSV, newline="") as f:
        total = sum(1 for _ in f)
    if fieldnames is not None:
        return total  # every row is data; header came from CSV_HEADER
    # Auto-detect: if the first line looks like a header, don't count it
    with open(LABELS_CSV, newline="") as f:
        first_line = f.readline()
    return total - (1 if CSV_FILE_COLUMN in first_line else 0)


def _build_pool_by_column(column: str, values: list, fieldnames: list | None) -> list:
    """Return 0-based data-row indices where `column` matches any of `values`.

    Results are grouped by value in the order values were given, so that
    normal mode iterates all matches for the first value, then the second, etc.
    """
    # Deduplicate while preserving order
    seen: set = set()
    ordered_values = [v for v in values if not (v in seen or seen.add(v))]
    buckets: dict = {v: [] for v in ordered_values}
    with open(LABELS_CSV, newline="") as f:
        reader = csv.DictReader(f, fieldnames=fieldnames, delimiter=_csv_delimiter())
        if column not in (reader.fieldnames or []):
            sys.exit(f"liig-carousel: column '{column}' not found in CSV header")
        for i, row in enumerate(reader):
            val = row.get(column, "").strip()
            if val in buckets:
                buckets[val].append(i)
    return [idx for v in ordered_values for idx in buckets[v]]

def _build_pool_by_query(where_clause: str, fieldnames: list | None) -> list:
    """Return 0-based data-row indices matching a SQL WHERE clause."""
    # Accept both "ID >= 10" and "* WHERE ID >= 10" spellings
    clause = re.sub(r"^\*\s+WHERE\s+", "", where_clause, flags=re.IGNORECASE).strip()

    conn = sqlite3.connect(":memory:")
    with open(LABELS_CSV, newline="") as f:
        reader = csv.DictReader(f, fieldnames=fieldnames, delimiter=_csv_delimiter())
        cols = ", ".join(f'"{c}"' for c in (reader.fieldnames or []))
        placeholders = ", ".join("?" * len(reader.fieldnames or []))
        conn.execute(f"CREATE TABLE data ({cols})")
        conn.executemany(
            f"INSERT INTO data VALUES ({placeholders})",
            (list(row.values()) for row in reader),
        )

    try:
        rows = conn.execute(f"SELECT rowid - 1 FROM data WHERE {clause}").fetchall()
    except sqlite3.OperationalError as e:
        sys.exit(f"liig-carousel: invalid query: {e}")
    finally:
        conn.close()

    return [r[0] for r in rows]

# ── Argument parsing ──────────────────────────────────────────────────────────

def _parse_index_args(tokens: list, row_count: int) -> list:
    pool = []
    for raw in tokens:
        for token in re.split(r"[,\s]+", raw):
            if not token:
                continue
            m = re.fullmatch(r"(\d+)-(\d+)", token)
            if m:
                lo, hi = int(m.group(1)), int(m.group(2))
                for i in range(lo, hi + 1):
                    if i >= row_count:
                        sys.exit(f"liig-carousel: index {i} out of range (0–{row_count - 1})")
                    pool.append(i)
            elif re.fullmatch(r"\d+", token):
                i = int(token)
                if i >= row_count:
                    sys.exit(f"liig-carousel: index {i} out of range (0–{row_count - 1})")
                pool.append(i)
            else:
                sys.exit(f"liig-carousel: unrecognised index token '{token}'")
    return pool

# ── Signal / interruptible sleep ──────────────────────────────────────────────

_skip_sleep = False


def _handle_usr1(signum, frame):
    global _skip_sleep
    _skip_sleep = True


signal.signal(signal.SIGUSR1, _handle_usr1)


def interruptible_sleep(seconds: int) -> None:
    global _skip_sleep
    _skip_sleep = False
    if seconds < 0:
        while not _skip_sleep:
            time.sleep(1)
        print("liig-carousel: SIGUSR1 received — advancing")
        _skip_sleep = False
        return
    remaining = seconds
    while remaining > 0:
        time.sleep(1)
        remaining -= 1
        if _skip_sleep:
            print("liig-carousel: SIGUSR1 received — skipping remaining interval")
            _skip_sleep = False
            return

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    global INPUT_DIR, LABELS_CSV, CSV_HEADER, CSV_FILE_COLUMN, CSV_DELIMITER, LABEL_FORMAT, GENERATION_INTERVAL_S, CAROUSEL_MODE

    parser = argparse.ArgumentParser(
        prog="liig-carousel",
        description="Randomly rotate wallpapers via liig.",
    )
    parser.add_argument(
        "--config", metavar="FILE",
        help="path to config file (default: $XDG_CONFIG_HOME/liig/config.toml)",
    )
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument(
        "--by", metavar="COLUMN",
        help="select rows where COLUMN matches the given value(s)",
    )
    selector.add_argument(
        "--query", metavar="WHERE_CLAUSE",
        help='SQL WHERE clause to filter rows, e.g. "YEAR >= 1900 AND STYLE = \'oil\'"',
    )
    parser.add_argument(
        "values", nargs="*",
        help=(
            "row indices/ranges (default) or column values (with --by). "
            "Indices are 0-based, counting from the first non-header row."
        ),
    )

    carousel_group = parser.add_argument_group(
        "carousel options (override config)"
    )
    carousel_group.add_argument(
        "--generation-interval-s", dest="generation_interval_s", type=int,
        metavar="SECONDS",
        help="seconds between rotations; -1 for manual-advance only",
    )
    carousel_group.add_argument(
        "--carousel-mode", dest="carousel_mode",
        choices=["normal", "shuffle", "smart-shuffle"],
        help="how to step through the pool: normal, shuffle, or smart-shuffle",
    )

    liig_group = parser.add_argument_group(
        "liig options (forwarded to liig.sh, override config)"
    )
    for dest, flag, help_text in _SHARED_ARGS + _LIIG_ARGS:
        liig_group.add_argument(flag, dest=dest, metavar=dest.upper(), help=help_text)

    args = parser.parse_args()

    _load_config(Path(args.config) if args.config else CONFIG_FILE)

    if args.query and args.values:
        sys.exit("liig-carousel: --query does not take positional arguments")

    # Apply carousel-specific overrides
    if args.labels_csv      is not None: LABELS_CSV      = Path(args.labels_csv)
    if args.csv_header       is not None: CSV_HEADER       = args.csv_header
    if args.csv_file_column  is not None: CSV_FILE_COLUMN  = args.csv_file_column
    if args.csv_delimiter    is not None: CSV_DELIMITER    = args.csv_delimiter
    if args.input_dir        is not None: INPUT_DIR        = args.input_dir
    if args.label_format     is not None: LABEL_FORMAT     = args.label_format
    if args.generation_interval_s is not None: GENERATION_INTERVAL_S = args.generation_interval_s
    if args.carousel_mode    is not None: CAROUSEL_MODE    = args.carousel_mode

    if not INPUT_DIR:
        sys.exit("liig-carousel: INPUT_DIR is required (set in config or pass --input-dir)")
    if not LABELS_CSV:
        sys.exit("liig-carousel: LABELS_CSV is required (set in config or pass --labels-csv)")
    if not LABEL_FORMAT:
        sys.exit("liig-carousel: LABEL_FORMAT is required (set in config or pass --label-format)")

    # Build the list of liig.sh passthrough args
    liig_args: list[str] = []
    if args.config is not None:
        liig_args.extend(["--config", args.config])
    for dest, flag, _ in _SHARED_ARGS + _LIIG_ARGS:
        val = getattr(args, dest, None)
        if val is not None:
            liig_args.extend([flag, str(val)])

    fieldnames = _get_fieldnames()
    row_count = _row_count(fieldnames)
    if row_count <= 0:
        sys.exit("liig-carousel: no data rows in CSV")

    if args.query:
        pool = _build_pool_by_query(args.query, fieldnames)
        if not pool:
            sys.exit("liig-carousel: no rows matched the given query")
        pool_desc = f"{len(pool)} rows matching query"
    elif args.by:
        if not args.values:
            sys.exit("liig-carousel: --by requires at least one value to match")
        pool = _build_pool_by_column(args.by, args.values, fieldnames)
        if not pool:
            sys.exit(f"liig-carousel: no rows matched --by {args.by} with the given values")
        pool_desc = f"{len(pool)} rows matching {args.by}"
    elif args.values:
        pool = _parse_index_args(args.values, row_count)
        if not pool:
            sys.exit("liig-carousel: no indices parsed from arguments")
        pool_desc = f"{len(pool)} selected indices"
    else:
        pool = []
        pool_desc = f"{row_count} rows"

    # PID file
    pid_file = Path("/tmp/liig-rotate.pid")
    pid_file.write_text(str(os.getpid()))
    import atexit
    atexit.register(lambda: pid_file.unlink(missing_ok=True))

    effective_pool = pool if pool else list(range(row_count))

    pid = os.getpid()
    if GENERATION_INTERVAL_S < 0:
        print(f"liig-carousel: starting; {pool_desc}, manual advance only, {CAROUSEL_MODE}  (PID {pid})")
    else:
        print(f"liig-carousel: starting; {pool_desc}, interval {GENERATION_INTERVAL_S}s, {CAROUSEL_MODE}  (PID {pid})")
    print(f"liig-carousel: send SIGUSR1 (kill -USR1 {pid}) to advance immediately")

    position = 0
    history: collections.deque = collections.deque(
        maxlen=min(20, len(effective_pool) // 2)
    )

    while True:
        if CAROUSEL_MODE == "normal":
            index = effective_pool[position % len(effective_pool)]
            position += 1
        elif CAROUSEL_MODE == "smart-shuffle":
            excluded = set(history)
            candidates = [i for i in effective_pool if i not in excluded]
            if not candidates:
                candidates = effective_pool
            index = random.choice(candidates)
            history.append(index)
        else:  # shuffle
            index = random.choice(effective_pool)

        print(f"liig-carousel: picking index {index}")
        result = subprocess.run([str(LIIG)] + liig_args + [str(index)])
        if result.returncode != 0:
            print(f"liig-carousel: liig exited with error for index {index}", file=sys.stderr)
        interruptible_sleep(GENERATION_INTERVAL_S)


if __name__ == "__main__":
    main()
