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

> 提供相机发布与调试工具：RealSense 三相机统一话题发布 + OpenCV 本地相机查看。
> 它不负责底层控制算法，主要负责把系统组件快速拉起来，方便接入 LeRobot 录制/遥操作流程。

## 3. 典型使用流程

1. 构建并加载工作空间：

```bash
cd <你的工作空间>
colcon build --packages-select openarmx_lerobot
source install/setup.bash
```

2. 终端 1：启动双臂机器人

```bash
# 实机模式：先启动 CAN 通道
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up

sudo ip link set can1 down
sudo ip link set can1 type can bitrate 1000000
sudo ip link set can1 up

cd <你的工作空间>
source install/setup.bash

ros2 launch openarmx_bringup openarmx.bimanual.launch.py \
  control_mode:=mit \
  robot_controller:=forward_position_controller \
  use_fake_hardware:=false
```

3. 终端 2：启动 Pico 桥接

```bash
cd <你的工作空间>
source install/setup.bash
ros2 run openarmx_teleop_bridge_vr_pico openarmx_teleop_bridge_vr_pico_node
```

4. 终端 3：启动 VR 遥操节点

```bash
cd ~/openarmx_ws/
source install/setup.bash
ros2 launch openarmx_teleop_vr_pico teleop_vr_pico.launch.py
```

5. 终端 4：启动相机发布节点

将序列号和型号替换为实际值；序列号通常标注于相机机底部标签：

```bash
cd ~/openarmx_ws/
source install/setup.bash
ros2 launch openarmx_lerobot camera_publisher.launch.py \
  width:=424 height:=240 fps:=15 \
  cam_left_serial:=序列号 cam_left_type:=型号 \
  cam_right_serial:=序列号 cam_right_type:=型号 \
  cam_head_serial:=序列号 cam_head_type:=型号
```

示例：

```bash
ros2 launch openarmx_lerobot camera_publisher.launch.py \
  width:=424 height:=240 fps:=15 \
  cam_left_serial:=218622270388 cam_left_type:=D405 \
  cam_right_serial:=218622274446 cam_right_type:=D405 \
  cam_head_serial:=335522070220 cam_head_type:=D435
```

6. 终端 5：启动 LeRobot 采集-接收端（如果在其他电脑进行数据接收，可不运行这一步）

```bash
lerobot-env  # 启动 conda 中的 lerobot 环境

HF_HUB_OFFLINE=1 lerobot-record \
  --robot.type=openarmx_follower_ros2 \
  --teleop.type=openarmx_leader_ros2 \
  --dataset.repo_id=local/你的数据名称 \
  --dataset.single_task="你执行的任务名称" \
  --dataset.num_episodes=采集的总组数 \
  --dataset.episode_time_s=每组时长秒数 \
  --dataset.reset_time_s=组间重置时长秒数 \
  --dataset.push_to_hub=false \
  --display_data=true
```

示例：

```bash
lerobot-env  # 启动 conda 中的 lerobot 环境

HF_HUB_OFFLINE=1 lerobot-record \
  --robot.type=openarmx_follower_ros2 \
  --teleop.type=openarmx_leader_ros2 \
  --dataset.repo_id=local/openarmx_dataset \
  --dataset.single_task="Teleop OpenArmX robot" \
  --dataset.num_episodes=100 \
  --dataset.episode_time_s=60 \
  --dataset.reset_time_s=5 \
  --dataset.push_to_hub=false \
  --display_data=true
```
数据默认保存路径：`~/.cache/huggingface/lerobot/local`

**采集快捷键说明**

- `→`：结束并保存当前 episode，进入 reset
- `←`：丢弃当前 episode，重新录制
- `Esc`：停止录制并退出

**采集参数速查**

常用参数：

- `HF_HUB_OFFLINE=1`：HF Hub 离线模式
- `--robot.type`：机器人插件类型
- `--teleop.type`：遥操作插件类型
- `--dataset.repo_id`：数据集标识（本地示例：`local/openarmx_dataset`）
- `--dataset.single_task`：任务描述
- `--dataset.num_episodes`：采集总回合数
- `--dataset.episode_time_s`：每回合最长时长
- `--dataset.reset_time_s`：回合间重置等待
- `--dataset.push_to_hub`：是否上传到 Hub
- `--display_data`：是否实时可视化

其他可选参数：

- `--dataset.root`：自定义保存路径
- `--dataset.fps`：限制采样帧率
- `--dataset.video`：图像是否编码为视频
- `--dataset.vcodec`：视频编码器（默认 `libsvtav1`）
- `--dataset.video_encoding_batch_size`：每批编码 episode 数
- `--dataset.private`：上传时设为私有
- `--dataset.tags`：Hub 标签
- `--dataset.num_image_writer_processes`：图像写入进程数
- `--dataset.num_image_writer_threads_per_camera`：每相机写入线程数
- `--dataset.rename_map`：重命名观测键

---
