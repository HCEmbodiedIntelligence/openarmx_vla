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

"""ROS2 图像话题相机实现。

通过订阅 ROS2 图像话题获取相机数据，支持跨设备网络传输。
相机硬件连接在工控机上，通过 ROS2 DDS 将图像数据发送到其他设备。
"""

from __future__ import annotations

import abc
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import Image

from lerobot.cameras.camera import Camera
from lerobot.cameras.configs import CameraConfig, ColorMode, Cv2Rotation
from lerobot.utils.errors import DeviceAlreadyConnectedError, DeviceNotConnectedError

logger = logging.getLogger(__name__)


def get_cv2_rotation(rotation: Cv2Rotation) -> int | None:
    """Convert Cv2Rotation enum to OpenCV rotation constant."""
    if rotation == Cv2Rotation.NO_ROTATION:
        return None
    elif rotation == Cv2Rotation.ROTATE_90:
        return cv2.ROTATE_90_CLOCKWISE
    elif rotation == Cv2Rotation.ROTATE_180:
        return cv2.ROTATE_180
    elif rotation == Cv2Rotation.ROTATE_270:
        return cv2.ROTATE_90_COUNTERCLOCKWISE
    return None


@CameraConfig.register_subclass("ros2")
@dataclass(kw_only=True)
class Ros2CameraConfig(CameraConfig):
    """ROS2 图像话题相机配置。

    通过订阅 ROS2 图像话题获取相机数据，支持跨设备网络传输。

    Attributes:
        image_topic: 要订阅的图像话题名称
        color_mode: 输出颜色模式 (RGB 或 BGR)
        rotation: 图像旋转角度
        use_depth: 是否同时订阅深度图
        depth_topic: 深度图话题名称 (如果 use_depth=True)
        qos_reliability: QoS 可靠性策略 ("best_effort" 或 "reliable")
        queue_size: 订阅队列深度
    """

    image_topic: str = "/camera/color/image_raw"
    color_mode: ColorMode = ColorMode.RGB
    rotation: Cv2Rotation = Cv2Rotation.NO_ROTATION
    use_depth: bool = False
    depth_topic: str = "/camera/depth/image_raw"
    qos_reliability: str = "best_effort"  # "best_effort" 延迟低，"reliable" 保证送达
    queue_size: int = 1  # 只保留最新帧，减少延迟


class Ros2Camera(Camera):
    """通过 ROS2 话题订阅获取图像的相机类。

    工作原理:
    1. 相机硬件连接在工控机上，工控机运行 RealSense ROS2 节点发布图像
    2. 本类创建 ROS2 订阅者，接收图像话题
    3. 通过 ROS2 DDS，图像可以跨设备网络传输

    优点:
    - 相机只需连接一台设备，其他设备通过网络获取图像
    - 无需在多设备间插拔相机线
    - 解决多 USB 相机带宽不足问题

    Example:
        config = Ros2CameraConfig(
            image_topic="/cam_left/color/image_raw",
            fps=15,
            width=424,
            height=240,
        )
        camera = Ros2Camera(config)
        camera.connect()
        frame = camera.async_read()
        camera.disconnect()
    """

    def __init__(self, config: Ros2CameraConfig):
        super().__init__(config)
        self.config = config

        self._node: Node | None = None
        self._executor: SingleThreadedExecutor | None = None
        self._spin_thread: threading.Thread | None = None

        self._image_sub = None
        self._depth_sub = None

        self._lock = threading.Lock()
        self._latest_frame: NDArray[Any] | None = None
        self._latest_depth: NDArray[Any] | None = None
        self._new_frame_event = threading.Event()

        self._is_connected = False
        self.rotation: int | None = get_cv2_rotation(config.rotation)

    def __str__(self) -> str:
        return f"Ros2Camera({self.config.image_topic})"

    @property
    def is_connected(self) -> bool:
        """检查相机是否已连接。"""
        return self._is_connected

    @staticmethod
    def find_cameras() -> list[dict[str, Any]]:
        """查找可用的 ROS2 图像话题。

        注意: 需要 ROS2 环境已初始化。
        """
        found = []

        if not rclpy.ok():
            try:
                rclpy.init()
            except Exception:
                return found

        try:
            node = Node("ros2_camera_finder")
            topic_names_and_types = node.get_topic_names_and_types()

            for topic_name, topic_types in topic_names_and_types:
                if "sensor_msgs/msg/Image" in topic_types:
                    found.append({
                        "type": "Ros2Camera",
                        "topic": topic_name,
                        "id": topic_name,
                    })

            node.destroy_node()
        except Exception as e:
            logger.warning(f"Failed to find ROS2 cameras: {e}")

        return found

    def connect(self, warmup: bool = True) -> None:
        """连接到 ROS2 图像话题。

        Args:
            warmup: 是否等待接收第一帧图像
        """
        if self.is_connected:
            raise DeviceAlreadyConnectedError(f"{self} is already connected.")

        # 初始化 ROS2
        if not rclpy.ok():
            rclpy.init()

        # 创建节点
        node_name = f"ros2_camera_{self.config.image_topic.replace('/', '_').strip('_')}"
        self._node = Node(node_name)

        # 配置 QoS
        if self.config.qos_reliability == "reliable":
            reliability = ReliabilityPolicy.RELIABLE
        else:
            reliability = ReliabilityPolicy.BEST_EFFORT

        qos_profile = QoSProfile(
            reliability=reliability,
            history=HistoryPolicy.KEEP_LAST,
            depth=self.config.queue_size,
        )

        # 创建图像订阅者
        self._image_sub = self._node.create_subscription(
            Image,
            self.config.image_topic,
            self._image_callback,
            qos_profile,
        )

        # 如果需要深度图，创建深度订阅者
        if self.config.use_depth:
            self._depth_sub = self._node.create_subscription(
                Image,
                self.config.depth_topic,
                self._depth_callback,
                qos_profile,
            )

        # 启动 executor 线程
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)
        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

        self._is_connected = True

        # 等待第一帧
        if warmup:
            logger.info(f"{self} waiting for first frame...")
            t0 = time.time()
            timeout = 10.0  # 网络传输可能需要更长时间
            while self._latest_frame is None:
                if time.time() - t0 > timeout:
                    logger.warning(f"{self} timeout waiting for first frame. "
                                   f"Ensure the image publisher is running.")
                    break
                time.sleep(0.1)

            if self._latest_frame is not None:
                logger.info(f"{self} connected, receiving frames.")

    def disconnect(self) -> None:
        """断开与 ROS2 话题的连接。"""
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        # 销毁订阅者
        if self._image_sub is not None:
            self._node.destroy_subscription(self._image_sub)
            self._image_sub = None

        if self._depth_sub is not None:
            self._node.destroy_subscription(self._depth_sub)
            self._depth_sub = None

        # 停止 executor
        if self._executor is not None:
            self._executor.shutdown()
            self._executor = None

        if self._spin_thread is not None:
            self._spin_thread.join(timeout=2.0)
            self._spin_thread = None

        # 销毁节点
        if self._node is not None:
            self._node.destroy_node()
            self._node = None

        self._is_connected = False
        self._latest_frame = None
        self._latest_depth = None

        logger.info(f"{self} disconnected.")

    def _image_callback(self, msg: Image) -> None:
        """处理接收到的图像消息。"""
        try:
            # 将 ROS2 Image 消息转换为 numpy 数组
            frame = self._ros_image_to_numpy(msg)

            # 应用后处理（颜色转换、旋转）
            frame = self._postprocess_image(frame)

            with self._lock:
                self._latest_frame = frame
            self._new_frame_event.set()

        except Exception as e:
            logger.error(f"Error processing image from {self.config.image_topic}: {e}")

    def _depth_callback(self, msg: Image) -> None:
        """处理接收到的深度图消息。"""
        try:
            # 深度图通常是 16UC1 格式
            if msg.encoding == "16UC1" or msg.encoding == "mono16":
                depth = np.frombuffer(msg.data, dtype=np.uint16).reshape(msg.height, msg.width)
            elif msg.encoding == "32FC1":
                depth = np.frombuffer(msg.data, dtype=np.float32).reshape(msg.height, msg.width)
            else:
                logger.warning(f"Unsupported depth encoding: {msg.encoding}")
                return

            # 应用旋转
            if self.rotation is not None:
                depth = cv2.rotate(depth, self.rotation)

            with self._lock:
                self._latest_depth = depth

        except Exception as e:
            logger.error(f"Error processing depth from {self.config.depth_topic}: {e}")

    def _ros_image_to_numpy(self, msg: Image) -> NDArray[Any]:
        """将 ROS2 Image 消息转换为 numpy 数组。"""
        # 根据编码确定数据类型和通道数
        encoding = msg.encoding.lower()

        if encoding in ("rgb8", "bgr8"):
            dtype = np.uint8
            channels = 3
        elif encoding in ("rgba8", "bgra8"):
            dtype = np.uint8
            channels = 4
        elif encoding == "mono8":
            dtype = np.uint8
            channels = 1
        elif encoding == "mono16" or encoding == "16uc1":
            dtype = np.uint16
            channels = 1
        else:
            # 默认尝试作为 RGB8
            dtype = np.uint8
            channels = 3
            logger.warning(f"Unknown encoding '{msg.encoding}', assuming RGB8")

        # 转换为 numpy 数组
        if channels == 1:
            frame = np.frombuffer(msg.data, dtype=dtype).reshape(msg.height, msg.width)
        else:
            frame = np.frombuffer(msg.data, dtype=dtype).reshape(msg.height, msg.width, channels)

        # 处理 RGBA -> RGB
        if channels == 4:
            frame = frame[:, :, :3]

        # 处理 BGR -> RGB 或 RGB -> BGR
        if encoding == "bgr8" or encoding == "bgra8":
            # 输入是 BGR
            if self.config.color_mode == ColorMode.RGB:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # 否则保持 BGR
        else:
            # 输入是 RGB
            if self.config.color_mode == ColorMode.BGR:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            # 否则保持 RGB

        return frame

    def _postprocess_image(self, frame: NDArray[Any]) -> NDArray[Any]:
        """应用后处理：旋转等。"""
        if self.rotation is not None:
            frame = cv2.rotate(frame, self.rotation)
        return frame

    def read(self, color_mode: ColorMode | None = None) -> NDArray[Any]:
        """同步读取一帧图像。

        注意: 对于 ROS2 相机，这个方法返回最近接收到的帧。
        如果没有新帧，会等待直到超时。
        """
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        # 等待新帧
        self._new_frame_event.wait(timeout=1.0)

        with self._lock:
            if self._latest_frame is None:
                raise RuntimeError(f"No frame available from {self}")
            frame = self._latest_frame.copy()

        # 如果请求不同的颜色模式，进行转换
        if color_mode is not None and color_mode != self.config.color_mode:
            if color_mode == ColorMode.BGR and self.config.color_mode == ColorMode.RGB:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            elif color_mode == ColorMode.RGB and self.config.color_mode == ColorMode.BGR:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        return frame

    def async_read(self, timeout_ms: float = 200) -> NDArray[Any]:
        """异步读取最新的一帧图像。

        Args:
            timeout_ms: 等待新帧的超时时间（毫秒）

        Returns:
            最新的图像帧 (numpy 数组)
        """
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        # 等待新帧或超时
        got_frame = self._new_frame_event.wait(timeout=timeout_ms / 1000.0)

        with self._lock:
            if self._latest_frame is None:
                raise TimeoutError(f"No frame received from {self} within {timeout_ms}ms. "
                                   f"Ensure the image publisher is running and topic is correct.")
            frame = self._latest_frame.copy()
            self._new_frame_event.clear()

        return frame

    def read_depth(self, timeout_ms: float = 200) -> NDArray[Any]:
        """读取深度图。

        Args:
            timeout_ms: 超时时间（毫秒）

        Returns:
            深度图 (numpy 数组)
        """
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        if not self.config.use_depth:
            raise RuntimeError(f"Depth is not enabled for {self}")

        with self._lock:
            if self._latest_depth is None:
                raise TimeoutError(f"No depth frame received from {self}")
            return self._latest_depth.copy()
