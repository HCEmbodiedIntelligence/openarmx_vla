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

import logging
import time
from typing import Any

from lerobot.teleoperators.teleoperator import Teleoperator
from lerobot.teleoperators.utils import TeleopEvents
from lerobot.utils.errors import DeviceAlreadyConnectedError, DeviceNotConnectedError

from .config_openarmx_ros2 import OpenArmXRos2TeleopConfig
from .ros2_interface_openarmx import OpenArmXRos2TeleopInterface

logger = logging.getLogger(__name__)


class OpenArmXRos2Teleop(Teleoperator):
    """LeRobot teleoperator that consumes OpenArmX VR ROS 2 command topics."""

    config_class = OpenArmXRos2TeleopConfig
    # Keep type name aligned with lerobot CLI choice list
    name = "openarmx_ros2"

    def __init__(self, config: OpenArmXRos2TeleopConfig):
        super().__init__(config)
        self.config = config
        self.ros2 = OpenArmXRos2TeleopInterface(config.ros2)

        self._all_joint_names = self.config.ros2.left_joint_names + self.config.ros2.right_joint_names

    @property
    def action_features(self) -> dict[str, type]:
        return {f"{j}.pos": float for j in self._all_joint_names}

    @property
    def feedback_features(self) -> dict[str, type]:
        # This teleop doesn't ingest haptic/led feedback today.
        return {}

    @property
    def is_connected(self) -> bool:
        return self.ros2.is_connected

    def connect(self, calibrate: bool = True) -> None:
        if self.is_connected:
            raise DeviceAlreadyConnectedError(f"{self} already connected")

        self.ros2.connect()
        self.configure()

        # Wait briefly for the first teleop command to arrive.
        t0 = time.time()
        while self.ros2.get_latest_joint_positions() is None:
            if time.time() - t0 > 3.0:
                break
            time.sleep(0.05)

    def calibrate(self) -> None:
        # VR topic inputs don't need calibration here.
        return

    @property
    def is_calibrated(self) -> bool:
        return True

    def configure(self) -> None:
        return

    def get_action(self) -> dict[str, Any]:
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        latest = self.ros2.get_latest_joint_positions()

        # If no data available (no commands AND no joint_states), raise error
        if latest is None:
            raise ValueError(
                "No action data available. Ensure robot is publishing /joint_states "
                "or teleop_node is publishing /commands (press grip to start)."
            )

        left, right = latest["left"], latest["right"]
        expected_left = len(self.config.ros2.left_joint_names)
        expected_right = len(self.config.ros2.right_joint_names)
        if len(left) != expected_left or len(right) != expected_right:
            raise ValueError(
                f"Teleop command length mismatch (left {len(left)}/{expected_left}, right {len(right)}/{expected_right})"
            )

        action: dict[str, float] = {}
        for name, value in zip(self.config.ros2.left_joint_names, left):
            action[f"{name}.pos"] = float(value)
        for name, value in zip(self.config.ros2.right_joint_names, right):
            action[f"{name}.pos"] = float(value)
        return action

    def send_feedback(self, feedback: dict[str, Any]) -> None:
        # No feedback channel implemented.
        return

    def disconnect(self) -> None:
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")
        self.ros2.disconnect()

    def get_teleop_events(self) -> dict[str, Any]:
        """
        检测遥操作事件，用于 HIL-SERL 人类干预检测。

        当用户按下 VR 手柄的 grip 扳机时，表示人类接管控制。
        """
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        left_grip = self.ros2.get_grip_value("left")
        right_grip = self.ros2.get_grip_value("right")

        # 任一手的 grip 扳机按下 (> 0.5) 表示人类干预
        is_intervention = (left_grip > 0.5) or (right_grip > 0.5)

        return {
            TeleopEvents.IS_INTERVENTION: is_intervention,
            TeleopEvents.TERMINATE_EPISODE: False,
            TeleopEvents.SUCCESS: False,
            TeleopEvents.RERECORD_EPISODE: False,
        }
