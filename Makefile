.PHONY: setup test lint check validate-artifacts clean-generated \
	experiments-offline experiments-live update-paper-hashes \
	render-paper audit-claims check-stale paper-main paper-report research-artifact

setup:
	uv sync --dev

test:
	uv run pytest

lint:
	uv run ruff check ait tests

check: lint test

validate-artifacts:
	uv run python -m ait.artifacts results

clean-generated:
	rm -f results/derived/*.json results/generated/*.tex

experiments-offline:
	uv run python -m ait.experiments.run_offline --output-root results

experiments-live:
	@echo "Run explicit plans from docs/REPRODUCIBILITY.md; no automatic credentialed calls."

update-paper-hashes:
	uv run python -m ait.paper.update_artifact_hashes \
	  --manifest configs/paper_artifacts.yaml \
	  --root .

render-paper:
	uv run python -m ait.paper.render_tables \
	  --manifest configs/paper_artifacts.yaml \
	  --output results/generated

audit-claims:
	uv run python -m ait.paper.audit_claims

check-stale:
	uv run python -m ait.paper.check_stale

paper-main:
	@command -v latexmk >/dev/null 2>&1 || { \
	  echo "BLOCKED: latexmk not found. Install TeX Live (e.g. texlive-latex-extra / latexmk)."; \
	  exit 1; \
	}
	@kpsewhich IEEEtran.cls >/dev/null 2>&1 || { \
	  echo "BLOCKED: IEEEtran.cls not found. Install texlive-publishers (Debian/Ubuntu) or TeX Live publishers collection."; \
	  exit 1; \
	}
	latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

paper-report:
	@command -v latexmk >/dev/null 2>&1 || { \
	  echo "BLOCKED: latexmk not found. Install TeX Live (e.g. texlive-latex-extra / latexmk)."; \
	  exit 1; \
	}
	latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex

research-artifact:
	$(MAKE) check
	$(MAKE) experiments-offline
	$(MAKE) update-paper-hashes
	$(MAKE) check-stale
	$(MAKE) render-paper
	$(MAKE) audit-claims
	$(MAKE) paper-main
	$(MAKE) paper-report
