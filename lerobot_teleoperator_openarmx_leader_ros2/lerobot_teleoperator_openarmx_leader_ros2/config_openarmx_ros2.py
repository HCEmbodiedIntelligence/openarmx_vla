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

from lerobot.teleoperators.config import TeleoperatorConfig


@dataclass
class OpenArmXRos2TeleopInterfaceConfig:
    """ROS 2 wiring for the OpenArmX teleop feed."""

    namespace: str = ""  # Optional ROS namespace

    # Subscribe to the same topic that teleop_node publishes to (direct control mode)
    left_command_topic: str = "/left_forward_position_controller/commands"
    right_command_topic: str = "/right_forward_position_controller/commands"

    # Joint ordering for incoming commands (must match controller 'joints:' order)
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


@TeleoperatorConfig.register_subclass("openarmx_leader_ros2")
@dataclass
class OpenArmXRos2TeleopConfig(TeleoperatorConfig):
    """LeRobot TeleoperatorConfig for OpenArmX via ROS 2 VR command topics."""

    ros2: OpenArmXRos2TeleopInterfaceConfig = field(default_factory=OpenArmXRos2TeleopInterfaceConfig)
