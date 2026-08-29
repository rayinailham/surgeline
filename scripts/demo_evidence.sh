#!/usr/bin/env bash
# P14 — segmen "bukti" untuk video: query ke antrean, ditampilkan pelan-pelan.
# Tidak ada prompt shell, tidak ada jalur mesin, tidak ada kredensial di layar.
set -euo pipefail

RUN=${RUN:-p14-demo}
DB="data/${RUN}/queue.db"
PAUSE=${PAUSE:-2.2}
SQL=(sqlite3 -init /dev/null -noheader -list)
PROJECT=${PROJECT:-$(cd "$(dirname "$0")/.." && pwd)}

# WINDOW=1 -> buka sendiri di jendela terminal bersih (font besar, tanpa transparansi),
# supaya bisa direkam sebagai satu window class `foot`.
if [ "${WINDOW:-0}" = "1" ]; then
  exec foot -o "main.font=JetBrainsMono Nerd Font:size=19" -o "colors.alpha=1.0" \
    -o "main.pad=28x22 center" -o "main.initial-window-size-chars=110x30" \
    -e env WINDOW=0 RUN="$RUN" PAUSE="$PAUSE" bash "$PROJECT/scripts/demo_evidence.sh"
fi

cd "$PROJECT"

say() { printf '\n\033[1;36m$ %s\033[0m\n' "$1"; sleep 1.0; }
out() { printf '%s\n' "$1"; }

clear
printf '\033[1;37mBukti diambil dari database antrean, bukan dari tampilan layar.\033[0m\n'
sleep 1.5

say "sqlite3 queue.db \"SELECT status, COUNT(*) FROM jobs GROUP BY status\""
"${SQL[@]}" "$DB" "SELECT status||'  '||COUNT(*) FROM jobs GROUP BY status ORDER BY status"
sleep "$PAUSE"

say "sqlite3 queue.db \"SELECT COUNT(*) FROM jobs WHERE status IN ('pending','claimed')\"  -- sisa"
out "$("${SQL[@]}" "$DB" "SELECT COUNT(*) FROM jobs WHERE status IN ('pending','claimed')")"
sleep "$PAUSE"

say "sqlite3 queue.db \"SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs\"  -- data ganda"
out "$("${SQL[@]}" "$DB" "SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs")"
sleep "$PAUSE"

say "sqlite3 queue.db \"SELECT COUNT(*)-COUNT(DISTINCT confirmation) FROM jobs WHERE status='ok'\"  -- nomor konfirmasi ganda"
out "$("${SQL[@]}" "$DB" "SELECT COUNT(*)-COUNT(DISTINCT confirmation) FROM jobs WHERE status='ok'")"
sleep "$PAUSE"

say "sqlite3 queue.db \"SELECT COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation='')\"  -- berhasil tanpa nomor"
out "$("${SQL[@]}" "$DB" "SELECT COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation='')")"
sleep "$PAUSE"

say "sqlite3 queue.db \"SELECT external_ref, confirmation FROM jobs WHERE status='ok' LIMIT 4\""
"${SQL[@]}" "$DB" "SELECT external_ref||'   '||confirmation FROM jobs WHERE status='ok' ORDER BY rowid LIMIT 4"
sleep 3.0
