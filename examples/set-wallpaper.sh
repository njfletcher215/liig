#!/bin/bash

# must be the same as ~/.config/liig/config.toml's OUTPUT_FILE
WALLPAPER="/tmp/wallpaper-art-image.png"
DISPLAY="DP-2"

touch "$WALLPAPER"
inotifywait -m -e close_write "$WALLPAPER" | while IFS= read -r _; do
    awww img -o "$DISPLAY" "$WALLPAPER" --transition-type none
done

