#!/usr/bin/env bash
set -euo pipefail

# Replays EL6224 startup writes extracted from a TwinCAT PREOP->FreeRun capture.
#
# Usage:
#   ./replay_el6224_twincat_startup.sh [slave_position]
#
# Example:
#   ./replay_el6224_twincat_startup.sh 2

POS="${1:-2}"

slave_state="$(ethercat slaves 2>/dev/null | awk -v p="$POS" '$1==p {print $3}')"
if [[ -z "$slave_state" ]]; then
	echo "Could not read EtherCAT slave state for position $POS. Is EtherCAT master running?" >&2
	exit 2
fi

if [[ "$slave_state" == "OP" ]]; then
	echo "Slave $POS is in OP. Stop ros2_control first, then run this script in PREOP/SAFEOP." >&2
	exit 3
fi

echo "[1/3] Apply PDO assignment sequence (0x1c12/0x1c13)"
ethercat download -p "$POS" --type uint8  0x1c12 0x00 0
ethercat download -p "$POS" --type uint8  0x1c13 0x00 0
ethercat download -p "$POS" --type uint16 0x1c13 0x01 0x1a05
ethercat download -p "$POS" --type uint16 0x1c13 0x02 0x1a04
ethercat download -p "$POS" --type uint16 0x1c13 0x03 0x1a00
ethercat download -p "$POS" --type uint16 0x1c13 0x04 0x1a01
ethercat download -p "$POS" --type uint8  0x1c13 0x00 4

echo "[2/3] Apply per-subindex startup settings (TwinCAT-equivalent)"
# TwinCAT uses complete-access (CA) writes with the exact hex payloads exported below.
# On this Linux setup, CA downloads sometimes fail with 0x06090031 (value too high).
# So we replicate the same effect using per-subindex writes, which should work equivalently
# since we set the exact same values TwinCAT uses.
# 
# TwinCAT CA payloads (from TwinCAT Startup XML export):
#   0x8000 CA write sub 1: 010063001a000000100117005000000000000300
#   0x8010 CA write sub 1: 190001006402000011010c00c300000000002300
#   0x8020 CA write sub 1: (all zeros)
#   0x8030 CA write sub 1: (all zeros)
#
# These correspond to the DT35 and E3AS IO-Link sensor startup configurations.
# TwinCAT applies these AFTER PDO assignment (0x1c12/0x1c13) is complete.

# Port 1 (0x8000): DT35
ethercat download -p "$POS" --type uint32 0x8000 0x04 6488065
ethercat download -p "$POS" --type uint32 0x8000 0x05 26
ethercat download -p "$POS" --type uint8  0x8000 0x20 16
ethercat download -p "$POS" --type uint8  0x8000 0x21 1
ethercat download -p "$POS" --type uint8  0x8000 0x22 23
ethercat download -p "$POS" --type uint8  0x8000 0x24 80
ethercat download -p "$POS" --type uint8  0x8000 0x25 0
ethercat download -p "$POS" --type uint16 0x8000 0x28 2

# Port 2 (0x8010): E3AS
ethercat download -p "$POS" --type uint32 0x8010 0x04 65561
ethercat download -p "$POS" --type uint32 0x8010 0x05 612
ethercat download -p "$POS" --type uint8  0x8010 0x20 17
ethercat download -p "$POS" --type uint8  0x8010 0x21 1
ethercat download -p "$POS" --type uint8  0x8010 0x22 12
ethercat download -p "$POS" --type uint8  0x8010 0x24 195
ethercat download -p "$POS" --type uint8  0x8010 0x25 0
ethercat download -p "$POS" --type uint16 0x8010 0x28 2

echo "[3/3] Read back key objects"
ethercat upload -p "$POS" 0x1c13 0x00 --type uint8
ethercat upload -p "$POS" 0x1c13 0x01 --type uint16
ethercat upload -p "$POS" 0x1c13 0x02 --type uint16
ethercat upload -p "$POS" 0x1c13 0x03 --type uint16
ethercat upload -p "$POS" 0x1c13 0x04 --type uint16
ethercat upload -p "$POS" 0x8000 0x28 --type uint16
ethercat upload -p "$POS" 0x8010 0x28 --type uint16

echo "Done."
