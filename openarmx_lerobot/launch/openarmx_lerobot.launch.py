#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    robot_controller = LaunchConfiguration("robot_controller")
    control_mode = LaunchConfiguration("control_mode")
    use_fake_hardware = LaunchConfiguration("use_fake_hardware")

    bridge_start_delay_s = LaunchConfiguration("bridge_start_delay_s")
    teleop_start_delay_s = LaunchConfiguration("teleop_start_delay_s")

    use_xacro = LaunchConfiguration("use_xacro")
    rate_topic = LaunchConfiguration("rate_topic")
    slow_max_step_deg = LaunchConfiguration("slow_max_step_deg")
    fast_max_step_deg = LaunchConfiguration("fast_max_step_deg")
    control_rate = LaunchConfiguration("control_rate")
    ik_iterations = LaunchConfiguration("ik_iterations")
    publish_visualization_tf = LaunchConfiguration("publish_visualization_tf")
    print_performance = LaunchConfiguration("print_performance")
    use_link4_ext = LaunchConfiguration("use_link4_ext")
    constraint_mode = LaunchConfiguration("constraint_mode")
    connect_lerobot = LaunchConfiguration("connect_lerobot")
    grip_threshold = LaunchConfiguration("grip_threshold")
    left_grip_topic = LaunchConfiguration("left_grip_topic")
    right_grip_topic = LaunchConfiguration("right_grip_topic")

    bringup_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("openarmx_bringup"),
                "launch",
                "openarmx.bimanual.launch.py",
            )
        ),
        launch_arguments={
            "control_mode": control_mode,
            "robot_controller": robot_controller,
            "use_fake_hardware": use_fake_hardware,
        }.items(),
    )

    pico_bridge = Node(
        package="pico_pose_bridge",
        executable="pico_pose_bridge_node",
        name="pico_pose_bridge_node",
        output="screen",
    )

    teleop_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory("openarmx_teleop_by_pico"),
                "launch",
                "teleop_by_pico.launch.py",
            )
        ),
        launch_arguments={
            "use_xacro": use_xacro,
            "rate_topic": rate_topic,
            "slow_max_step_deg": slow_max_step_deg,
            "fast_max_step_deg": fast_max_step_deg,
            "control_rate": control_rate,
            "ik_iterations": ik_iterations,
            "publish_visualization_tf": publish_visualization_tf,
            "print_performance": print_performance,
            "use_link4_ext": use_link4_ext,
            "constraint_mode": constraint_mode,
            "connect_lerobot": connect_lerobot,
            "grip_threshold": grip_threshold,
            "left_grip_topic": left_grip_topic,
            "right_grip_topic": right_grip_topic,
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("robot_controller", default_value="forward_position_controller"),
            DeclareLaunchArgument("control_mode", default_value="mit"),
            DeclareLaunchArgument("use_fake_hardware", default_value="false"),
            DeclareLaunchArgument("bridge_start_delay_s", default_value="1.0"),
            DeclareLaunchArgument("teleop_start_delay_s", default_value="2.0"),
            DeclareLaunchArgument("use_xacro", default_value="true"),
            DeclareLaunchArgument("rate_topic", default_value="/pico_right_controller/rate"),
            DeclareLaunchArgument("slow_max_step_deg", default_value="1.0"),
            DeclareLaunchArgument("fast_max_step_deg", default_value="12.0"),
            DeclareLaunchArgument("control_rate", default_value="100.0"),
            DeclareLaunchArgument("ik_iterations", default_value="3"),
            DeclareLaunchArgument("publish_visualization_tf", default_value="true"),
            DeclareLaunchArgument("print_performance", default_value="false"),
            DeclareLaunchArgument("use_link4_ext", default_value="true"),
            DeclareLaunchArgument("constraint_mode", default_value="joint"),
            DeclareLaunchArgument("connect_lerobot", default_value="false"),
            DeclareLaunchArgument("grip_threshold", default_value="0.5"),
            DeclareLaunchArgument("left_grip_topic", default_value="/pico_left_controller/grip"),
            DeclareLaunchArgument("right_grip_topic", default_value="/pico_right_controller/grip"),
            bringup_launch,
            TimerAction(period=bridge_start_delay_s, actions=[pico_bridge]),
            TimerAction(period=teleop_start_delay_s, actions=[teleop_launch]),
        ]
    )
