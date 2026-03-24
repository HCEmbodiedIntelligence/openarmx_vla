# OpenArmX + LeRobot 使用手册

面向已搭建好 `/home/ubuntu/openarmx_ws` 工作区的快速说明，帮助把 OpenArmX 通过 ROS2 接入 LeRobot，并使用 Pico VR 遥操作。

## 前置准备
- 若局域网内有其他机器发布干扰，最简单的隔离方式：在本机所有终端统一设置独立的域（替换成你自选的数字，确保与他人不同），所有下面的命令前都执行：  
  ```bash
  export ROS_DOMAIN_ID=77
  ```
- 安装 LeRobot 及本仓库插件（只需一次）：
  ```bash
  # LeRobot 源码
  cd /home/ubuntu/openarmx_ws/src/lerobot_reference/lerobot
  pip install -e .

  # OpenArmX 机器人/遥操作插件
  pip install -e /home/ubuntu/openarmx_ws/src/lerobot_robot_openarmx_follower_ros2
  pip install -e /home/ubuntu/openarmx_ws/src/lerobot_teleoperator_openarmx_leader_ros2
  ```
- 建议提前编译 openarmx_teleop_bridge_vr_pico（如果未编译过）：
  ```bash
  cd /home/ubuntu/openarmx_ws
  colcon build --packages-select openarmx_teleop_bridge_vr_pico
  ```

## 一键三合一启动（新的 launch）
新增 ROS2 包 `openarmx_lerobot`，提供组合启动：
## VR+直接遥操作“仿真机器人”
```bash
cd ~/openarmx_ws
source install/setup.bash
ros2 launch openarmx_lerobot openarmx_lerobot.launch.py \
  robot_controller:=forward_position_controller \
  control_mode:=mit \
  use_fake_hardware:=true \
  connect_lerobot:=false
```
## VR+通过lerobot遥操作“仿真机器人”
```bash
cd ~/openarmx_ws
source install/setup.bash
ros2 launch openarmx_lerobot openarmx_lerobot.launch.py \
  robot_controller:=forward_position_controller \
  control_mode:=mit \
  use_fake_hardware:=true \
  connect_lerobot:=true
```
等价于依次运行：
1) 启动机器人，接收运动 
ros2 launch openarmx_bringup openarmx.bimanual.launch.py use_fake_hardware:=true robot_controller:=forward_position_controller
2) 
ros2 run openarmx_teleop_bridge_vr_pico openarmx_teleop_bridge_vr_pico_node
3) 
ros2 launch openarmx_teleop_vr_pico teleop_by_pico.launch.py connect_lerobot:=false publish_visualization_tf:=true enable_placo_viewer:=true

参数说明（可按需调整）：
- `robot_controller`：默认 `forward_position_controller`
- `control_mode`：默认 `mit`
- `use_fake_hardware`：默认 `true`（仿真/无真机时）
- `connect_lerobot`：默认 `true`，通过lerobot中转遥操作，为false时则直接遥操作；
- 透传 teleop 参数（有默认值）：`urdf_path`、`rate_topic`、`slow_max_step_deg`、`control_rate`、`ik_iterations`、`publish_visualization_tf`、`print_performance`、`use_link4_ext`、`constraint_mode`


## 步骤 1：启动机器人 bringup
- **仿真模式**（如有仿真/虚拟控制器，请使用对应参数或仿真 launch）  
  ```bash
  cd ~/openarmx_ws
  source install/setup.bash
  ros2 launch openarmx_bringup openarmx.bimanual.launch.py \
    robot_controller:=forward_position_controller \
    control_mode:=mit \
    use_fake_hardware:=true
  # 若有专用仿真控制器/模型，请替换为对应 launch 或 controller 名
  ```
- **真机模式（默认）**  
  ```bash
  cd ~/openarmx_ws
  source install/setup.bash
  ros2 launch openarmx_bringup openarmx.bimanual.launch.py \
    robot_controller:=forward_position_controller \
    control_mode:=mit
  ```

确认 `/joint_states` 正在发布，控制器话题存在：
```bash
ros2 topic hz /joint_states
ros2 topic list | grep forward_position_controller
```

## 步骤 2：启动 Pico 数据链（openarmx_teleop_bridge_vr_pico）
在另一个终端：
```bash
  cd ~/openarmx_ws
  source install/setup.bash
  ros2 run openarmx_teleop_bridge_vr_pico openarmx_teleop_bridge_vr_pico_node 
```
- 如果你有真机 + OpenXR 发送器，按 `openarmx_teleop_bridge_vr_pico/README-运行.md` 启动 `pico_openxr_sender`。
- 若使用默认桩数据，节点仍会输出模拟轨迹，可用 `ros2 topic echo /pico_left_controller/pose` 验证。

## 步骤 3：启动 VR 遥操作节点
运行你的 VR 发布节点（`openarmx_teleop_vr_pico` 或 `openarmx_teleop_leader`）
如果使用pico节点
```bash
ros2 launch openarmx_teleop_vr_pico teleop_by_pico.launch.py connect_lerobot:=true
```
并确保它发布到以下话题（可用 remap）：
- `/left_forward_position_controller/commands_original`
- `/right_forward_position_controller/commands_original`

示例检查：
```bash
ros2 topic hz /left_forward_position_controller/commands_original
ros2 topic echo /left_forward_position_controller/commands_original --once
```

## 步骤 4：用 LeRobot 贯通 VR → 机器人
在新的终端执行示例脚本（使用默认配置即可跑通）：
```bash
python3 - <<'PY'
from lerobot.teleoperators import make_teleoperator
from lerobot.robots import make_robot
import time

robot = make_robot({"type": "openarmx_ros2"})
teleop = make_teleoperator({"type": "openarmx_ros2"})

robot.connect(calibrate=False)
teleop.connect()

for _ in range(200):
    action = teleop.get_action()  # 从 *_original 话题读取关节目标
    robot.send_action(action)     # 发布到 forward_position_controller/commands
    time.sleep(0.01)

robot.disconnect()
teleop.disconnect()
PY
```
同时可监控话题确认数据流：
```bash
ros2 topic echo /left_forward_position_controller/commands --once
```

## 可选：相机输入
若需要 3 路 OpenCV 相机，按 LeRobot 文档配置 `cameras` 字段（在 `openarmx_ros2` RobotConfig 中），即可在 `get_observation()` 返回的字典里读取图像。

如果要启动 3 路 RealSense 并统一发布到 `/cam_left/*`、`/cam_right/*`、`/cam_head/*`，可使用：

```bash
W=640
H=480
FPS=30

ros2 launch openarmx_lerobot camera_publisher.launch.py \
  width:=$W height:=$H fps:=$FPS \
  cam_left_type:=D435 cam_right_type:=D435 cam_head_type:=D435
```

相机颜色参数现在也可以在启动时直接配置，例如曝光、增益和白平衡：

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
- `cam_*_color_exposure` 范围是 `1..10000`
- `cam_*_color_gain` 范围是 `0..128`
- `cam_*_color_white_balance` 范围是 `2800..6500`
- 若只写手动曝光/增益或手动白平衡，launch 会自动关闭对应自动模式

## 常见问题排查
- `Teleop commands have not been received yet.`：确认 VR 节点在向 `_original` 话题发消息，频率>0。
- 关节数量不匹配警告：检查 VR 节点发布数组长度与 `lerobot_teleoperator_openarmx_leader_ros2/config_openarmx_ros2.py` 中的关节列表一致。
- 没有动作输出：确认 bringup 中的控制器话题名与 `OpenArmXRos2Config.ros2.left/right_command_topic` 相同，必要时在创建 robot 时传入自定义 topic 名。

## GUI 工具：摄像头快速查看
默认自动枚举可用 OpenCV 相机（探测 0..5），每路开一个窗口叠加 index/path 和 FPS，任意窗口按 `q` 退出：
```bash
cd /home/ubuntu/openarmx_ws/src/openarmx_lerobot
python3 camera_viewer.py
```
如需自定义设备索引或视频文件：
```bash
python3 camera_viewer.py --cams 0 1 2             # 自定义列表
python3 camera_viewer.py --cams /dev/video4       # 单路
python3 camera_viewer.py --cams video.mp4 --fps 30 --width 640 --height 480
```
若提示 GUI 不可用，请安装带 HighGUI 的 OpenCV：`python3 -m pip install --upgrade opencv-python`。
