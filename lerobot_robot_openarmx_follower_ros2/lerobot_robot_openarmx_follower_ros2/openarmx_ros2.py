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

import bisect
import logging
import os
import time
from functools import cached_property
from typing import Any

import yaml

from lerobot.cameras.camera import Camera
from lerobot.robots import Robot
from lerobot.robots.utils import ensure_safe_goal_position
from lerobot.utils.errors import DeviceAlreadyConnectedError, DeviceNotConnectedError

from .config_openarmx_ros2 import OpenArmXRos2Config
from .ros2_camera import Ros2Camera, Ros2CameraConfig
from .ros2_interface_openarmx import OpenArmXRos2Interface

logger = logging.getLogger(__name__)


def make_cameras(camera_configs: dict[str, Any]) -> dict[str, Camera]:
    """创建相机实例，支持 Ros2Camera 和 LeRobot 内置相机类型。"""
    cameras: dict[str, Camera] = {}

    for key, cfg in camera_configs.items():
        if isinstance(cfg, Ros2CameraConfig):
            # 使用我们的 ROS2 相机
            cameras[key] = Ros2Camera(cfg)
        else:
            # 回退到 LeRobot 内置的相机工厂
            from lerobot.cameras.utils import make_cameras_from_configs
            cameras[key] = make_cameras_from_configs({key: cfg})[key]

    return cameras


class OpenArmXRos2(Robot):
    """OpenArmX bimanual robot controlled via ROS 2 topics.

    Observations:
      - per-joint positions from /joint_states
      - optional camera frames (if configured)

    Actions:
      - per-joint target positions published as Float64MultiArray to:
        /left_forward_position_controller/commands
        /right_forward_position_controller/commands

    The command vector ordering is defined by config.ros2.left_joint_names / right_joint_names.
    """

    config_class = OpenArmXRos2Config
    # Keep type name aligned with lerobot CLI choice list
    name = "openarmx_ros2"

    def __init__(self, config: OpenArmXRos2Config):
        super().__init__(config)
        self.config = config
        self.ros2 = OpenArmXRos2Interface(config.ros2)
        self.cameras = make_cameras(config.cameras)

        self._all_joint_names = self.config.ros2.left_joint_names + self.config.ros2.right_joint_names

        self._calibrated=False

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        motor_state_ft = {f"{j}.pos": float for j in self._all_joint_names}
        cams_ft = {
            cam: (self.config.cameras[cam].height, self.config.cameras[cam].width, 3) for cam in self.cameras
        }
        return {**motor_state_ft, **cams_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return {f"{j}.pos": float for j in self._all_joint_names}

    @property
    def is_connected(self) -> bool:
        return self.ros2.is_connected and all(cam.is_connected for cam in self.cameras.values())

    def connect(self, calibrate: bool = True) -> None:
        if self.is_connected:
            raise DeviceAlreadyConnectedError(f"{self} already connected")

        for cam in self.cameras.values():
            cam.connect()
        self.ros2.connect()

        # OpenArmX is calibrated/configured by ROS bringup.
        self.configure()

        # Wait for joint state once to avoid get_observation failing immediately.
        t0 = time.time()
        while self.ros2.get_joint_positions(self._all_joint_names) is None:
            if time.time() - t0 > 5.0:
                break
            time.sleep(0.05)

        if calibrate:
            self.calibrate()

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated

    def calibrate(self) -> None:
        self._replay_teach_action(self.config.init_pos_path, joint_thr=0.174)
        self._calibrated=True

    def configure(self) -> None:
        return  # handled externally


    def get_observation(self) -> dict[str, Any]:
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        obs: dict[str, Any] = {}
        positions = self.ros2.get_joint_positions(self._all_joint_names)
        if positions is None:
            raise ValueError("Joint state is not available yet.")

        # Fill all joints (if some are missing, fail loudly to avoid silent dataset corruption)
        missing = [j for j in self._all_joint_names if j not in positions]
        if missing:
            raise ValueError(f"Missing joints in joint_states: {missing}")

        obs.update({f"{j}.pos": positions[j] for j in self._all_joint_names})

        for cam_key, cam in self.cameras.items():
            try:
                obs[cam_key] = cam.async_read(timeout_ms=300)
            except Exception as e:
                logger.error(f"Failed to read camera {cam_key}: {e}")
                obs[cam_key] = None

        return obs

    def send_action(self, action: dict[str, float]) -> dict[str, float]:
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        # Build per-joint goals
        goal = {k.removesuffix(".pos"): float(v) for k, v in action.items() if k.endswith(".pos")}

        # Skip sending if configured (direct teleop mode - teleop_node controls robot)
        if self.config.skip_send_action:
            return {f"{j}.pos": goal[j] for j in self._all_joint_names}

        # Optional relative clipping (same helper as other robots)
        if self.config.max_relative_target is not None:
            present = self.ros2.get_joint_positions(self._all_joint_names)
            if present is None:
                raise ValueError("Joint state is not available yet.")
            goal_present = {f"{j}.pos": (goal[j], present[j]) for j in self._all_joint_names}
            clipped = ensure_safe_goal_position(goal_present, self.config.max_relative_target)
            goal = {k.removesuffix(".pos"): v for k, v in clipped.items()}

        left_vec = [goal[j] for j in self.config.ros2.left_joint_names]
        right_vec = [goal[j] for j in self.config.ros2.right_joint_names]

        self.ros2.send_left_positions(left_vec)
        self.ros2.send_right_positions(right_vec)

        return {f"{j}.pos": goal[j] for j in self._all_joint_names}

    def disconnect(self) -> None:
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")
        
        self._replay_teach_action(self.config.return_pos_path, joint_thr=0.348)
        for cam in self.cameras.values():
            cam.disconnect()
        self.ros2.disconnect()
        self._calibrated=False

    def _replay_teach_action(self,yaml_path,joint_thr=None):
        """Load demo.yaml trajectory and slowly move robot to the initial position.

        Args:
            yaml_path: Path to the demo YAML file containing the trajectory.
            joint_thr: If set, compare current joint positions with the first
                trajectory point. When any joint difference exceeds this
                threshold, the robot will not move and a ValueError is raised.
        """
        if yaml_path is None:
            return  # No demo file configured, skip calibration.

        if not os.path.isfile(yaml_path):
            logger.warning(f"Demo YAML not found: {yaml_path}, skipping calibration.")
            return


        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        yaml_joint_names: list[str] = data["joint_names"]
        points: list[dict] = data["points"]

        # Build mapping: joint name -> index in yaml positions vector
        name_to_yaml_idx = {name: i for i, name in enumerate(yaml_joint_names)}

        # Verify all configured joints exist in the yaml
        left_names = self.config.ros2.left_joint_names
        right_names = self.config.ros2.right_joint_names
        all_cfg_names = left_names + right_names
        missing = [j for j in all_cfg_names if j not in name_to_yaml_idx]
        if missing:
            raise ValueError(f"Joints in config not found in demo YAML: {missing}")

        # Parse time_from_start (handle both float and {secs, nsecs} dict)
        def _parse_time(t):
            if isinstance(t, dict):
                return float(t.get("secs", 0)) + float(t.get("nsecs", 0)) * 1e-9
            return float(t)

        times = [_parse_time(p["time_from_start"]) for p in points]
        all_positions = [p["positions"] for p in points]

        # Convert each yaml point to left/right command vectors (in config order)
        left_goals: list[list[float]] = []
        right_goals: list[list[float]] = []
        for pos in all_positions:
            pos_map = {yaml_joint_names[i]: float(pos[i]) for i in range(len(yaml_joint_names))}
            left_goals.append([pos_map[j] for j in left_names])
            right_goals.append([pos_map[j] for j in right_names])

        # --- Joint threshold check: compare current pose with first trajectory point ---
        if joint_thr is not None:
            current_positions = self.ros2.get_joint_positions(self._all_joint_names)
            if current_positions is None:
                raise ValueError("Joint state is not available yet.")

            first_goals = left_goals[0] + right_goals[0]  # ordered as all_joint_names
            exceeded: list[tuple[int, str, float]] = []
            for idx, (name, first_val) in enumerate(zip(self._all_joint_names, first_goals)):
                diff = abs(current_positions[name] - first_val)
                if diff > joint_thr:
                    exceeded.append((idx, name, diff))

            if exceeded:
                for idx, name, diff in exceeded:
                    logger.warning(
                        f"Joint #{idx} '{name}' diff={diff:.4f} exceeds threshold {joint_thr}"
                    )
                max_item = max(exceeded, key=lambda x: x[2])
                raise ValueError(
                    f"Joint position difference too large: joint #{max_item[0]} '{max_item[1]}' "
                    f"diff={max_item[2]:.4f} > threshold={joint_thr}. "
                    f"Total {len(exceeded)} joint(s) exceeded. Robot will not move."
                )

        # Slowly execute the trajectory via linear interpolation
        speed_scale = self.config.calib_speed_scale
        dt = 0.05  # 50 ms control loop period
        total_duration = times[-1] / speed_scale
        logger.info(
            f"Calibration: executing demo trajectory '{yaml_path}' "
            f"({len(points)} points, {total_duration:.1f}s at speed_scale={speed_scale})"
        )

        t0 = time.time()
        while True:
            elapsed = time.time() - t0
            traj_time = elapsed * speed_scale

            if traj_time >= times[-1]:
                break

            # Locate segment [i, i+1] via binary search
            i = bisect.bisect_right(times, traj_time) - 1
            if i < 0:
                i = 0
            if i >= len(times) - 1:
                i = len(times) - 2

            t_start = times[i]
            t_end = times[i + 1]
            alpha = (traj_time - t_start) / (t_end - t_start) if (t_end - t_start) > 1e-9 else 0.0
            # alpha=0.0

            # Linear interpolation for left and right arm
            left_vec = [
                left_goals[i][k] + alpha * (left_goals[i + 1][k] - left_goals[i][k])
                for k in range(len(left_names))
            ]
            right_vec = [
                right_goals[i][k] + alpha * (right_goals[i + 1][k] - right_goals[i][k])
                for k in range(len(right_names))
            ]

            self.ros2.send_left_positions(left_vec)
            self.ros2.send_right_positions(right_vec)

            time.sleep(dt)

        # Force-send the final point for precise positioning
        self.ros2.send_left_positions(left_goals[-1])
        self.ros2.send_right_positions(right_goals[-1])
        logger.info("Calibration trajectory completed, robot at initial position.")