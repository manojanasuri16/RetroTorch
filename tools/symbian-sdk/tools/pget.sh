#!/bin/sh
# Parallel ranged download: pget.sh URL OUTFILE [PARTS]
set -e
URL=$1; OUT=$2; N=${3:-16}
REAL=$(curl -sIL -o /dev/null -w '%{url_effective}' "$URL")
LEN=$(curl -sIL "$REAL" | grep -i '^content-length' | tail -1 | tr -dc 0-9)
[ -n "$LEN" ] || { echo "no length for $URL"; exit 1; }
PART=$(( (LEN + N - 1) / N ))
i=0; pids=""
while [ $i -lt $N ]; do
  s=$(( i * PART )); e=$(( s + PART - 1 )); [ $e -ge $LEN ] && e=$((LEN - 1))
  ( until curl -sfL --retry 20 -r $s-$e -o "$OUT.part$i" "$REAL" && [ $(stat -c %s "$OUT.part$i") -eq $((e - s + 1)) ]; do sleep 3; done ) &
  pids="$pids $!"; i=$((i + 1))
done
wait $pids
i=0; : > "$OUT"
while [ $i -lt $N ]; do cat "$OUT.part$i" >> "$OUT"; rm "$OUT.part$i"; i=$((i + 1)); done
echo "done $OUT $(stat -c %s "$OUT") of $LEN"
