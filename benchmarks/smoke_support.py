"""Offline building blocks for a future isolated SastBench smoke test.

These helpers do not start the official CLI or manage Docker resources.
"""

from collections import Counter
from pathlib import Path
import uuid


LABELS = frozenset(("true_positive", "false_positive"))


def run_id():
    return "argus-smoke-" + uuid.uuid4().hex


def clean_environment(home: Path, tmp: Path, path: str):
    """Construct a fresh process environment; never copy the caller's environment."""
    if not home.is_absolute() or not tmp.is_absolute() or not path:
        raise ValueError("absolute private HOME and TMPDIR and an explicit PATH are required")
    return {"HOME": str(home), "TMPDIR": str(tmp), "PATH": path,
            "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1"}


def audit_results(findings, results):
    """Account for every input; never invent labels for unmatched error rows."""
    inputs = {}
    for finding in findings:
        key = finding.get("finding_id")
        if not isinstance(key, str) or not key or key in inputs:
            raise ValueError("missing or duplicate finding_id")
        if finding.get("ground_truth") not in LABELS:
            raise ValueError("invalid ground truth")
        inputs[key] = finding
    by_id = {}
    unassigned = 0
    for result in results:
        key = result.get("finding_id")
        if key is None:
            unassigned += 1
        elif key not in inputs or key in by_id:
            raise ValueError("unknown or duplicate result finding_id")
        else:
            by_id[key] = result
    counts = Counter()
    matrix = Counter()
    for key, finding in inputs.items():
        result = by_id.get(key)
        if result is None:
            counts["missing_result"] += 1
        elif result.get("status") != "success":
            counts["process_error"] += 1
        elif result.get("prediction") not in LABELS:
            counts["invalid_prediction"] += 1
        elif result.get("ground_truth") != finding["ground_truth"]:
            counts["label_mismatch"] += 1
        else:
            counts["eligible"] += 1
            matrix[(finding["ground_truth"], result["prediction"])] += 1
    return {"input_count": len(inputs), "eligible": counts["eligible"],
            "missing_result": counts["missing_result"], "process_error": counts["process_error"],
            "invalid_prediction": counts["invalid_prediction"], "label_mismatch": counts["label_mismatch"],
            "unassigned_error_rows": unassigned,
            "confusion": {f"{truth}:{prediction}": matrix[(truth, prediction)]
                          for truth in sorted(LABELS) for prediction in sorted(LABELS)}}
