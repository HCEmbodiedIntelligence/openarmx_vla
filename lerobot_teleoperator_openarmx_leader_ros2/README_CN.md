# lerobot_teleoperator_openarmx_leader_ros2 中文说明

## 1. 包简介

`lerobot_teleoperator_openarmx_leader_ros2` 是 LeRobot 的 OpenArmX Leader 端遥操作插件。  
它订阅 OpenArmX VR 链路中的 ROS2 关节命令话题，并将其转换为 LeRobot 标准 action 字典（`*.pos`）。

核心功能：

1. 订阅左右臂 `Float64MultiArray` 命令输入。
2. 按关节顺序映射为 LeRobot action 键（例如 `openarmx_left_joint1.pos`）。
3. 提供 `get_action()` 给 LeRobot 控制环使用，不主动下发机器人控制命令。

## 2. 包结构

```text
lerobot_teleoperator_openarmx_leader_ros2/
├── README.md
├── README_CN.md
├── pyproject.toml
└── lerobot_teleoperator_openarmx_leader_ros2/
    ├── __init__.py
    ├── config_openarmx_ros2.py      # 配置定义（ROS2话题 + 关节顺序）
    ├── openarmx_ros2.py             # LeRobot Teleoperator 实现
    └── ros2_interface_openarmx.py   # ROS2订阅接口（命令/关节状态/grip）
```

## 3. 数据流

1. 上游 teleop 节点发布左右臂目标关节数组（通常是 `*_commands_original`）。
2. 本包订阅左右话题并缓存最新命令。
3. 调用 `get_action()` 时输出 LeRobot 格式动作字典。
4. 若未收到命令，会回退使用 `/joint_states` 当前位姿作为动作（保持不动）。
5. 同时订阅 `/pico_left_controller/grip`、`/pico_right_controller/grip` 用于人类干预事件检测。

## 4. 安装

在工作空间源码目录安装（可编辑模式）：

```bash
# 激活你的 lerobot 虚拟环境
lerobot-env   # 这是我们设置的激活 lerobot 虚拟环境快捷命令。因为 conda 会和本地 python 起冲突，导致编译失败。所以我们默认不初始化 conda，只在使用时通过快捷命令激活！

cd <你的工作空间>/src/openarmx_vla/lerobot_teleoperator_openarmx_leader_ros2
pip install -e . --no-deps
```

## 5. 关键可修改参数

## Teleoperator 总配置 `OpenArmXRos2TeleopConfig`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ros2` | `OpenArmXRos2TeleopInterfaceConfig(...)` | ROS2 订阅接口参数 |

## ROS2 订阅接口配置 `OpenArmXRos2TeleopInterfaceConfig`

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `namespace` | `""` | ROS2 命名空间 |
| `left_command_topic` | `/left_forward_position_controller/commands_original` | 左臂输入命令话题 |
| `right_command_topic` | `/right_forward_position_controller/commands_original` | 右臂输入命令话题 |
| `left_joint_names` | 左臂 8 关节名 | 左臂输入数组顺序（必须与发布端一致） |
| `right_joint_names` | 右臂 8 关节名 | 右臂输入数组顺序（必须与发布端一致） |

注意：`left_joint_names`/`right_joint_names` 的顺序直接决定 action 各关节的映射关系，和上游发布顺序不一致会导致关节错位。

## 固定订阅（当前实现）

以下话题在当前代码中是固定值（非配置参数）：

1. `/joint_states`：命令缺失时的回退数据源。
2. `/pico_left_controller/grip`：左手 grip，用于干预检测。
3. `/pico_right_controller/grip`：右手 grip，用于干预检测。

## 6. 最小使用示例

```python
from lerobot.teleoperators import make_teleoperator

teleop = make_teleoperator(
    {
        "type": "openarmx_ros2",
        "ros2": {
            "left_command_topic": "/left_forward_position_controller/commands_original",
            "right_command_topic": "/right_forward_position_controller/commands_original",
        },
    }
)

teleop.connect()
action = teleop.get_action()  # dict: { "<joint>.pos": value, ... }
events = teleop.get_teleop_events()  # 包含是否人类干预
teleop.disconnect()
```

## 7. 常见问题

1. `get_action()` 报无数据  
先确认上游是否在发布 `left/right_command_topic`；若未发布，再检查 `/joint_states` 是否存在。

2. 动作关节对应不对  
检查 `left_joint_names`/`right_joint_names` 顺序是否与上游数组顺序完全一致。

3. 干预检测一直为 False  
检查 `/pico_left_controller/grip` 与 `/pico_right_controller/grip` 是否有数据，阈值逻辑为 `> 0.5` 判定干预。


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
