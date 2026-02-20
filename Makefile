.PHONY: help quick-gate smoke-gate full-regression pre-release-verify

help:
	@echo "Common operator flows"
	@echo "  make quick-gate         # fast gate: smoke + targeted pytest"
	@echo "  make smoke-gate         # smoke gate only"
	@echo "  make full-regression    # full test suite"
	@echo "  make pre-release-verify # full pre-release verifier"
	@echo ""
	@echo "Optional env vars: RUN_ID, EPOCHS, ARTIFACTS_DIR, PYTEST_ARGS"

quick-gate:
	@RUN_ID="$${RUN_ID:-quick-gate-$$(date +%Y%m%d-%H%M%S)}"; \
	echo "[quick-gate] RUN_ID=$$RUN_ID"; \
	env RUN_ID="$$RUN_ID" EPOCHS="$${EPOCHS:-1}" ARTIFACTS_DIR="$${ARTIFACTS_DIR:-artifacts}" bash scripts/smoke_test.sh; \
	python3 -m pytest -q tests/test_phase4_health_check.py tests/test_training_runner_cli_contract.py $${PYTEST_ARGS:-}

smoke-gate:
	@RUN_ID="$${RUN_ID:-smoke-gate-$$(date +%Y%m%d-%H%M%S)}"; \
	echo "[smoke-gate] RUN_ID=$$RUN_ID"; \
	env RUN_ID="$$RUN_ID" EPOCHS="$${EPOCHS:-1}" ARTIFACTS_DIR="$${ARTIFACTS_DIR:-artifacts}" bash scripts/smoke_test.sh

full-regression:
	@python3 -m pytest -q $${PYTEST_ARGS:-}

pre-release-verify:
	@env ARTIFACTS_DIR="$${ARTIFACTS_DIR:-artifacts}" EPOCHS="$${EPOCHS:-1}" RUN_ID_PREFIX="$${RUN_ID_PREFIX:-pre-release}" bash scripts/pre_release_verify.sh
