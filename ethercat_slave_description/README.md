# ethercat_slave_description
Collection of EtherCAT module example configurations for the `ethercat_driver`.

## See also
- [EL6224 IO-Link setup, configuration, ROS 2 usage, and troubleshooting](../../../../README_EL6224_IO_LINK.md)

## Automatic IODD-driven EL6224 setup
You can auto-generate EL6224 port startup SDO settings from an IODD XML file:

```bash
ros2 run ethercat_slave_description generate_el6224_from_iodd.py \
  --iodd /path/to/SICK-DT35-DL35-20200224-IODD1.1.xml \
  --port 1 \
  --mode specific \
  --frame-capability-source comspeed \
  --update-yaml /path/to/beckhoff_el6224.yaml
```

Notes:
- `--mode specific` writes Device ID / Vendor ID / revision / m-sequence / PD lengths from the IODD.
- `--mode auto` only sets selected port to IO-Link Auto mode.
- `--frame-capability-source comspeed` maps IODD bitrate (`COM1/COM2/COM3`) to `0/1/2` for `0x80n0:21`.
- `--frame-capability-source mseq` writes raw IODD `mSequenceCapability` to `0x80n0:21`.
- The script deactivates other EL6224 ports by default to avoid parallel probing.
- It prints a suggested TxPDO channel mapping for the selected port (`0x6000/0x6010/0x6020/0x6030 :01`).

## Decode EL6224 process data
Use the decoder script to translate raw process data words into readable sensor values:

```bash
python3 src/ethercat_driver_ros2_examples/ethercat_slave_description/scripts/decode_el6224_values.py --position 2
```

Watch mode:

```bash
python3 src/ethercat_driver_ros2_examples/ethercat_slave_description/scripts/decode_el6224_values.py --position 2 --watch --interval 0.3
```

## Modules using `GenericEcSlave`
The list of available example EtherCAT module configurations for the `GenericEcSlave` Hardware Interface plugin.
### Beckhoff
- **Beckhoff_EL1008**: EtherCAT Terminal, 8-channel digital input, 24 V DC, 3 ms.
- **Beckhoff_EL1018**: EtherCAT Terminal, 8-channel digital input, 24 V DC, 10 us.
- **Beckhoff_EL2008**: EtherCAT Terminal, 8-channel digital output, 24 V DC, 0.5 A.
- **Beckhoff_EL2088**: EtherCAT Terminal, 8-channel digital output, 24 V DC, 0.5 A, ground switching.
- **Beckhoff_EL2124**: EtherCAT Terminal, 4-channel digital output, 5 V DC, 20 mA.
- **Beckhoff_EL3102**: EtherCAT Terminal, 2-channel analog input, voltage, ±10 V, 16 bit, differential.
- **Beckhoff_EL3104**: EtherCAT Terminal, 4-channel analog input, voltage, ±10 V, 16 bit, differential.
- **Beckhoff_EL4132**: EtherCAT Terminal, 2-channel analog output, voltage, ±10 V, 16 bit.
- **Beckhoff_EL4134**: EtherCAT Terminal, 4-channel analog output, voltage, ±10 V, 16 bit.
- **Beckhoff_EL5101**: EtherCAT Terminal, 1-channel encoder interface, incremental, 5 V DC (DIFF RS422, TTL), 1 MHz.

### ATI
- **ATI_FTSensor**: ATI EtherCAT F/T Sensor

### Advantech
- **AMAX-5051**: Digital Input Module, 8-channel digital input, 24 V DC, 4 ms.
- **AMAX-5056**: Sink-type Digital Output Module, 8-channel digital output, 24 V DC, 0.3 A.

### Omron
- **Omron_NX_ECC201_NX_ID5442**: Omron EtherCAT Coupler NX_ECC201 with Input module NX_ID5442.
- **Omron_NX_ECC201_NX_OD5256**: Omron EtherCAT Coupler NX_ECC201 with Output module NX_OD5256.

## Motor drive modules using `EcCiA402Drive`
The list of available example EtherCAT motor drive module configurations for the `EcCiA402Drive` Hardware Interface plugin.
### Maxon
- **EPOS3**: EPOS3 70/10 EtherCAT, digital positioning controller, 10 A, 11 - 70 VDC
  - Plugin : `EcCiA402Drive`

### Schneider Electric
- **Schneider_ATV320**: Schneider Electric Variable frequency drive. Coupled with VW3A3601 communication card.
  - Plugin : `EcCiA402Drive`

### Elmo
- **Elmo Gold**: Elmo Gold servo drive.
  - Plugin : `EcCiA402Drive`

### Technosoft
- **Technosoft IPOS 3604**: Technosoft IPOS 3064 motor drive.
  - Plugin : `EcCiA402Drive`

### Synapticon
- **Synapticon SOMANET Circulo 9**: Synapticon SOMANET Circulo 9 Safe Motion servo drive.
  - Plugin : `EcCiA402Drive`
