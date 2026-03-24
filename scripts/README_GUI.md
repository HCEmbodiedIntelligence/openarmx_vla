# VLA GUI One-Click Launch Guide

## Goal

After running one command, multiple terminal windows will pop up in sequence, just like manually following `README_CN(1).md`.

## Files

- ⚠️ `config/vla_collect.env`: Centralized configuration for robot, camera, and data collection parameters. **<span style="color:red">Please modify the parameters you want to configure here.</span>**
- `scripts/vla_collect_gui.sh`: GUI multi-terminal one-click launch script

## Three Modes

```bash
cd /home/openarmx/openarmx_ws/src/openarmx_vla

# 1. Start only the real robot + Pico Bridge + VR Teleop
bash scripts/vla_collect_gui.sh base

# 2. Start robot low-level stack + camera publishing
bash scripts/vla_collect_gui.sh base_camera

# 3. Start robot low-level stack + camera publishing + LeRobot data collection
bash scripts/vla_collect_gui.sh collect

# One-click close all terminals opened by this script
bash scripts/vla_collect_gui.sh stop
```

## Pre-Launch Self-Check

```bash
bash scripts/vla_collect_gui.sh check
```

`stop` allows you to manually close some terminals first; running it afterward will still not report errors.

The following will be checked in advance:

- `setup.bash`
- `DISPLAY` / `WAYLAND_DISPLAY`
- `gnome-terminal`
- `ros2`
- `lerobot-env` (as needed, checked in interactive shell mode)

In `collect` mode, `lerobot-env` is executed first in the data collection terminal, and then `lerobot-record` is executed.

## Parameter Modification

Directly edit the following file: **<span style="color:red">Please prioritize modifying the parameters you want to configure here.</span>**

- `config/vla_collect.env`

It already includes:

- Robot low-level parameters
- Pico / VR teleoperation parameters
- Camera resolution, frame rate, serial number, model
- `CAM_RIGHT_COLOR_EXPOSURE`
- `CAM_RIGHT_COLOR_GAIN`
- Other `cam_left/right/head_color_*` parameters
- LeRobot data collection parameters

## Notes

- Must be run in a graphical desktop terminal; the script will call `gnome-terminal`
- `W/H/FPS` will be used for both camera publishing and `lerobot-record`
- Each popped-up terminal will remain open after commands finish, for easier on-site troubleshooting
- This version has removed the log directory generation feature
- Terminal state file is written to `STATE_FILE` by default for precise shutdown by `stop`
