# Docs Consistency Report — Stream B (historical/tracker debt)

Date: 2026-02-20 (KST)
Scope: historical/tracker docs consistency cleanup (docs-only)

## 1) What was scanned
- Phase PM trackers (`PHASE1~5_PM_TRACKER.md`, `GUI_PHASE1~3_PM_TRACKER.md`)
- Historical planning doc (`BLUEPRINT.md`)
- Cross-check baseline: `docs/RUNBOOK.md` and current runner/script paths

## 2) Changes made

### A. Explicit historical labeling added
To prevent operational confusion while preserving chronology, an explicit historical note was added at the top of:
- `docs/BLUEPRINT.md`
- `docs/PHASE1_PM_TRACKER.md`
- `docs/PHASE2_PM_TRACKER.md`
- `docs/PHASE3_PM_TRACKER.md`
- `docs/PHASE4_PM_TRACKER.md`
- `docs/PHASE5_PM_TRACKER.md`
- `docs/GUI_PHASE1_PM_TRACKER.md`
- `docs/GUI_PHASE2_PM_TRACKER.md`
- `docs/GUI_PHASE3_PM_TRACKER.md`

Historical note states that current operational truth is in `docs/RUNBOOK.md` + latest ARCH/FINAL/CLOSEOUT docs.

### B. Stale contract/path references normalized (without deleting history)
1. `docs/PHASE2_PM_TRACKER.md`
   - Updated stale model artifact wording:
     - historical: `artifacts/models/{run_id}/model.keras`
     - current: `artifacts/checkpoints/{run_id}/best.keras`, `last.keras`
   - Kept original timeline intent, but clarified old-vs-current contract inline.

2. `docs/BLUEPRINT.md`
   - Artifact section now explicitly tags `.pt` references as historical draft.
   - Added current checkpoint contract (`best.keras`, `last.keras`).
   - Added implementation note pointing to current executable paths:
     `src/preprocessing/smoke.py`, `src/training/runner.py`, `scripts/run_e2e.sh`, `scripts/smoke_test.sh`.

## 3) Contradiction risk status
- High-risk contradiction source (old PM states like NOT DONE/PENDING) is now reduced by historical banners.
- Phase tracker status text remains intact for chronology, but no longer reads as current ops guidance.

## 4) Remaining debt (not edited in this pass)
1. PM tracker files without historical banner (currently):
   - `docs/E2E_EXECUTION_PM_TRACKER.md`
   - `docs/GUI_PHASE4_PM_TRACKER.md`
   - `docs/GUI_PHASE5_PM_TRACKER.md`
   (These appear more final/current, but can be similarly labeled if policy is to mark all trackers as historical snapshots.)

2. Additional historical result/review docs may still contain period-specific contract assumptions. They are lower risk than PM trackers but could be batch-labeled in a follow-up sweep.

## 5) Net effect
- Preserved historical chronology.
- Reduced operator confusion by clearly separating historical snapshots from current operational source-of-truth docs.
- Normalized the most obvious stale artifact contract references that conflicted with current implementation.
