.PHONY: help lint format type-check ci-gate quick-gate smoke-gate edge-smoke-env edge-wheelhouse-build edge-wheelhouse-install edge-make-mobile-bundle edge-validate-mobile-bundle edge-validate-mobile-benchmark edge-make-device-result edge-ingest-example edge-release-example edge-ingest-device edge-release-gate edge-selection-lane full-regression pre-release-verify

help:
	@echo "Common operator flows"
	@echo "  make lint               # ruff lint + formatting check"
	@echo "  make format             # apply ruff formatting + safe auto-fixes"
	@echo "  make type-check         # mypy type checks"
	@echo "  make ci-gate            # lint + type-check + full regression tests"
	@echo "  make quick-gate         # fast gate: smoke + targeted pytest"
	@echo "  make smoke-gate         # smoke gate only"
	@echo "  make edge-smoke-env     # fresh-venv edge install/run validation (MODE=ops|benchmark-onnx|train-export)"
	@echo "  make edge-wheelhouse-build # build offline wheelhouse for edge profiles"
	@echo "  make edge-wheelhouse-install # install selected edge profile from a wheelhouse"
	@echo "  make edge-make-mobile-bundle # generate Android/iOS mobile bundle manifest from export manifest"
	@echo "  make edge-validate-mobile-bundle # validate Android/iOS mobile bundle manifest"
	@echo "  make edge-validate-mobile-benchmark # validate Android/iOS mobile benchmark payload"
	@echo "  make edge-make-device-result # generate a real-device benchmark JSON payload"
	@echo "  make edge-ingest-example # generate + ingest one sample device benchmark payload for RUN_ID"
	@echo "  make edge-release-example # generate + ingest + release-gate one sample device payload for RUN_ID"
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

edge-smoke-env:
	@MPLCFG="$${MPLCONFIGDIR:-/tmp/mpl-spline}"; \
	XDGCACHE="$${XDG_CACHE_HOME:-/tmp/xdg-cache-spline}"; \
	mkdir -p "$$MPLCFG" "$$XDGCACHE"; \
	EXTRA_ARGS=""; \
	if [ -n "$${WHEELHOUSE_DIR:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --wheelhouse-dir $${WHEELHOUSE_DIR}"; fi; \
	if [ -n "$${MIN_FREE_DISK_MB:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --min-free-disk-mb $${MIN_FREE_DISK_MB}"; fi; \
	if [ -n "$${MIN_TOTAL_MEMORY_MB:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --min-total-memory-mb $${MIN_TOTAL_MEMORY_MB}"; fi; \
	if [ -n "$${ONNX_SMOKE_MODEL:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --onnx-smoke-model $${ONNX_SMOKE_MODEL}"; fi; \
	if [ "$${SKIP_FUNCTIONAL_SMOKE:-0}" = "1" ]; then EXTRA_ARGS="$$EXTRA_ARGS --skip-functional-smoke"; fi; \
	eval "MPLCONFIGDIR=$$MPLCFG XDG_CACHE_HOME=$$XDGCACHE bash scripts/edge_smoke_env.sh --mode $${MODE:-ops} --venv-dir $${VENV_DIR:-.venv-edge-smoke} --artifacts-dir $${ARTIFACTS_DIR:-artifacts-edge-smoke} --cache-root $$XDGCACHE --run-id $${RUN_ID:-edge-smoke-$$(date +%Y%m%d-%H%M%S)} $$EXTRA_ARGS"

edge-wheelhouse-build:
	@EXTRA_ARGS=""; \
	if [ "$${CLEAN:-0}" = "1" ]; then EXTRA_ARGS="$$EXTRA_ARGS --clean"; fi; \
	eval "bash scripts/build_edge_wheelhouse.sh --mode $${MODE:-all} --wheelhouse-dir $${WHEELHOUSE_DIR:-wheelhouse-edge} $$EXTRA_ARGS"

edge-wheelhouse-install:
	@EXTRA_ARGS=""; \
	if [ "$${SKIP_VALIDATE:-0}" = "1" ]; then EXTRA_ARGS="$$EXTRA_ARGS --skip-validate"; fi; \
	if [ "$${SKIP_FUNCTIONAL_SMOKE:-0}" = "1" ]; then EXTRA_ARGS="$$EXTRA_ARGS --skip-functional-smoke"; fi; \
	eval "bash scripts/install_edge_from_wheelhouse.sh --mode $${MODE:-ops} --wheelhouse-dir $${WHEELHOUSE_DIR:-wheelhouse-edge} --venv-dir $${VENV_DIR:-.venv-edge-offline} --cache-root $${CACHE_ROOT:-/tmp/xdg-cache-spline-edge-offline} --artifacts-dir $${ARTIFACTS_DIR:-artifacts-edge-offline} $$EXTRA_ARGS"

edge-make-mobile-bundle:
	@OUTPUT="$${OUTPUT:?OUTPUT is required (e.g. make edge-make-mobile-bundle OUTPUT=/tmp/android_bundle.json)}"; \
	EXPORT_MANIFEST="$${EXPORT_MANIFEST:?EXPORT_MANIFEST is required (e.g. artifacts/exports/<run_id>/manifest.json)}"; \
	PLATFORM="$${PLATFORM:?PLATFORM is required (android or ios)}"; \
	BUNDLE_ID="$${BUNDLE_ID:?BUNDLE_ID is required (e.g. ai.tollama.splineforecast)}"; \
	EXTRA_ARGS=""; \
	if [ -n "$${BUILD_NUMBER:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --build-number $${BUILD_NUMBER}"; fi; \
	if [ -n "$${RUNTIME_STACK:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --runtime-stack $${RUNTIME_STACK}"; fi; \
	if [ -n "$${RELATIVE_MODEL_PATH:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --relative-model-path $${RELATIVE_MODEL_PATH}"; fi; \
	if [ -n "$${ASSET_PACK:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --asset-pack $${ASSET_PACK}"; fi; \
	if [ -n "$${ABI_FILTERS:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --abi-filters $${ABI_FILTERS}"; fi; \
	if [ -n "$${RUNTIME_LIBRARY:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --runtime-library $${RUNTIME_LIBRARY}"; fi; \
	if [ -n "$${MIN_SDK:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --min-sdk $${MIN_SDK}"; fi; \
	if [ -n "$${BUNDLE_RESOURCE_SUBDIR:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --bundle-resource-subdir $${BUNDLE_RESOURCE_SUBDIR}"; fi; \
	if [ -n "$${MINIMUM_IOS_VERSION:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --minimum-ios-version $${MINIMUM_IOS_VERSION}"; fi; \
	eval "python3 scripts/make_mobile_bundle_manifest.py --platform $$PLATFORM --export-manifest $$EXPORT_MANIFEST --output $$OUTPUT --bundle-id $$BUNDLE_ID $$EXTRA_ARGS"

edge-validate-mobile-bundle:
	@BUNDLE_MANIFEST="$${BUNDLE_MANIFEST:?BUNDLE_MANIFEST is required (e.g. make edge-validate-mobile-bundle BUNDLE_MANIFEST=examples/mobile_bundle_android_tflite.json)}"; \
	EXTRA_ARGS=""; \
	if [ "$${STRICT_PLATFORM_POLICY:-0}" = "1" ]; then EXTRA_ARGS="$$EXTRA_ARGS --strict-platform-policy"; fi; \
	eval "python3 scripts/validate_mobile_bundle.py --bundle-manifest $$BUNDLE_MANIFEST $$EXTRA_ARGS"

edge-validate-mobile-benchmark:
	@BENCHMARK_RESULT="$${BENCHMARK_RESULT:?BENCHMARK_RESULT is required (e.g. make edge-validate-mobile-benchmark BENCHMARK_RESULT=examples/mobile_benchmark_result_android_pixel8.json)}"; \
	EXTRA_ARGS=""; \
	if [ -n "$${EXPECTED_PLATFORM:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --expected-platform $${EXPECTED_PLATFORM}"; fi; \
	if [ "$${NO_REQUIRE_METADATA:-0}" = "1" ]; then EXTRA_ARGS="$$EXTRA_ARGS --no-require-metadata"; fi; \
	if [ "$${NO_REQUIRE_ACCURACY:-0}" = "1" ]; then EXTRA_ARGS="$$EXTRA_ARGS --no-require-accuracy"; fi; \
	if [ "$${STRICT_RUNTIME_POLICY:-0}" = "1" ]; then EXTRA_ARGS="$$EXTRA_ARGS --strict-runtime-policy"; fi; \
	eval "python3 scripts/validate_mobile_benchmark_result.py --benchmark-result $$BENCHMARK_RESULT $$EXTRA_ARGS"

edge-make-device-result:
	@OUTPUT="$${OUTPUT:?OUTPUT is required (e.g. make edge-make-device-result OUTPUT=/tmp/android_edge.json)}"; \
	MPLCFG="$${MPLCONFIGDIR:-/tmp/mpl-spline}"; \
	XDGCACHE="$${XDG_CACHE_HOME:-/tmp/xdg-cache-spline}"; \
	mkdir -p "$$MPLCFG"; \
	mkdir -p "$$XDGCACHE"; \
	EXTRA_ARGS=""; \
	if [ -n "$${FROM_REPORT_JSON:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --from-report-json $${FROM_REPORT_JSON}"; fi; \
	if [ -n "$${RUNTIME_STACK:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --runtime-stack $${RUNTIME_STACK}"; fi; \
	if [ -n "$${FALLBACK_CHAIN:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --fallback-chain $${FALLBACK_CHAIN}"; fi; \
	if [ -n "$${STATUS:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --status $${STATUS}"; fi; \
	if [ -n "$${LATENCY_P50_MS:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --latency-p50-ms $${LATENCY_P50_MS}"; fi; \
	if [ -n "$${LATENCY_P95_MS:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --latency-p95-ms $${LATENCY_P95_MS}"; fi; \
	if [ -n "$${MEMORY_PEAK_MB:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --memory-peak-mb $${MEMORY_PEAK_MB}"; fi; \
	if [ -n "$${SIZE_MB:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --size-mb $${SIZE_MB}"; fi; \
	if [ -n "$${ATTEMPTS:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --attempts $${ATTEMPTS}"; fi; \
	if [ -n "$${FAILURES:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --failures $${FAILURES}"; fi; \
	if [ -n "$${ACCURACY_RMSE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-rmse $${ACCURACY_RMSE}"; fi; \
	if [ -n "$${ACCURACY_BASELINE_RMSE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-baseline-rmse $${ACCURACY_BASELINE_RMSE}"; fi; \
	if [ -n "$${ACCURACY_RMSE_DEGRADATION_PCT:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-rmse-degradation-pct $${ACCURACY_RMSE_DEGRADATION_PCT}"; fi; \
	if [ -n "$${ACCURACY_MAE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-mae $${ACCURACY_MAE}"; fi; \
	if [ -n "$${ACCURACY_WAPE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-wape $${ACCURACY_WAPE}"; fi; \
	if [ -n "$${ACCURACY_MAX_ABS_DIFF:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-max-abs-diff $${ACCURACY_MAX_ABS_DIFF}"; fi; \
	if [ -n "$${ACCURACY_N_SAMPLES:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-n-samples $${ACCURACY_N_SAMPLES}"; fi; \
	if [ -n "$${PER_HORIZON_RMSE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --per-horizon-rmse $${PER_HORIZON_RMSE}"; fi; \
	eval "MPLCONFIGDIR=$$MPLCFG XDG_CACHE_HOME=$$XDGCACHE python3 scripts/make_edge_device_result.py --output $$OUTPUT $$EXTRA_ARGS"

edge-ingest-example:
	@RUN_ID="$${RUN_ID:?RUN_ID is required (e.g. make edge-ingest-example RUN_ID=edge-demo-001)}"; \
	DEVICE_PROFILE="$${DEVICE_PROFILE:-android_high_end}"; \
	DEVICE_JSON="$${DEVICE_JSON:-/tmp/$$RUN_ID-$$DEVICE_PROFILE-device.json}"; \
	MPLCFG="$${MPLCONFIGDIR:-/tmp/mpl-spline}"; \
	XDGCACHE="$${XDG_CACHE_HOME:-/tmp/xdg-cache-spline}"; \
	mkdir -p "$$MPLCFG"; \
	mkdir -p "$$XDGCACHE"; \
	EXTRA_ARGS=""; \
	if [ -n "$${FROM_REPORT_JSON:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --from-report-json $${FROM_REPORT_JSON}"; fi; \
	if [ -n "$${RUNTIME_STACK:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --runtime-stack $${RUNTIME_STACK}"; else EXTRA_ARGS="$$EXTRA_ARGS --runtime-stack tflite"; fi; \
	if [ -n "$${FALLBACK_CHAIN:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --fallback-chain $${FALLBACK_CHAIN}"; else EXTRA_ARGS="$$EXTRA_ARGS --fallback-chain tflite,keras"; fi; \
	if [ -n "$${STATUS:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --status $${STATUS}"; fi; \
	if [ -n "$${LATENCY_P50_MS:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --latency-p50-ms $${LATENCY_P50_MS}"; else EXTRA_ARGS="$$EXTRA_ARGS --latency-p50-ms 18.4"; fi; \
	if [ -n "$${LATENCY_P95_MS:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --latency-p95-ms $${LATENCY_P95_MS}"; else EXTRA_ARGS="$$EXTRA_ARGS --latency-p95-ms 24.7"; fi; \
	if [ -n "$${MEMORY_PEAK_MB:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --memory-peak-mb $${MEMORY_PEAK_MB}"; else EXTRA_ARGS="$$EXTRA_ARGS --memory-peak-mb 212.0"; fi; \
	if [ -n "$${SIZE_MB:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --size-mb $${SIZE_MB}"; else EXTRA_ARGS="$$EXTRA_ARGS --size-mb 4.2"; fi; \
	if [ -n "$${ATTEMPTS:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --attempts $${ATTEMPTS}"; else EXTRA_ARGS="$$EXTRA_ARGS --attempts 200"; fi; \
	if [ -n "$${FAILURES:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --failures $${FAILURES}"; else EXTRA_ARGS="$$EXTRA_ARGS --failures 0"; fi; \
	if [ -n "$${ACCURACY_RMSE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-rmse $${ACCURACY_RMSE}"; else EXTRA_ARGS="$$EXTRA_ARGS --accuracy-rmse 0.94"; fi; \
	if [ -n "$${ACCURACY_BASELINE_RMSE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-baseline-rmse $${ACCURACY_BASELINE_RMSE}"; else EXTRA_ARGS="$$EXTRA_ARGS --accuracy-baseline-rmse 1.00"; fi; \
	if [ -n "$${ACCURACY_RMSE_DEGRADATION_PCT:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-rmse-degradation-pct $${ACCURACY_RMSE_DEGRADATION_PCT}"; fi; \
	if [ -n "$${ACCURACY_MAE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-mae $${ACCURACY_MAE}"; else EXTRA_ARGS="$$EXTRA_ARGS --accuracy-mae 0.71"; fi; \
	if [ -n "$${ACCURACY_WAPE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-wape $${ACCURACY_WAPE}"; else EXTRA_ARGS="$$EXTRA_ARGS --accuracy-wape 8.9"; fi; \
	if [ -n "$${ACCURACY_MAX_ABS_DIFF:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-max-abs-diff $${ACCURACY_MAX_ABS_DIFF}"; else EXTRA_ARGS="$$EXTRA_ARGS --accuracy-max-abs-diff 1.42"; fi; \
	if [ -n "$${ACCURACY_N_SAMPLES:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --accuracy-n-samples $${ACCURACY_N_SAMPLES}"; else EXTRA_ARGS="$$EXTRA_ARGS --accuracy-n-samples 64"; fi; \
	if [ -n "$${PER_HORIZON_RMSE:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --per-horizon-rmse $${PER_HORIZON_RMSE}"; else EXTRA_ARGS="$$EXTRA_ARGS --per-horizon-rmse 0.81,0.93,1.05"; fi; \
	echo "[edge-ingest-example] generating $$DEVICE_JSON"; \
	eval "MPLCONFIGDIR=$$MPLCFG XDG_CACHE_HOME=$$XDGCACHE python3 scripts/make_edge_device_result.py --output $$DEVICE_JSON $$EXTRA_ARGS"; \
	echo "[edge-ingest-example] ingesting $$DEVICE_PROFILE=$$DEVICE_JSON into RUN_ID=$$RUN_ID"; \
	MPLCONFIGDIR="$$MPLCFG" XDG_CACHE_HOME="$$XDGCACHE" python3 scripts/ingest_edge_device_bench.py --run-id "$$RUN_ID" --artifacts-dir "$${ARTIFACTS_DIR:-artifacts}" --device-result "$$DEVICE_PROFILE=$$DEVICE_JSON"

edge-release-example:
	@RUN_ID="$${RUN_ID:?RUN_ID is required (e.g. make edge-release-example RUN_ID=edge-demo-001)}"; \
	MPLCFG="$${MPLCONFIGDIR:-/tmp/mpl-spline}"; \
	XDGCACHE="$${XDG_CACHE_HOME:-/tmp/xdg-cache-spline}"; \
	mkdir -p "$$MPLCFG"; \
	mkdir -p "$$XDGCACHE"; \
	$(MAKE) edge-ingest-example RUN_ID="$$RUN_ID" ARTIFACTS_DIR="$${ARTIFACTS_DIR:-artifacts}" DEVICE_PROFILE="$${DEVICE_PROFILE:-android_high_end}" DEVICE_JSON="$${DEVICE_JSON:-/tmp/$$RUN_ID-$${DEVICE_PROFILE:-android_high_end}-device.json}" FROM_REPORT_JSON="$${FROM_REPORT_JSON:-}" RUNTIME_STACK="$${RUNTIME_STACK:-}" FALLBACK_CHAIN="$${FALLBACK_CHAIN:-}" STATUS="$${STATUS:-}" LATENCY_P50_MS="$${LATENCY_P50_MS:-}" LATENCY_P95_MS="$${LATENCY_P95_MS:-}" MEMORY_PEAK_MB="$${MEMORY_PEAK_MB:-}" SIZE_MB="$${SIZE_MB:-}" ATTEMPTS="$${ATTEMPTS:-1000}" FAILURES="$${FAILURES:-}" ACCURACY_RMSE="$${ACCURACY_RMSE:-}" ACCURACY_BASELINE_RMSE="$${ACCURACY_BASELINE_RMSE:-}" ACCURACY_RMSE_DEGRADATION_PCT="$${ACCURACY_RMSE_DEGRADATION_PCT:-}" ACCURACY_MAE="$${ACCURACY_MAE:-}" ACCURACY_WAPE="$${ACCURACY_WAPE:-}" ACCURACY_MAX_ABS_DIFF="$${ACCURACY_MAX_ABS_DIFF:-}" ACCURACY_N_SAMPLES="$${ACCURACY_N_SAMPLES:-}" PER_HORIZON_RMSE="$${PER_HORIZON_RMSE:-}" MPLCONFIGDIR="$$MPLCFG" XDG_CACHE_HOME="$$XDGCACHE"; \
	echo "[edge-release-example] applying release gate for RUN_ID=$$RUN_ID"; \
	MPLCONFIGDIR="$$MPLCFG" XDG_CACHE_HOME="$$XDGCACHE" python3 scripts/edge_release_gate.py --run-id "$$RUN_ID" --artifacts-dir "$${ARTIFACTS_DIR:-artifacts}" --required-profiles "$${REQUIRED_PROFILES:-$${DEVICE_PROFILE:-android_high_end}}"

edge-ingest-device:
	@RUN_ID="$${RUN_ID:?RUN_ID is required (e.g. make edge-ingest-device RUN_ID=...)}"; \
	DEVICE_RESULTS="$${DEVICE_RESULTS:?DEVICE_RESULTS is required (e.g. android_high_end=/tmp/android.json,ios_high_end=/tmp/ios.json)}"; \
	MPLCFG="$${MPLCONFIGDIR:-/tmp/mpl-spline}"; \
	XDGCACHE="$${XDG_CACHE_HOME:-/tmp/xdg-cache-spline}"; \
	mkdir -p "$$MPLCFG"; \
	mkdir -p "$$XDGCACHE"; \
	IFS=','; \
	set -- $$DEVICE_RESULTS; \
	ARGS=""; \
	for item in "$$@"; do ARGS="$$ARGS --device-result $$item"; done; \
	eval "MPLCONFIGDIR=$$MPLCFG XDG_CACHE_HOME=$$XDGCACHE python3 scripts/ingest_edge_device_bench.py --run-id $$RUN_ID --artifacts-dir $${ARTIFACTS_DIR:-artifacts} $$ARGS"

edge-release-gate:
	@RUN_ID="$${RUN_ID:?RUN_ID is required (e.g. make edge-release-gate RUN_ID=...)}"; \
	MPLCFG="$${MPLCONFIGDIR:-/tmp/mpl-spline}"; \
	XDGCACHE="$${XDG_CACHE_HOME:-/tmp/xdg-cache-spline}"; \
	mkdir -p "$$MPLCFG"; \
	mkdir -p "$$XDGCACHE"; \
	EXTRA_ARGS=""; \
	if [ -n "$${DEVICE_RESULTS:-}" ]; then \
	  IFS=','; set -- $$DEVICE_RESULTS; \
	  for item in "$$@"; do EXTRA_ARGS="$$EXTRA_ARGS --device-result $$item"; done; \
	fi; \
	if [ -n "$${DEVICE_RESULTS_DIR:-}" ]; then EXTRA_ARGS="$$EXTRA_ARGS --device-results-dir $${DEVICE_RESULTS_DIR}"; fi; \
	eval "MPLCONFIGDIR=$$MPLCFG XDG_CACHE_HOME=$$XDGCACHE python3 scripts/edge_release_gate.py \
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
