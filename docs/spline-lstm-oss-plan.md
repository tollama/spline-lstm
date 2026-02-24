# OSS Release Quality Improvement Plan — spline-lstm

## Context

**spline-lstm** is an ML time-series forecasting project combining spline preprocessing with LSTM neural networks. It includes a Python pipeline (`src/`), FastAPI backend, and React UI. Code quality is solid (good type hints, 106 tests, clean architecture), but the repository has significant hygiene and packaging gaps that prevent a credible public OSS release:

- **2,269 files that shouldn't be tracked** (1,541 in `ui/node_modules`, 657 in `artifacts/`, 21 in `checkpoints/`, 50 in `logs/`, 8 `.DS_Store` files)
- No LICENSE file, CONTRIBUTING guide, or CI/CD
- Not installable as a Python package (no `pyproject.toml`)
- 5 unused dependencies in `requirements.txt`
- No linter/formatter configuration

---

## Phase A: Repository Cleanup (Critical)

**Goal:** Remove ~2,270 tracked files that should be gitignored.

### A1. Update `.gitignore`

Add missing entries to `.gitignore`:

```
backend/data/jobs_store.json
backend/data/jobs_store.json.lock
**/.DS_Store
```

### A2. Untrack files already covered by `.gitignore`

```bash
git rm -r --cached ui/node_modules/
git rm -r --cached ui/dist/
git rm -r --cached artifacts/
git rm -r --cached checkpoints/
git rm -r --cached logs/
git rm --cached .DS_Store artifacts/.DS_Store artifacts/checkpoints/.DS_Store backend/.DS_Store checkpoints/.DS_Store data/.DS_Store src/.DS_Store ui/.DS_Store
git rm --cached backend/data/jobs_store.json backend/data/jobs_store.json.lock
```

### A3. Squash to clean initial commit

With only 15 commits and 33 MB in `.git`, squash all history into a single "Initial public release" commit. This gives a clean slate for the public repo and drops 33 MB of dead artifact blobs from history.

```bash
# After completing A1 and A2:
git reset --soft $(git rev-list --max-parents=0 HEAD)
git commit -m "Initial public release"
git push --force origin main
```

**Files to modify:** `.gitignore`

---

## Phase B: OSS Essentials

**Goal:** Add standard files every public OSS project needs.

| File                                        | Action                                                            |
| ------------------------------------------- | ----------------------------------------------------------------- |
| `LICENSE`                                   | Create MIT license file (currently claimed in README but missing) |
| `CONTRIBUTING.md`                           | Dev setup, running tests, code style, PR process                  |
| `CHANGELOG.md`                              | Initialize with current feature set as v0.1.0                     |
| `CODE_OF_CONDUCT.md`                        | Adopt Contributor Covenant v2.1                                   |
| `SECURITY.md`                               | Vulnerability reporting process                                   |
| `.github/ISSUE_TEMPLATE/bug_report.md`      | Bug report template                                               |
| `.github/ISSUE_TEMPLATE/feature_request.md` | Feature request template                                          |
| `.github/PULL_REQUEST_TEMPLATE.md`          | PR checklist template                                             |

---

## Phase C: Packaging & Dependencies

**Goal:** Make the project pip-installable and clean up deps.

### C1. Create `pyproject.toml`

- Build system: setuptools
- Package name: `spline-lstm`, version `0.1.0`
- `requires-python = ">=3.10,<3.12"`
- Core deps: numpy, scipy, pandas, tensorflow, matplotlib, tqdm, pyyaml
- Optional groups: `[backend]` (fastapi, uvicorn), `[dev]` (pytest, ruff, mypy, pre-commit)
- Console script entry point: `spline-lstm = "src.training.runner:main"`
- Ruff + mypy tool config (see Phase E)

### C2. Clean `requirements.txt`

Remove 5 unused dependencies:

- `torch>=2.0.0` — zero imports in `src/`, PyTorch fallback was removed
- `paho-mqtt>=1.6.0` — zero imports anywhere
- `seaborn>=0.12.0` — zero imports in `src/`
- `jupyter>=1.0.0` — dev tool, not a runtime dep
- `httpx>=0.27.0` — zero imports in `src/`

Keep `requirements.txt` as a flat convenience mirror of `pyproject.toml` core deps.

### C3. Add `__version__` to `src/__init__.py`

```python
__version__ = "0.1.0"
```

### C4. Fix `examples/train_example.py`

Replace `sys.path.insert` hack with proper package imports (works after `pip install -e .`).

**Files to modify:** `pyproject.toml` (new), `requirements.txt`, `src/__init__.py`, `examples/train_example.py`

---

## Phase D: CI/CD — GitHub Actions

**Goal:** Automated quality gates on every push/PR.

### D1. `.github/workflows/ci.yml`

Three jobs:

1. **Lint & Type Check** (fast, no TF needed)
   
   - `ruff check src/ tests/`
   - `ruff format --check src/ tests/`
   - `mypy src/`

2. **Test** (needs TF)
   
   - `pip install -e ".[dev]"`
   - `pytest tests/ -v --tb=short`

3. **Smoke Gate** (integration)
   
   - `pip install -e ".[dev,backend]"`
   - `make smoke-gate`

### D2. `.github/workflows/ui.yml` (optional)

- `cd ui && npm ci && npm run test && npm run build`

### D3. Add CI badge to README

**Files to create:** `.github/workflows/ci.yml`, `.github/workflows/ui.yml`

---

## Phase E: Code Quality Tooling

**Goal:** Enforce consistent style and catch bugs automatically.

### E1. Ruff config (in `pyproject.toml`)

```toml
[tool.ruff]
target-version = "py310"
line-length = 120
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]
```

### E2. Mypy config (in `pyproject.toml`)

```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
ignore_missing_imports = true
```

### E3. Pre-commit hooks (`.pre-commit-config.yaml`)

- ruff (lint + format)
- trailing-whitespace, end-of-file-fixer, check-yaml
- `check-added-large-files --maxkb=500` (prevents future artifact commits)
- `detect-private-key`

### E4. Initial formatting pass

Run `ruff format` and `ruff check --fix` across `src/` and `tests/` as a single commit.

### E5. Extend Makefile

Add targets: `lint`, `format`, `type-check`, `ci-gate`

**Files to modify:** `pyproject.toml`, `Makefile`
**Files to create:** `.pre-commit-config.yaml`

---

## Execution Order

```
A (repo cleanup) → B (OSS essentials) → C (packaging) + E (tooling) in parallel → D (CI/CD)
```

---

## Deferred (Future Phases)

These are out of scope for this round but documented for follow-up:

- **Phase F: Documentation refinement** — Rewrite README for external users, reorganize 123 docs files, clean root dir, translate Korean runbook
- **Phase G: Optional improvements** — Backend modularization (1,283-line main.py), `py.typed` marker, Dockerfile, enhanced logging

---

## Verification

After all phases:

1. `git clone` from scratch — verify repo is <5 MB, no artifacts/node_modules
2. `pip install -e ".[dev,backend]"` — verify clean install
3. `make ci-gate` — lint + type-check + full tests pass
4. `make smoke-gate` — E2E integration passes
5. `ruff check src/ tests/` — zero violations
6. Verify LICENSE, CONTRIBUTING, CHANGELOG, CODE_OF_CONDUCT exist at root
7. GitHub Actions green on push
8. README renders well on GitHub with badges, quick start, and no internal jargon
