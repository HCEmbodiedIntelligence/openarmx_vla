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
import threading
import time

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray, Float32
from sensor_msgs.msg import JointState

from .config_openarmx_ros2 import OpenArmXRos2TeleopInterfaceConfig

logger = logging.getLogger(__name__)


class OpenArmXRos2TeleopInterface:
    """Minimal ROS 2 subscriber interface for the OpenArmX teleoperator feed."""

    def __init__(self, config: OpenArmXRos2TeleopInterfaceConfig):
        self.config = config

        self._node: Node | None = None
        self._executor: SingleThreadedExecutor | None = None
        self._spin_thread: threading.Thread | None = None

        self._left_sub = None
        self._right_sub = None
        self._joint_state_sub = None
        self._left_grip_sub = None
        self._right_grip_sub = None

        self._lock = threading.Lock()
        self._last_left: list[float] | None = None
        self._last_right: list[float] | None = None
        self._joint_states: dict[str, float] = {}  # Fallback when no commands
        self._left_grip_value: float = 0.0
        self._right_grip_value: float = 0.0
        self._warned_left_len = False
        self._warned_right_len = False

        self.is_connected = False

    def connect(self) -> None:
        if self.is_connected:
            return

        if not rclpy.ok():
            rclpy.init()

        self._node = Node("openarmx_lerobot_teleop_interface", namespace=self.config.namespace)

        self._left_sub = self._node.create_subscription(
            Float64MultiArray, self.config.left_command_topic, self._left_cb, 5
        )
        self._right_sub = self._node.create_subscription(
            Float64MultiArray, self.config.right_command_topic, self._right_cb, 5
        )
        # Subscribe to joint_states as fallback when no commands received
        self._joint_state_sub = self._node.create_subscription(
            JointState, "/joint_states", self._joint_state_cb, 5
        )
        # 订阅 VR grip 话题用于干预检测
        self._left_grip_sub = self._node.create_subscription(
            Float32, "/pico_left_controller/grip", self._left_grip_cb, 5
        )
        self._right_grip_sub = self._node.create_subscription(
            Float32, "/pico_right_controller/grip", self._right_grip_cb, 5
        )

        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

        # Allow some time for the subscriptions to start receiving data.
        time.sleep(0.2)
        self.is_connected = True

    def disconnect(self) -> None:
        if not self.is_connected:
            return

        if self._left_sub is not None:
            self._left_sub.destroy()
            self._left_sub = None
        if self._right_sub is not None:
            self._right_sub.destroy()
            self._right_sub = None
        if self._joint_state_sub is not None:
            self._joint_state_sub.destroy()
            self._joint_state_sub = None
        if self._left_grip_sub is not None:
            self._left_grip_sub.destroy()
            self._left_grip_sub = None
        if self._right_grip_sub is not None:
            self._right_grip_sub.destroy()
            self._right_grip_sub = None

        if self._node is not None:
            self._node.destroy_node()
            self._node = None

        if self._executor is not None:
            self._executor.shutdown()
            self._executor = None

        if self._spin_thread is not None:
            self._spin_thread.join(timeout=2.0)
            self._spin_thread = None

        self.is_connected = False

    def _left_cb(self, msg: Float64MultiArray) -> None:
        data = [float(x) for x in msg.data]
        expected = len(self.config.left_joint_names)
        if expected and len(data) != expected:
            if not self._warned_left_len:
                logger.warning(
                    "Left command length %s does not match expected joint count %s; ignoring message",
                    len(data),
                    expected,
                )
                self._warned_left_len = True
            return
        with self._lock:
            self._last_left = data

    def _right_cb(self, msg: Float64MultiArray) -> None:
        data = [float(x) for x in msg.data]
        expected = len(self.config.right_joint_names)
        if expected and len(data) != expected:
            if not self._warned_right_len:
                logger.warning(
                    "Right command length %s does not match expected joint count %s; ignoring message",
                    len(data),
                    expected,
                )
                self._warned_right_len = True
            return
        with self._lock:
            self._last_right = data

    def _joint_state_cb(self, msg: JointState) -> None:
        """Store joint states as fallback when no commands received."""
        with self._lock:
            for name, pos in zip(msg.name, msg.position):
                self._joint_states[name] = float(pos)

    def _left_grip_cb(self, msg: Float32) -> None:
        with self._lock:
            self._left_grip_value = float(msg.data)

    def _right_grip_cb(self, msg: Float32) -> None:
        with self._lock:
            self._right_grip_value = float(msg.data)

    def get_grip_value(self, side: str) -> float:
        """获取 grip 扳机值 (0.0-1.0)"""
        with self._lock:
            if side == "left":
                return self._left_grip_value
            elif side == "right":
                return self._right_grip_value
            else:
                raise ValueError(f"Unknown side: {side}")

    def _get_fallback_from_joint_states(self, joint_names: list[str]) -> list[float] | None:
        """Get current positions from joint_states as fallback."""
        with self._lock:
            if not self._joint_states:
                return None
            result = []
            for name in joint_names:
                if name in self._joint_states:
                    result.append(self._joint_states[name])
                else:
                    return None  # Missing joint, can't use as fallback
            return result

    def get_latest_joint_positions(self) -> dict[str, list[float]] | None:
        """Return the most recent left/right command vectors.

        Priority:
        1. Use commands from /commands topic if available
        2. Fall back to current joint_states (action = current position = "stay still")
        3. Return None only if neither is available
        """
        with self._lock:
            left = None if self._last_left is None else list(self._last_left)
            right = None if self._last_right is None else list(self._last_right)

        # If both commands are available, use them
        if left is not None and right is not None:
            return {"left": left, "right": right}

        # If one or both sides missing, try to use joint_states as fallback
        # This means action = current position = "stay still" (scientifically correct!)
        if left is None:
            left = self._get_fallback_from_joint_states(self.config.left_joint_names)
            if left is not None:
                logger.debug("Left commands not received, using current joint_states")
        if right is None:
            right = self._get_fallback_from_joint_states(self.config.right_joint_names)
            if right is not None:
                logger.debug("Right commands not received, using current joint_states")

        # If still missing (no joint_states either), return None
        if left is None or right is None:
            return None

        return {"left": left, "right": right}
