.PHONY: help lint format type-check ci-gate quick-gate smoke-gate edge-ingest-device edge-release-gate edge-selection-lane full-regression pre-release-verify

help:
	@echo "Common operator flows"
	@echo "  make lint               # ruff lint + formatting check"
	@echo "  make format             # apply ruff formatting + safe auto-fixes"
	@echo "  make type-check         # mypy type checks"
	@echo "  make ci-gate            # lint + type-check + full regression tests"
	@echo "  make quick-gate         # fast gate: smoke + targeted pytest"
	@echo "  make smoke-gate         # smoke gate only"
	@echo "  make edge-ingest-device # ingest real-device benchmark JSON into edge_bench"
	@echo "  make edge-release-gate  # OTA promotion gate from edge benchmark results"
	@echo "  make edge-selection-lane # run candidate lane and auto-select champion/fallback (BENCHMARK/GATE/SCORE/TEACHER options optional)"
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

edge-ingest-device:
	@RUN_ID="$${RUN_ID:?RUN_ID is required (e.g. make edge-ingest-device RUN_ID=...)}"; \
	DEVICE_RESULTS="$${DEVICE_RESULTS:?DEVICE_RESULTS is required (e.g. android_high_end=/tmp/android.json,ios_high_end=/tmp/ios.json)}"; \
	IFS=','; \
	set -- $$DEVICE_RESULTS; \
	ARGS=""; \
	for item in "$$@"; do ARGS="$$ARGS --device-result $$item"; done; \
	eval "python3 scripts/ingest_edge_device_bench.py --run-id $$RUN_ID --artifacts-dir $${ARTIFACTS_DIR:-artifacts} $$ARGS"

edge-release-gate:
	@RUN_ID="$${RUN_ID:?RUN_ID is required (e.g. make edge-release-gate RUN_ID=...)}"; \
	EXTRA_ARGS=""; \
	if [ -n "$${DEVICE_RESULTS:-}" ]; then \
	  IFS=','; set -- $$DEVICE_RESULTS; \
	  for item in "$$@"; do EXTRA_ARGS="$$EXTRA_ARGS --device-result $$item"; done; \
	fi; \
	if [ -n "$${DEVICE_RESULTS_DIR:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --device-results-dir $${DEVICE_RESULTS_DIR}"; fi; \
	eval "python3 scripts/edge_release_gate.py \
	  --run-id $$RUN_ID \
	  --artifacts-dir $${ARTIFACTS_DIR:-artifacts} \
	  --required-profiles $${REQUIRED_PROFILES:-android_high_end,ios_high_end} \
	  $$EXTRA_ARGS"

edge-selection-lane:
	@EXTRA_ARGS=""; \
	if [ -n "$${BENCHMARK_PROFILES:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --benchmark-profiles $${BENCHMARK_PROFILES}"; fi; \
	if [ -n "$${GATE_REQUIRED_PROFILES:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --gate-required-profiles $${GATE_REQUIRED_PROFILES}"; fi; \
	if [ -n "$${SCORE_PROFILES:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --score-profiles $${SCORE_PROFILES}"; fi; \
	if [ -n "$${SCORE_PROFILE_WEIGHTS:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --score-profile-weights $${SCORE_PROFILE_WEIGHTS}"; fi; \
	if [ -n "$${GATE_DEVICE_RESULTS_DIR_TEMPLATE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --gate-device-results-dir-template $${GATE_DEVICE_RESULTS_DIR_TEMPLATE}"; fi; \
	if [ -n "$${TEACHER_PROVIDER:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --teacher-provider $${TEACHER_PROVIDER}"; fi; \
	if [ -n "$${TOLLAMA_BASE_URL:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --tollama-base-url $${TOLLAMA_BASE_URL}"; fi; \
	if [ -n "$${TEACHER_BACKTEST_LENGTH:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --teacher-backtest-length $${TEACHER_BACKTEST_LENGTH}"; fi; \
	if [ -n "$${TEACHER_BACKTEST_HORIZON:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --teacher-backtest-horizon $${TEACHER_BACKTEST_HORIZON}"; fi; \
	if [ "$${TEACHER_ENABLE_FORECAST_FALLBACK:-1}" = "0" ]; then EXTRA_ARGS="$$EXTRA_ARGS --no-teacher-enable-forecast-fallback"; fi; \
	if [ -n "$${TEACHER_MODELS:-}" ]; then IFS=','; set -- $$TEACHER_MODELS; for item in "$$@"; do EXTRA_ARGS="$$EXTRA_ARGS --teacher-model $$item"; done; fi; \
	eval "python3 scripts/edge_selection_lane.py \
	  --workspace-dir . \
	  --artifacts-dir $${ARTIFACTS_DIR:-artifacts} \
	  --candidates $${CANDIDATES:-gru,tcn,dlinear} \
	  --seeds $${SEEDS:-41,42,43} \
	  --selection-profile $${SELECTION_PROFILE:-desktop_reference} \
	  --max-accuracy-degradation-pct $${MAX_ACCURACY_DEGRADATION_PCT:-2.0} \
	  $$EXTRA_ARGS"

full-regression:
	@python3 -m pytest -q $${PYTEST_ARGS:-}

pre-release-verify:
	@env ARTIFACTS_DIR="$${ARTIFACTS_DIR:-artifacts}" EPOCHS="$${EPOCHS:-1}" RUN_ID_PREFIX="$${RUN_ID_PREFIX:-pre-release}" bash scripts/pre_release_verify.sh
