# openarmx_lerobot English Documentation

## 1. Package Structure

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

## 2. Package Purpose

`openarmx_lerobot` is a "composed launcher and usage guide" package with two main goals:

> Provide camera publishing and debugging tools: unified topic publishing for three RealSense cameras + local camera viewing with OpenCV.
> It does not implement low-level control algorithms. Its main role is to quickly bring up system components so they can be integrated into LeRobot data recording/teleoperation workflows.

## 3. Typical Workflow

1. Build and source the workspace:

```bash
cd <your_workspace>
colcon build --packages-select openarmx_lerobot
source install/setup.bash
```

2. Terminal 1: Start the dual-arm robot

```bash
# Real hardware mode: initialize CAN interfaces first
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up

sudo ip link set can1 down
sudo ip link set can1 type can bitrate 1000000
sudo ip link set can1 up

cd <your_workspace>
source install/setup.bash

ros2 launch openarmx_bringup openarmx.bimanual.launch.py \
  control_mode:=mit \
  robot_controller:=forward_position_controller \
  use_fake_hardware:=false
```

3. Terminal 2: Start the Pico bridge

```bash
cd <your_workspace>
source install/setup.bash
ros2 run openarmx_teleop_bridge_vr_pico openarmx_teleop_bridge_vr_pico_node
```

4. Terminal 3: Start the VR teleoperation node

```bash
cd ~/openarmx_ws/
source install/setup.bash
ros2 launch openarmx_teleop_vr_pico teleop_vr_pico.launch.py
```

5. Terminal 4: Start camera publisher nodes

Replace the serial numbers and models with your actual devices. Serial numbers are usually printed on the label at the bottom of each camera:

```bash
cd ~/openarmx_ws/
source install/setup.bash
ros2 launch openarmx_lerobot camera_publisher.launch.py \
  width:=424 height:=240 fps:=15 \
  cam_left_serial:=SERIAL cam_left_type:=MODEL \
  cam_right_serial:=SERIAL cam_right_type:=MODEL \
  cam_head_serial:=SERIAL cam_head_type:=MODEL
```

Example:

```bash
ros2 launch openarmx_lerobot camera_publisher.launch.py \
  width:=424 height:=240 fps:=15 \
  cam_left_serial:=218622270388 cam_left_type:=D405 \
  cam_right_serial:=218622274446 cam_right_type:=D405 \
  cam_head_serial:=335522070220 cam_head_type:=D435
```

6. Terminal 5: Start LeRobot data collection receiver
(If you are receiving data on another computer, you can skip this step.)

```bash
lerobot-env  # activate the lerobot conda environment

HF_HUB_OFFLINE=1 lerobot-record \
  --robot.type=openarmx_follower_ros2 \
  --teleop.type=openarmx_leader_ros2 \
  --dataset.repo_id=local/your_dataset_name \
  --dataset.single_task="your_task_description" \
  --dataset.num_episodes=TOTAL_EPISODES \
  --dataset.episode_time_s=SECONDS_PER_EPISODE \
  --dataset.reset_time_s=SECONDS_FOR_RESET \
  --dataset.push_to_hub=false \
  --display_data=true
```

Example:

```bash
lerobot-env  # activate the lerobot conda environment

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

Default data save path: `~/.cache/huggingface/lerobot/local`

**Collection Hotkeys**

- `→`: End and save the current episode, then enter reset
- `←`: Discard the current episode and re-record
- `Esc`: Stop recording and exit

**Collection Parameter Quick Reference**

Common parameters:

- `HF_HUB_OFFLINE=1`: HF Hub offline mode
- `--robot.type`: Robot plugin type
- `--teleop.type`: Teleoperation plugin type
- `--dataset.repo_id`: Dataset identifier (local example: `local/openarmx_dataset`)
- `--dataset.single_task`: Task description
- `--dataset.num_episodes`: Total number of episodes to collect
- `--dataset.episode_time_s`: Maximum duration per episode
- `--dataset.reset_time_s`: Reset wait time between episodes
- `--dataset.push_to_hub`: Whether to upload to Hub
- `--display_data`: Whether to visualize data in real time

Other optional parameters:

- `--dataset.root`: Custom save path
- `--dataset.fps`: Limit sampling frame rate
- `--dataset.video`: Whether to encode images as video
- `--dataset.vcodec`: Video codec (default: `libsvtav1`)
- `--dataset.video_encoding_batch_size`: Number of episodes per encoding batch
- `--dataset.private`: Upload as private dataset
- `--dataset.tags`: Hub tags
- `--dataset.num_image_writer_processes`: Number of image writer processes
- `--dataset.num_image_writer_threads_per_camera`: Number of writer threads per camera
- `--dataset.rename_map`: Rename observation keys

---
