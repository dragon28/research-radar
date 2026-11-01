.PHONY: setup test lint demo serve n8n-setup n8n-import n8n-run n8n-editor

N8N := ./n8n/node_modules/.bin/n8n
N8N_ENV := N8N_USER_FOLDER=$(CURDIR)/.n8n N8N_DIAGNOSTICS_ENABLED=false N8N_HOST=127.0.0.1 N8N_LISTEN_ADDRESS=127.0.0.1

setup:            ## Python env (no runtime dependencies, dev tools only)
	uv sync

lint:
	uv run ruff check .

test:
	uv run pytest -q

demo:             ## offline demo on saved feeds -> out/demo/*.md
	uv run radar demo

serve:            ## local API that n8n calls (127.0.0.1:8765)
	uv run radar serve

n8n-setup:        ## project-local n8n (needs Node >= 24)
	cd n8n && npm ci --no-audit --no-fund && npm install-scripts approve sqlite3 && npm rebuild sqlite3

n8n-import:
	$(N8N_ENV) $(N8N) import:workflow --input=n8n/workflow.json

n8n-run:          ## run the workflow once from the command line (needs `make serve` running)
	$(N8N_ENV) $(N8N) execute --id ResearchRadar01

n8n-editor:       ## editor at http://127.0.0.1:5678 (localhost only)
	$(N8N_ENV) $(N8N) start
