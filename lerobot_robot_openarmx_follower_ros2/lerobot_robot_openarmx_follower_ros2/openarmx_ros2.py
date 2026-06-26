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
        # False = closed, True = open. None means that the first policy output
        # will initialize the state.
        self._gripper_binary_state: dict[str, bool | None] = {
            joint: None for joint in self._all_joint_names if "finger_joint" in joint
        }
        self._gripper_pending_state: dict[str, bool | None] = {
            joint: None for joint in self._gripper_binary_state
        }
        self._gripper_pending_count: dict[str, int] = {
            joint: 0 for joint in self._gripper_binary_state
        }
        self._gripper_hold_until_step: dict[str, int] = {
            joint: 0 for joint in self._gripper_binary_state
        }
        self._gripper_debug_step = 0

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
        self._replay_teach_action(self.config.init_pos_path, joint_thr=0.20)
        self._calibrated=True

    def configure(self) -> None:
        return  # handled externally

    def reset(self) -> None:
        """Move from the current pose to the last waypoint in init_pos.yaml."""
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        self.ros2.set_reset_active(True)
        try:
            # Allow the VR teleop node to observe the inhibit message before
            # publishing the first reset command.
            time.sleep(0.2)
            goal = self._load_reset_goal_from_yaml(self.config.init_pos_path)
            self._move_to_joint_goal(goal)
        finally:
            try:
                self.ros2.set_reset_active(False)
            except Exception:
                logger.exception("Failed to release the teleop reset inhibit.")

    def _load_reset_goal_from_yaml(self, yaml_path: str | None) -> dict[str, float]:
        if yaml_path is None:
            raise ValueError("Reset YAML path is not configured.")
        if not os.path.isfile(yaml_path):
            raise ValueError(f"Reset YAML not found: {yaml_path}")

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        yaml_joint_names: list[str] = data["joint_names"]
        points: list[dict[str, Any]] = data["points"]
        if not points:
            raise ValueError(f"Reset YAML has no trajectory points: {yaml_path}")

        final_positions = points[-1]["positions"]
        if len(final_positions) != len(yaml_joint_names):
            raise ValueError("Reset YAML final waypoint length does not match joint_names.")

        pos_map = {yaml_joint_names[i]: float(final_positions[i]) for i in range(len(yaml_joint_names))}

        missing = [j for j in self._all_joint_names if j not in pos_map]
        if missing:
            raise ValueError(f"Joints in config not found in reset YAML: {missing}")

        return {j: pos_map[j] for j in self._all_joint_names}

    def _move_to_joint_goal(
        self,
        goal: dict[str, float],
        dt: float = 0.05,
        max_step: float = 0.03,
        goal_tolerance: float = 0.05,
        timeout_s: float = 30.0,
    ) -> None:
        """Safely interpolate from the current pose to the target joint pose."""
        start_t = time.time()
        command = self.ros2.get_joint_positions(self._all_joint_names)
        if command is None:
            raise ValueError("Joint state is not available yet.")
        missing = [j for j in self._all_joint_names if j not in command]
        if missing:
            raise ValueError(f"Missing joints in joint_states during reset: {missing}")
        logger.info(
            "Reset: moving robot to target pose with dt=%.3fs, max_step=%.3frad, tolerance=%.3frad",
            dt,
            max_step,
            goal_tolerance,
        )

        while True:
            present = self.ros2.get_joint_positions(self._all_joint_names)
            if present is None:
                raise ValueError("Joint state is not available yet.")

            missing = [j for j in self._all_joint_names if j not in present]
            if missing:
                raise ValueError(f"Missing joints in joint_states during reset: {missing}")

            next_goal: dict[str, float] = {}
            max_error = 0.0
            for joint in self._all_joint_names:
                error = goal[joint] - present[joint]
                max_error = max(max_error, abs(error))
                command_error = goal[joint] - command[joint]
                if abs(command_error) <= max_step:
                    next_goal[joint] = goal[joint]
                else:
                    next_goal[joint] = command[joint] + max_step * (1.0 if command_error > 0.0 else -1.0)

            if max_error <= goal_tolerance:
                break

            left_vec = [next_goal[j] for j in self.config.ros2.left_joint_names]
            right_vec = [next_goal[j] for j in self.config.ros2.right_joint_names]
            self.ros2.send_left_positions(left_vec)
            self.ros2.send_right_positions(right_vec)
            command = next_goal

            if time.time() - start_t > timeout_s:
                errors = sorted(
                    ((j, abs(goal[j] - present[j])) for j in self._all_joint_names),
                    key=lambda item: item[1],
                    reverse=True,
                )
                unresolved = ", ".join(
                    f"{name}={error:.4f}rad" for name, error in errors if error > goal_tolerance
                )
                raise TimeoutError(
                    f"Reset timed out after {timeout_s:.1f}s; unresolved joints: {unresolved}"
                )

            time.sleep(dt)

        left_vec = [goal[j] for j in self.config.ros2.left_joint_names]
        right_vec = [goal[j] for j in self.config.ros2.right_joint_names]
        self.ros2.send_left_positions(left_vec)
        self.ros2.send_right_positions(right_vec)
        logger.info("Reset: robot reached target pose from init_pos.yaml final waypoint.")


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

        if self.config.binary_gripper:
            goal = self._classify_gripper_goals(goal)

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

    def _classify_gripper_goals(self, goal: dict[str, float]) -> dict[str, float]:
        """Map continuous policy gripper outputs to stable closed/open commands."""
        close_threshold = self.config.gripper_close_threshold
        open_threshold = self.config.gripper_open_threshold
        if close_threshold >= open_threshold:
            raise ValueError(
                "gripper_close_threshold must be smaller than gripper_open_threshold "
                f"(got {close_threshold} >= {open_threshold})."
            )
        confirm_frames = self.config.gripper_confirm_frames
        if confirm_frames < 1:
            raise ValueError(f"gripper_confirm_frames must be >= 1 (got {confirm_frames}).")
        debug_every = self.config.gripper_debug_log_every
        if debug_every < 0:
            raise ValueError(f"gripper_debug_log_every must be >= 0 (got {debug_every}).")
        min_open_frames = self.config.gripper_min_open_frames
        min_closed_frames = self.config.gripper_min_closed_frames
        if min_open_frames < 0 or min_closed_frames < 0:
            raise ValueError(
                "gripper_min_open_frames and gripper_min_closed_frames must be >= 0 "
                f"(got {min_open_frames}, {min_closed_frames})."
            )
        self._gripper_debug_step += 1

        midpoint = (close_threshold + open_threshold) / 2.0
        classified = dict(goal)
        for joint, previous_state in self._gripper_binary_state.items():
            raw = goal[joint]
            state = previous_state
            if state is None:
                state = raw >= midpoint
                self._gripper_pending_state[joint] = None
                self._gripper_pending_count[joint] = 0
                hold_frames = min_open_frames if state else min_closed_frames
                self._gripper_hold_until_step[joint] = self._gripper_debug_step + hold_frames
            else:
                desired_state = state
                hold_active = self._gripper_debug_step < self._gripper_hold_until_step[joint]
                if not hold_active:
                    if state and raw <= close_threshold:
                        desired_state = False
                    elif not state and raw >= open_threshold:
                        desired_state = True

                if desired_state != state:
                    if self._gripper_pending_state[joint] == desired_state:
                        self._gripper_pending_count[joint] += 1
                    else:
                        self._gripper_pending_state[joint] = desired_state
                        self._gripper_pending_count[joint] = 1

                    if self._gripper_pending_count[joint] >= confirm_frames:
                        state = desired_state
                        hold_frames = min_open_frames if state else min_closed_frames
                        self._gripper_hold_until_step[joint] = self._gripper_debug_step + hold_frames
                        self._gripper_pending_state[joint] = None
                        self._gripper_pending_count[joint] = 0
                else:
                    self._gripper_pending_state[joint] = None
                    self._gripper_pending_count[joint] = 0

            if state != previous_state:
                logger.info(
                    "Binary gripper: %s raw=%.5f -> state=%d (%s)",
                    joint,
                    raw,
                    int(state),
                    "open" if state else "closed",
                )
            elif debug_every and self._gripper_debug_step % debug_every == 0:
                pending_state = self._gripper_pending_state[joint]
                hold_remaining = max(0, self._gripper_hold_until_step[joint] - self._gripper_debug_step)
                logger.info(
                    "Binary gripper debug: step=%d %s raw=%.5f state=%d pending=%s/%d "
                    "hold=%d thr_close=%.5f thr_open=%.5f",
                    self._gripper_debug_step,
                    joint,
                    raw,
                    int(state),
                    (
                        "open"
                        if pending_state is True
                        else "closed"
                        if pending_state is False
                        else "none"
                    ),
                    self._gripper_pending_count[joint],
                    hold_remaining,
                    close_threshold,
                    open_threshold,
                )
            self._gripper_binary_state[joint] = state
            classified[joint] = (
                self.config.gripper_open_position
                if state
                else self.config.gripper_closed_position
            )

        return classified

    def disconnect(self) -> None:
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        try:
            self.ros2.set_reset_active(True)
            time.sleep(0.2)
            # LeRobot skips the inter-episode reset after the final episode.
            # Move to the start of return_pos.yaml before replaying it home.
            reset_goal = self._load_reset_goal_from_yaml(self.config.init_pos_path)
            self._move_to_joint_goal(reset_goal)
            self._replay_teach_action(self.config.return_pos_path, joint_thr=0.348)
        except Exception:
            logger.exception("Return trajectory failed; disconnecting devices anyway.")
        finally:
            try:
                self.ros2.set_reset_active(False)
                time.sleep(0.1)
            except Exception:
                logger.exception("Failed to release the teleop reset inhibit.")
            for cam in self.cameras.values():
                try:
                    cam.disconnect()
                except Exception:
                    logger.exception("Failed to disconnect camera during robot shutdown.")
            self.ros2.disconnect()
            self._calibrated = False

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
