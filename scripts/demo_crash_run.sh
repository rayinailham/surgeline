#!/usr/bin/env bash
# P14 — orkestrasi demo untuk video: run 50.000 yang sengaja dimatikan paksa 2×.
#
# Dipakai bersama scripts/demo_dashboard.sh: skrip ini yang bekerja di latar,
# dashboard yang direkam. Semua angka di video berasal dari run ini, bukan naskah.
#
#   RUN=p14-demo WARMUP=36000 bash scripts/demo_crash_run.sh
#
# Alur: jalankan N worker -> tunggu sampai WARMUP job terminal (di luar rekaman)
#       -> tandai siap (file .ready) -> kill -9 pada detik KILL1 & KILL2 setelah
#       siap -> nyalakan lagi tiap kali -> jalan sampai antrean habis.
set -euo pipefail

RUN=${RUN:-p14-demo}
WORKERS=${WORKERS:-8}
BASE_URL=${BASE_URL:-http://127.0.0.1:8110}
WARMUP=${WARMUP:-36000}          # job terminal sebelum rekaman dimulai
KILL1=${KILL1:-150}              # detik setelah .ready
KILL2=${KILL2:-540}
DOWNTIME=${DOWNTIME:-25}         # berapa lama sistem dibiarkan mati
DB="data/${RUN}/queue.db"
LOG="data/${RUN}-demo.log"
READY="data/${RUN}.ready"
UV="uv run --no-sync"

# log ke stderr + berkas, supaya $(kill_workers) hanya menangkap angkanya
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG" >&2; }

terminal_count() {
  sqlite3 "$DB" "SELECT COUNT(*) FROM jobs WHERE status IN ('ok','failed','dead')"
}
ok_count() { sqlite3 "$DB" "SELECT COUNT(*) FROM jobs WHERE status='ok'"; }
left_count() {
  sqlite3 "$DB" "SELECT COUNT(*) FROM jobs WHERE status IN ('pending','claimed')"
}

start_workers() {
  $UV python -m src.run --run "$RUN" --workers "$WORKERS" \
    --base-url "$BASE_URL" >>"$LOG" 2>&1 &
  WORKER_PARENT=$!
  log "worker dinyalakan (pid induk $WORKER_PARENT, N=$WORKERS)"
}

kill_workers() {   # kill -9 hanya proses worker run ini; pola sengaja spesifik
  local before; before=$(ok_count)
  log "KILL -9 saat berhasil=$before"
  pkill -9 -f "src\.worker --run ${RUN} " || true
  kill -9 "$WORKER_PARENT" 2>/dev/null || true
  wait "$WORKER_PARENT" 2>/dev/null || true
  echo "$before"
}

test -f "$DB" || { echo "antrean $DB tidak ada; jalankan make load dulu" >&2; exit 1; }
rm -f "$READY"
: >"$LOG"

log "mulai: total=$(sqlite3 "$DB" 'SELECT COUNT(*) FROM jobs') sisa=$(left_count)"
start_workers

while [ "$(terminal_count)" -lt "$WARMUP" ]; do
  sleep 5
  if ! kill -0 "$WORKER_PARENT" 2>/dev/null; then
    log "worker berhenti sendiri saat pemanasan"; break
  fi
done
log "pemanasan selesai: terminal=$(terminal_count) — rekaman boleh mulai"
: >"$READY"

sleep "$KILL1"
OK1=$(kill_workers)
sleep "$DOWNTIME"
start_workers

sleep "$KILL2"
OK2=$(kill_workers)
sleep "$DOWNTIME"
start_workers

wait "$WORKER_PARENT" 2>/dev/null || true
while [ "$(left_count)" -gt 0 ]; do
  log "sisa $(left_count) job (job yatim menunggu lease) — nyalakan lagi"
  start_workers
  wait "$WORKER_PARENT" 2>/dev/null || true
done

log "SELESAI berhasil=$(ok_count) sisa=$(left_count)"
log "berhasil saat kill-1=$OK1 · kill-2=$OK2 · akhir=$(ok_count)"
