# ethercat_test_drive

Example ROS 2 package for testing a mixed Beckhoff EtherCAT I/O bus via
`ros2_control` GPIO controllers.

## Bus Topology

| Pos | Module | Description | Interfaces |
|-----|--------|-------------|------------|
| 0 | EK1100 | EtherCAT Coupler | passive — no config |
| 1 | EL2622 | 2-ch Relay Output (NO, 230 V AC / 30 V DC) | **command:** `relay_1`, `relay_2` |
| 2 | EL1002 | 2-ch Digital Input (24 V DC, 3 ms) | **state:** `d_input.1`, `d_input.2` |
| 3 | EL2002 | 2-ch Digital Output (24 V DC, 0.5 A) | **command:** `d_output.1`, `d_output.2` |
| 4 | EL6224 | 4-port IO-Link Master (Ch.1 = SICK DT35) | **state:** `distance`, `state_ch1`–`4`, `device_diag`, `device_state` |
| 5 | EL6751 | CANopen Master | not used in this demo |

## Prerequisites

```bash
# Start the IgH EtherCAT Master
sudo /etc/init.d/ethercat start

# Verify slaves
ethercat slaves
#   0  0:0  PREOP  +  EK1100 EtherCAT-Koppler (2A E-Bus)
#   1  0:1  PREOP  +  EL2622 2K. Relaisausgang …
#   2  0:2  PREOP  +  EL1002 2K. Dig. Eingang 24V …
#   3  0:3  PREOP  +  EL2002 2K. Dig. Ausgang 24V …
#   4  0:4  PREOP  +  EL6224 4-port IO-Link Master …
#   5  0:5  PREOP  +  EL6751 CANopen-Master-Klemme
```

## Build

```bash
cd ~/ethercat_driver_ws
source install/setup.bash
colcon build --packages-select ethercat_test_drive
source install/setup.bash
```

## Launch

```bash
ros2 launch ethercat_test_drive test_drive.launch.py
```

## Safety (TwinSAFE/FSoE) Demo

This package also provides a dedicated safety-only launch for:

- EL6900 TwinSAFE Logic (safety master)
- EL1904 TwinSAFE input (safety slave)
- EL2904 TwinSAFE output (safety slave)

Expected bus positions for this demo:

- `7` -> EL6900
- `8` -> EL1904
- `9` -> EL2904

### Launch safety demo

```bash
ros2 launch ethercat_test_drive safety_test_drive.launch.py
```

### Verify transitions

```bash
# Watch EtherCAT state transitions while launch is running
ethercat slaves

# Inspect PDO mappings used by the safety YAMLs
ethercat pdos -p 7
ethercat pdos -p 8
ethercat pdos -p 9
```

### Safety notes

- The launch sets EtherCAT `transfer_config` to `config/el6900_el1904_el2904_fsoe.yaml`.
- The transfer sizes in this demo are all `6` bytes, matching the FSoE command + CRC + connection ID frames.
- Persistent `PREOP` after launch usually indicates a TwinSAFE project/configuration mismatch (or not activated logic), not a ROS launch issue.

### Control the safety group from ROS

The `gpio_safety_controller` exposes a single `safety_states_control` command interface that
writes to EL6900 register `0xF200:01` (the TwinSAFE group control word).
The bit layout follows the order of group port inputs defined in the TwinSAFE project:

| Bit | Value | TwinCAT variable      | Function                  |
|-----|-------|-----------------------|---------------------------|
| 0   | 1     | GroupPort_ErrAck      | Error acknowledgement      |
| 1   | 2     | GroupPort_RunStop     | Run / Stop                 |

Restart is handled by TwinSAFE Standard Input 1 (mapped in this setup via
RxPDO `0x17f0 -> 0x6000:01`) exposed as `restart_standard_input`.

```bash
# Start safety group (Run=1, ErrAck=0)
ros2 topic pub --once /gpio_safety_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['el6900_gpio'],
      interface_values: [{interface_names: ['safety_states_control'],
                          values: [2.0]}]}"

# Acknowledge error while running (Run=1, ErrAck=1)
ros2 topic pub --once /gpio_safety_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['el6900_gpio'],
      interface_values: [{interface_names: ['safety_states_control'],
                          values: [3.0]}]}"

# Pulse Restart input (0 -> 1 -> 0) for FBEstop1.Restart
ros2 topic pub --once /gpio_safety_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['el6900_gpio'],
      interface_values: [{interface_names: ['restart_standard_input'],
                          values: [1.0]}]}"

ros2 topic pub --once /gpio_safety_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['el6900_gpio'],
      interface_values: [{interface_names: ['restart_standard_input'],
                          values: [0.0]}]}"

# Stop safety group (all group ports LOW)
ros2 topic pub --once /gpio_safety_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['el6900_gpio'],
      interface_values: [{interface_names: ['safety_states_control'],
                          values: [0.0]}]}"
```

Read back EL6900 status:

```bash
ros2 topic echo /gpio_safety_controller/gpio_states
```

The same topic also includes EL1904 input channels as state interfaces:
- `estop_ch1`
- `estop_ch2`
- `estop_ch3`
- `estop_ch4`

To monitor E-stop transitions while pressing/releasing the button, stream:

```bash
ros2 topic echo /gpio_safety_controller/gpio_states
```

For this EL6900 setup (as shown in TwinCAT CoE Online), `safety_project_state=1`
indicates RUN. Do not assume a generic numeric mapping across projects/firmware;
use the TwinCAT label for object `0xF100:01` as the source of truth.

### TwinCAT variable → PDO mapping reference

| TwinCAT variable     | TwinCAT assignment                        | PDO index  | ROS interface                  |
|----------------------|-------------------------------------------|------------|-------------------------------|
| GroupPort_RunStop    | Run.In (TwinSafeGroup1)                   | 0xF200:01 bit1 | `safety_states_control` bit 1 |
| GroupPort_ErrAck     | ErrorAcknowledgement.In (TwinSafeGroup1)  | 0xF200:01 bit0 | `safety_states_control` bit 0 |
| Restart              | FBEstop1.Restart from Standard Input 1    | 0x17f0 -> 0x6000:01 | `restart_standard_input` |
| Estop1_1             | EL1904 InputChannel1                      | 0x6001:01  | TwinSAFE internal logic input |
| Estop1_2             | EL1904 InputChannel2                      | 0x6001:02  | TwinSAFE internal logic input |
| EstopOut             | EL2904 OutputChannel1 (driven by FBAnd1)  | 0x7001:01  | EL2904 output (FSoE driven)   |

## Usage

All modules are managed by a single `gpio_controller`
(`gpio_controllers/GpioCommandController`).

### Control relays (EL2622)

```bash
# Close relay 1, leave relay 2 open
ros2 topic pub --once /gpio_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['relays'],
      interface_values: [{interface_names: ['relay_1', 'relay_2'],
                          values: [1.0, 0.0]}]}"

# Close both relays
ros2 topic pub --once /gpio_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['relays'],
      interface_values: [{interface_names: ['relay_1', 'relay_2'],
                          values: [1.0, 1.0]}]}"

# Open both relays
ros2 topic pub --once /gpio_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['relays'],
      interface_values: [{interface_names: ['relay_1', 'relay_2'],
                          values: [0.0, 0.0]}]}"
```

### Control digital outputs (EL2002)

```bash
# Turn on output 1, turn off output 2
ros2 topic pub --once /gpio_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['digital_outputs'],
      interface_values: [{interface_names: ['d_output.1', 'd_output.2'],
                          values: [1.0, 0.0]}]}"
```

### Control relays AND digital outputs simultaneously

```bash
ros2 topic pub --once /gpio_controller/commands \
    control_msgs/msg/DynamicInterfaceGroupValues \
    "{interface_groups: ['relays', 'digital_outputs'],
      interface_values: [
        {interface_names: ['relay_1', 'relay_2'], values: [1.0, 1.0]},
        {interface_names: ['d_output.1', 'd_output.2'], values: [1.0, 0.0]}
      ]}"
```

### Read digital inputs + IO-Link sensor states

```bash
# Stream all state interfaces (digital inputs + IO-Link sensor)
ros2 topic echo /gpio_controller/gpio_states
```

### Inspect interfaces

```bash
ros2 control list_hardware_interfaces
ros2 control list_controllers
```

## IO-Link Sensor — SICK DT35-B15551

The `distance` state interface reports the raw 16-bit process data from the
DT35 laser distance sensor connected to EL6224 port 1.

| IO-Link Index | Parameter | Default |
|---------------|-----------|---------|
| 83 | ProcessDataSelect (mode) | 3 = raw 16-bit distance |
| 105 | ProcessDataResolution | 1 = mm |

**Note:** The EL6224 TxPDO 0x1a00 (IO-Link Ch.1 data) is populated only after
the EL6224 transitions to OP and IO-Link negotiation completes. If the
`distance` value reads 0 after launch, verify with `ethercat pdos -p 4` that
the mapping `0x6000:01 uint16` is present.

## Files

| File | Purpose |
|------|---------|
| `description/ros2_control/test_drive.ros2_control.xacro` | GPIO + ec_module definitions for all 4 modules |
| `description/config/test_drive.config.xacro` | Top-level robot description |
| `config/controllers.yaml` | GpioCommandController configuration |
| `launch/test_drive.launch.py` | ros2_control launch file |

### Safety files

| File | Purpose |
|------|---------|
| `description/ros2_control/safety_test_drive.ros2_control.xacro` | Safety ec_module declarations (EL6900/EL1904/EL2904) |
| `description/config/safety_test_drive.config.xacro` | Top-level safety robot description |
| `config/safety_controllers.yaml` | Minimal controller manager params for safety launch |
| `config/el6900_el1904_el2904_fsoe.yaml` | FSoE transfer net definition |
| `config/beckhoff_el6900.yaml` | EL6900 PDO/SM mapping |
| `config/beckhoff_el1904.yaml` | EL1904 PDO/SM mapping |
| `config/beckhoff_el2904.yaml` | EL2904 PDO/SM mapping |
| `launch/safety_test_drive.launch.py` | Safety-only ros2_control launch |

## Slave Description YAMLs

Located in `ethercat_slave_description/config/beckhoff/`:
- `beckhoff_el2622.yaml` — 2-ch relay output
- `beckhoff_el1002.yaml` — 2-ch digital input
- `beckhoff_el2002.yaml` — 2-ch digital output
- `beckhoff_el6224.yaml` — IO-Link master (with DT35 Ch.1 mapping)
