#!/usr/bin/env bash
# P14 — jendela browser bersih berisi dashboard, khusus untuk direkam.
#
# Profil sementara (bukan profil browser user): tanpa tab lain, tanpa bookmark,
# tanpa ekstensi, telemetri mati, tanpa jaringan ke luar. Kiosk = hanya isi halaman,
# tidak ada address bar yang bisa membocorkan apa pun. Menutup diri setelah DURATION.
#
#   URL=http://127.0.0.1:8120 DURATION=1500 bash scripts/demo_dashboard.sh
set -euo pipefail

URL=${URL:-http://127.0.0.1:8120}
DURATION=${DURATION:-600}      # batas atas; jendela ditutup lebih awal kalau WATCH_DB tuntas
WATCH_DB=${WATCH_DB:-}         # kalau diisi: tutup jendela begitu antrean tuntas
GRACE=${GRACE:-15}             # detik menahan layar "selesai" sebelum menutup
ZOOM=${ZOOM:-1.5}
BROWSER=${BROWSER:-firefox}

command -v "$BROWSER" >/dev/null || { echo "browser tidak ada: $BROWSER" >&2; exit 1; }

PROFILE=$(mktemp -d /tmp/surgeline-demo-profile.XXXXXX)
trap 'rm -rf "$PROFILE"' EXIT

cat >"$PROFILE/user.js" <<PREFS
user_pref("layout.css.devPixelsPerPx", "${ZOOM}");
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("datareporting.healthreport.uploadEnabled", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.enabled", false);
user_pref("browser.safebrowsing.malware.enabled", false);
user_pref("browser.safebrowsing.phishing.enabled", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("extensions.getAddons.cache.enabled", false);
user_pref("network.dns.disablePrefetch", true);
user_pref("browser.newtabpage.enabled", false);
PREFS

MOZ_ENABLE_WAYLAND=1 "$BROWSER" --no-remote --profile "$PROFILE" --kiosk "$URL" &
BROWSER_PID=$!

if [ -n "$WATCH_DB" ]; then
  elapsed=0
  while [ "$elapsed" -lt "$DURATION" ]; do
    left=$(sqlite3 "$WATCH_DB" \
      "SELECT COUNT(*) FROM jobs WHERE status IN ('pending','claimed')" 2>/dev/null || echo 1)
    [ "$left" = "0" ] && { sleep "$GRACE"; break; }
    sleep 5
    elapsed=$(( elapsed + 5 ))
  done
else
  sleep "$DURATION"
fi

kill "$BROWSER_PID" 2>/dev/null || true
wait "$BROWSER_PID" 2>/dev/null || true
