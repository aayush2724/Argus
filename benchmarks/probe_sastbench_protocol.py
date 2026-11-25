#!/usr/bin/env python3
"""Probe the pinned SastBench task offline; this is not an evaluator smoke test."""

import argparse
import importlib.util
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

PIN = "b8d95b7720491b21d039b7504999577ba7ebb12b"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="Pinned SastBench checkout")
    args = parser.parse_args()

    # Refuse a different version rather than silently claiming protocol parity.
    import subprocess

    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=args.checkout, text=True
    ).strip()
    if revision != PIN:
        parser.error(f"expected {PIN}, got {revision}")

    class Celery:
        def __init__(self, *_args, **_kwargs):
            pass

        def config_from_object(self, _config):
            pass

        def task(self, **_kwargs):
            return lambda function: function

    celery = types.ModuleType("celery")
    celery.Celery = Celery
    utils = types.ModuleType("utils")
    spec = importlib.util.spec_from_file_location(
        "sastbench_tasks_probe", args.checkout / "evaluation" / "tasks.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load SastBench task")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"celery": celery, "utils": utils}):
        spec.loader.exec_module(module)

    calls = []
    findings = [
        {"finding_id": "a", "ground_truth": "true_positive", "to_analyzer": {"id": "a"}},
        {"finding_id": "b", "ground_truth": "false_positive", "to_analyzer": {"id": "b"}},
    ]

    def post(url, payload, timeout_seconds):
        calls.append((url.rsplit("/", 1)[-1], payload))
        if url.endswith("/preprocess"):
            return {"status": "success"}
        return {"prediction": "true_positive", "confidence": 0.5}

    with tempfile.TemporaryDirectory(prefix="argus-sastbench-probe-") as tmp:
        root = Path(tmp)
        worktree = root / "worktree"
        worktree.mkdir()
        replacements = {
            "setup_git_worktree": lambda *_: worktree,
            "get_processed_data_id": lambda *_: "fixture",
            "start_rest_container": lambda *_args, **_kwargs: {
                "base_url": "http://fixture", "project_name": "fixture", "container_id": "fixture"
            },
            "wait_for_http": lambda *_args, **_kwargs: True,
            "post_json": post,
            "get_processed_data_cache_dir": lambda: root / "cache",
            "stop_rest_container": lambda *_args: None,
        }
        with patch.multiple(utils, create=True, **replacements), patch.dict(
            "os.environ", {}, clear=True
        ):
            task = types.SimpleNamespace(update_state=lambda **_kwargs: None)
            result = module.process_commit(task, "fixture-repo", "abc", findings, str(root))

    assert result["status"] == "success", result
    assert [name for name, _ in calls] == ["preprocess", "analyze", "analyze"], calls
    assert [payload["finding_data"] for _, payload in calls[1:]] == [
        item["to_analyzer"] for item in findings
    ]
    assert all("ground_truth" not in payload for _, payload in calls[1:])
    assert [item["is_correct"] for item in result["results"]] == [True, False]
    print(f"PASS {PIN}: one preprocess, two payloads, and label-based correctness")
    print("Offline mocked task probe only; Docker, grouping, isolation and official smoke remain untested.")


if __name__ == "__main__":
    main()
