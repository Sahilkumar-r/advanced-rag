PY ?= .venv/Scripts/python
.PHONY: help test lint scan safety ci-retrieval ci serve seed docs dashboard
help:
	@echo "test ci-retrieval ci lint scan safety serve seed docs dashboard. See docs/06-IMPLEMENTATION-PLAN.md."
test:
	$(PY) -m pytest -q
lint:
	$(PY) -m ruff check src scripts tests
scan:
	$(PY) scripts/scan_secrets.py
safety:
	$(PY) scripts/run_safety_eval.py
docs:
	$(PY) scripts/fetch_docs.py
ci-retrieval: docs
	$(PY) scripts/ci_retrieval_check.py
ci: lint scan test safety ci-retrieval
seed:
	$(PY) scripts/seed_users.py
serve:
	$(PY) scripts/serve.py
dashboard:
	$(PY) scripts/make_dashboard.py
