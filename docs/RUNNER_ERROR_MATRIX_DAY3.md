# Runner Validation/Error Matrix (Day 3)

## 1) Consume-path validation matrix

| Validation point | Trigger | Error code | Exit code |
|---|---|---|---|
| `processed.npz` required keys (`feature_names`, `target_indices`) | key missing | `ARTIFACT_CONTRACT_ERROR` | 22 |
| `processed.npz` data key for series mode | `scaled` and `raw_target` both absent | `ARTIFACT_CONTRACT_ERROR` | 22 |
| artifacts-style bundle split contract | `split_contract.json` missing | `ARTIFACT_CONTRACT_ERROR` | 22 |
| split contract schema | `schema_version != phase1.split_contract.v1` | `ARTIFACT_CONTRACT_ERROR` | 22 |
| run_id consistency | CLI/path/meta/preprocessor mismatch | `RUN_ID_MISMATCH` | 27 |
| tensor shapes | X/y dimension or batch mismatch | `INPUT_SHAPE_ERROR` | 23 |
| split result sufficiency | empty train/val/test windows | `INSUFFICIENT_DATA_ERROR` | 26 |

## 2) stderr/error payload template

```json
{
  "ok": false,
  "exit_code": 22,
  "error": {
    "code": "ARTIFACT_CONTRACT_ERROR",
    "message": "[ARTIFACT_CONTRACT_ERROR] processed.npz missing required keys: ['feature_names']",
    "type": "ValueError"
  }
}
```

- logger format: `RUNNER_FAILURE code=<exit_code> error_code=<error.code> message=<error.message>`
- CLI failure always prints the JSON payload to stderr before exit.
