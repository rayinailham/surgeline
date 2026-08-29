# SurgeLine — orkestrasi (D1). Produksi selalu `uv run --no-sync` (D1).
#
# Pipeline ujung ke ujung:  make all
# Salinan bersih (D9):      make all TARGET_PORT=8111 DASH_PORT=8121 \
#                                    TARGET_CONTAINER=surgeline-target-clean

UV      := uv run --no-sync
PYTHON  := $(UV) python

# --- knob (semua boleh ditimpa di baris perintah) ---------------------------
RUN              ?= demo
ROWS             ?= 50000
SEED             ?= 42
DUPLICATES       ?= 50
WORKERS          ?= 4
TIMEOUT_MS       ?= 5000
KILLS            ?= 0
TARGET_PORT      ?= 8110
DASH_PORT        ?= 8120
TARGET_CONTAINER ?= surgeline-target
INPUT            ?= data/input/records.csv

BASE_URL := http://127.0.0.1:$(TARGET_PORT)
RUN_DIR  := data/$(RUN)
QUEUE_DB := $(RUN_DIR)/queue.db
COMPOSE  := SURGELINE_TARGET_PORT=$(TARGET_PORT) \
            SURGELINE_TARGET_CONTAINER=$(TARGET_CONTAINER) docker compose

.DEFAULT_GOAL := help

.PHONY: help env setup test audit target-up target-down target-oracles \
        gen-data load run recover dashboard report verify diagram demo-video clean all

help:  ## Daftar target yang tersedia
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

env:  ## Verifikasi lingkungan (versi tool + port yang dipakai)
	@echo "uv       : $$(uv --version)"
	@echo "python   : $$($(PYTHON) -c 'import sys;print(sys.version.split()[0])')"
	@echo "docker   : $$(docker --version)"
	@echo "compose  : $$(docker compose version | head -1)"
	@echo "sqlite3  : $$(sqlite3 --version | cut -d" " -f1)"
	@ss -tlnp 2>/dev/null | grep -E ':($(TARGET_PORT)|$(DASH_PORT))\b' \
		|| echo "port     : $(TARGET_PORT)/$(DASH_PORT) bebas"

setup:  ## Pasang dependency (uv.lock) + Chromium Playwright — TANPA --with-deps (Arch)
	uv sync --frozen
	$(UV) playwright install chromium

test:  ## Jalankan unit test (unittest, D1)
	$(UV) python -m compileall -q src scripts
	$(UV) python -m unittest discover -s src -v

audit:  ## Pindai rahasia & artefak runtime (A12); exit 1 kalau ada kebocoran
	$(PYTHON) scripts/secret_audit.py

# --- target app --------------------------------------------------------------
target-up:  ## Nyalakan target app :$(TARGET_PORT) (docker-compose.yml project, D2/D9)
	$(COMPOSE) up -d --build
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do \
		code=$$(curl -sS -o /dev/null -w '%{http_code}' $(BASE_URL)/health 2>/dev/null); \
		if [ "$$code" = "200" ]; then echo "target-up: $(BASE_URL)/health -> 200"; exit 0; fi; \
		sleep 1; \
	done; \
	echo "target-up GAGAL: $(BASE_URL)/health tidak 200"; $(COMPOSE) logs --tail=30 target; exit 1

target-down:  ## Matikan target app (container + state target ikut hilang)
	$(COMPOSE) down

target-oracles:  ## Buktikan chaos 5% deterministik pada dua target segar (P2)
	$(PYTHON) scripts/target_oracles.py

# --- pipeline ----------------------------------------------------------------
gen-data:  ## Bikin $(ROWS) record sintetis CSV+XLSX ke data/input (D10; menolak menimpa)
	@if [ -f $(INPUT) ]; then \
		echo "gen-data: $(INPUT) sudah ada, data mentah tidak ditimpa (D10)"; \
	else \
		$(PYTHON) scripts/gen_data.py --rows $(ROWS) --seed $(SEED) \
			--duplicates $(DUPLICATES) --out $(dir $(INPUT)); \
	fi

load:  ## Muat $(INPUT) ke antrean data/$(RUN)/queue.db (dedup DB, D4)
	$(PYTHON) -m src.load --input $(INPUT) --run $(RUN)

run:  ## Jalankan $(WORKERS) worker sampai antrean habis (D7/D8/D12)
	$(PYTHON) -m src.run --run $(RUN) --workers $(WORKERS) \
		--base-url $(BASE_URL) --timeout-ms $(TIMEOUT_MS)

recover:  ## Tarik job yatim (claimed lewat lease) kembali ke pending (D8)
	$(PYTHON) -m src.recover --run $(RUN)

dashboard:  ## Dashboard read-only :$(DASH_PORT) (D11; Ctrl-C untuk berhenti)
	$(PYTHON) -m src.dashboard --run $(RUN) --port $(DASH_PORT)

report:  ## Tulis reports/digest.md + reports/REPORT.xlsx dari antrean (P13)
	$(PYTHON) -m src.report --run $(RUN) --workers $(WORKERS) --kills $(KILLS)

verify:  ## Gerbang hasil: antrean tuntas & duplikat NOL (A1/A2) — exit 1 kalau tidak
	@test -f $(QUEUE_DB) || { echo "verify GAGAL: $(QUEUE_DB) tidak ada"; exit 1; }
	@sqlite3 $(QUEUE_DB) \
		"SELECT 'total     : '||COUNT(*) FROM jobs; \
		 SELECT 'terminal  : '||COUNT(*) FROM jobs WHERE status IN ('ok','failed','dead'); \
		 SELECT 'sisa      : '||COUNT(*) FROM jobs WHERE status IN ('pending','claimed'); \
		 SELECT 'dup ref   : '||(COUNT(*)-COUNT(DISTINCT external_ref)) FROM jobs; \
		 SELECT 'dup konf  : '||(COUNT(*)-COUNT(DISTINCT confirmation)) FROM jobs WHERE status='ok'; \
		 SELECT 'ok kosong : '||COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation=''); \
		 SELECT status||' : '||COUNT(*) FROM jobs GROUP BY status ORDER BY status;"
	@sisa=$$(sqlite3 $(QUEUE_DB) "SELECT COUNT(*) FROM jobs WHERE status IN ('pending','claimed')"); \
	 dupref=$$(sqlite3 $(QUEUE_DB) "SELECT COUNT(*)-COUNT(DISTINCT external_ref) FROM jobs"); \
	 dupkonf=$$(sqlite3 $(QUEUE_DB) "SELECT COUNT(*)-COUNT(DISTINCT confirmation) FROM jobs WHERE status='ok'"); \
	 kosong=$$(sqlite3 $(QUEUE_DB) "SELECT COUNT(*) FROM jobs WHERE status='ok' AND (confirmation IS NULL OR confirmation='')"); \
	 if [ "$$sisa" -ne 0 ] || [ "$$dupref" -ne 0 ] || [ "$$dupkonf" -ne 0 ] || [ "$$kosong" -ne 0 ]; then \
		echo "verify GAGAL: sisa=$$sisa dup_ref=$$dupref dup_konf=$$dupkonf ok_kosong=$$kosong"; exit 1; \
	 fi; \
	 echo "verify OK: antrean tuntas, dup_ref=0, dup_konf=0, ok tanpa nomor konfirmasi=0"

diagram:  ## Render assets/architecture.png dari assets/architecture.dot (butuh graphviz)
	dot -Tpng -Gdpi=140 assets/architecture.dot -o assets/architecture.png
	@echo "diagram: assets/architecture.png"

demo-video:  ## Rakit assets/demo.mp4 + screenshot dari rekaman data/rec (P14)
	RUN=$(RUN) bash scripts/make_demo_video.sh

clean:  ## Hapus antrean run ini + laporan (data mentah data/input TIDAK dihapus)
	rm -rf $(RUN_DIR) reports/digest.md reports/REPORT.xlsx
	@echo "clean: $(RUN_DIR) + reports/ dibersihkan (data/input dibiarkan)"

all: target-up gen-data load run report verify  ## Pipeline penuh: target -> data -> antrean -> worker -> laporan -> gerbang
	@echo "make all: SELESAI (run=$(RUN) workers=$(WORKERS) target=$(BASE_URL))"
