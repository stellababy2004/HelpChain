"""Execute release-gate ref and publication contracts without network access."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
if os.name == "nt":
    BASH = str(
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
    )


def step_script(filename, name):
    source = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
    step = source.split(f"      - name: {name}\n", 1)[1].split("\n      - name:", 1)[0]
    return textwrap.dedent(step.split("        run: |\n", 1)[1])


@unittest.skipUnless(BASH and Path(BASH).exists(), "bash is required")
class GateWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = dict(
            os.environ,
            GIT_AUTHOR_NAME="Gate test",
            GIT_AUTHOR_EMAIL="gate@example.test",
            GIT_COMMITTER_NAME="Gate test",
            GIT_COMMITTER_EMAIL="gate@example.test",
        )
        self.env.pop("PYTHONHOME", None)
        self.env["GATE_TEST_PYTHON"] = Path(sys.executable).as_posix()
        self.git("init", "-b", "main")
        baseline = self.root / "docs/security/security-release-gate-baseline.json"
        baseline.parent.mkdir(parents=True)
        baseline.write_text('{"version": 1}\n', encoding="utf-8")
        self.git("add", "docs/security/security-release-gate-baseline.json")
        self.git("commit", "-m", "initial trusted base")
        self.old = self.git("rev-parse", "HEAD")
        self.git("commit", "--allow-empty", "-m", "advanced trusted base")
        self.base = self.git("rev-parse", "HEAD")
        tree = self.git("rev-parse", "HEAD^{tree}")
        self.head = self.git("commit-tree", tree, "-p", self.old, "-m", "PR head")
        self.merge = self.git(
            "commit-tree", tree, "-p", self.base, "-p", self.head, "-m", "PR merge"
        )
        self.git("checkout", "--detach", self.merge)
        self.git("remote", "add", "origin", ".")
        self.pr = {
            "number": 211,
            "state": "open",
            "head": {"sha": self.head},
            "base": {
                "sha": self.old,
                "ref": "main",
                "repo": {"full_name": "owner/HelpChain"},
            },
            "merge_commit_sha": self.merge,
        }
        self.env.update(
            EVENT_HEAD_SHA=self.merge,
            EVENT_PR_HEAD_SHA=self.head,
            EVENT_BASE_SHA=self.old,
            EVENT_NAME="pull_request",
            DEFAULT_BRANCH="main",
            PR_NUMBER="211",
            GITHUB_REPOSITORY="owner/HelpChain",
            GITHUB_OUTPUT="outputs.txt",
        )

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args],
            cwd=self.root,
            env=self.env,
            stderr=subprocess.PIPE,
            text=True,
        ).strip()

    def report(self):
        self.env["TEST_PR_JSON"] = json.dumps(self.pr)
        script = step_script(
            "security-release-gate.yml", "Resolve trusted PR SHAs and baseline"
        )
        return subprocess.run(
            [
                BASH,
                "--noprofile",
                "--norc",
                "-c",
                'gh() { printf "%s\\n" "$TEST_PR_JSON"; }\npython() { "$GATE_TEST_PYTHON" "$@"; }\n'
                + script,
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
        )

    def test_advancing_base_uses_verified_parent_baseline(self):
        result = self.report()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"base_sha={self.base}", (self.root / "outputs.txt").read_text())
        self.assertEqual(
            json.loads((self.root / "trusted-baseline.json").read_text()),
            {"version": 1},
        )

    def test_current_base_and_verified_merge(self):
        self.env["EVENT_BASE_SHA"] = self.base
        result = self.report()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_invalid_current_base_snapshot_fails(self):
        self.pr["base"]["sha"] = "invalid"
        self.assertNotEqual(self.report().returncode, 0)

    def test_changed_pr_head_fails(self):
        self.pr["head"]["sha"] = self.old
        self.assertNotEqual(self.report().returncode, 0)
        self.assertFalse((self.root / "outputs.txt").exists())

    def test_wrong_second_parent_fails(self):
        self.env["EVENT_PR_HEAD_SHA"] = self.old
        self.assertNotEqual(self.report().returncode, 0)

    def test_untrusted_first_parent_fails(self):
        self.git("update-ref", "refs/heads/main", self.old)
        self.assertNotEqual(self.report().returncode, 0)

    def test_invalid_event_sha_fails(self):
        self.env["EVENT_BASE_SHA"] = "invalid"
        self.assertNotEqual(self.report().returncode, 0)

    def test_resolution_failure_cannot_publish_successful_check(self):
        script = step_script(
            "security-release-gate-trusted.yml", "Publish PR-head security check"
        )
        self.env.update(
            REFS_STATUS="failure", REPORT_STATUS="success", HEAD_SHA=self.head
        )
        result = subprocess.run(
            [
                BASH,
                "--noprofile",
                "--norc",
                "-c",
                "gh() { echo called >> gh-called; }\n" + script,
            ],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PR identity resolution failed", result.stdout)
        self.assertFalse((self.root / "gh-called").exists())

    def test_invalid_validated_sha_cannot_publish(self):
        script = step_script(
            "security-release-gate-trusted.yml", "Publish PR-head security check"
        )
        self.env.update(REFS_STATUS="success", REPORT_STATUS="success", HEAD_SHA="")
        result = subprocess.run(
            [BASH, "--noprofile", "--norc", "-c", script],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing or invalid validated PR head SHA", result.stdout)


if __name__ == "__main__":
    unittest.main()
