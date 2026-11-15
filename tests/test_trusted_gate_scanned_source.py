"""The trusted gate must hash scanned Git content without checking out PR code."""

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "trusted_scanned_context_gate", ROOT / "scripts/security_release_gate.py"
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)

FINDING = {
    "scanner": "CodeQL",
    "rule": "py/url-redirection",
    "path": "backend/helpchain_backend/src/routes/admin.py",
    "line": 2,
}


class ScannedSourceContextTests(unittest.TestCase):
    def test_exact_commit_source_is_used_not_worktree(self):
        scanned_sha = "a" * 40
        with patch.object(
            gate.subprocess,
            "run",
            return_value=SimpleNamespace(
                stdout="unrelated\n    return redirect(target or fallback_url, code=303)\n"
            ),
        ) as run:
            digest = gate.finding_context_digest(FINDING, source_ref=scanned_sha)
        self.assertTrue(digest.startswith("sha256:"))
        run.assert_called_once_with(
            ["git", "show", f"{scanned_sha}:{FINDING['path']}"],
            check=True,
            capture_output=True,
            encoding="utf-8",
        )

    def test_invalid_commit_ref_fails_closed(self):
        with patch.object(gate.subprocess, "run") as run:
            self.assertIsNone(
                gate.finding_context_digest(
                    FINDING, source_ref="main;touch /tmp/unsafe"
                )
            )
        run.assert_not_called()

    def test_missing_scanned_file_fails_closed(self):
        with patch.object(
            gate.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(128, ["git", "show"]),
        ):
            self.assertIsNone(gate.finding_context_digest(FINDING, source_ref="b" * 40))


if __name__ == "__main__":
    unittest.main()
