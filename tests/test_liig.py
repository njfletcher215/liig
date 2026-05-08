"""Tests for liig.sh — one test per config option / value variant."""

import pytest
from conftest import INPUT_DIR


# ── Shared test data ──────────────────────────────────────────────────────────

_LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud "
    "exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure "
    "dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. "
    "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt "
    "mollit anim id est laborum. Sed ut perspiciatis unde omnis iste natus error sit "
    "voluptatem accusantium doloremque laudantium, totam rem aperiam eaque ipsa quae ab "
    "illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo "
    "enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia "
    "consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro "
    "quisquam est, qui dolorem ipsum quia dolor sit amet consectetur adipisci velit, sed "
    "quia non numquam eius modi tempora incidunt."
)

# Variants shared by image-position and label-position tests:
#   default (short label, no margins), m30_p50, long lorem ipsum, long+m30_p50
_IMG_LABEL_VARIANTS = [
    pytest.param([], "",           id="default"),
    pytest.param(["--label-margins-px", "30", "--label-padding-px", "50"], "_m30_p50", id="m30_p50"),
    pytest.param(["--label-format", _LOREM], "_long", id="long"),
    pytest.param(["--label-format", _LOREM, "--label-margins-px", "30", "--label-padding-px", "50"], "_long_m30_p50", id="long_m30_p50"),
]

# Alias used by label-position tests (same set of variants)
_POS_MP_VARIANTS = _IMG_LABEL_VARIANTS


# ── Canvas ────────────────────────────────────────────────────────────────────

def test_canvas_size_default(run):
    run("default")


@pytest.mark.parametrize("w,h", [
    ("800", "400"),
    ("1920", "1080"),
])
def test_canvas_size(run, w, h):
    run(f"{w}x{h}", extra_args=[
        "--canvas-width-px",  w,
        "--canvas-height-px", h,
    ])


@pytest.mark.parametrize("canvas_color,label_color", [
    ("white",   "black"),
    ("black",   "white"),
    ("green",   "black"),
    ("none",    "black"),
    ("#336699", "white"),
])
def test_canvas_color(run, canvas_color, label_color):
    safe = canvas_color.replace("#", "hash")
    run(safe, extra_args=[
        "--canvas-color", canvas_color,
        "--label-color",  label_color,
    ])


# ── Image placement ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("lv_args,lv_sfx", _IMG_LABEL_VARIANTS)
@pytest.mark.parametrize("pos,label_pos,label_align", [
    # label_pos: where text goes relative to the image
    # label_align: alignment within the text box
    ("center",       "top-right relative", "left"),    # label right of image
    ("top-left",     "top-right relative", "left"),    # label right of image
    ("top",          "bottom relative",    "center"),  # label below image
    ("top-right",    "top-left relative",  "right"),   # label left of image
    ("right",        "top-left relative",  "right"),   # label left of image
    ("bottom-right", "top-left relative",  "right"),   # label left of image
    ("bottom",       "top relative",       "center"),  # label above image
    ("bottom-left",  "top-right relative", "left"),    # label right of image
    ("left",         "top-right relative", "left"),    # label right of image
])
def test_image_position(run, pos, label_pos, label_align, lv_args, lv_sfx):
    run(f"{pos.replace('-', '_')}{lv_sfx}", extra_args=[
        "--image-position",  pos,
        "--label-position",  label_pos,
        "--label-alignment", label_align,
    ] + lv_args)


@pytest.mark.parametrize("lv_args,lv_sfx", _IMG_LABEL_VARIANTS)
@pytest.mark.parametrize("label_pos,suffix", [
    ("right relative",        "right"),
    ("left relative",         "left"),
    ("top relative",          "top"),
    ("bottom relative",       "bottom"),
    ("top-right relative",    "top_right"),
    ("bottom-left relative",  "bottom_left"),
])
def test_image_position_center_both(run, label_pos, suffix, lv_args, lv_sfx):
    run(f"{suffix}{lv_sfx}", extra_args=[
        "--image-position", "center-both",
        "--label-position", label_pos,
    ] + lv_args)


@pytest.mark.parametrize("flag", ["true", "false"])
def test_scale_images(run, flag):
    run(flag, extra_args=["--scale-images", flag])


def test_image_max_width(run):
    run("200", extra_args=["--image-max-width-px", "200"])


def test_image_max_height(run):
    run("150", extra_args=["--image-max-height-px", "150"])


def test_image_max_both(run):
    run("200x150", extra_args=[
        "--image-max-width-px",  "200",
        "--image-max-height-px", "150",
    ])


# ── Label position — relative ─────────────────────────────────────────────────

@pytest.mark.parametrize("mp_args,mp_sfx", _POS_MP_VARIANTS)
@pytest.mark.parametrize("pos", [
    "center",
    "top",       "right-top",   "left-top",
    "right",     "top-right",   "bottom-right",
    "bottom",    "right-bottom","left-bottom",
    "left",      "top-left",    "bottom-left",
])
def test_label_position_relative(run, pos, mp_args, mp_sfx):
    run(
        f"{pos.replace('-', '_')}{mp_sfx}",
        extra_args=["--label-position", f"{pos} relative"] + mp_args,
    )


# ── Label position — absolute ─────────────────────────────────────────────────

@pytest.mark.parametrize("mp_args,mp_sfx", _POS_MP_VARIANTS)
@pytest.mark.parametrize("pos", [
    "center",
    "top",     "bottom",
    "left",    "right",
    "top-left",     "top-right",    "left-top",
    "bottom-left",  "bottom-right", "left-bottom",
    "right-top",    "right-bottom",
])
def test_label_position_absolute(run, pos, mp_args, mp_sfx):
    run(
        f"{pos.replace('-', '_')}{mp_sfx}",
        extra_args=["--label-position", f"{pos} absolute"] + mp_args,
    )


# ── Label position — relative-inner ──────────────────────────────────────────

@pytest.mark.parametrize("mp_args,mp_sfx", _POS_MP_VARIANTS)
@pytest.mark.parametrize("pos", [
    "center",
    "top",     "bottom",
    "left",    "right",
    "top-left",     "top-right",    "left-top",
    "bottom-left",  "bottom-right", "left-bottom",
    "right-top",    "right-bottom",
])
def test_label_position_relative_inner(run, pos, mp_args, mp_sfx):
    run(
        f"{pos.replace('-', '_')}{mp_sfx}",
        extra_args=["--label-position", f"{pos} relative-inner"] + mp_args,
    )


# ── Label margins ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("margins", [
    "0",
    "5",
    "20",
    "10 20",
    "5 10 15 20",
])
def test_label_margins(run, margins):
    run(margins.replace(" ", "_"), extra_args=["--label-margins-px", margins])


# ── Label alignment ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("align,justify", [
    ("left",   False),
    ("center", False),
    ("right",  False),
    ("left",   True),
    ("center", True),
    ("right",  True),
])
def test_label_alignment(run, align, justify):
    name = f"{align}_justified" if justify else align
    extra = ["--label-alignment", align, "--label-format", _LOREM]
    if justify:
        extra += ["--label-justify", "true"]
    run(name, extra_args=extra)


# ── Label color ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("label_color,canvas_color", [
    ("black",   "white"),
    ("white",   "black"),   # white text needs dark canvas
    ("red",     "white"),
    ("#ff8800", "white"),
])
def test_label_color(run, label_color, canvas_color):
    run(label_color.replace("#", "hash"), extra_args=[
        "--label-color",  label_color,
        "--canvas-color", canvas_color,
    ])


# ── Label font ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("font", [
    "Sans 12",
    "Sans Bold 16",
    "Monospace 10",
])
def test_label_font(run, font):
    run(font.replace(" ", "_"), extra_args=["--label-font", font])


# ── Label background color ────────────────────────────────────────────────────

@pytest.mark.parametrize("label_background_color,label_color,canvas_color", [
    ("none",              "black", None),
    ("white",             "black", None),
    ("black",             "white", None),   # dark bg needs light text
    ("rgba(255,0,0,128)", "white", "blue"), # transparent red over blue canvas shows blend
])
def test_label_background_color(run, label_background_color, label_color, canvas_color):
    safe = label_background_color.replace("(", "").replace(")", "").replace(",", "_").replace(" ", "")
    extra = ["--label-background-color", label_background_color, "--label-color", label_color]
    if canvas_color is not None:
        extra += ["--canvas-color", canvas_color]
    run(safe, extra_args=extra)


# ── Label format ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fmt,suffix,extra", [
    ("{AUTHOR}",                                                    "one_var",        []),
    ("{AUTHOR} {TITLE}",                                            "two_vars",       []),
    ("{AUTHOR}\n{TITLE}\n{DATE}\n{TECHNIQUE}\n{LOCATION}",         "all_vars_newlines", []),
    ("Artist: {AUTHOR}\nTitle: {TITLE}\n({DATE})",                 "mixed_static",   []),
    ("Static label text",                                          "static",         []),
    (_LOREM,                                                       "long",           []),
    (_LOREM,                                                       "long_m30_p50",   ["--label-margins-px", "30", "--label-padding-px", "50"]),
])
def test_label_format(run, fmt, suffix, extra):
    run(suffix, extra_args=["--label-format", fmt] + extra)


# ── Label max width ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("max_w,suffix", [
    ("300",  "300"),
    ("300",  "300_m30_p50"),
])
def test_label_max_width(run, max_w, suffix):
    extra = ["--label-format", _LOREM, "--label-max-width-px", max_w]
    if "m30_p50" in suffix:
        extra += ["--label-margins-px", "30", "--label-padding-px", "50"]
    run(suffix, extra_args=extra)


# ── Label position fallbacks ──────────────────────────────────────────────────
#
# Each fallback chain covers 3 distinct sides.  Blocking all 3 would require
# an IMAGE_POSITION that is simultaneously on two opposite sides (top+bottom or
# left+right), which no single position value can satisfy.  Therefore the
# "all candidates exhausted → skip generation" path is unreachable and has no
# test here.
#
# Chains and the IMAGE_POSITION values that trigger each fallback level:
#
#   top-right / right  → right-top    (img "right")
#                      → right-bottom (img "top-right")
#   bottom-right       → right-bottom (img "right")
#                      → right-top    (img "bottom-right")
#   top-left / left    → left-top     (img "left")
#                      → left-bottom  (img "top-left")
#   bottom-left        → left-bottom  (img "left")
#                      → left-top     (img "bottom-left")
#   top / right-top    → top-right    (img "top")
#                      → top-left     (img "top-right")
#   left-top           → top-left     (img "top")
#                      → top-right    (img "top-left")
#   bottom / right-bottom → bottom-right (img "bottom")
#                         → bottom-left  (img "bottom-right")
#   left-bottom        → bottom-left  (img "bottom")
#                      → bottom-right (img "bottom-left")


@pytest.mark.parametrize("label_pos,img_pos,fallback_to", [
    # top-right/right → right-top: right side blocked, top side free
    ("top-right", "right",     "right-top"),
    ("right",     "right",     "right-top"),
    # top-right/right → right-bottom: right+top both blocked
    ("top-right", "top-right", "right-bottom"),
    ("right",     "top-right", "right-bottom"),
])
def test_label_fallback_right_chain(run, label_pos, img_pos, fallback_to):
    run(
        f"{label_pos.replace('-', '_')}_to_{fallback_to.replace('-', '_')}",
        extra_args=[
            "--image-position", img_pos,
            "--label-position", f"{label_pos} relative",
        ],
    )


@pytest.mark.parametrize("label_pos,img_pos,fallback_to", [
    # bottom-right → right-bottom: right side blocked, bottom side free
    ("bottom-right", "right",        "right-bottom"),
    # bottom-right → right-top: right+bottom both blocked
    ("bottom-right", "bottom-right", "right-top"),
])
def test_label_fallback_bottom_right_chain(run, label_pos, img_pos, fallback_to):
    run(
        f"{label_pos.replace('-', '_')}_to_{fallback_to.replace('-', '_')}",
        extra_args=[
            "--image-position", img_pos,
            "--label-position", f"{label_pos} relative",
        ],
    )


@pytest.mark.parametrize("label_pos,img_pos,fallback_to", [
    # top-left/left → left-top: left side blocked, top side free
    ("top-left", "left",     "left-top"),
    ("left",     "left",     "left-top"),
    # top-left/left → left-bottom: left+top both blocked
    ("top-left", "top-left", "left-bottom"),
    ("left",     "top-left", "left-bottom"),
])
def test_label_fallback_left_chain(run, label_pos, img_pos, fallback_to):
    run(
        f"{label_pos.replace('-', '_')}_to_{fallback_to.replace('-', '_')}",
        extra_args=[
            "--image-position", img_pos,
            "--label-position", f"{label_pos} relative",
        ],
    )


@pytest.mark.parametrize("label_pos,img_pos,fallback_to", [
    # bottom-left → left-bottom: left side blocked, bottom side free
    ("bottom-left", "left",        "left-bottom"),
    # bottom-left → left-top: left+bottom both blocked
    ("bottom-left", "bottom-left", "left-top"),
])
def test_label_fallback_bottom_left_chain(run, label_pos, img_pos, fallback_to):
    run(
        f"{label_pos.replace('-', '_')}_to_{fallback_to.replace('-', '_')}",
        extra_args=[
            "--image-position", img_pos,
            "--label-position", f"{label_pos} relative",
        ],
    )


@pytest.mark.parametrize("label_pos,img_pos,fallback_to", [
    # top/right-top → top-right: top side blocked, right side free
    ("top",       "top",     "top-right"),
    ("right-top", "top",     "top-right"),
    # top/right-top → top-left: top+right both blocked
    ("top",       "top-right", "top-left"),
    ("right-top", "top-right", "top-left"),
])
def test_label_fallback_top_chain(run, label_pos, img_pos, fallback_to):
    run(
        f"{label_pos.replace('-', '_')}_to_{fallback_to.replace('-', '_')}",
        extra_args=[
            "--image-position", img_pos,
            "--label-position", f"{label_pos} relative",
        ],
    )


@pytest.mark.parametrize("label_pos,img_pos,fallback_to", [
    # left-top → top-left: top side blocked, left side free
    ("left-top", "top",      "top-left"),
    # left-top → top-right: top+left both blocked
    ("left-top", "top-left", "top-right"),
])
def test_label_fallback_left_top_chain(run, label_pos, img_pos, fallback_to):
    run(
        f"{label_pos.replace('-', '_')}_to_{fallback_to.replace('-', '_')}",
        extra_args=[
            "--image-position", img_pos,
            "--label-position", f"{label_pos} relative",
        ],
    )


@pytest.mark.parametrize("label_pos,img_pos,fallback_to", [
    # bottom/right-bottom → bottom-right: bottom side blocked, right side free
    ("bottom",       "bottom",        "bottom-right"),
    ("right-bottom", "bottom",        "bottom-right"),
    # bottom/right-bottom → bottom-left: bottom+right both blocked
    ("bottom",       "bottom-right",  "bottom-left"),
    ("right-bottom", "bottom-right",  "bottom-left"),
])
def test_label_fallback_bottom_chain(run, label_pos, img_pos, fallback_to):
    run(
        f"{label_pos.replace('-', '_')}_to_{fallback_to.replace('-', '_')}",
        extra_args=[
            "--image-position", img_pos,
            "--label-position", f"{label_pos} relative",
        ],
    )


@pytest.mark.parametrize("label_pos,img_pos,fallback_to", [
    # left-bottom → bottom-left: bottom side blocked, left side free
    ("left-bottom", "bottom",       "bottom-left"),
    # left-bottom → bottom-right: bottom+left both blocked
    ("left-bottom", "bottom-left",  "bottom-right"),
])
def test_label_fallback_left_bottom_chain(run, label_pos, img_pos, fallback_to):
    run(
        f"{label_pos.replace('-', '_')}_to_{fallback_to.replace('-', '_')}",
        extra_args=[
            "--image-position", img_pos,
            "--label-position", f"{label_pos} relative",
        ],
    )


# ── Label position fallback skip (all candidates exhausted) ──────────────────
#
# To exhaust all candidates in a chain, the image must physically fill the
# space that the fallback positions would occupy.  For example, the right-chain
# candidates are [right-side, top-side, bottom-side].  If the image fills the
# full canvas height at the right edge, all three have no pixel room.
#
# Technique: tiny 200×200 canvas + image scaled to fill it.
# With default 10px margins on all sides, a 171×200 image (portrait aspect ratio
# of our test images scaled to fit 200×200) leaves only 14–15px on left/right
# and 0px on top/bottom — all less than the 20px total margin required,
# making every candidate position in every chain have negative pixel space.

_SKIP_ARGS = [
    "--canvas-width-px",     "200",
    "--canvas-height-px",    "200",
    "--image-max-width-px",  "200",
    "--image-max-height-px", "200",
    "--scale-images",        "true",
    "--image-position",      "center",
]

@pytest.mark.parametrize("label_pos", ["right", "top-right", "bottom-right"])
def test_label_skip_right_chain(run_expect_skip, label_pos):
    run_expect_skip(extra_args=_SKIP_ARGS + ["--label-position", f"{label_pos} relative"])


@pytest.mark.parametrize("label_pos", ["left", "top-left", "bottom-left"])
def test_label_skip_left_chain(run_expect_skip, label_pos):
    run_expect_skip(extra_args=_SKIP_ARGS + ["--label-position", f"{label_pos} relative"])


@pytest.mark.parametrize("label_pos", ["top", "right-top", "left-top"])
def test_label_skip_top_chain(run_expect_skip, label_pos):
    run_expect_skip(extra_args=_SKIP_ARGS + ["--label-position", f"{label_pos} relative"])


@pytest.mark.parametrize("label_pos", ["bottom", "right-bottom", "left-bottom"])
def test_label_skip_bottom_chain(run_expect_skip, label_pos):
    run_expect_skip(extra_args=_SKIP_ARGS + ["--label-position", f"{label_pos} relative"])


# ── CSV header override ───────────────────────────────────────────────────────

def test_csv_header_override(run):
    """Use the no-header CSV file with an explicit CSV_HEADER."""
    run(
        "default",
        extra_args=[
            "--labels-csv",  str(INPUT_DIR / "tests-labels-no-header.csv"),
            "--csv-header",  "ID\tFILE\tAUTHOR\tBORN-DIED\tTITLE\tDATE\tTECHNIQUE\tLOCATION\tFORM\tTYPE\tSCHOOL\tTIMELINE\tURL",
            "--csv-file-column", "FILE",
        ],
    )
