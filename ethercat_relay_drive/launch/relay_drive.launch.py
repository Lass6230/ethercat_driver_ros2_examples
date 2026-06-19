# Copyright 2023 ICube Laboratory, University of Strasbourg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
relay_drive.launch.py
=====================
Launches the ros2_control stack for the EK1100 + EL2622 EtherCAT relay demo.

Prerequisites
-------------
  sudo /etc/init.d/ethercat start        # EtherCAT master must be running
  ethercat slaves                         # verify EK1100 (pos 0) + EL2622 (pos 1)

Launch
------
  ros2 launch ethercat_relay_drive relay_drive.launch.py

Control relays via topic
------------------------
  # Close relay 1, leave relay 2 open:
  ros2 topic pub --once /relay_gpio_controller/commands \
      control_msgs/msg/DynamicInterfaceGroupValues \
      "{interface_groups: ['relays'], interface_values: [{interface_names: ['relay_1', 'relay_2'], values: [1.0, 0.0]}]}"

  # Close both relays:
  ros2 topic pub --once /relay_gpio_controller/commands \
      control_msgs/msg/DynamicInterfaceGroupValues \
      "{interface_groups: ['relays'], interface_values: [{interface_names: ['relay_1', 'relay_2'], values: [1.0, 1.0]}]}"

  # Open both relays:
  ros2 topic pub --once /relay_gpio_controller/commands \
      control_msgs/msg/DynamicInterfaceGroupValues \
      "{interface_groups: ['relays'], interface_values: [{interface_names: ['relay_1', 'relay_2'], values: [0.0, 0.0]}]}"

List active interfaces
----------------------
  ros2 control list_hardware_interfaces
  ros2 control list_controllers
"""

from launch import LaunchDescription
from launch.substitutions import Command, FindExecutable, PathJoinSubstitution

from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    # Get URDF via xacro
    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            PathJoinSubstitution(
                [
                    FindPackageShare("ethercat_relay_drive"),
                    "description/config",
                    "relay_drive.config.xacro",
                ]
            ),
        ]
    )
    robot_description = {"robot_description": robot_description_content}

    robot_controllers = PathJoinSubstitution(
        [
            FindPackageShare("ethercat_relay_drive"),
            "config",
            "controllers.yaml",
        ]
    )

    # ros2_control node (controller manager + EthercatDriver hardware interface)
    control_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[robot_description, robot_controllers],
        output="both",
    )

    # robot_state_publisher — publishes URDF to /robot_description topic
    robot_state_pub_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="both",
        parameters=[robot_description],
    )

    # Spawn the GPIO relay controller
    relay_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["relay_gpio_controller", "-c", "/controller_manager"],
    )

    nodes = [
        control_node,
        robot_state_pub_node,
        relay_controller_spawner,
    ]

    return LaunchDescription(nodes)
