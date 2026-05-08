# liig

**L**abel-**i**n-**i**mage **g**enerator. Composites a source image onto a canvas and renders a text label from CSV data alongside it.

## Scripts

| Script | Description |
|---|---|
| `liig.sh` | Generate labelled images from a CSV file, one per row |
| `liig-carousel.py` | Repeatedly call liig with rotating row indices — for use as a wallpaper rotator |

## Dependencies

- [ImageMagick](https://imagemagick.org) (with Pango support)
- Python 3.11+ (if using `liig-carousel`)

## Installation

### Via install script

```sh
git clone https://github.com/you/liig ~/liig
cd ~/liig && sudo -E ./install.sh
```

The installer will:

- Copy `liig` to a chosen directory (default: `/usr/bin`)
- Optionally copy `liig-carousel` to a chosen directory (default: `/usr/bin`)
- Write a config file and walk through basic setup.

### Manual installation

1. Clone or download this repository:

   ```sh
   git clone https://github.com/you/liig ~/liig
   ```

2. Copy the scripts to a directory on your `PATH`:

   ```sh
   install -m 755 ~/liig/liig.sh /usr/bin/liig
   install -m 755 ~/liig/liig-carousel.py /usr/bin/liig-carousel  # if desired
   ```

3. Create a config file:

   ```sh
   mkdir -p ~/.config/liig
   cp ~/liig/config.toml.example ~/.config/liig/config.toml
   ```

## Configuration

liig reads its config from `$XDG_CONFIG_HOME/liig/config.toml` (default: `~/.config/liig/config.toml`). Every option can also be passed as a CLI flag, which takes precedence over the config file.

The following options are required — all others have defaults:

| Option | Description |
|---|---|
| `INPUT_DIR` | Directory containing the source images |
| `LABELS_CSV` | Path to the tab- or comma-delimited CSV file |
| `LABEL_FORMAT` | Label text, e.g. `{FILE}` or `{AUTHOR} — {TITLE}` |

`LABEL_FORMAT` supports `{COLUMN_NAME}` placeholders matching your CSV header, and [Pango markup](https://docs.gtk.org/Pango/pango_markup.html) for rich text.

Full descriptions of every option can be found in [`config.toml.example`](config.toml.example).

## Usage

### liig

```
liig [OPTIONS]         generate one image per CSV row → OUTPUT_DIR
liig [OPTIONS] INDEX   generate one image for row INDEX → OUTPUT_FILE
```

`INDEX` is 0-based, counting from the first non-header row.

```sh
# Generate images for all rows
liig

# Generate a single image for the first row
liig 0

# With config overrides
liig --output-file ~/wallpaper.png --canvas-width-px 2560 --canvas-height-px 1440 0
```

### liig-carousel

```
liig-carousel [OPTIONS] [INDEX|RANGE ...]
liig-carousel [OPTIONS] --by COLUMN VALUE [VALUE ...]
liig-carousel [OPTIONS] --query "SQL WHERE CLAUSE"
```

With no positional arguments, rotates through all rows in the csv. To limit its pool:

```sh
# Specific indices and ranges
liig-carousel 0 5 10-20

# Rows where a column matches one or more values
liig-carousel --by SCHOOL German Dutch

# Rows matching an SQL WHERE clause
liig-carousel --query "YEAR >= 1800 AND SCHOOL = 'French'"
```

**Carousel modes** (set via `--carousel-mode` or `CAROUSEL_MODE` in config):

| Mode | Behaviour |
|---|---|
| `normal` | Sequential (default) |
| `shuffle` | Random pick each interval |
| `smart-shuffle` | Random, avoiding recently shown rows |

**Manual advance:**

Send `SIGUSR1` to skip the current wait and advance immediately:

```sh
kill -USR1 $(cat /tmp/liig-rotate.pid)
```

Set `--generation-interval-s -1` to disable the timer entirely and use only manual advance.

## Running the tests

Additional dependency: [pytest](https://pytest.org) (`pip install pytest`).

```sh
cd ~/liig
python3 -m pytest
```

## Wallpaper integration

See [WALLPAPER.md](WALLPAPER.md) for a complete guide to using liig and liig-carousel to display a rotating gallery of fine art as your desktop wallpaper.