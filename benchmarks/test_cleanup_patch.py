"""Offline verification of the proposed pinned-upstream startup cleanup patch."""

import ast
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
UPSTREAM = Path('/tmp/argus-sastbench-m0')
PIN = 'b8d95b7720491b21d039b7504999577ba7ebb12b'


class CleanupPatchTests(unittest.TestCase):
    def test_pinned_patch_eliminates_startup_inventory_and_deletion(self):
        if not (UPSTREAM / 'evaluation/evaluation_cli.py').exists():
            self.skipTest('pinned upstream checkout unavailable at /tmp/argus-sastbench-m0')
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=UPSTREAM, text=True).strip()
        self.assertEqual(revision, PIN)
        original = (UPSTREAM / 'evaluation/evaluation_cli.py').read_bytes()
        committed = subprocess.check_output(['git', 'show', f'{PIN}:evaluation/evaluation_cli.py'], cwd=UPSTREAM)
        self.assertEqual(original, committed, 'upstream CLI must match the pinned source')
        with tempfile.TemporaryDirectory(prefix='argus-patch-test-') as tmp:
            source = Path(tmp) / 'evaluation/evaluation_cli.py'
            source.parent.mkdir()
            source.write_bytes(original)
            subprocess.run(['patch', '-p1', '--batch', '-i', str(ROOT / 'sastbench-disable-global-cleanup.patch')],
                           cwd=tmp, check=True, capture_output=True)
            tree = ast.parse(source.read_text())
        runner = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'EvaluationRunner')
        method = next(node for node in runner.body if isinstance(node, ast.FunctionDef) and node.name == 'run_evaluation')
        calls = {node.func.attr for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                 and node.func.value.id == 'utils'}
        # Neither global selector runs, regardless of container/network/volume inventory.
        self.assertNotIn('cleanup_orphaned_docker_networks', calls)
        self.assertNotIn('cleanup_neo4j_containers', calls)
        self.assertIn('check_docker_available', calls)


if __name__ == '__main__':
    unittest.main()
