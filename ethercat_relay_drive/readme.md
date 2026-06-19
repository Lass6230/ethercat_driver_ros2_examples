# Launch the stack
ros2 launch ethercat_relay_drive relay_drive.launch.py

# Close relay 1, leave relay 2 open
ros2 topic pub --once /relay_gpio_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['relays'], interface_values: [{interface_names: ['relay_1', 'relay_2'], values: [1.0, 0.0]}]}"

# Close both relays
ros2 topic pub --once /relay_gpio_controller/commands control_msgs/msg/DynamicInterfaceGroupValues "{interface_groups: ['relays'], interface_values: [{interface_names: ['relay_1', 'relay_2'], values: [1.0, 1.0]}]}"