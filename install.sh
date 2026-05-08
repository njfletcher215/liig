#!/usr/bin/env bash
set -euo pipefail

script_dir="$(dirname "$(realpath "$0")")"

prompt() {
    local msg="$1" default="$2" answer
    read -r -p "$msg [$default]: " answer
    printf '%s' "${answer:-$default}"
}

confirm() {
    local msg="$1" default="${2:-n}" answer
    read -r -p "$msg [$default]: " answer
    [[ "${answer:-$default}" =~ ^[Yy] ]]
}

expand_path() { printf '%s' "${1/#\~/$HOME}"; }

# Write KEY = "VALUE" into a config file, replacing KEY = "".
# Uses python so the value is treated as a literal string (no \n expansion, etc.)
set_config_value() {
    local key="$1" value="$2" file="$3"
    python3 - "$key" "$value" "$file" <<'PYEOF'
import sys
key, value, path = sys.argv[1], sys.argv[2], sys.argv[3]
content = open(path).read()
content = content.replace(f'{key} = ""', f'{key} = "{value}"', 1)
open(path, 'w').write(content)
PYEOF
}

echo "=== liig installer ==="
echo

# ---------------------------------------------------------------------------
# 1. Binaries
# ---------------------------------------------------------------------------

install_dir=$(prompt "Install directory" "/usr/bin")
install_dir="$(expand_path "$install_dir")"
[[ "$install_dir" != /* ]] && install_dir="$PWD/$install_dir"

mkdir -p "$install_dir"

install -m 755 "$script_dir/liig.sh" "$install_dir/liig"
echo "-> Installed liig to $install_dir/liig"

if confirm "Install liig-carousel?" "n"; then
    install -m 755 "$script_dir/liig-carousel.py" "$install_dir/liig-carousel"
    echo "-> Installed liig-carousel to $install_dir/liig-carousel"
fi

echo

# ---------------------------------------------------------------------------
# 2. Config file
# ---------------------------------------------------------------------------

xdg_config="${XDG_CONFIG_HOME:-$HOME/.config}"
config_default="$xdg_config/liig/config.toml"

config_path=$(prompt "Config file path" "$config_default")
config_path="$(expand_path "$config_path")"
[[ "$config_path" != /* ]] && config_path="$PWD/$config_path"

if [[ -f "$config_path" ]]; then
    echo "-> Config already exists at '$config_path' — skipping."
else
    mkdir -p "$(dirname "$config_path")"
    cp "$script_dir/config.toml.example" "$config_path"

    echo
    echo "Required options (press Enter to leave as blank and edit manually):"
    echo

    input_dir=$(prompt "INPUT_DIR  — directory containing source images" "")
    input_dir="$(expand_path "$input_dir")"
    [[ -n "$input_dir" ]] && set_config_value "INPUT_DIR" "$input_dir" "$config_path"

    labels_csv=$(prompt "LABELS_CSV — path to CSV file with label data" "")
    labels_csv="$(expand_path "$labels_csv")"
    [[ -n "$labels_csv" ]] && set_config_value "LABELS_CSV" "$labels_csv" "$config_path"

    label_format=$(prompt "LABEL_FORMAT — label text, e.g. {FILE} or {AUTHOR} — {TITLE}" "{FILE}")
    [[ -n "$label_format" ]] && set_config_value "LABEL_FORMAT" "$label_format" "$config_path"

    if [[ -n "${SUDO_USER:-}" ]]; then
        chown "$SUDO_USER:" "$(dirname "$config_path")" "$config_path"
    fi

    echo
    echo "-> Wrote config to $config_path"
fi

echo
echo "Done!"
