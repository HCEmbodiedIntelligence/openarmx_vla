# lerobot_robot_openarmx_follower_ros2 中文说明

## 1. 包简介

`lerobot_robot_openarmx_follower_ros2` 是 LeRobot 的 OpenArmX ROS2 适配插件。  
它的作用是把 OpenArmX 的 ROS2 话题接口封装成 LeRobot 的 `Robot` 接口，方便做数据采集、回放和策略推理。

核心功能：

1. 从 `/joint_states` 读取双臂关节状态作为观测。
2. 向左右控制器命令话题发布 `Float64MultiArray` 关节目标。
3. 支持通过 ROS2 图像话题接入多路相机（RGB/Depth）。

## 2. 包结构

```text
lerobot_robot_openarmx_follower_ros2/
├── README.md
├── README_CN.md
├── pyproject.toml
├── setup.py
└── lerobot_robot_openarmx_follower_ros2/
    ├── __init__.py
    ├── config_openarmx_ros2.py        # 配置定义（机器人 + ROS2 + 相机）
    ├── openarmx_ros2.py               # LeRobot Robot 实现
    ├── ros2_interface_openarmx.py     # ROS2关节状态订阅/命令发布接口
    └── ros2_camera.py                 # ROS2图像话题相机实现
```

## 3. 数据流

1. ROS2 控制系统发布 `/joint_states`。
2. 本包读取关节状态，生成 LeRobot 观测。
3. LeRobot 给出动作（每个关节目标）。
4. 本包将动作发布到：
   - `/left_forward_position_controller/commands`
   - `/right_forward_position_controller/commands`
5. 可选：从 `/cam_*/color/image`、`/cam_*/depth/image` 读取图像作为视觉观测。

## 4. 安装

在工作空间源码目录安装（可编辑模式）：

```bash
# 激活你的 lerobot 虚拟环境
lerobot-env   # 这是我们设置的激活 lerobot 虚拟环境快捷命令。因为 conda 会和本地 python 起冲突，导致编译失败。所以我们默认不初始化 conda，只在使用时通过快捷命令激活！

cd <你的工作空间>/src/openarmx_vla/lerobot_robot_openarmx_follower_ros2
pip install -e . --no-deps
```

## 5. 关键可修改参数

## 机器人总配置 `OpenArmXRos2Config`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `skip_send_action` | `True` | `True` 时只采集不下发动作；`False` 时会真实发送控制命令 |
| `max_relative_target` | `None` | 限制每步关节变化幅度（安全裁剪） |
| `ros2` | `OpenArmXRos2InterfaceConfig(...)` | ROS2 关节接口参数 |
| `cameras` | 3 路 ROS2 相机 | 相机配置字典（右/左/头） |

## ROS2 关节接口配置 `OpenArmXRos2InterfaceConfig`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `namespace` | `""` | ROS2 命名空间 |
| `joint_states_topic` | `/joint_states` | 关节状态输入话题 |
| `left_command_topic` | `/left_forward_position_controller/commands` | 左臂命令话题 |
| `right_command_topic` | `/right_forward_position_controller/commands` | 右臂命令话题 |
| `left_joint_names` | 左臂 8 关节名 | 左臂命令向量顺序（必须与控制器一致） |
| `right_joint_names` | 右臂 8 关节名 | 右臂命令向量顺序（必须与控制器一致） |

注意：`left_joint_names`/`right_joint_names` 的顺序直接决定下发数组的含义，和控制器配置不一致会导致动作错位。

## 相机配置 `Ros2CameraConfig`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `image_topic` | `/camera/color/image_raw` | RGB 图像话题 |
| `use_depth` | `False` | 是否启用深度图 |
| `depth_topic` | `/camera/depth/image_raw` | 深度图话题 |
| `fps` | 配置中给定 | 目标帧率（用于 LeRobot 特征描述） |
| `width`/`height` | 配置中给定 | 图像分辨率 |
| `color_mode` | `RGB` | 输出颜色格式 |
| `rotation` | `NO_ROTATION` | 图像旋转 |
| `qos_reliability` | `best_effort` | QoS 可靠性（低延迟） |
| `queue_size` | `1` | 缓冲队列长度（保最新帧） |


## 许可证

本作品采用知识共享 署名-非商业性使用-相同方式共享 4.0 国际许可协议 (CC BY-NC-SA 4.0) 进行许可。

版权所有 (c) 2026 成都长数机器人有限公司 (Chengdu Changshu Robot Co., Ltd.)

详情请参阅 [LICENSE_CN.md](LICENSE) 文件或访问：http://creativecommons.org/licenses/by-nc-sa/4.0/

## 作者

- **Zhang Li** (张力)
- 公司: Chengdu Changshu Robot Co., Ltd. (成都长数机器人有限公司)
- 网站: https://openarmx.com/

## 版本

**当前版本**：1.0.0

---

## 📞 联系我们

### 成都长数机器人有限公司
**Chengdu Changshu Robotics Co., Ltd.**

| 联系方式 | 信息 |
|---------|------|
| 📧 邮箱 | openarmrobot@gmail.com |
| 📱 电话/微信 | +86-17746530375 |
| 🌐 官网 | <https://openarmx.com/> |
| 📍 地址 | 天津经济技术开发区西区新业八街11号华诚机械厂 |
| 👤 联系人 | 王先生 |
