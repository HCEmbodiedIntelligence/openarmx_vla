# openarmx_lerobot 中文说明

## 1. 包结构

```text
openarmx_lerobot/
├── README.md
├── README_CN.md
├── camera_viewer.py
├── package.xml
├── setup.py
├── setup.cfg
├── launch/
│   ├── openarmx_lerobot.launch.py
│   └── camera_publisher.launch.py
└── openarmx_lerobot/
    └── __init__.py
```

## 2. 包定位

`openarmx_lerobot` 是一个“组合启动与使用指南”包，主要做两件事：

1. 提供一键启动链路：
   `openarmx_bringup` + `openarmx_teleop_bridge_vr_pico` + `openarmx_teleop_vr_pico`
2. 提供相机发布与调试工具：
   RealSense 三相机统一话题发布 + OpenCV 本地相机查看。

它不负责底层控制算法，主要负责把系统组件快速拉起来，方便接入 LeRobot 录制/遥操作流程。

## 3. 典型使用流程

1. 构建并加载工作空间：

```bash
cd /home/openarmx/VLA_new
colcon build --packages-select openarmx_lerobot
source install/setup.bash
```

2. 启动“三合一”链路（仿真示例）：

```bash
ros2 launch openarmx_lerobot openarmx_lerobot.launch.py \
  robot_controller:=forward_position_controller \
  control_mode:=mit \
  use_fake_hardware:=true \
  connect_lerobot:=true
```

3. 在新终端运行 LeRobot 录制或策略循环（参考 `lerobot_record_usage.md`）。

## 4. 核心启动文件

## 4.1 `openarmx_lerobot.launch.py`

作用：一次性启动以下组件：

1. `openarmx_bringup`（机器人基础控制）
2. `openarmx_teleop_bridge_vr_pico_node`（Pico 数据桥接）
3. `openarmx_teleop_vr_pico`（VR 遥操作节点）

常用参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `robot_controller` | `forward_position_controller` | 机器人控制器名称 |
| `control_mode` | `mit` | 控制模式 |
| `use_fake_hardware` | `true` | 是否使用仿真硬件 |
| `connect_lerobot` | `true` | `true` 发布到 `*_commands_original` 供 LeRobot 中转 |
| `urdf_path` | 自动解析 | teleop 使用的 URDF 路径 |
| `rate_topic` | `/pico_right_controller/rate` | 速度档位话题 |
| `slow_max_step_deg` | `1.0` | 慢速最大关节步进（度） |
| `control_rate` | `100.0` | 控制循环频率（Hz） |
| `ik_iterations` | `3` | 每周期求解迭代次数 |
| `publish_visualization_tf` | `true` | 是否发布可视化 TF |
| `print_performance` | `true` | 是否打印性能日志 |
| `use_link4_ext` | `true` | 是否启用扩展约束帧 |
| `constraint_mode` | `link` | 约束模式：`joint` 或 `link` |
| `grip_threshold` | `0.5` | grip 使能阈值 |
| `left_grip_topic` | `/pico_left_controller/grip` | 左握把话题 |
| `right_grip_topic` | `/pico_right_controller/grip` | 右握把话题 |

## 4.2 `camera_publisher.launch.py`

作用：启动 3 路 RealSense（左/右/头），并统一发布话题：

1. `/cam_left/color/image`、`/cam_left/depth/image`
2. `/cam_right/color/image`、`/cam_right/depth/image`
3. `/cam_head/color/image`、`/cam_head/depth/image`

常用参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `width` | `424` | 图像宽度 |
| `height` | `240` | 图像高度 |
| `fps` | `15` | 帧率 |
| `cam_left_serial` | `218622270388` | 左相机序列号 |
| `cam_left_type` | `D405` | 左相机型号（D405/D435/D435I） |
| `cam_right_serial` | `218622274446` | 右相机序列号 |
| `cam_right_type` | `D405` | 右相机型号（D405/D435/D435I） |
| `cam_head_serial` | `335522070220` | 头相机序列号 |
| `cam_head_type` | `D435` | 头相机型号（D405/D435/D435I） |
| `cam_*_color_auto_exposure` | `unset` | 颜色自动曝光：`true/false/unset` |
| `cam_*_color_exposure` | `unset` | 颜色手动曝光，范围 `1..10000` |
| `cam_*_color_gain` | `unset` | 颜色手动增益，范围 `0..128` |
| `cam_*_color_auto_white_balance` | `unset` | 颜色自动白平衡：`true/false/unset` |
| `cam_*_color_white_balance` | `unset` | 颜色手动白平衡，范围 `2800..6500` |
| `cam_*_color_brightness` | `unset` | 颜色亮度，范围 `-64..64` |
| `cam_*_color_contrast` | `unset` | 颜色对比度，范围 `0..100` |
| `cam_*_color_saturation` | `unset` | 颜色饱和度，范围 `0..100` |
| `cam_*_color_sharpness` | `unset` | 颜色锐度，范围 `0..100` |

示例：

```bash
W=640
H=480
FPS=30

ros2 launch openarmx_lerobot camera_publisher.launch.py \
  width:=$W height:=$H fps:=$FPS \
  cam_left_type:=D435 cam_right_type:=D435 cam_head_type:=D435
```

曝光与白平衡示例：

```bash
# 左手相机：关闭自动曝光，设置手动曝光和增益
W=640
H=480
FPS=30

ros2 launch openarmx_lerobot camera_publisher.launch.py \
  width:=$W height:=$H fps:=$FPS \
  cam_left_color_auto_exposure:=false \
  cam_left_color_exposure:=400 \
  cam_left_color_gain:=32

# 头部相机：关闭自动白平衡，设置手动白平衡
ros2 launch openarmx_lerobot camera_publisher.launch.py \
  width:=$W height:=$H fps:=$FPS \
  cam_head_color_auto_white_balance:=false \
  cam_head_color_white_balance:=4600
```

说明：

- `unset` 表示不主动设置该参数，保持驱动默认行为
- 若只写 `cam_*_color_exposure` 或 `cam_*_color_gain`，launch 会自动补成 `cam_*_color_auto_exposure:=false`
- 若只写 `cam_*_color_white_balance`，launch 会自动补成 `cam_*_color_auto_white_balance:=false`
- 不要同时设置 `color_auto_exposure:=true` 和 `color_exposure:=...`
- 不要同时设置 `color_auto_white_balance:=true` 和 `color_white_balance:=...`

## 5. 调试与验证

话题检查：

```bash
ros2 topic list | grep -E "joint_states|forward_position_controller|pico_|cam_"
ros2 topic hz /joint_states
ros2 topic hz /left_forward_position_controller/commands_original
ros2 topic hz /cam_left/color/image
```

本地相机快速查看工具（非 ROS）：

```bash
cd /home/openarmx/VLA_new/src/openarmx_vla/openarmx_lerobot
python3 camera_viewer.py --cams 0 1 2
```

## 6. 常见调整建议

1. 录制/训练前先用 `use_fake_hardware:=true` 打通全链路。
2. 出现控制跳变时，优先降低 `slow_max_step_deg` 或提高 `control_rate`。
3. 网络带宽紧张时，降低相机 `width/height/fps`，并保持 `best_effort` QoS（接收端配置）。
4. 多机联调时统一设置 `ROS_DOMAIN_ID`，避免串话题。
