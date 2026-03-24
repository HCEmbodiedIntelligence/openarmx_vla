# VLA GUI 一键启动说明

## 目标

执行一个命令后，像手动照着 `README_CN(1).md` 操作一样，依次弹出多个终端窗口。

## 文件

- ⚠️ `config/vla_collect.env`：集中配置机器人、相机、数采参数。**<span style="color:red">请到这里修改您要配置的参数。</span>**
- `scripts/vla_collect_gui.sh`：GUI 多终端一键启动脚本

## 三种模式

```bash
cd /home/openarmx/openarmx_ws/src/openarmx_vla

# 1. 只启动机器人真机 + Pico Bridge + VR Teleop
bash scripts/vla_collect_gui.sh base

# 2. 启动机器人底层 + 相机发布
bash scripts/vla_collect_gui.sh base_camera

# 3. 启动机器人底层 + 相机发布 + LeRobot 数采
bash scripts/vla_collect_gui.sh collect

# 一键关闭本脚本打开的所有终端
bash scripts/vla_collect_gui.sh stop
```

## 启动前自检

```bash
bash scripts/vla_collect_gui.sh check
```

`stop` 支持你手动先关闭部分终端，再执行也不会报错。

会提前检查：

- `setup.bash`
- `DISPLAY` / `WAYLAND_DISPLAY`
- `gnome-terminal`
- `ros2`
- `lerobot-env`（按需，按交互式 shell 方式检查）

`collect` 模式会在数采终端内先执行 `lerobot-env`，再执行 `lerobot-record`。

## 参数修改

直接修改以下文件：**<span style="color:red">请优先在这里修改您要配置的参数。</span>**

- `config/vla_collect.env`

其中已包含：

- 机器人底层参数
- Pico / VR 遥操作参数
- 相机分辨率、帧率、序列号、型号
- `CAM_RIGHT_COLOR_EXPOSURE`
- `CAM_RIGHT_COLOR_GAIN`
- 其他 `cam_left/right/head_color_*` 参数
- LeRobot 数采参数

## 注意

- 必须在图形桌面终端中执行，脚本会调用 `gnome-terminal`
- `W/H/FPS` 会同时用于相机发布和 `lerobot-record`
- 每个弹出的终端在命令结束后会保留，方便现场排查
- 本版本已去掉日志目录生成功能
- 终端状态文件默认写入 `STATE_FILE`，用于 `stop` 精准关闭
