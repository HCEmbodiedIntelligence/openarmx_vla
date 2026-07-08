# Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#
# Copyright (c) 2026 Chengdu Changshu Robot Co., Ltd.
# https://www.openarmx.com
#
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike
# 4.0 International License (CC BY-NC-SA 4.0).
#
# To view a copy of this license, visit:
# http://creativecommons.org/licenses/by-nc-sa/4.0/
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

from __future__ import annotations

from dataclasses import dataclass, field

from lerobot.cameras import CameraConfig
from lerobot.cameras.configs import ColorMode, Cv2Rotation
from lerobot.robots import RobotConfig

from .ros2_camera import Ros2CameraConfig


@dataclass
class OpenArmXRos2InterfaceConfig:
    """ROS 2 wiring for OpenArmX.

    OpenArmX uses ros2_control forward_command_controller topics like:
    - /left_forward_position_controller/commands
    - /right_forward_position_controller/commands

    and publishes joint states on /joint_states.
    """

    namespace: str = ""  # Optional ROS namespace

    joint_states_topic: str = "/joint_states"

    left_command_topic: str = "/left_forward_position_controller/commands"
    right_command_topic: str = "/right_forward_position_controller/commands"
    reset_active_topic: str = "/openarmx/reset_active"

    # Joint ordering for commands (must match controller 'joints:' order)
    left_joint_names: list[str] = field(
        default_factory=lambda: [
            "openarmx_left_joint1",
            "openarmx_left_joint2",
            "openarmx_left_joint3",
            "openarmx_left_joint4",
            "openarmx_left_joint5",
            "openarmx_left_joint6",
            "openarmx_left_joint7",
            "openarmx_left_finger_joint1",
        ]
    )
    right_joint_names: list[str] = field(
        default_factory=lambda: [
            "openarmx_right_joint1",
            "openarmx_right_joint2",
            "openarmx_right_joint3",
            "openarmx_right_joint4",
            "openarmx_right_joint5",
            "openarmx_right_joint6",
            "openarmx_right_joint7",
            "openarmx_right_finger_joint1",
        ]
    )


@RobotConfig.register_subclass("openarmx_follower_ros2")
@dataclass
class OpenArmXRos2Config(RobotConfig):
    """LeRobot RobotConfig for OpenArmX via ROS 2 topics."""

    # Safety: clip per-joint relative steps (radians). If None, no clipping.
    max_relative_target: float | dict[str, float] | None = 0.523

    # Skip send_action (for direct teleop mode where teleop_node controls robot directly)
    # When True, lerobot only records data without sending commands to robot
    skip_send_action: bool = True

    # Convert the policy's continuous gripper prediction into a binary state.
    # The classifier uses hysteresis, then maps state 0/1 to the physical
    # prismatic-joint commands below.  Do not send 1.0 directly to the joint.
    binary_gripper: bool = False
    gripper_closed_position: float = 0.0
    gripper_open_position: float = 0.04
    gripper_close_threshold: float = 0.015
    gripper_open_threshold: float = 0.032
    # Require this many consecutive predictions beyond a threshold before
    # changing state. This filters short policy spikes at control-loop rate.
    gripper_confirm_frames: int = 5
    # Minimum duration to hold a binary gripper state after a transition.
    # This turns short policy pulses into executable gripper commands.
    gripper_min_open_frames: int = 0
    gripper_min_closed_frames: int = 0
    # Debug: print raw gripper policy outputs every N send_action calls.
    # 0 disables continuous debug logging; state changes are still logged.
    gripper_debug_log_every: int = 0

    # Path to a demo YAML file containing a joint trajectory.
    # When set, calibrate() loads the trajectory and slowly moves the robot to
    # the initial position defined at the end of the trajectory.
    init_pos_path: str | None = "/home/hc_op/openarmx_ws/init_pos.yaml"
    # init_pos_path: str | None =None

    return_pos_path: str | None = "/home/hc_op/openarmx_ws/return_pos.yaml"

    # Speed scale for calibration trajectory execution (e.g. 0.2 = 5x slower).
    calib_speed_scale: float = 1

    # cameras - 使用 ROS2 话题订阅相机 (支持跨设备网络传输)
    # 相机硬件连接在工控机上，通过 ROS2 DDS 发送图像到其他设备
    # 同时传输 RGB 彩色图像和深度图
    # 话题由 camera_publisher.launch.py 统一映射，无需关心相机类型 (D405/D435)
    cameras: dict[str, CameraConfig] = field(
        default_factory=lambda: {
            "cam_right": Ros2CameraConfig(
                image_topic="/cam_right/color/image",
                depth_topic="/cam_right/depth/image",
                fps=30,
                width=424,
                height=240,
                color_mode=ColorMode.RGB,
                use_depth=True,
                rotation=Cv2Rotation.NO_ROTATION,
                qos_reliability="best_effort",
                queue_size=1,
            ),
            "cam_left": Ros2CameraConfig(
                image_topic="/cam_left/color/image",
                depth_topic="/cam_left/depth/image",
                fps=30,
                width=424,
                height=240,
                color_mode=ColorMode.RGB,
                use_depth=True,
                rotation=Cv2Rotation.NO_ROTATION,
                qos_reliability="best_effort",
                queue_size=1,
            ),
            "cam_head": Ros2CameraConfig(
                image_topic="/cam_head/color/image",
                depth_topic="/cam_head/depth/image",
                fps=30,
                width=424,
                height=240,
                color_mode=ColorMode.RGB,
                use_depth=True,
                rotation=Cv2Rotation.NO_ROTATION,
                qos_reliability="best_effort",
                queue_size=1,
            ),
        }
    )

    ros2: OpenArmXRos2InterfaceConfig = field(default_factory=OpenArmXRos2InterfaceConfig)
