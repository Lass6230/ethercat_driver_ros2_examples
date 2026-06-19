#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# Key EL6224 objects relevant to IO-Link startup and process-data flow.
OBJECTS = [
    (0x1C13, 0x00, "uint8"),
    (0x1A00, 0x00, "uint8"),
    (0x1A01, 0x00, "uint8"),
    (0xA000, 0x01, "uint8"),
    (0xA000, 0x02, "uint8"),
    (0xA010, 0x01, "uint8"),
    (0xA010, 0x02, "uint8"),
    (0xF100, 0x01, "uint8"),
    (0xF100, 0x02, "uint8"),
    (0xF101, 0x0D, "uint8"),
    (0xF101, 0x10, "uint8"),
]


def add_port_objects(base_idx: int):
    return [
        (base_idx, 0x04, "uint32"),
        (base_idx, 0x05, "uint32"),
        (base_idx, 0x20, "uint8"),
        (base_idx, 0x21, "uint8"),
        (base_idx, 0x22, "uint8"),
        (base_idx, 0x24, "uint8"),
        (base_idx, 0x25, "uint8"),
        (base_idx, 0x28, "uint16"),
    ]


OBJECTS.extend(add_port_objects(0x8000))
OBJECTS.extend(add_port_objects(0x8010))
OBJECTS.extend(add_port_objects(0x9000))
OBJECTS.extend(add_port_objects(0x9010))


def key(idx: int, sub: int) -> str:
    return f"0x{idx:04X}:0x{sub:02X}"


def run_upload(position: int, idx: int, sub: int, data_type: str):
    cmd = [
        "ethercat",
        "upload",
        "-p",
        str(position),
        f"0x{idx:04x}",
        f"0x{sub:02x}",
        "--type",
        data_type,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()

    if proc.returncode != 0:
        return {
            "ok": False,
            "type": data_type,
            "raw": out,
            "error": err or f"exit={proc.returncode}",
        }

    # Typical output format: "0x00000201 513"
    m = re.search(r"^(0x[0-9a-fA-F]+)\s+(-?\d+)$", out)
    if m:
        return {
            "ok": True,
            "type": data_type,
            "hex": m.group(1).lower(),
            "dec": int(m.group(2)),
            "raw": out,
        }

    return {
        "ok": True,
        "type": data_type,
        "raw": out,
    }


def snapshot(position: int):
    data = {}
    for idx, sub, dtype in OBJECTS:
        data[key(idx, sub)] = run_upload(position, idx, sub, dtype)
    return data


def cmd_snapshot(args):
    snap = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "position": args.position,
        "values": snapshot(args.position),
    }
    out_path = Path(args.output)
    out_path.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote snapshot: {out_path}")


def cmd_diff(args):
    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))

    bvals = before.get("values", {})
    avals = after.get("values", {})
    keys = sorted(set(bvals.keys()) | set(avals.keys()))

    changed = []
    for k in keys:
        b = bvals.get(k)
        a = avals.get(k)
        if b != a:
            changed.append((k, b, a))

    if not changed:
        print("No differences.")
        return

    print(f"Differences: {len(changed)}")
    for k, b, a in changed:
        print(f"\n{k}")
        print(f"  before: {json.dumps(b, ensure_ascii=True)}")
        print(f"  after : {json.dumps(a, ensure_ascii=True)}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Snapshot and diff EL6224 CoE objects to diagnose startup behavior"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="Capture object values into JSON")
    p_snap.add_argument("--position", type=int, default=2, help="EtherCAT slave position")
    p_snap.add_argument("--output", required=True, help="Output JSON path")
    p_snap.set_defaults(func=cmd_snapshot)

    p_diff = sub.add_parser("diff", help="Show differences between two snapshot JSON files")
    p_diff.add_argument("--before", required=True, help="Before snapshot JSON path")
    p_diff.add_argument("--after", required=True, help="After snapshot JSON path")
    p_diff.set_defaults(func=cmd_diff)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
