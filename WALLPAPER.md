# ART500K wallpaper with liig

liig was originally built for a specific purpose: displaying a continuously rotating gallery of fine art from [ART500K](https://deepart.hkust.edu.hk/ART500K/art500k.html) as a desktop wallpaper.

This guide walks through how to set that up, using `awww` as the wallpaper manager and `systemd` to handle starting on boot.

## Getting Set Up

Download a dataset from [ART500K](https://deepart.hkust.edu.hk/ART500K/art500k.html). I used the **Raw images of visual arts with general label list** subset.

Since the datasets are so large, you may want to store them on a mounted drive. `liig-carousel` is designed to wait until the input directory exists before generating the first image, so it can be started at boot without worrying about mount ordering.

## Configuration

[`examples/config.toml`](examples/config.toml) is a ready-to-use config for this setup. Copy it to `~/.config/liig/config.toml` and update the `INPUT_DIR` and `LABELS_CSV` paths to match your dataset location. Examples of what the config looks like can be found at [`examples/example1.png`](examples/example1.png), [`examples/example2.png`](examples/example2.png), and [`examples/example3.png`](examples/example3.png).

## Connect to Wallpaper

The carousel writes each new image to `OUTPUT_FILE`, overwriting the previous one. A lightweight watcher picks up the `close_write` event and tells the wallpaper daemon to reload.

[`examples/set-wallpaper.sh`](examples/set-wallpaper.sh):

```bash
#!/bin/bash

# Must match OUTPUT_FILE in ~/.config/liig/config.toml
WALLPAPER="/tmp/wallpaper-art-image.png"
DISPLAY="DP-2"

touch "$WALLPAPER"
inotifywait -m -e close_write "$WALLPAPER" | while IFS= read -r _; do
    awww img -o "$DISPLAY" "$WALLPAPER" --transition-type none
done
```

`$DISPLAY` should be set to whatever your target display is named; my display is 'DP-2'.

## Start on Bootup

Two user services keep everything running across reboots.

`~/.config/systemd/user/liig-rotate.service`:

```ini
[Unit]
Description=liig wallpaper carousel

[Service]
ExecStart=liig-carousel
Restart=on-failure

[Install]
WantedBy=default.target
```

`~/.config/systemd/user/liig-wallpaper.service`:

```ini
[Unit]
Description=liig wallpaper watcher
After=graphical-session.target

[Service]
ExecStart=%h/scripts/set-wallpaper.sh
Restart=on-failure

[Install]
WantedBy=graphical-session.target
```

Enable and start both:

```sh
systemctl --user daemon-reload
systemctl --user enable --now liig-rotate.service liig-wallpaper.service
```