"""Tests for liig batch mode and nested directory handling."""

from conftest import INPUT_DIR


def test_batch_generates_all_files(run_batch):
    """Batch mode creates one output PNG per CSV row, using the FILE stem + .png."""
    out_dir = run_batch()
    pngs = sorted(p.name for p in out_dir.glob("*.png"))
    assert pngs == [f"{i}.png" for i in range(1, 10)]


def test_batch_nested_dirs(run_batch):
    """Batch mode mirrors the FILE column's directory tree in the output directory."""
    out_dir = run_batch(extra_args=["--labels-csv", str(INPUT_DIR / "nested-labels.csv")])
    assert (out_dir / "nested" / "a" / "1.png").exists()
    assert (out_dir / "nested" / "b" / "2.png").exists()
    assert (out_dir / "3.png").exists()
    assert len(list(out_dir.rglob("*.png"))) == 3
