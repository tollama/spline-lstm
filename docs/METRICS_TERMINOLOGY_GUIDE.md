# Metrics & Covariate Terminology Guide (Lint Checklist)

This one-page guide standardizes wording in `README.md`, `docs/`, and `runbook/`.

## 1) Canonical Metric Names

Use these exact forms:

- `MAE`
- `MSE`
- `RMSE`
- `robust MAPE`
- `R2`

### Extended metric (when explicitly supported)

- `MASE` (currently trainer-path only)

### Canonical display order

- Runner/ops docs: `MAE, MSE, RMSE, robust MAPE, R2`
- Trainer-extended docs: `MAE, MSE, RMSE, robust MAPE, MASE, R2`

---

## 2) Forbidden / Legacy Variants

Replace these variants when found in formal metric lists, table headers, and contracts:

- `MAPE(robust)` → `robust MAPE`
- `mape(robust)` → `robust MAPE`
- `mase` (metric token) → `MASE`
- `R²` → `R2`
- Mixed metric ordering (e.g., `RMSE, MAE, ...`) → canonical order

> Note: In narrative prose, generic mentions may remain if they are not formal metric identifiers.

---

## 3) Covariate Terminology Rules

- Prefer `covariate` / `covariates` consistently in English sections.
- Keep actual CLI flags unchanged when referenced:
  - `--covariate-cols`
  - `--covariate-spec`
- Do not rename flags in docs for style reasons.

---

## 4) Copy-Paste Templates

### Runner metric list sentence

```text
평가 지표: MAE, MSE, RMSE, robust MAPE, R2
```

### Trainer-extended metric list sentence

```text
평가 지표: MAE, MSE, RMSE, robust MAPE, MASE, R2
```

### Table header (runner)

```text
| MAE | MSE | RMSE | robust MAPE | R2 |
```

### Table header (trainer-extended)

```text
| MAE | MSE | RMSE | robust MAPE | MASE | R2 |
```

---

## 5) Quick Lint Commands (Manual)

Run from project root:

```bash
grep -RIn "MAPE(robust)\|mape(robust)" README.md docs/ runbook/
grep -RIn "\bR²\b" README.md docs/ runbook/
grep -RIn "\bmase\b" README.md docs/ runbook/
```

If results appear in formal metric sections, normalize to the appropriate canonical list.

---

## 6) Scope & Non-Goals

- Scope: `README.md`, `docs/`, `runbook/` terminology consistency.
- Non-goal: changing model logic, formulas, or source code behavior.
