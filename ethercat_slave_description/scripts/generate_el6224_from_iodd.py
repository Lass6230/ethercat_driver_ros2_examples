#!/usr/bin/env python3

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


EL6224_VENDOR_ID = "0x00000002"
EL6224_PRODUCT_ID = "0x18503052"


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def find_first(root: ET.Element, name: str):
    for elem in root.iter():
        if local_name(elem.tag) == name:
            return elem
    return None


def parse_iodd(iodd_path: Path):
    root = ET.parse(iodd_path).getroot()

    device_identity = find_first(root, "DeviceIdentity")
    if device_identity is None:
        raise RuntimeError("IODD parsing error: <DeviceIdentity> not found")

    device_id = int(device_identity.attrib.get("deviceId", "0"))
    vendor_id = int(device_identity.attrib.get("vendorId", "0"))

    comm_profile = find_first(root, "CommNetworkProfile")
    physical_layer = find_first(root, "PhysicalLayer")
    if comm_profile is None or physical_layer is None:
        raise RuntimeError("IODD parsing error: CommNetworkProfile/PhysicalLayer not found")

    iolink_revision = comm_profile.attrib.get("iolinkRevision", "V1.0")
    bitrate = physical_layer.attrib.get("bitrate", "")
    min_cycle_us = int(physical_layer.attrib.get("minCycleTime", "2300"))
    mseq_capability = int(physical_layer.attrib.get("mSequenceCapability", "33"))

    # Common COM speed enum mapping (used by many masters):
    # COM1 -> 0, COM2 -> 1, COM3 -> 2
    comspeed_map = {"COM1": 0, "COM2": 1, "COM3": 2}
    comspeed_reg = comspeed_map.get(bitrate.upper(), None) if bitrate else None

    # EL6224 uses 100 us steps for min cycle time register.
    min_cycle_reg = max(1, int(math.ceil(min_cycle_us / 100.0)))

    # Determine default ProcessDataSelect mode if available.
    process_data_select_default = 3
    for elem in root.iter():
        if local_name(elem.tag) == "Variable" and elem.attrib.get("id") == "V_ProcessDataSelect":
            process_data_select_default = int(elem.attrib.get("defaultValue", "3"))
            break

    # Determine process data input bit length.
    # Most sensors (including DT35) define 16-bit process data for all modes.
    pd_in_bits = None
    for elem in root.iter():
        if local_name(elem.tag) == "ProcessDataIn":
            bit_len = elem.attrib.get("bitLength")
            if bit_len:
                pd_in_bits = int(bit_len)
                break

    if pd_in_bits is None:
        pd_in_bits = 16
    pd_in_bytes = max(1, int(math.ceil(pd_in_bits / 8.0)))

    # Determine process data output bit length, if present.
    pd_out_bits = 0
    for elem in root.iter():
        if local_name(elem.tag) == "ProcessDataOut":
            bit_len = elem.attrib.get("bitLength")
            if bit_len:
                pd_out_bits = int(bit_len)
                break
    pd_out_bytes = int(math.ceil(pd_out_bits / 8.0)) if pd_out_bits > 0 else 0

    # V1.0 -> 16, V1.1 -> 17
    revision_reg = 17 if "1.1" in iolink_revision else 16

    return {
        "device_id": device_id,
        "vendor_id": vendor_id,
        "iolink_revision": iolink_revision,
        "bitrate": bitrate,
        "comspeed_reg": comspeed_reg,
        "revision_reg": revision_reg,
        "min_cycle_us": min_cycle_us,
        "min_cycle_reg": min_cycle_reg,
        "mseq_capability": mseq_capability,
        "pd_in_bits": pd_in_bits,
        "pd_in_bytes": pd_in_bytes,
        "pd_out_bits": pd_out_bits,
        "pd_out_bytes": pd_out_bytes,
        "process_data_select_default": process_data_select_default,
    }


def hex_index(base_port_index: int) -> str:
    return f"0x{base_port_index:04x}"


def hex_input_index(base_input_index: int) -> str:
    return f"0x{base_input_index:04x}"


def generate_sdo_block(info, port: int, mode: str, frame_capability_source: str) -> str:
    settings_index = 0x8000 + (port - 1) * 0x10

    if frame_capability_source == "comspeed":
        frame_capability_value = (
            info["comspeed_reg"] if info["comspeed_reg"] is not None else info["mseq_capability"]
        )
    else:
        frame_capability_value = info["mseq_capability"]

    lines = []
    lines.append("sdo:")
    lines.append(f"  # Auto-generated from IODD")
    lines.append(f"  #   Device ID:            {info['device_id']}")
    lines.append(f"  #   Vendor ID:            {info['vendor_id']}")
    lines.append(f"  #   IO-Link revision:     {info['iolink_revision']} (reg={info['revision_reg']})")
    lines.append(f"  #   Bitrate:              {info['bitrate'] or 'n/a'} (comspeed reg={info['comspeed_reg']})")
    lines.append(f"  #   mSequenceCapability:  {info['mseq_capability']}")
    lines.append(f"  #   Frame capability src: {frame_capability_source} (value={frame_capability_value})")
    lines.append(f"  #   Min cycle time:       {info['min_cycle_us']} us (reg={info['min_cycle_reg']})")
    lines.append(f"  #   PD in/out:            {info['pd_in_bits']} bit / {info['pd_out_bits']} bit")
    lines.append(f"  #   ProcessDataSelect:    default={info['process_data_select_default']}")

    if mode == "specific":
        lines.append(f"  - {{index: {hex_index(settings_index)}, sub_index: 0x04, type: uint32, value: {info['device_id']}}}   # Device ID")
        lines.append(f"  - {{index: {hex_index(settings_index)}, sub_index: 0x05, type: uint32, value: {info['vendor_id']}}}   # Vendor ID")
        lines.append(f"  - {{index: {hex_index(settings_index)}, sub_index: 0x20, type: uint8,  value: {info['revision_reg']}}}   # IO-Link Revision")
        lines.append(f"  - {{index: {hex_index(settings_index)}, sub_index: 0x21, type: uint8,  value: {frame_capability_value}}}   # Frame capability")
        lines.append(f"  - {{index: {hex_index(settings_index)}, sub_index: 0x22, type: uint8,  value: {info['min_cycle_reg']}}}   # Min cycle time")
        lines.append(f"  - {{index: {hex_index(settings_index)}, sub_index: 0x24, type: uint8,  value: {info['pd_in_bytes']}}}   # PD input length (bytes)")
        lines.append(f"  - {{index: {hex_index(settings_index)}, sub_index: 0x25, type: uint8,  value: {info['pd_out_bytes']}}}   # PD output length (bytes)")
        lines.append(f"  - {{index: {hex_index(settings_index)}, sub_index: 0x28, type: uint16, value: 2}}   # Master Control: IO-Link Specific")
    else:
        lines.append(f"  - {{index: {hex_index(settings_index)}, sub_index: 0x28, type: uint16, value: 1}}   # Master Control: IO-Link Auto")

    # Deactivate all other ports to avoid accidental parallel probing.
    for other_port in [1, 2, 3, 4]:
        if other_port == port:
            continue
        other_idx = 0x8000 + (other_port - 1) * 0x10
        lines.append(f"  - {{index: {hex_index(other_idx)}, sub_index: 0x28, type: uint16, value: 0}}   # Port {other_port} deactivated")

    return "\n".join(lines)


def generate_tpdo_hint(port: int, state_interface: str) -> str:
    in_index = 0x6000 + (port - 1) * 0x10
    return (
        "# Suggested TxPDO channel for selected port\n"
        "# (ensure your existing tpdo block has this mapping):\n"
        f"#   - {{index: {hex_input_index(in_index)}, sub_index: 0x01, type: uint16_be, state_interface: {state_interface}}}"
    )


def update_yaml_sdo_block(yaml_path: Path, new_sdo_block: str):
    content = yaml_path.read_text(encoding="utf-8")
    pattern = re.compile(r"(^sdo:\n)(.*?)(^tpdo:\n)", re.MULTILINE | re.DOTALL)
    replacement = new_sdo_block + "\n\n" + "tpdo:\n"
    new_content, count = pattern.subn(replacement, content, count=1)
    if count != 1:
        raise RuntimeError("Could not find a unique 'sdo:' ... 'tpdo:' block in target YAML")
    yaml_path.write_text(new_content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Generate EL6224 startup SDO settings from an IO-Link IODD XML file"
    )
    parser.add_argument("--iodd", required=True, help="Path to IODD XML file")
    parser.add_argument("--port", type=int, choices=[1, 2, 3, 4], default=1, help="EL6224 port number")
    parser.add_argument("--mode", choices=["specific", "auto"], default="specific", help="Master mode for selected port")
    parser.add_argument(
        "--frame-capability-source",
        choices=["comspeed", "mseq"],
        default="comspeed",
        help="How to derive 0x80n0:21. 'comspeed' uses bitrate COM1/2/3 -> 0/1/2; 'mseq' uses raw mSequenceCapability.",
    )
    parser.add_argument("--state-interface", default="distance", help="ROS state interface name used in tpdo hint")
    parser.add_argument("--update-yaml", help="If provided, replace sdo block in this EL6224 YAML file")

    args = parser.parse_args()

    iodd_path = Path(args.iodd)
    if not iodd_path.exists():
        print(f"IODD file not found: {iodd_path}", file=sys.stderr)
        return 2

    info = parse_iodd(iodd_path)
    sdo_block = generate_sdo_block(info, args.port, args.mode, args.frame_capability_source)

    print("# ---------------------------------------------------------------------------")
    print("# Auto-generated EL6224 configuration")
    print("# ---------------------------------------------------------------------------")
    print(f"vendor_id: {EL6224_VENDOR_ID}")
    print(f"product_id: {EL6224_PRODUCT_ID}")
    print("")
    print(sdo_block)
    print("")
    print(generate_tpdo_hint(args.port, args.state_interface))

    if args.update_yaml:
        yaml_path = Path(args.update_yaml)
        if not yaml_path.exists():
            print(f"Target YAML file not found: {yaml_path}", file=sys.stderr)
            return 3
        update_yaml_sdo_block(yaml_path, sdo_block)
        print(f"\nUpdated SDO block in: {yaml_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
