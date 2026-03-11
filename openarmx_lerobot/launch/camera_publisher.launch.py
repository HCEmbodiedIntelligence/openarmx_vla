#!/usr/bin/env python3
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

"""
RealSense 相机 ROS2 发布节点启动文件。

在工控机上运行此 launch 文件，将三个 RealSense 相机的 RGB 图像和深度图通过 ROS2 话题发布。
其他设备（如 Jetson）可以通过订阅这些话题获取相机数据。

支持的相机类型:
    - D405: RGB 集成在深度模块
    - D435: 独立 RGB 模块

话题统一映射 (接收端使用统一格式，无需关心相机类型):
    - /cam_left/color/image   (RGB 图像)
    - /cam_left/depth/image   (深度图)
    - /cam_right/color/image
    - /cam_right/depth/image
    - /cam_head/color/image
    - /cam_head/depth/image

命令行参数:
    - width: 图像宽度 (默认: 424)
    - height: 图像高度 (默认: 240)
    - fps: 帧率 (默认: 15)
    - cam_left_serial: 左手相机序列号 (默认: 218622270388)
    - cam_left_type: 左手相机类型 D405/D435 (默认: D405)
    - cam_right_serial: 右手相机序列号 (默认: 218622274446)
    - cam_right_type: 右手相机类型 D405/D435 (默认: D405)
    - cam_head_serial: 头部相机序列号 (默认: 335522070220)
    - cam_head_type: 头部相机类型 D405/D435 (默认: D435)

使用方法:
    # 默认配置启动
    ros2 launch openarmx_lerobot camera_publisher.launch.py

    # 自定义分辨率和帧率
    ros2 launch openarmx_lerobot camera_publisher.launch.py width:=640 height:=480 fps:=30

    # 自定义相机配置
    ros2 launch openarmx_lerobot camera_publisher.launch.py \\
        cam_left_serial:=123456789012 cam_left_type:=D435 \\
        cam_head_serial:=987654321098 cam_head_type:=D405

    # 确保所有设备使用相同的 ROS_DOMAIN_ID
    export ROS_DOMAIN_ID=42
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


# ============================================================================
# 支持的分辨率和帧率配置
# ============================================================================

# D405 支持的配置 (RGB 和深度共用深度模块)
D405_SUPPORTED_PROFILES = {
    # (width, height): [supported fps list]
    (1280, 720): [5, 15, 30],
    (848, 480): [5, 15, 30, 60, 90],
    (640, 480): [5, 15, 30, 60, 90],
    (640, 360): [5, 15, 30, 60, 90],
    (480, 270): [5, 15, 30, 60, 90],
    (424, 240): [5, 15, 30, 60, 90],
}

# D435 支持的配置
# 注意: D435 的 RGB 和深度模块分辨率可以不同，这里列出常用的共同支持配置
D435_SUPPORTED_PROFILES = {
    # (width, height): [supported fps list]
    (1920, 1080): [6, 15, 30],
    (1280, 720): [6, 15, 30],
    (848, 480): [6, 15, 30, 60, 90],
    (640, 480): [6, 15, 30, 60, 90],
    (640, 360): [6, 15, 30, 60, 90],
    (480, 270): [6, 15, 30, 60, 90],
    (424, 240): [6, 15, 30, 60, 90],
}


def validate_profile(cam_type: str, width: int, height: int, fps: int) -> tuple[bool, str]:
    """
    验证相机配置是否支持。

    Args:
        cam_type: 相机类型 (D405 或 D435)
        width: 图像宽度
        height: 图像高度
        fps: 帧率

    Returns:
        (is_valid, message): 是否有效及提示信息
    """
    cam_type_upper = cam_type.upper()

    if cam_type_upper == "D405":
        profiles = D405_SUPPORTED_PROFILES
    elif cam_type_upper in ("D435", "D435I"):
        profiles = D435_SUPPORTED_PROFILES
    else:
        return False, f"不支持的相机类型: {cam_type}，仅支持 D405 和 D435"

    resolution = (width, height)

    if resolution not in profiles:
        supported_res = ", ".join([f"{w}x{h}" for w, h in profiles.keys()])
        return False, (
            f"{cam_type_upper} 不支持分辨率 {width}x{height}\n"
            f"支持的分辨率: {supported_res}"
        )

    supported_fps = profiles[resolution]
    if fps not in supported_fps:
        return False, (
            f"{cam_type_upper} 在分辨率 {width}x{height} 下不支持帧率 {fps}\n"
            f"支持的帧率: {supported_fps}"
        )

    return True, f"{cam_type_upper} 配置有效: {width}x{height}@{fps}fps"


def create_camera_node(context, name: str, serial: str, cam_type: str, profile: str):
    """
    创建 RealSense 相机节点，并统一话题名称。

    Args:
        context: Launch context
        name: 相机名称 (如 cam_left, cam_right, cam_head)
        serial: 相机序列号
        cam_type: 相机类型 (D405 或 D435)
        profile: 分辨率和帧率配置字符串 (如 "424x240x15")

    Returns:
        配置好的 Node 对象
    """
    # 获取实际参数值
    serial_value = serial.perform(context) if hasattr(serial, 'perform') else serial
    cam_type_value = cam_type.perform(context) if hasattr(cam_type, 'perform') else cam_type
    profile_value = profile.perform(context) if hasattr(profile, 'perform') else profile

    # 序列号需要添加下划线前缀
    serial_str = f"_{serial_value}"

    # 根据相机类型确定原始话题名称和参数配置
    if cam_type_value.upper() == "D405":
        # D405: RGB 集成在深度模块，原始话题是 image_rect_raw
        camera_params = {
            "serial_no": serial_str,
            "depth_module.depth_profile": profile_value,
            "depth_module.color_profile": profile_value,
            "enable_color": True,
            "enable_depth": True,
            "align_depth.enable": True,
            "enable_infra1": False,
            "enable_infra2": False,
            "enable_gyro": False,
            "enable_accel": False,
            "pointcloud.enable": False,
        }
        # D405 的原始 RGB 话题是 color/image_rect_raw
        original_color_topic = f"/{name}/{name}/color/image_rect_raw"
    else:
        # D435/D435i: 独立 RGB 模块，原始话题是 image_raw
        camera_params = {
            "serial_no": serial_str,
            "rgb_camera.color_profile": profile_value,
            "depth_module.depth_profile": profile_value,
            "enable_color": True,
            "enable_depth": True,
            "align_depth.enable": True,
            "enable_infra1": False,
            "enable_infra2": False,
            "enable_gyro": False,
            "enable_accel": False,
            "pointcloud.enable": False,
        }
        # D435 的原始 RGB 话题是 color/image_raw
        original_color_topic = f"/{name}/{name}/color/image_raw"

    # 深度话题两种相机都相同
    original_depth_topic = f"/{name}/{name}/aligned_depth_to_color/image_raw"

    # 统一后的话题名称
    unified_color_topic = f"/{name}/color/image"
    unified_depth_topic = f"/{name}/depth/image"

    # 设置话题重映射
    remappings = [
        (original_color_topic, unified_color_topic),
        (original_depth_topic, unified_depth_topic),
    ]

    return Node(
        package="realsense2_camera",
        executable="realsense2_camera_node",
        name=name,
        namespace=name,
        parameters=[camera_params],
        remappings=remappings,
        output="screen",
    )


def launch_setup(context, *args, **kwargs):
    """动态创建相机节点"""
    # 获取配置参数
    width = int(LaunchConfiguration('width').perform(context))
    height = int(LaunchConfiguration('height').perform(context))
    fps = int(LaunchConfiguration('fps').perform(context))

    # 构建 profile 字符串
    profile = f"{width}x{height}x{fps}"

    # 获取各相机配置
    cam_left_serial = LaunchConfiguration('cam_left_serial')
    cam_left_type = LaunchConfiguration('cam_left_type')
    cam_right_serial = LaunchConfiguration('cam_right_serial')
    cam_right_type = LaunchConfiguration('cam_right_type')
    cam_head_serial = LaunchConfiguration('cam_head_serial')
    cam_head_type = LaunchConfiguration('cam_head_type')

    # 获取相机类型字符串用于校验
    cam_left_type_str = cam_left_type.perform(context)
    cam_right_type_str = cam_right_type.perform(context)
    cam_head_type_str = cam_head_type.perform(context)

    # 校验所有相机配置
    cameras_to_validate = [
        ("cam_left", cam_left_type_str),
        ("cam_right", cam_right_type_str),
        ("cam_head", cam_head_type_str),
    ]

    log_actions = []
    has_error = False

    for cam_name, cam_type_str in cameras_to_validate:
        is_valid, message = validate_profile(cam_type_str, width, height, fps)
        if not is_valid:
            has_error = True
            log_actions.append(
                LogInfo(msg=f"\n[ERROR] {cam_name} ({cam_type_str}) 配置无效:\n{message}\n")
            )
        else:
            log_actions.append(
                LogInfo(msg=f"[INFO] {cam_name}: {message}")
            )

    if has_error:
        # 打印支持的配置帮助信息
        log_actions.append(LogInfo(msg="\n" + "=" * 60))
        log_actions.append(LogInfo(msg="请参考 README 文档选择支持的分辨率和帧率组合"))
        log_actions.append(LogInfo(msg="或使用命令 rs-enumerate-devices -c 查看相机支持的配置"))
        log_actions.append(LogInfo(msg="=" * 60 + "\n"))

        # 返回错误信息但不创建节点
        raise RuntimeError(
            f"\n配置校验失败！\n"
            f"当前配置: {width}x{height}@{fps}fps\n"
            f"请检查相机类型和分辨率/帧率是否匹配。\n"
            f"运行 'rs-enumerate-devices -c' 查看相机支持的配置。"
        )

    # 创建相机节点
    cam_left_node = create_camera_node(
        context, "cam_left", cam_left_serial, cam_left_type, profile
    )
    cam_right_node = create_camera_node(
        context, "cam_right", cam_right_serial, cam_right_type, profile
    )
    cam_head_node = create_camera_node(
        context, "cam_head", cam_head_serial, cam_head_type, profile
    )

    return log_actions + [cam_left_node, cam_right_node, cam_head_node]


def generate_launch_description():
    return LaunchDescription([
        # 分辨率和帧率参数
        DeclareLaunchArgument(
            'width',
            default_value='424',
            description='图像宽度 (像素)'
        ),
        DeclareLaunchArgument(
            'height',
            default_value='240',
            description='图像高度 (像素)'
        ),
        DeclareLaunchArgument(
            'fps',
            default_value='15',
            description='帧率 (Hz)'
        ),

        # 左手相机参数
        DeclareLaunchArgument(
            'cam_left_serial',
            default_value='218622270388',
            description='左手相机序列号'
        ),
        DeclareLaunchArgument(
            'cam_left_type',
            default_value='D405',
            description='左手相机类型 (D405 或 D435)'
        ),

        # 右手相机参数
        DeclareLaunchArgument(
            'cam_right_serial',
            default_value='218622274446',
            description='右手相机序列号'
        ),
        DeclareLaunchArgument(
            'cam_right_type',
            default_value='D405',
            description='右手相机类型 (D405 或 D435)'
        ),

        # 头部相机参数
        DeclareLaunchArgument(
            'cam_head_serial',
            default_value='335522070220',
            description='头部相机序列号'
        ),
        DeclareLaunchArgument(
            'cam_head_type',
            default_value='D435',
            description='头部相机类型 (D405 或 D435)'
        ),

        # 使用 OpaqueFunction 动态创建节点
        OpaqueFunction(function=launch_setup),
    ])
