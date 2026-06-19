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
test_drive.launch.py
====================
Launches the ros2_control stack for the full EtherCAT I/O test bus.

Bus topology
------------
  Pos 0:  EK1100  EtherCAT Coupler        (passive)
  Pos 1:  EL2002  2-ch Digital Output
  Pos 2:  EL6224  IO-Link Master  (Ch.1 = SICK DT35-B15551)
  Pos 3:  EL1008  8-ch Digital Input
  Pos 4:  EL2622  2-ch Relay Output
  Pos 5:  EL6751  CANopen Master           (not used)

Prerequisites
-------------
  sudo /etc/init.d/ethercat start
  ethercat slaves

Launch
------
  ros2 launch ethercat_test_drive test_drive.launch.py

Control relays (EL2622)
-----------------------
  ros2 topic pub --once /gpio_controller/commands \\
      control_msgs/msg/DynamicInterfaceGroupValues \\
      "{interface_groups: ['relays'], \\
        interface_values: [{interface_names: ['relay_1', 'relay_2'], \\
                            values: [1.0, 0.0]}]}"

Control digital outputs (EL2002)
--------------------------------
  ros2 topic pub --once /gpio_controller/commands \\
      control_msgs/msg/DynamicInterfaceGroupValues \\
      "{interface_groups: ['digital_outputs'], \\
        interface_values: [{interface_names: ['d_output.1', 'd_output.2'], \\
                            values: [1.0, 1.0]}]}"

Read all states (digital inputs + IO-Link sensor)
--------------------------------------------------
  ros2 topic echo /gpio_controller/gpio_states

List active interfaces
----------------------
  ros2 control list_hardware_interfaces
  ros2 control list_controllers
"""

from launch import LaunchDescription
from launch.substitutions import Command, FindExecutable, PathJoinSubstitution

from launch_ros.actions import Node
from launch_ros.descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    # Get URDF via xacro
    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            PathJoinSubstitution(
                [
                    FindPackageShare("ethercat_test_drive"),
                    "description/config",
                    "test_drive.config.xacro",
                ]
            ),
        ]
    )
    robot_description = {
        "robot_description": ParameterValue(robot_description_content, value_type=str)
    }

    robot_controllers = PathJoinSubstitution(
        [
            FindPackageShare("ethercat_test_drive"),
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

    # Spawn the unified GPIO controller (handles all 4 modules)
    gpio_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["gpio_controller", "-c", "/controller_manager"],
    )

    nodes = [
        control_node,
        robot_state_pub_node,
        gpio_controller_spawner,
    ]

    return LaunchDescription(nodes)
