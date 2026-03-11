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

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    robot_controller = LaunchConfiguration("robot_controller", default="forward_position_controller")
    control_mode = LaunchConfiguration("control_mode", default="mit")
    use_fake_hardware = LaunchConfiguration("use_fake_hardware", default="true")
    connect_lerobot = LaunchConfiguration("connect_lerobot", default="true")

    # teleop default args from teleop_by_pico.launch.py
    try:
        openarmx_description_share = get_package_share_directory("openarmx_description")
        default_urdf = os.path.join(openarmx_description_share, "urdf", "robot", "openarmx_bimanual_sim_ext.urdf")
    except Exception:
        default_urdf = "/home/ubuntu/openarmx_ws/src/openarmx_description/urdf/robot/openarmx_bimanual_sim_ext.urdf"

    urdf_path = LaunchConfiguration("urdf_path", default=default_urdf)
    rate_topic = LaunchConfiguration("rate_topic", default="/pico_right_controller/rate")
    slow_max_step_deg = LaunchConfiguration("slow_max_step_deg", default="1.0")
    control_rate = LaunchConfiguration("control_rate", default="100.0")
    ik_iterations = LaunchConfiguration("ik_iterations", default="3")
    publish_visualization_tf = LaunchConfiguration("publish_visualization_tf", default="true")
    print_performance = LaunchConfiguration("print_performance", default="true")
    use_link4_ext = LaunchConfiguration("use_link4_ext", default="true")
    constraint_mode = LaunchConfiguration("constraint_mode", default="link")
    grip_threshold = LaunchConfiguration("grip_threshold", default="0.5")
    left_grip_topic = LaunchConfiguration("left_grip_topic", default="/pico_left_controller/grip")
    right_grip_topic = LaunchConfiguration("right_grip_topic", default="/pico_right_controller/grip")

    bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory("openarmx_bringup"), "launch", "openarmx.bimanual.launch.py")
        ),
        launch_arguments={
            "robot_controller": robot_controller,
            "control_mode": control_mode,
            "use_fake_hardware": use_fake_hardware,
        }.items(),
    )

    pico_bridge = Node(
        package="openarmx_teleop_bridge_vr_pico",
        executable="openarmx_teleop_bridge_vr_pico_node",
        name="openarmx_teleop_bridge_vr_pico_node",
        output="screen",
    )

    teleop_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory("openarmx_teleop_vr_pico"), "launch", "teleop_vr_pico.launch.py")
        ),
        launch_arguments={
            "connect_lerobot": connect_lerobot,
            "urdf_path": urdf_path,
            "rate_topic": rate_topic,
            "slow_max_step_deg": slow_max_step_deg,
            "control_rate": control_rate,
            "ik_iterations": ik_iterations,
            "publish_visualization_tf": publish_visualization_tf,
            "print_performance": print_performance,
            "use_link4_ext": use_link4_ext,
            "constraint_mode": constraint_mode,
            "grip_threshold": grip_threshold,
            "left_grip_topic": left_grip_topic,
            "right_grip_topic": right_grip_topic,
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_controller", default_value="forward_position_controller"),
            DeclareLaunchArgument("control_mode", default_value="mit"),
            DeclareLaunchArgument("use_fake_hardware", default_value="true"),
            DeclareLaunchArgument("connect_lerobot", default_value="true"),
            DeclareLaunchArgument("urdf_path", default_value=default_urdf),
            DeclareLaunchArgument("rate_topic", default_value="/pico_right_controller/rate"),
            DeclareLaunchArgument("slow_max_step_deg", default_value="1.0"),
            DeclareLaunchArgument("control_rate", default_value="100.0"),
            DeclareLaunchArgument("ik_iterations", default_value="3"),
            DeclareLaunchArgument("publish_visualization_tf", default_value="true"),
            DeclareLaunchArgument("print_performance", default_value="true"),
            DeclareLaunchArgument("use_link4_ext", default_value="true"),
            DeclareLaunchArgument("constraint_mode", default_value="link"),
            DeclareLaunchArgument("grip_threshold", default_value="0.5"),
            DeclareLaunchArgument("left_grip_topic", default_value="/pico_left_controller/grip"),
            DeclareLaunchArgument("right_grip_topic", default_value="/pico_right_controller/grip"),
            bringup_launch,
            pico_bridge,
            teleop_launch,
        ]
    )
