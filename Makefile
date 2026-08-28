# SurgeLine — orkestrasi (D1). Target diisi bertahap per fase.
# Produksi selalu `uv run --no-sync` (D1).

UV      := uv run --no-sync
PYTHON  := $(UV) python

.DEFAULT_GOAL := help

.PHONY: help env test audit target-up target-down target-oracles

help:  ## Daftar target yang tersedia
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

env:  ## Verifikasi lingkungan (versi tool + port 8110/8120)
	@echo "uv       : $$(uv --version)"
	@echo "python   : $$($(PYTHON) -c 'import sys;print(sys.version.split()[0])')"
	@echo "docker   : $$(docker --version)"
	@echo "compose  : $$(docker compose version | head -1)"
	@echo "sqlite3  : $$(sqlite3 --version | cut -d" " -f1)"
	@ss -tlnp 2>/dev/null | grep -E ':(8110|8120)\b' || echo "port     : 8110/8120 bebas"

test:  ## Jalankan unit test (unittest, D1)
	$(UV) python -m compileall -q src scripts
	$(UV) python -m unittest discover -s src -v

audit:  ## Cek tidak ada rahasia/artefak runtime yang ter-stage (P14 mengisi scripts/secret_audit.py)
	@if [ -x scripts/secret_audit.py ]; then \
		$(UV) python scripts/secret_audit.py; \
	else \
		echo "audit: scripts/secret_audit.py belum ada (dibuat di P14) - cek manual"; \
		git status --short | grep -E '(^|/)(\.env|data/|reports/|auth/)|\.(db|sqlite)' \
			&& { echo "AUDIT GAGAL: artefak terlarang ter-stage"; exit 1; } \
			|| echo "audit manual: bersih"; \
	fi

target-up:  ## Nyalakan target app :8110 (docker-compose.yml project, D2/D9)
	docker compose up -d --build
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		code=$$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8110/health 2>/dev/null); \
		if [ "$$code" = "200" ]; then echo "target-up: :8110/health -> 200"; exit 0; fi; \
		sleep 1; \
	done; \
	echo "target-up GAGAL: :8110/health tidak 200"; docker compose logs --tail=30 target; exit 1

target-down:  ## Matikan target app (container + state target ikut hilang)
	docker compose down

target-oracles:  ## Buktikan chaos 5% deterministik pada dua target segar (P2)
	$(PYTHON) scripts/target_oracles.py
