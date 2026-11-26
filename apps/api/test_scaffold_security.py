"""Read-only guards for the initial API scaffold."""
import json
from pathlib import Path
import unittest


API = Path(__file__).resolve().parent
SCRIPTS = {
    "build": "tsc",
    "typecheck": "tsc --noEmit",
    "start": "node dist/index.js",
}
PLACEHOLDER = (
    "// API and worker implementation will be added in later milestones.\n"
    "export {};\n"
)


class ScaffoldSecurityTests(unittest.TestCase):
    def test_extensionless_bootstrap_is_absent(self):
        init = API / "init"
        self.assertFalse(init.exists() or init.is_symlink())

    def test_package_scripts_have_no_unreviewed_hooks(self):
        package = json.loads((API / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["scripts"], SCRIPTS)

    def test_scaffold_entrypoint_has_no_executable_bootstrap(self):
        source = (API / "src" / "index.ts").read_text(encoding="utf-8")
        self.assertEqual(source, PLACEHOLDER)


if __name__ == "__main__":
    unittest.main()
