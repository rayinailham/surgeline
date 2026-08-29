#!/usr/bin/env bash
# P14 — rakit assets/demo.mp4 dari potongan mentah hasil scripts/record-segment.sh.
#
# Semua angka pada kartu penutup dibaca dari antrean hasil run (bukan diketik),
# supaya klaim di video selalu bisa ditelusuri ke database.
#
#   RUN=p14-demo bash scripts/make_demo_video.sh
#
# Masukan  : data/rec/dashboard.mkv (dashboard, panjang) · data/rec/bukti.mkv (terminal)
# Keluaran : assets/demo.mp4 (1920x1080, H.264, yuv420p, tanpa audio)
#            assets/{before,crash,after}.png
set -euo pipefail

RUN=${RUN:-p14-demo}
DB=${DB:-data/${RUN}/queue.db}
REC=${REC:-data/rec}
WORK=${WORK:-data/rec/work}
OUT=${OUT:-assets/demo.mp4}
FONT=${FONT:-/usr/share/fonts/TTF/DejaVuSans.ttf}
FONT_BOLD=${FONT_BOLD:-/usr/share/fonts/TTF/DejaVuSans-Bold.ttf}
BG=${BG:-#0b1220}
DASH_TARGET_SECONDS=${DASH_TARGET_SECONDS:-78}   # panjang segmen dashboard setelah dipercepat

mkdir -p "$WORK" "$(dirname "$OUT")"

q() { sqlite3 "$DB" "$1"; }

TOTAL=$(q "SELECT COUNT(*) FROM jobs")
OK=$(q "SELECT COUNT(*) FROM jobs WHERE status='ok'")
FAILED=$(q "SELECT COUNT(*) FROM jobs WHERE status='failed'")
DEAD=$(q "SELECT COUNT(*) FROM jobs WHERE status='dead'")
LEFT=$(q "SELECT COUNT(*) FROM jobs WHERE status IN ('pending','claimed')")
DUP_REF=$(q "SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs")
DUP_CONF=$(q "SELECT COUNT(*)-COUNT(DISTINCT confirmation) FROM jobs WHERE status='ok'")

fmt() { printf "%'d" "$1" | tr ',' '.'; }
TOTAL_F=$(fmt "$TOTAL"); OK_F=$(fmt "$OK"); FAILED_F=$(fmt "$FAILED"); DEAD_F=$(fmt "$DEAD")

esc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e "s/'/\\\\'/g" -e 's/:/\\:/g' -e 's/%/\\%/g'; }

# kartu(berkas, detik, judul, baris1, baris2)
card() {
  local file=$1 secs=$2 title=$3 line1=$4 line2=$5
  ffmpeg -v error -y -f lavfi -i "color=c=${BG}:s=1920x1080:d=${secs}:r=30" \
    -vf "drawtext=fontfile=${FONT_BOLD}:text='$(esc "$title")':fontcolor=#f5f7fb:fontsize=74:x=(w-tw)/2:y=380,\
drawtext=fontfile=${FONT}:text='$(esc "$line1")':fontcolor=#9fb3d1:fontsize=40:x=(w-tw)/2:y=520,\
drawtext=fontfile=${FONT}:text='$(esc "$line2")':fontcolor=#9fb3d1:fontsize=40:x=(w-tw)/2:y=590,\
setsar=1" \
    -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$file"
}

# potongan(masukan, keluaran, mulai, durasi_sumber, faktor_cepat, takarir[, prafilter])
clip() {
  local src=$1 dst=$2 ss=$3 dur=$4 speed=$5 caption=$6 pre=${7:-}
  [ -n "$pre" ] && pre="${pre},"
  ffmpeg -v error -y -ss "$ss" -t "$dur" -i "$src" \
    -vf "${pre}setpts=PTS/${speed},scale=1920:1080:force_original_aspect_ratio=decrease,\
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=${BG},fps=30,setsar=1,\
drawbox=x=0:y=980:w=1920:h=100:color=black@0.72:t=fill,\
drawtext=fontfile=${FONT_BOLD}:text='$(esc "$caption")':fontcolor=#f5f7fb:fontsize=38:x=60:y=1010" \
    -an -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$dst"
}

DASH_SRC="$REC/dashboard.mkv"
EVID_SRC="$REC/bukti.mkv"
test -f "$DASH_SRC" || { echo "tidak ada $DASH_SRC" >&2; exit 1; }
test -f "$EVID_SRC" || { echo "tidak ada $EVID_SRC" >&2; exit 1; }

DASH_LEN=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$DASH_SRC" | cut -d. -f1)
SPEED=$(( DASH_LEN / DASH_TARGET_SECONDS ))
[ "$SPEED" -lt 1 ] && SPEED=1
echo "dashboard: ${DASH_LEN}s dipercepat ${SPEED}x -> $(( DASH_LEN / SPEED ))s"

card "$WORK/00-judul.mp4" 4 "SurgeLine" \
  "${TOTAL_F} form dikirim otomatis lewat browser" \
  "dimatikan paksa 2x di tengah jalan"

clip "$DASH_SRC" "$WORK/01-dashboard.mp4" 2 "$DASH_LEN" "$SPEED" \
  "Dashboard live (dipercepat ${SPEED}x) - 2x kill -9, lanjut sendiri"

EVID_LEN=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$EVID_SRC" | cut -d. -f1)
clip "$EVID_SRC" "$WORK/02-bukti.mp4" 0 "$EVID_LEN" 1 \
  "Bukti dari database: antrean tuntas, duplikat nol" \
  "crop=1920:560:0:0"

card "$WORK/03-penutup.mp4" 6 "${OK_F} berhasil - duplikat 0" \
  "${TOTAL_F} selesai - ${FAILED_F} ditolak validasi - ${DEAD_F} habis percobaan - sisa ${LEFT}" \
  "diuji hanya terhadap target milik sendiri di 127.0.0.1"

: >"$WORK/concat.txt"
for part in 00-judul 01-dashboard 02-bukti 03-penutup; do
  printf "file '%s'\n" "$(readlink -f "$WORK/${part}.mp4")" >>"$WORK/concat.txt"
done

ffmpeg -v error -y -f concat -safe 0 -i "$WORK/concat.txt" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -movflags +faststart -an "$OUT"

# Screenshot: sebelum / saat mati / setelah selesai — diambil dari rekaman yang sama.
SHOT_BEFORE=${SHOT_BEFORE:-5}
SHOT_CRASH=${SHOT_CRASH:-190}   # detik ke-190: kill pertama, angka membeku & laju turun
SHOT_AFTER=${SHOT_AFTER:-$(( DASH_LEN - 5 ))}
ffmpeg -v error -y -ss "$SHOT_BEFORE" -i "$DASH_SRC" -frames:v 1 assets/before.png
ffmpeg -v error -y -ss "$SHOT_CRASH"  -i "$DASH_SRC" -frames:v 1 assets/crash.png
ffmpeg -v error -y -ss "$SHOT_AFTER"  -i "$DASH_SRC" -frames:v 1 assets/after.png

ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt \
  -show_entries format=duration,size -of default=noprint_wrappers=1 "$OUT"
echo "angka kartu penutup: total=$TOTAL ok=$OK failed=$FAILED dead=$DEAD sisa=$LEFT dup_ref=$DUP_REF dup_konf=$DUP_CONF"
