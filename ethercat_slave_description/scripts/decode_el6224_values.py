#!/usr/bin/env python3

import argparse
import re
import subprocess
import sys
import time


def run_ethercat_upload(position: int, index: int, subindex: int, data_type: str) -> tuple[int, int]:
    cmd = [
        "ethercat",
        "upload",
        "-p",
        str(position),
        f"0x{index:04x}",
        f"0x{subindex:02x}",
        "--type",
        data_type,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "ethercat upload failed")

    out = proc.stdout.strip()
    match = re.search(r"0x([0-9a-fA-F]+)\s+(-?\d+)", out)
    if not match:
        raise RuntimeError(f"Unexpected ethercat output: {out}")

    value_hex = int(match.group(1), 16)
    value_dec = int(match.group(2))
    return value_hex, value_dec


def int16_from_u16(u16: int) -> int:
    return u16 - 0x10000 if (u16 & 0x8000) else u16


def decode_dt35_word(raw_u16: int, scale: float, offset: float) -> dict:
    # Working mapping in this workspace uses DT35 distance as UINT16 big-endian.
    distance_raw = ((raw_u16 & 0x00FF) << 8) | ((raw_u16 & 0xFF00) >> 8)
    calibrated_distance = distance_raw * scale + offset

    return {
        "raw_u16": raw_u16,
        "distance_raw": distance_raw,
        "calibrated_distance": calibrated_distance,
    }


def decode_e3as_word(raw_u32: int, scale: float, offset: float) -> dict:
    # Raw upload is returned as a 32-bit value while working YAML decodes by byte offset:
    # byte0..1 = UINT16_BE detection, byte2 = intensity, byte3 = flags.
    b0 = raw_u32 & 0xFF
    b1 = (raw_u32 >> 8) & 0xFF
    b2 = (raw_u32 >> 16) & 0xFF
    b3 = (raw_u32 >> 24) & 0xFF

    detection_value = (b0 << 8) | b1
    light_intensity = b2
    flags = b3
    calibrated_detection = detection_value * scale + offset

    return {
        "raw_u32": raw_u32,
        "detection_value": detection_value,
        "calibrated_detection": calibrated_detection,
        "light_intensity": light_intensity,
        "error": bool(flags & 0x80),
        "warning": bool(flags & 0x40),
        "error_low_light": bool(flags & 0x10),
        "instability_alarm": bool(flags & 0x04),
        "control_output2": bool(flags & 0x02),
        "control_output1": bool(flags & 0x01),
    }


def read_once(position: int, dt35_scale: float, dt35_offset: float, e3as_scale: float, e3as_offset: float):
    dt35_hex, dt35_dec = run_ethercat_upload(position, 0x6000, 0x01, "uint16")
    e3as_hex, e3as_dec = run_ethercat_upload(position, 0x6010, 0x01, "uint32")
    p1_hex, p1_dec = run_ethercat_upload(position, 0xF100, 0x01, "uint8")
    p2_hex, p2_dec = run_ethercat_upload(position, 0xF100, 0x02, "uint8")

    dt35 = decode_dt35_word(dt35_dec, dt35_scale, dt35_offset)
    e3as = decode_e3as_word(e3as_dec, e3as_scale, e3as_offset)

    print("EL6224 decoded values")
    print("====================")
    print(f"Port states: ch1={p1_dec} (0x{p1_hex:02X}), ch2={p2_dec} (0x{p2_hex:02X})")
    print("")
    print("DT35 (port 1)")
    print(f"  Raw 0x6000:01: 0x{dt35_hex:04X} ({dt35_dec})")
    print(f"  Distance value (UINT16_BE): {dt35['distance_raw']}")
    print(f"  Calibrated distance: {dt35['calibrated_distance']:g} mm")
    print("")
    print("E3AS (port 2)")
    print(f"  Raw 0x6010:01: 0x{e3as_hex:08X} ({e3as_dec})")
    print(f"  Detection value (INT16): {e3as['detection_value']}")
    print(f"  Detection value (calibrated): {e3as['calibrated_detection']:g}")
    print(f"  Light intensity (UINT8): {e3as['light_intensity']}")
    print(f"  Flags: error={int(e3as['error'])}, warning={int(e3as['warning'])}, "
          f"error_low_light={int(e3as['error_low_light'])}, instability_alarm={int(e3as['instability_alarm'])}, "
          f"out2={int(e3as['control_output2'])}, out1={int(e3as['control_output1'])}")


def main():
    parser = argparse.ArgumentParser(description="Decode EL6224 process data values into meaningful fields")
    parser.add_argument("--position", type=int, default=2, help="EtherCAT slave position (default: 2)")
    parser.add_argument("--watch", action="store_true", help="Poll continuously")
    parser.add_argument("--interval", type=float, default=0.3, help="Watch polling period in seconds")
    parser.add_argument(
        "--dt35-scale",
        type=float,
        default=1.0,
        help="Multiply DT35 distance by this factor before reporting calibrated values",
    )
    parser.add_argument(
        "--dt35-offset",
        type=float,
        default=0.0,
        help="Add this offset to the DT35 calibrated value after scaling",
    )
    parser.add_argument(
        "--e3as-scale",
        type=float,
        default=1.0,
        help="Multiply E3AS detection_value (UINT16_BE) by this factor before reporting calibrated values",
    )
    parser.add_argument(
        "--e3as-offset",
        type=float,
        default=0.0,
        help="Add this offset to the E3AS calibrated detection value after scaling",
    )
    args = parser.parse_args()

    if args.watch:
        try:
            while True:
                print("\n" + "-" * 40)
                read_once(args.position, args.dt35_scale, args.dt35_offset, args.e3as_scale, args.e3as_offset)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0

    try:
        read_once(args.position, args.dt35_scale, args.dt35_offset, args.e3as_scale, args.e3as_offset)
        return 0
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
