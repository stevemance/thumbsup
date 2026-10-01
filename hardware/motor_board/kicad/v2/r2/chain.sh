#!/bin/bash
# replay the r2 chain: r2/chain.sh [last stage]
D="$(dirname "$0")"
prev=proj
for s in r2_bridge r2_drive r2_u2east r2_bms r2_senr r2_main; do
  echo "== $s"
  "$D/stage.sh" $s $prev | grep -E "DRC err|FAIL|^    "
  prev=$s
  [ "$s" = "$1" ] && break
done
