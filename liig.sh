#!/bin/bash
# liig — Label-In-Image Generator
# Usage:
#   liig         — generate labelled images for every CSV row → OUTPUT_DIR
#   liig <index> — generate one labelled image for row <index> → OUTPUT_FILE
#                         index 0 = first data row (row after header, or row 1 if
#                         no header)

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────

CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/liig/config.toml"

# Parse a TOML config file (simple key = value / key = '''...''' only).
# Sets each key as a shell variable in the current environment.
load_config() {
    local file="$1"
    [[ -f "$file" ]] || return 0   # no config file is fine; defaults apply

    local in_multiline="" ml_key="" ml_val=""
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Continuation of a multiline literal string
        if [[ -n "$in_multiline" ]]; then
            if [[ "$line" == *"'''"* ]]; then
                # Closing delimiter — strip everything from ''' onward
                local tail="${line%%\'\'\'*}"
                ml_val+="${tail}"
                # Remove the leading newline that TOML adds after the opening '''
                ml_val="${ml_val#$'\n'}"
                printf -v "$ml_key" '%s' "$ml_val"
                in_multiline=""
                ml_key=""
                ml_val=""
            else
                ml_val+="${line}"$'\n'
            fi
            continue
        fi

        # Skip blank lines and comments
        [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue

        # key = value
        if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*(.*) ]]; then
            local key="${BASH_REMATCH[1]}"
            local val="${BASH_REMATCH[2]}"

            # Multiline literal string  '''
            if [[ "$val" == "'''"* ]]; then
                local rest="${val#\'\'\'}"
                if [[ "$rest" == *"'''"* ]]; then
                    # Opening and closing on same line
                    val="${rest%%\'\'\'*}"
                    printf -v "$key" '%s' "$val"
                else
                    in_multiline=1
                    ml_key="$key"
                    ml_val="${rest}"$'\n'
                fi
                continue
            fi

            # Single-quoted string
            if [[ "$val" =~ ^\'(.*)\'$ ]]; then
                val="${BASH_REMATCH[1]}"
            # Double-quoted string
            elif [[ "$val" =~ ^\"(.*)\"$ ]]; then
                val="${BASH_REMATCH[1]}"
            fi

            # Strip inline comment (only outside strings)
            val="${val%%[[:space:]]\#*}"

            printf -v "$key" '%s' "$val"
        fi
    done < "$file"
}

# ── Defaults ──────────────────────────────────────────────────────────────────
# Variables left empty here are required and must be set in the config file.
# Variables with values match the commented-out defaults in config.toml.example.

INPUT_DIR=""
LABELS_CSV=""
CSV_FILE_COLUMN="FILE"
CSV_HEADER=""
CSV_DELIMITER=""
OUTPUT_DIR="output"
OUTPUT_FILE="output.png"
CANVAS_WIDTH_PX=1920
CANVAS_HEIGHT_PX=1080
CANVAS_COLOR="none"
IMAGE_POSITION="center"
SCALE_IMAGES=false
IMAGE_MAX_WIDTH_PX=""
IMAGE_MAX_HEIGHT_PX=""
LABEL_POSITION="top-right relative"
LABEL_MARGINS_PX="10"
LABEL_ALIGNMENT="left"
LABEL_JUSTIFY="false"
LABEL_COLOR="black"
LABEL_FONT=""
LABEL_BACKGROUND_COLOR="none"
LABEL_PADDING_PX="10"
LABEL_MAX_WIDTH_PX=""
LABEL_FORMAT=""

# Pre-scan for --config before loading defaults
for (( _i=1; _i<=$#; _i++ )); do
    if [[ "${!_i}" == "--config" ]]; then
        _j=$(( _i + 1 ))
        CONFIG_FILE="${!_j}"
        break
    fi
done

load_config "$CONFIG_FILE"

die() { echo "liig: error: $*" >&2; exit 1; }

show_help() {
    cat <<'EOF'
Usage:
  liig [OPTIONS]        generate labelled images for every CSV row → OUTPUT_DIR
  liig [OPTIONS] INDEX  generate one labelled image for row INDEX  → OUTPUT_FILE
                        INDEX is 0-based (0 = first data row)

Options:
  -h, --help            show this help message and exit
  --config FILE         config file (default: $XDG_CONFIG_HOME/liig/config.toml)

Input:
  --input-dir DIR       directory containing source images
  --labels-csv FILE     path to the CSV file with label data
  --csv-file-column COL CSV column containing image file paths (default: FILE)
  --csv-header HDR      explicit header for headerless CSV files (same delimiter as the file)
  --csv-delimiter CHAR  field delimiter character (default: auto-detect)

Output:
  --output-dir DIR      batch output directory (default: output)
  --output-file FILE    single-mode output file (default: output.png)

Canvas:
  --canvas-width-px N   canvas width in pixels (default: 1920)
  --canvas-height-px N  canvas height in pixels (default: 1080)
  --canvas-color COLOR  canvas background color (default: none)

Image:
  --image-position POS  where to place the source image on the canvas
                        values: center | center-both |
                                top-left | top | top-right | right |
                                bottom-right | bottom | bottom-left | left
                        center-both centers the image+label block as a unit
                        (default: center)
  --scale-images BOOL   scale images up to fill max dimensions (default: false)
  --image-max-width-px N   max image width in pixels
  --image-max-height-px N  max image height in pixels

Label:
  --label-position POS  label placement: POSITION [relative|absolute|relative-inner]
                        positions: center |
                                   top | right-top | left-top |
                                   right | top-right | bottom-right |
                                   bottom | right-bottom | left-bottom |
                                   left | top-left | bottom-left
                        relative       — place label adjacent to the image edge
                        absolute       — place label at a fixed canvas region
                        relative-inner — place label inside the image bounds
                        (default: "top-right relative")
  --label-margins-px PX outer spacing around the label box; CSS shorthand:
                        1 value: all sides  2 values: top/bottom right/left
                        4 values: top right bottom left  (default: 10)
  --label-padding-px PX inner spacing between the label border and text content;
                        same shorthand as --label-margins-px  (default: 10)
  --label-alignment ALN text alignment within the label box: left | center | right
                        (default: left)
  --label-justify BOOL  stretch full lines to fill the label box width (default: false)
  --label-color COLOR   label text color (default: black)
  --label-font FONT     Pango font description, e.g. "Sans Bold 14"
  --label-background-color COLOR
                        background color painted behind the label text (default: none)
  --label-max-width-px N  cap the label text box width; text wraps at this width
                          even if more canvas space is available
  --label-format FMT    label text with {COLUMN_NAME} placeholders for CSV columns;
                        supports Pango markup  (default: {FILE})
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)                show_help; exit 0 ;;
            --config)                 shift 2 ;;  # already handled by pre-scan
            --input-dir)              INPUT_DIR="$2";              shift 2 ;;
            --labels-csv)             LABELS_CSV="$2";             shift 2 ;;
            --csv-file-column)        CSV_FILE_COLUMN="$2";        shift 2 ;;
            --csv-header)             CSV_HEADER="$2";             shift 2 ;;
            --csv-delimiter)          CSV_DELIMITER="$2";          shift 2 ;;
            --output-dir)             OUTPUT_DIR="$2";             shift 2 ;;
            --output-file)            OUTPUT_FILE="$2";            shift 2 ;;
            --canvas-width-px)        CANVAS_WIDTH_PX="$2";        shift 2 ;;
            --canvas-height-px)       CANVAS_HEIGHT_PX="$2";       shift 2 ;;
            --canvas-color)           CANVAS_COLOR="$2";           shift 2 ;;
            --image-position)         IMAGE_POSITION="$2";         shift 2 ;;
            --scale-images)           SCALE_IMAGES="$2";           shift 2 ;;
            --image-max-width-px)     IMAGE_MAX_WIDTH_PX="$2";     shift 2 ;;
            --image-max-height-px)    IMAGE_MAX_HEIGHT_PX="$2";    shift 2 ;;
            --label-position)         LABEL_POSITION="$2";         shift 2 ;;
            --label-margins-px)       LABEL_MARGINS_PX="$2";       shift 2 ;;
            --label-alignment)        LABEL_ALIGNMENT="$2";        shift 2 ;;
            --label-justify)          LABEL_JUSTIFY="$2";          shift 2 ;;
            --label-color)            LABEL_COLOR="$2";            shift 2 ;;
            --label-font)             LABEL_FONT="$2";             shift 2 ;;
            --label-background-color) LABEL_BACKGROUND_COLOR="$2"; shift 2 ;;
            --label-padding-px)       LABEL_PADDING_PX="$2";       shift 2 ;;
            --label-max-width-px)     LABEL_MAX_WIDTH_PX="$2";     shift 2 ;;
            --label-format)           LABEL_FORMAT="$2";           shift 2 ;;
            -*)                       die "Unknown option: $1" ;;
            *)
                [[ -z "${_INDEX:-}" ]] || die "Unexpected positional argument: $1"
                _INDEX="$1"
                shift
                ;;
        esac
    done
}

_INDEX=""
parse_args "$@"

[[ -n "$INPUT_DIR"        ]] || die "INPUT_DIR is required (set in config or pass --input-dir)"
[[ -n "$LABELS_CSV"       ]] || die "LABELS_CSV is required (set in config or pass --labels-csv)"

if [[ -z "$CSV_DELIMITER" ]]; then
    _first_line=$(head -1 "$LABELS_CSV")
    _tab_count=$(printf '%s' "$_first_line" | tr -cd '\t' | wc -c)
    _comma_count=$(printf '%s' "$_first_line" | tr -cd ',' | wc -c)
    if (( _tab_count >= _comma_count && _tab_count > 0 )); then
        CSV_DELIMITER=$'\t'
    elif (( _comma_count > 0 )); then
        CSV_DELIMITER=','
    else
        CSV_DELIMITER=$'\t'
    fi
    unset _first_line _tab_count _comma_count
fi


[[ -n "$LABEL_FORMAT"     ]] || die "LABEL_FORMAT is required (set in config or pass --label-format)"

# IMAGE_MAX_WIDTH/HEIGHT default to canvas size if not set
[[ -z "$IMAGE_MAX_WIDTH_PX"  ]] && IMAGE_MAX_WIDTH_PX=$(( CANVAS_WIDTH_PX * 8 / 10 ))
[[ -z "$IMAGE_MAX_HEIGHT_PX" ]] && IMAGE_MAX_HEIGHT_PX="$CANVAS_HEIGHT_PX"

# ── Helpers ───────────────────────────────────────────────────────────────────

escape_pango() {
    printf '%s' "$1" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g'
}

# Parse CSS-style margin shorthand into four variables: _top _right _bottom _left
parse_margins() {
    local spec="$1"
    read -r -a parts <<< "$spec"
    case "${#parts[@]}" in
        1) _top="${parts[0]}"; _right="${parts[0]}"; _bottom="${parts[0]}"; _left="${parts[0]}" ;;
        2) _top="${parts[0]}"; _right="${parts[1]}"; _bottom="${parts[0]}"; _left="${parts[1]}" ;;
        3) _top="${parts[0]}"; _right="${parts[1]}"; _bottom="${parts[2]}"; _left="${parts[1]}" ;;
        4) _top="${parts[0]}"; _right="${parts[1]}"; _bottom="${parts[2]}"; _left="${parts[3]}" ;;
        *) die "LABEL_MARGINS_PX must be 1–4 space-separated pixel values, got: '$spec'" ;;
    esac
}

# Return the ImageMagick -gravity keyword for a given position string
# (top-left → NorthWest, right → East, etc.)
position_to_gravity() {
    case "$1" in
        top-left)     echo "NorthWest" ;;
        top)          echo "North"     ;;
        top-right)    echo "NorthEast" ;;
        right)        echo "East"      ;;
        bottom-right) echo "SouthEast" ;;
        bottom)       echo "South"     ;;
        bottom-left)  echo "SouthWest" ;;
        left)         echo "West"      ;;
        center)       echo "Center"    ;;
        center-both)  echo "NorthWest" ;;
        *) die "Unknown position: '$1'" ;;
    esac
}

# Compute _min_txt_w: the minimum text-box width to consider a position usable.
# = pixel width of min(8, longest_plain_text_line) characters in the configured font.
# Requires global _label_font_arg. Sets global _min_txt_w.
_compute_min_txt_w() {
    local pango_text="$1"

    # Strip pango markup to plain text, find the longest line
    local plain max_len=0 line
    plain=$(printf '%s' "$pango_text" | sed 's/<[^>]*>//g')
    while IFS= read -r line; do
        local len=${#line}
        (( len > max_len )) && max_len=$len
    done <<< "$plain"
    (( max_len < 1 )) && max_len=1

    # Sample string of min(8, max_len) 'X' characters
    local min_chars=$(( max_len < 8 ? max_len : 8 ))
    local tmpl="XXXXXXXX"
    local sample="${tmpl:0:$min_chars}"

    _min_txt_w=$(magick "${_label_font_arg[@]}" -fill black \
        pango:"$sample" -format "%w\n" info:)
}

# Returns 0 (success) if the candidate label position has enough pixel space
# to fit the full label text (including wrapping) with margins applied.
# Requires globals: _pango_text, _label_font_arg, _min_txt_w.
_label_pos_has_room() {
    local img_x="$1" img_y="$2" img_w="$3" img_h="$4"
    local txt_pos="$5" txt_mode="$6"
    [[ "$txt_mode" == "absolute" || "$txt_mode" == "relative-inner" ]] && return 0

    local tx ty tw th
    read -r tx ty tw th < <(text_geometry "$img_x" "$img_y" "$img_w" "$img_h" "$txt_pos" "$txt_mode")

    # Not wide enough for the minimum text (also catches tw <= 0)
    (( tw < _min_txt_w )) && return 1

    # Not tall enough to fit all text rendered at this width (wrapping included)
    local rendered_h
    rendered_h=$(magick "${_label_font_arg[@]}" -size "${tw}x" -fill black \
        pango:"${_pango_text}" -format "%h\n" info:)
    (( rendered_h > th )) && return 1

    return 0
}

# Resolves the effective label position, trying fallbacks when the requested
# position is blocked by the image.  Echoes the resolved position, or nothing
# if every candidate is blocked (caller should render without a label).
#
# Fallback chains (per-edge, then cross-edge):
#   top-right / right   → right-top  → right-bottom
#   bottom-right        → right-bottom → right-top
#   top-left / left     → left-top   → left-bottom
#   bottom-left         → left-bottom → left-top
#   top / right-top     → top-right  → top-left
#   left-top            → top-left   → top-right
#   bottom / right-bottom → bottom-right → bottom-left
#   left-bottom         → bottom-left → bottom-right
resolve_label_position() {
    local img_x="$1" img_y="$2" img_w="$3" img_h="$4"
    local txt_pos="$5" txt_mode="$6"

    [[ "$txt_mode" == "absolute" || "$txt_mode" == "relative-inner" ]] && { echo "$txt_pos"; return 0; }

    local -a candidates
    case "$txt_pos" in
        top-right | right)      candidates=( "$txt_pos" right-top    right-bottom  ) ;;
        bottom-right)           candidates=( bottom-right right-bottom right-top   ) ;;
        top-left | left)        candidates=( "$txt_pos" left-top     left-bottom   ) ;;
        bottom-left)            candidates=( bottom-left left-bottom  left-top     ) ;;
        top | right-top)        candidates=( "$txt_pos" top-right    top-left      ) ;;
        left-top)               candidates=( left-top    top-left     top-right    ) ;;
        bottom | right-bottom)  candidates=( "$txt_pos" bottom-right  bottom-left  ) ;;
        left-bottom)            candidates=( left-bottom  bottom-left  bottom-right ) ;;
        *)  echo "$txt_pos"; return 0 ;;   # center etc. — no conflicts possible
    esac

    local pos
    for pos in "${candidates[@]}"; do
        if _label_pos_has_room "$img_x" "$img_y" "$img_w" "$img_h" "$pos" "$txt_mode"; then
            echo "$pos"; return 0
        fi
    done
    return 1   # all candidates exhausted — no room anywhere
}

# ── CSV helpers ───────────────────────────────────────────────────────────────

# Read the header row and determine if the CSV has one.
# Sets globals: _headers (associative array col→index), _has_header, _data_start_line
init_csv() {
    declare -gA _col_index=()
    _has_header=0
    _data_start_line=1

    local first_line
    first_line=$(sed -n '1p' "$LABELS_CSV")

    local effective_header=""
    if [[ -n "$CSV_HEADER" ]]; then
        effective_header="$CSV_HEADER"
        # Check column count matches
        local csv_cols
        csv_cols=$(awk -F"$CSV_DELIMITER" '{print NF; exit}' "$LABELS_CSV")
        local hdr_cols
        hdr_cols=$(awk -F"$CSV_DELIMITER" '{print NF; exit}' <<< "$CSV_HEADER")
        # If the first line of the CSV looks like a header (contains CSV_FILE_COLUMN),
        # skip it; otherwise treat line 1 as data.
        if echo "$first_line" | grep -qF "$CSV_FILE_COLUMN"; then
            _has_header=1
            _data_start_line=2
            # Validate column counts match
            [[ "$csv_cols" -eq "$hdr_cols" ]] || \
                die "CSV_HEADER has $hdr_cols columns but CSV file has $csv_cols columns"
        else
            _data_start_line=1
            [[ "$csv_cols" -eq "$hdr_cols" ]] || \
                die "CSV_HEADER has $hdr_cols columns but CSV file has $csv_cols columns"
        fi
    else
        # No explicit header — first line must be a header
        if echo "$first_line" | grep -qF "$CSV_FILE_COLUMN"; then
            effective_header="$first_line"
            _has_header=1
            _data_start_line=2
        else
            # No header anywhere
            die "No CSV_HEADER set and the first CSV line does not appear to be a header (column '$CSV_FILE_COLUMN' not found)"
        fi
    fi

    # Build column index map
    local i=0
    IFS="$CSV_DELIMITER" read -r -a _hdr_cols <<< "$effective_header"
    for col in "${_hdr_cols[@]}"; do
        _col_index["$col"]=$i
        (( ++i ))
    done
}

# Given a 0-based data index, read that CSV row into associative array _row
read_csv_row() {
    local index="$1"
    local line_num=$(( _data_start_line + index ))
    local raw_line
    raw_line=$(sed -n "${line_num}p" "$LABELS_CSV")
    [[ -n "$raw_line" ]] || die "CSV index $index is out of range"

    declare -gA _row=()
    IFS="$CSV_DELIMITER" read -r -a _fields <<< "$raw_line"
    for col in "${!_col_index[@]}"; do
        local idx="${_col_index[$col]}"
        _row["$col"]="${_fields[$idx]:-}"
    done
}

csv_row_count() {
    local total
    total=$(wc -l < "$LABELS_CSV")
    echo $(( total - _data_start_line + 1 ))
}

# ── Label rendering ───────────────────────────────────────────────────────────

# Substitute {COLUMN} placeholders and unescape TOML literal-string sequences.
# Pango-escapes each field value before substitution.
build_pango_text() {
    local fmt="$LABEL_FORMAT"
    # Trim leading/trailing newlines added by TOML multiline strings
    fmt="${fmt#$'\n'}"
    fmt="${fmt%$'\n'}"

    for col in "${!_row[@]}"; do
        local escaped
        escaped=$(escape_pango "${_row[$col]}")
        fmt="${fmt//\{$col\}/$escaped}"
    done
    printf '%s' "$fmt"
}

# Compute image resize geometry string
resize_geometry() {
    local src="$1"
    local max_w="$IMAGE_MAX_WIDTH_PX"
    local max_h="$IMAGE_MAX_HEIGHT_PX"

    if [[ "$SCALE_IMAGES" == "true" ]]; then
        # Scale to fill the max box (up or down)
        echo "${max_w}x${max_h}"
    else
        # Scale down only (never up)
        echo "${max_w}x${max_h}>"
    fi
}

# Calculate (image_x, image_y) on canvas given image dims and IMAGE_POSITION
image_offset() {
    local img_w="$1" img_h="$2"
    local canvas_w="$CANVAS_WIDTH_PX" canvas_h="$CANVAS_HEIGHT_PX"

    local ix=0 iy=0
    case "$IMAGE_POSITION" in
        top-left)     ix=0;                              iy=0 ;;
        top)          ix=$(( (canvas_w - img_w) / 2 ));  iy=0 ;;
        top-right)    ix=$(( canvas_w - img_w ));         iy=0 ;;
        right)        ix=$(( canvas_w - img_w ));         iy=$(( (canvas_h - img_h) / 2 )) ;;
        bottom-right) ix=$(( canvas_w - img_w ));         iy=$(( canvas_h - img_h )) ;;
        bottom)       ix=$(( (canvas_w - img_w) / 2 ));  iy=$(( canvas_h - img_h )) ;;
        bottom-left)  ix=0;                              iy=$(( canvas_h - img_h )) ;;
        left)         ix=0;                              iy=$(( (canvas_h - img_h) / 2 )) ;;
        center)       ix=$(( (canvas_w - img_w) / 2 ));  iy=$(( (canvas_h - img_h) / 2 )) ;;
        center-both)  ix=$(( (canvas_w - img_w) / 2 ));  iy=$(( (canvas_h - img_h) / 2 )) ;;
    esac
    echo "$ix $iy"
}

# Return (text_x, text_y, text_w, text_h_limit) given image/canvas dims,
# text position/mode/margins, and (optionally) the pre-rendered label dimensions.
#
# Each position is defined by an anchor: a specific point on the label box that
# aligns with a specific point on the image (relative) or canvas (absolute).
# rendered_w and rendered_h (args 7 and 8, default 0) are the trimmed pixel
# dimensions of the rendered label.  Passing 0 returns correct tw/th but
# placeholder tx/ty; call again with actual rendered dims to get the final tx/ty.
text_geometry() {
    local img_x="$1" img_y="$2" img_w="$3" img_h="$4"
    local txt_pos="$5" txt_mode="$6"
    local rendered_w="${7:-0}" rendered_h="${8:-0}"
    local canvas_w="$CANVAS_WIDTH_PX" canvas_h="$CANVAS_HEIGHT_PX"

    parse_margins "$LABEL_MARGINS_PX"
    local mt="$_top" mr="$_right" mb="$_bottom" ml="$_left"
    parse_margins "$LABEL_PADDING_PX"
    local mt="$((mt + $_top))" mr="$((mr + $_right))" mb="$((mb + $_bottom))" ml="$((ml + $_left))"

    local tx=0 ty=0 tw=0 th=0

    if [[ "$txt_mode" == "relative" ]]; then
        case "$txt_pos" in
            # ── Right of image ────────────────────────────────────────────────
            top-right)
                # anchor: top-left of label = top-right of image
                tx=$(( img_x + img_w + ml ))
                ty=$(( img_y + mt ))
                tw=$(( canvas_w - tx - mr ))
                th=$(( canvas_h - ty - mb ))
                ;;
            right)
                # anchor: midpoint of left edge of label = midpoint of right edge of image
                tx=$(( img_x + img_w + ml ))
                ty=$(( img_y + img_h / 2 - rendered_h / 2 ))
                tw=$(( canvas_w - tx - mr ))
                th=$(( img_h - mt - mb ))
                ;;
            bottom-right)
                # anchor: bottom-left of label = bottom-right of image
                tx=$(( img_x + img_w + ml ))
                ty=$(( img_y + img_h - mb - rendered_h ))
                tw=$(( canvas_w - tx - mr ))
                th=$(( img_h - mt - mb ))
                ;;
            # ── Left of image ─────────────────────────────────────────────────
            top-left)
                # anchor: top-right of label = top-left of image
                tx=$(( img_x - mr - rendered_w ))
                ty=$(( img_y + mt ))
                tw=$(( img_x - ml - mr ))
                th=$(( canvas_h - ty - mb ))
                ;;
            left)
                # anchor: midpoint of right edge of label = midpoint of left edge of image
                tx=$(( img_x - mr - rendered_w ))
                ty=$(( img_y + img_h / 2 - rendered_h / 2 ))
                tw=$(( img_x - ml - mr ))
                th=$(( img_h - mt - mb ))
                ;;
            bottom-left)
                # anchor: bottom-right of label = bottom-left of image
                tx=$(( img_x - mr - rendered_w ))
                ty=$(( img_y + img_h - mb - rendered_h ))
                tw=$(( img_x - ml - mr ))
                th=$(( img_h - mt - mb ))
                ;;
            # ── Above image ───────────────────────────────────────────────────
            top)
                # anchor: midpoint of bottom edge of label = midpoint of top edge of image
                tx=$(( img_x + img_w / 2 - rendered_w / 2 ))
                ty=$(( img_y - mb - rendered_h ))
                tw=$(( img_w - ml - mr ))
                th=$(( img_y - mt - mb ))
                ;;
            right-top)
                # anchor: bottom-right of label = top-right of image
                tx=$(( img_x + img_w - mr - rendered_w ))
                ty=$(( img_y - mb - rendered_h ))
                tw=$(( img_w / 2 - ml - mr ))
                th=$(( img_y - mt - mb ))
                ;;
            left-top)
                # anchor: bottom-left of label = top-left of image
                tx=$(( img_x + ml ))
                ty=$(( img_y - mb - rendered_h ))
                tw=$(( img_w / 2 - ml - mr ))
                th=$(( img_y - mt - mb ))
                ;;
            # ── Below image ───────────────────────────────────────────────────
            bottom)
                # anchor: midpoint of top edge of label = midpoint of bottom edge of image
                tx=$(( img_x + img_w / 2 - rendered_w / 2 ))
                ty=$(( img_y + img_h + mt ))
                tw=$(( img_w - ml - mr ))
                th=$(( canvas_h - img_y - img_h - mt - mb ))
                ;;
            right-bottom)
                # anchor: top-right of label = bottom-right of image
                tx=$(( img_x + img_w - mr - rendered_w ))
                ty=$(( img_y + img_h + mt ))
                tw=$(( img_w / 2 - ml - mr ))
                th=$(( canvas_h - img_y - img_h - mt - mb ))
                ;;
            left-bottom)
                # anchor: top-left of label = bottom-left of image
                tx=$(( img_x + ml ))
                ty=$(( img_y + img_h + mt ))
                tw=$(( img_w / 2 - ml - mr ))
                th=$(( canvas_h - img_y - img_h - mt - mb ))
                ;;
            # ── Center (over image) ───────────────────────────────────────────
            center)
                # anchor: centerpoint of label = centerpoint of image
                tx=$(( img_x + img_w / 2 - rendered_w / 2 ))
                ty=$(( img_y + img_h / 2 - rendered_h / 2 ))
                tw=$(( img_w - ml - mr ))
                th=$(( img_h - mt - mb ))
                ;;
        esac
    elif [[ "$txt_mode" == "relative-inner" ]]; then
        # relative-inner: same anchor semantics as absolute but relative to the image bounds.
        local hih=$(( img_h / 2 ))
        case "$txt_pos" in
            top)
                # anchor: midpoint of top edge of label = midpoint of top edge of image
                tx=$(( img_x + img_w / 2 - rendered_w / 2 ))
                ty=$(( img_y + mt ))
                tw=$(( img_w - ml - mr ));  th=$(( img_h - mt - mb ))
                ;;
            bottom)
                # anchor: midpoint of bottom edge of label = midpoint of bottom edge of image
                tx=$(( img_x + img_w / 2 - rendered_w / 2 ))
                ty=$(( img_y + img_h - mb - rendered_h ))
                tw=$(( img_w - ml - mr ));  th=$(( img_h - mt - mb ))
                ;;
            left)
                # anchor: midpoint of left edge of label = midpoint of left edge of image
                tx=$(( img_x + ml ))
                ty=$(( img_y + hih - rendered_h / 2 ))
                tw=$(( img_w - ml - mr ));  th=$(( img_h - mt - mb ))
                ;;
            right)
                # anchor: midpoint of right edge of label = midpoint of right edge of image
                tx=$(( img_x + img_w - mr - rendered_w ))
                ty=$(( img_y + hih - rendered_h / 2 ))
                tw=$(( img_w - ml - mr ));  th=$(( img_h - mt - mb ))
                ;;
            top-left | left-top)
                # anchor: top-left of label = top-left of image
                tx=$(( img_x + ml ));       ty=$(( img_y + mt ))
                tw=$(( img_w - ml - mr ));  th=$(( img_h - mt - mb ))
                ;;
            top-right | right-top)
                # anchor: top-right of label = top-right of image
                tx=$(( img_x + img_w - mr - rendered_w ))
                ty=$(( img_y + mt ))
                tw=$(( img_w - ml - mr ));  th=$(( img_h - mt - mb ))
                ;;
            bottom-left | left-bottom)
                # anchor: bottom-left of label = bottom-left of image
                tx=$(( img_x + ml ))
                ty=$(( img_y + img_h - mb - rendered_h ))
                tw=$(( img_w - ml - mr ));  th=$(( img_h - mt - mb ))
                ;;
            bottom-right | right-bottom)
                # anchor: bottom-right of label = bottom-right of image
                tx=$(( img_x + img_w - mr - rendered_w ))
                ty=$(( img_y + img_h - mb - rendered_h ))
                tw=$(( img_w - ml - mr ));  th=$(( img_h - mt - mb ))
                ;;
            center)
                # anchor: centerpoint of label = centerpoint of image
                tx=$(( img_x + img_w / 2 - rendered_w / 2 ))
                ty=$(( img_y + hih - rendered_h / 2 ))
                tw=$(( img_w - ml - mr ));  th=$(( img_h - mt - mb ))
                ;;
        esac
    else
        # absolute: positions refer to fixed canvas regions independent of the image.
        local hw=$(( canvas_w / 2 )) hh=$(( canvas_h / 2 ))
        case "$txt_pos" in
            top)
                # anchor: midpoint of top edge of label = midpoint of top edge of canvas
                tx=$(( hw - rendered_w / 2 ))
                ty=$mt
                tw=$(( canvas_w - ml - mr ));   th=$(( hh - mt - mb ))
                ;;
            bottom)
                # anchor: midpoint of bottom edge of label = midpoint of bottom edge of canvas
                tx=$(( hw - rendered_w / 2 ))
                ty=$(( canvas_h - mb - rendered_h ))
                tw=$(( canvas_w - ml - mr ));   th=$(( hh - mt - mb ))
                ;;
            left)
                # anchor: midpoint of left edge of label = midpoint of left edge of canvas
                tx=$ml
                ty=$(( hh - rendered_h / 2 ))
                tw=$(( hw - ml - mr ));         th=$(( canvas_h - mt - mb ))
                ;;
            right)
                # anchor: midpoint of right edge of label = midpoint of right edge of canvas
                tx=$(( canvas_w - mr - rendered_w ))
                ty=$(( hh - rendered_h / 2 ))
                tw=$(( hw - ml - mr ));         th=$(( canvas_h - mt - mb ))
                ;;
            top-left | left-top)
                # anchor: top-left of label = top-left of canvas
                tx=$ml;         ty=$mt
                tw=$(( hw - ml - mr ));         th=$(( hh - mt - mb ))
                ;;
            top-right | right-top)
                # anchor: top-right of label = top-right of canvas
                tx=$(( canvas_w - mr - rendered_w ))
                ty=$mt
                tw=$(( hw - ml - mr ));         th=$(( hh - mt - mb ))
                ;;
            bottom-left | left-bottom)
                # anchor: bottom-left of label = bottom-left of canvas
                tx=$ml
                ty=$(( canvas_h - mb - rendered_h ))
                tw=$(( hw - ml - mr ));         th=$(( hh - mt - mb ))
                ;;
            bottom-right | right-bottom)
                # anchor: bottom-right of label = bottom-right of canvas
                tx=$(( canvas_w - mr - rendered_w ))
                ty=$(( canvas_h - mb - rendered_h ))
                tw=$(( hw - ml - mr ));         th=$(( hh - mt - mb ))
                ;;
            center)
                # anchor: centerpoint of label = centerpoint of canvas
                tx=$(( canvas_w / 2 - rendered_w / 2 ))
                ty=$(( canvas_h / 2 - rendered_h / 2 ))
                tw=$(( canvas_w - ml - mr ));   th=$(( canvas_h - mt - mb ))
                ;;
        esac
    fi

    echo "$tx $ty $tw $th"
}

# ── Core image generation ─────────────────────────────────────────────────────

generate_image() {
    local index="$1"
    local out_path="$2"

    read_csv_row "$index"

    local file_col_idx="${_col_index[$CSV_FILE_COLUMN]:-}"
    [[ -n "$file_col_idx" ]] || die "CSV_FILE_COLUMN '$CSV_FILE_COLUMN' not found in header"
    local rel_path="${_row[$CSV_FILE_COLUMN]}"
    local src_image="${INPUT_DIR}/${rel_path}"
    [[ -f "$src_image" ]] || { echo "liig: warning: '$src_image' not found, skipping." >&2; return 1; }

    local resize_geo
    resize_geo=$(resize_geometry "$src_image")

    # Actual rendered size of the image
    local img_w img_h
    read -r img_w img_h < <(magick "$src_image" -resize "$resize_geo" -format "%w %h\n" info:)

    local img_offset
    img_offset=$(image_offset "$img_w" "$img_h")
    local img_x img_y
    read -r img_x img_y <<< "$img_offset"

    # Parse LABEL_POSITION
    local txt_pos txt_mode="relative"
    read -r -a tp_parts <<< "$LABEL_POSITION"
    txt_pos="${tp_parts[0]}"
    [[ "${#tp_parts[@]}" -ge 2 ]] && txt_mode="${tp_parts[1]}"

    # Pre-compute label text and font args; _label_pos_has_room reads these globals
    # from the subshell created by resolve_label_position.
    _label_font_arg=()
    [[ -n "$LABEL_FONT" ]] && _label_font_arg=(-font "$LABEL_FONT")
    _pango_text=$(build_pango_text)
    _min_txt_w=1
    _compute_min_txt_w "$_pango_text"

    # For center-both, use extremal image coordinates so text_geometry/resolve_label_position
    # sees the maximum available text width and the room check reflects reality.
    if [[ "$IMAGE_POSITION" == "center-both" ]]; then
        case "$txt_pos" in
            top-right|right|bottom-right) img_x=0 ;;
            top-left|left|bottom-left)    img_x=$(( CANVAS_WIDTH_PX - img_w )) ;;
            top|left-top|right-top)       img_y=$(( CANVAS_HEIGHT_PX - img_h )) ;;
            bottom|left-bottom|right-bottom) img_y=0 ;;
        esac
    fi

    local effective_pos
    effective_pos=$(resolve_label_position "$img_x" "$img_y" "$img_w" "$img_h" "$txt_pos" "$txt_mode") || true
    if [[ -z "$effective_pos" ]]; then
        echo "liig: error: index $index: no room for label at any fallback position, skipping" >&2
        return 1
    elif [[ "$effective_pos" != "$txt_pos" ]]; then
        echo "liig: warning: index $index: label position '$txt_pos' has no room, falling back to '$effective_pos'" >&2
        txt_pos="$effective_pos"
    fi

    # Map LABEL_ALIGNMENT and LABEL_JUSTIFY to pango defines.
    local pango_align="left"
    case "$LABEL_ALIGNMENT" in
        right)  pango_align="right" ;;
        center) pango_align="center" ;;
    esac
    local pango_justify_arg=()
    [[ "$LABEL_JUSTIFY" == "true" ]] && pango_justify_arg=(-define pango:justify=true)

    # First pass: get tw (rendered dims don't affect tw/th)
    local _tx0 _ty0 tw th
    read -r _tx0 _ty0 tw th < <(text_geometry "$img_x" "$img_y" "$img_w" "$img_h" "$txt_pos" "$txt_mode")
    [[ -n "$LABEL_MAX_WIDTH_PX" ]] && (( LABEL_MAX_WIDTH_PX < tw )) && tw=$LABEL_MAX_WIDTH_PX

    # Pre-render to get actual label dimensions for anchor-point calculations
    local rendered_w rendered_h
    read -r rendered_w rendered_h < <(
        magick "${_label_font_arg[@]}" \
            -fill "$LABEL_COLOR" -background none \
            -size "${tw}x" \
            -define pango:align="$pango_align" \
            "${pango_justify_arg[@]}" \
            pango:"${_pango_text}" -trim -format "%w %h\n" info:
    )

    # Second pass: get final tx/ty using actual rendered dimensions
    local tx ty
    read -r tx ty tw th < <(text_geometry "$img_x" "$img_y" "$img_w" "$img_h" "$txt_pos" "$txt_mode" "$rendered_w" "$rendered_h")
    [[ -n "$LABEL_MAX_WIDTH_PX" ]] && (( LABEL_MAX_WIDTH_PX < tw )) && tw=$LABEL_MAX_WIDTH_PX

    # For center-both: recompute img_x/img_y so the image+label block is centered,
    # then redo text_geometry with the final image position to get correct tx/ty.
    if [[ "$IMAGE_POSITION" == "center-both" ]]; then
        parse_margins "$LABEL_MARGINS_PX"
        local cb_ml="$_left" cb_mr="$_right" cb_mt="$_top" cb_mb="$_bottom"
        parse_margins "$LABEL_PADDING_PX"
        cb_ml=$(( cb_ml + _left ))
        cb_mr=$(( cb_mr + _right ))
        cb_mt=$(( cb_mt + _top ))
        cb_mb=$(( cb_mb + _bottom ))
        case "$txt_pos" in
            top-right|right|bottom-right)
                img_x=$(( (CANVAS_WIDTH_PX - img_w - cb_ml - rendered_w) / 2 ))
                img_y=$(( (CANVAS_HEIGHT_PX - img_h) / 2 ))
                ;;
            top-left|left|bottom-left)
                img_x=$(( (CANVAS_WIDTH_PX - img_w + cb_mr + rendered_w) / 2 ))
                img_y=$(( (CANVAS_HEIGHT_PX - img_h) / 2 ))
                ;;
            top|left-top|right-top)
                img_x=$(( (CANVAS_WIDTH_PX - img_w) / 2 ))
                img_y=$(( (CANVAS_HEIGHT_PX - img_h + cb_mb + rendered_h) / 2 ))
                ;;
            bottom|left-bottom|right-bottom)
                img_x=$(( (CANVAS_WIDTH_PX - img_w) / 2 ))
                img_y=$(( (CANVAS_HEIGHT_PX - img_h - cb_mt - rendered_h) / 2 ))
                ;;
            *)
                img_x=$(( (CANVAS_WIDTH_PX - img_w) / 2 ))
                img_y=$(( (CANVAS_HEIGHT_PX - img_h) / 2 ))
                ;;
        esac
        read -r tx ty tw th < <(text_geometry "$img_x" "$img_y" "$img_w" "$img_h" "$txt_pos" "$txt_mode" "$rendered_w" "$rendered_h")
        [[ -n "$LABEL_MAX_WIDTH_PX" ]] && (( LABEL_MAX_WIDTH_PX < tw )) && tw=$LABEL_MAX_WIDTH_PX
    fi

    # Parse padding: extends the background beyond the text content area
    parse_margins "$LABEL_PADDING_PX"
    local padt="$_top" padr="$_right" padb="$_bottom" padl="$_left"
    local bg_tx=$(( tx - padl )) bg_ty=$(( ty - padt ))

    # Extend the canvas to add padding around the trimmed text image.
    # Using -extent instead of -splice: -gravity West -splice fails on images
    # below a certain size threshold with "pixels are not authentic" from
    # QueueAuthenticPixelCacheNexus.
    local pad_splice_args=()
    if (( padl + padr + padt + padb > 0 )); then
        pad_splice_args=(
            -background none -gravity NorthWest
            -extent "%[fx:w+${padl}+${padr}]x%[fx:h+${padt}+${padb}]-${padl}-${padt}"
        )
    fi

    local img_gravity img_geom
    if [[ "$IMAGE_POSITION" == "center-both" ]]; then
        img_gravity="NorthWest"
        img_geom="+${img_x}+${img_y}"
    else
        img_gravity=$(position_to_gravity "$IMAGE_POSITION")
        img_geom="+0+0"
    fi

    local size_arg="${CANVAS_WIDTH_PX}x${CANVAS_HEIGHT_PX}"

    # Apply background color after trimming so it covers only the text content area.
    local label_bg_after=()
    [[ "$LABEL_BACKGROUND_COLOR" != "none" ]] && \
        label_bg_after=(\( +clone -alpha opaque -fill "$LABEL_BACKGROUND_COLOR" -colorize 100 \) +swap -compose Over -composite)

    magick \
        -size "$size_arg" "xc:${CANVAS_COLOR}" \
        \( "$src_image" -resize "$resize_geo" \) \
        -gravity "$img_gravity" \
        -geometry "$img_geom" \
        -composite \
        \( \
            -gravity Center \
            "${_label_font_arg[@]}" \
            -fill "$LABEL_COLOR" \
            -background none \
            -size "${tw}x" \
            -define pango:align="$pango_align" \
            "${pango_justify_arg[@]}" \
            pango:"${_pango_text}" \
            -trim +repage \
            "${pad_splice_args[@]}" \
            "${label_bg_after[@]}" \
        \) \
        -gravity NorthWest \
        -geometry "+${bg_tx}+${bg_ty}" \
        -composite \
        "$out_path"
}

# ── Modes ─────────────────────────────────────────────────────────────────────

mode_single() {
    local index="${1:-}"
    [[ "$index" =~ ^[0-9]+$ ]] || die "index must be a non-negative integer, got '$index'"

    echo "Waiting for INPUT_DIR '${INPUT_DIR}' to exist..."
    while [[ ! -d "$INPUT_DIR" ]]; do sleep 2; done

    init_csv
    generate_image "$index" "$OUTPUT_FILE"
    echo "liig: wrote $OUTPUT_FILE"
}

mode_batch() {
    echo "Waiting for INPUT_DIR '${INPUT_DIR}' to exist..."
    while [[ ! -d "$INPUT_DIR" ]]; do sleep 2; done

    init_csv
    local total
    total=$(csv_row_count)
    echo "liig: processing $total rows → $OUTPUT_DIR"
    mkdir -p "$OUTPUT_DIR"

    local i
    for (( i = 0; i < total; i++ )); do
        read_csv_row "$i"
        local rel_path="${_row[$CSV_FILE_COLUMN]}"
        local out_path="${OUTPUT_DIR}/${rel_path}"
        mkdir -p "$(dirname "$out_path")"
        # Replace extension with .png
        out_path="${out_path%.*}.png"
        if generate_image "$i" "$out_path"; then
            echo "liig: [$i/$total] $out_path"
        fi
    done

    echo "liig: batch complete."
}

# ── Entry point ───────────────────────────────────────────────────────────────

if [[ -n "$_INDEX" ]]; then
    mode_single "$_INDEX"
else
    mode_batch
fi
