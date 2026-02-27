.PHONY: help lint format type-check ci-gate quick-gate smoke-gate edge-release-gate edge-selection-lane full-regression pre-release-verify

help:
	@echo "Common operator flows"
	@echo "  make lint               # ruff lint + formatting check"
	@echo "  make format             # apply ruff formatting + safe auto-fixes"
	@echo "  make type-check         # mypy type checks"
	@echo "  make ci-gate            # lint + type-check + full regression tests"
	@echo "  make quick-gate         # fast gate: smoke + targeted pytest"
	@echo "  make smoke-gate         # smoke gate only"
	@echo "  make edge-release-gate  # OTA promotion gate from edge benchmark results"
	@echo "  make edge-selection-lane # run candidate lane and auto-select champion/fallback"
	@echo "  make full-regression    # full test suite"
	@echo "  make pre-release-verify # full pre-release verifier"
	@echo ""
	@echo "Optional env vars: RUN_ID, EPOCHS, ARTIFACTS_DIR, PYTEST_ARGS"

lint:
	@ruff check src/ tests/
	@ruff format --check src/ tests/

format:
	@ruff format src/ tests/
	@ruff check --fix src/ tests/

type-check:
	@mypy src/

ci-gate: lint type-check full-regression

quick-gate:
	@RUN_ID="$${RUN_ID:-quick-gate-$$(date +%Y%m%d-%H%M%S)}"; \
	echo "[quick-gate] RUN_ID=$$RUN_ID"; \
	env RUN_ID="$$RUN_ID" EPOCHS="$${EPOCHS:-1}" ARTIFACTS_DIR="$${ARTIFACTS_DIR:-artifacts}" bash scripts/smoke_test.sh; \
	python3 -m pytest -q tests/test_phase4_health_check.py tests/test_training_runner_cli_contract.py $${PYTEST_ARGS:-}

smoke-gate:
	@RUN_ID="$${RUN_ID:-smoke-gate-$$(date +%Y%m%d-%H%M%S)}"; \
	echo "[smoke-gate] RUN_ID=$$RUN_ID"; \
	env RUN_ID="$$RUN_ID" EPOCHS="$${EPOCHS:-1}" ARTIFACTS_DIR="$${ARTIFACTS_DIR:-artifacts}" bash scripts/smoke_test.sh

edge-release-gate:
	@RUN_ID="$${RUN_ID:?RUN_ID is required (e.g. make edge-release-gate RUN_ID=...)}"; \
	python3 scripts/edge_release_gate.py \
	  --run-id "$$RUN_ID" \
	  --artifacts-dir "$${ARTIFACTS_DIR:-artifacts}" \
	  --required-profiles "$${REQUIRED_PROFILES:-android_high_end,ios_high_end}"

edge-selection-lane:
	@python3 scripts/edge_selection_lane.py \
	  --workspace-dir "." \
	  --artifacts-dir "$${ARTIFACTS_DIR:-artifacts}" \
	  --candidates "$${CANDIDATES:-gru,tcn,dlinear}" \
	  --seeds "$${SEEDS:-41,42,43}" \
	  --selection-profile "$${SELECTION_PROFILE:-desktop_reference}" \
	  --max-accuracy-degradation-pct "$${MAX_ACCURACY_DEGRADATION_PCT:-2.0}"

full-regression:
	@python3 -m pytest -q $${PYTEST_ARGS:-}

pre-release-verify:
	@env ARTIFACTS_DIR="$${ARTIFACTS_DIR:-artifacts}" EPOCHS="$${EPOCHS:-1}" RUN_ID_PREFIX="$${RUN_ID_PREFIX:-pre-release}" bash scripts/pre_release_verify.sh
