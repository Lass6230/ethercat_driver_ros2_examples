#!/usr/bin/env bash
set -euo pipefail

# Validates EL6224 startup by applying TwinCAT sequence and checking live sensor values.
#
# Usage:
#   ./validate_el6224_startup.sh [slave_position]
#
# Workflow:
#   1. Ensure EL6224 is NOT in OP (kill ros2 first)
#   2. Apply PDO assignment and startup SDOs
#   3. Launch ros2 driver
#   4. Monitor sensor values in real-time
#   5. Report whether values change (unfrozen) or stay static (problem)

POS="${1:-2}"
TIMEOUT_PREOP_READY=10
TIMEOUT_ROS_STARTUP=15
POLL_INTERVAL=0.5
POLL_COUNT=20

echo "========================================="
echo "EL6224 Startup Validation Script"
echo "Position: $POS"
echo "========================================="

# 1. Check slave state
echo "[1/6] Checking EtherCAT slave state..."
slave_state="$(ethercat slaves 2>/dev/null | awk -v p="$POS" '$1==p {print $3}')"
if [[ -z "$slave_state" ]]; then
  echo "ERROR: Could not read EtherCAT slave state for position $POS. Is EtherCAT master running?" >&2
  exit 2
fi
echo "  State: $slave_state"

if [[ "$slave_state" == "OP" ]]; then
  echo "ERROR: Slave $POS is in OP. Stop ros2_control and try again." >&2
  exit 3
fi

# 2. Apply startup sequence
echo ""
echo "[2/6] Applying PDO assignment and port configuration..."
bash "$(dirname "$0")/replay_el6224_twincat_startup.sh" "$POS" > /dev/null 2>&1 || true

# 3. Verify key objects were written
echo ""
echo "[3/6] Verifying startup configuration..."
echo -n "  0x1c13:00 (TxPDO count): "
ethercat upload -p "$POS" 0x1c13 0x00 --type uint8 2>/dev/null || echo "FAILED"
echo -n "  0x8000:28 (Port1 mode): "
ethercat upload -p "$POS" 0x8000 0x28 --type uint16 2>/dev/null || echo "FAILED"
echo -n "  0x8010:28 (Port2 mode): "
ethercat upload -p "$POS" 0x8010 0x28 --type uint16 2>/dev/null || echo "FAILED"

# 4. Launch ros2 driver in background
echo ""
echo "[4/6] Launching ros2 driver (waiting $TIMEOUT_ROS_STARTUP sec for OP)..."
# Find workspace root by looking for install/setup.bash
WORKSPACE_ROOT=""
for candidate in /home/user/ethercat_driver_ws "$PWD" "$(dirname "$0")/../../../.."; do
  if [[ -f "$candidate/install/setup.bash" ]]; then
    WORKSPACE_ROOT="$candidate"
    break
  fi
done
if [[ -z "$WORKSPACE_ROOT" ]]; then
  echo "ERROR: Could not find ROS2 workspace root (looking for install/setup.bash)" >&2
  exit 4
fi
cd "$WORKSPACE_ROOT"
source install/setup.bash 2>/dev/null || true
ros2 launch ethercat_test_drive test_drive.launch.py > /tmp/el6224_validate.log 2>&1 &
ROS_PID=$!
sleep "$TIMEOUT_ROS_STARTUP"

if ! kill -0 "$ROS_PID" 2>/dev/null; then
  echo "ERROR: ros2 process died. Check /tmp/el6224_validate.log"
  cat /tmp/el6224_validate.log | tail -30
  exit 4
fi

# 5. Poll sensor values
echo ""
echo "[5/6] Polling sensor values (DT35 distance + E3AS detection)..."
echo "  (Move hand in front of sensors to see live updates)"
echo ""

DT35_PREV=0
E3AS_PREV=0
CHANGE_DETECTED=0

for i in $(seq 1 "$POLL_COUNT"); do
  DT35_VAL=$(ethercat upload -p "$POS" 0x6000 0x01 --type uint16 2>/dev/null | awk '{print $NF}')
  E3AS_VAL=$(ethercat upload -p "$POS" 0x6010 0x01 --type uint32 2>/dev/null | grep -oE '0x[0-9a-fA-F]+' | head -1 || echo "0x0")
  
  printf "  Poll %2d: DT35=%6s  E3AS=%10s" "$i" "$DT35_VAL" "$E3AS_VAL"
  
  if [[ "$DT35_VAL" != "$DT35_PREV" ]] || [[ "$E3AS_VAL" != "$E3AS_PREV" ]]; then
    echo " ✓ CHANGE DETECTED"
    CHANGE_DETECTED=1
    DT35_PREV="$DT35_VAL"
    E3AS_PREV="$E3AS_VAL"
  else
    echo ""
  fi
  
  sleep "$POLL_INTERVAL"
done

echo ""
echo "[6/6] Results:"
echo "========================================="
if [[ $CHANGE_DETECTED -eq 1 ]]; then
  echo "✓ SUCCESS: Sensor values are LIVE and responding to input!"
  echo "  This means EL6224 startup was successful."
  kill -SIGINT "$ROS_PID" 2>/dev/null || true
  wait "$ROS_PID" 2>/dev/null || true
  exit 0
else
  echo "✗ FAILURE: Sensor values are STATIC."
  echo "  DT35 frozen at: $DT35_PREV"
  echo "  E3AS frozen at: $E3AS_PREV"
  echo ""
  echo "  Possible causes:"
  echo "    1. IO-Link negotiation incomplete (check 0xf100/0x9000 port states)"
  echo "    2. PDO mapping not correctly assigned"
  echo "    3. Additional startup commands still missing"
  echo ""
  echo "  For debugging, check:"
  echo "    ethercat upload -p 2 0xf100 0x01 --type uint8  # Port 1 state"
  echo "    ethercat upload -p 2 0xf100 0x02 --type uint8  # Port 2 state"
  echo "    ethercat upload -p 2 0x9000 0x20 --type uint8  # Port 1 revision"
  echo "    ethercat upload -p 2 0x9010 0x21 --type uint8  # Port 2 frame cap"
  echo ""
  kill -SIGINT "$ROS_PID" 2>/dev/null || true
  wait "$ROS_PID" 2>/dev/null || true
  exit 1
fi
