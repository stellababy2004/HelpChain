"""Offline regression coverage for trusted PR identity and scan provenance."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "gate_collect", Path(__file__).resolve().parents[1] / "scripts/security_release_gate_collect.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
HEAD = "5689fc321215170402930a5f567b116bdba52f2d"
MERGE = "55c17ce817c2c211f2813586673f509360cf5679"
BASE = "a" * 40
REPO = "owner/HelpChain"


class Client:
    repository = REPO

    def __init__(self, run, pr):
        self.run = run
        self.pr = pr
        self.candidates = [{"number": 214}]
        self.commit = {"sha": MERGE, "parents": [{"sha": BASE}, {"sha": HEAD}]}

    def get(self, path):
        if path == "pulls/214":
            return copy.deepcopy(self.pr)
        if path == f"commits/{MERGE}":
            return self.commit
        raise AssertionError(path)

    def get_paginated(self, path, key):
        if path == f"commits/{self.run['head_sha']}/pulls" and key == "pulls":
            return self.candidates
        raise AssertionError(path)


class TrustedIdentityTests(unittest.TestCase):
    def setUp(self):
        self.run = {"id": 43246159695, "workflow_id": 12, "run_attempt": 1,
                    "repository": {"full_name": REPO},
                    "head_repository": {"full_name": REPO},
                    "event": "pull_request", "status": "completed",
                    "conclusion": "success", "head_sha": HEAD, "pull_requests": []}
        self.pr = {"number": 214, "state": "open", "merged": False,
                   "head": {"sha": HEAD, "repo": {"full_name": REPO}},
                   "base": {"sha": BASE, "repo": {"full_name": REPO}},
                   "merge_commit_sha": MERGE}
        self.client = Client(self.run, self.pr)

    def resolve(self):
        return gate.resolve_pr_identity(self.client, self.run)

    def test_normal_pr(self):
        self.run["pull_requests"] = [{"number": 214}]
        self.assertEqual(self.resolve()["pr_head_sha"], HEAD)

    def test_empty_array_fallback(self):
        self.assertEqual(self.resolve()["scanned_sha"], HEAD)

    def test_open_merge_commit(self):
        self.run["head_sha"] = MERGE
        identity = self.resolve()
        self.assertEqual(identity, {"pr_number": 214, "pr_head_sha": HEAD,
                                    "scanned_sha": MERGE, "base_sha": BASE})

    def test_merged_pr_uses_first_parent_as_baseline(self):
        self.run["head_sha"] = MERGE
        self.pr.update(state="closed", merged=True)
        self.pr["base"]["sha"] = MERGE
        self.assertEqual(self.resolve()["base_sha"], BASE)

    def test_closed_unmerged_pr(self):
        self.pr["state"] = "closed"
        with self.assertRaises(gate.GitHubApiError):
            self.resolve()

    def test_mismatched_sha(self):
        self.run["head_sha"] = "b" * 40
        with self.assertRaises(gate.GitHubApiError):
            self.resolve()

    def test_stale_head(self):
        self.pr["head"]["sha"] = "b" * 40
        with self.assertRaises(gate.GitHubApiError):
            self.resolve()

    def test_missing_pr(self):
        self.client.candidates = []
        with self.assertRaises(gate.GitHubApiError):
            self.resolve()

    def test_ambiguous_pr(self):
        self.client.candidates *= 2
        with self.assertRaises(gate.GitHubApiError):
            self.resolve()

    def test_failed_scanner(self):
        for conclusion in ("failure", "cancelled", "timed_out", None):
            with self.subTest(conclusion=conclusion):
                self.run["conclusion"] = conclusion
                with self.assertRaises(gate.GitHubApiError):
                    self.resolve()

    def test_wrong_merge_parents(self):
        self.run["head_sha"] = MERGE
        for parents in ([HEAD, BASE], [BASE], ["b" * 40, HEAD], [BASE, "b" * 40]):
            with self.subTest(parents=parents):
                self.client.commit["parents"] = [{"sha": sha} for sha in parents]
                with self.assertRaises(gate.GitHubApiError):
                    self.resolve()

    def test_wrong_repository(self):
        self.pr["head"]["repo"]["full_name"] = "other/repo"
        with self.assertRaises(gate.GitHubApiError):
            self.resolve()

    def test_codeql_evidence_requires_actual_scanned_sha(self):
        self.run["head_sha"] = MERGE
        original = self.client.get_paginated
        analysis = {"id": 99, "commit_sha": HEAD, "tool": {"name": "CodeQL"},
                    "ref": "refs/pull/214/merge",
                    "analysis_key": ".github/workflows/codeql-analysis.yml:analyze",
                    "category": "python", "error": ""}

        def pages(path, key):
            if key == "analyses":
                return [analysis]
            if key == "alerts":
                return []
            return original(path, key)

        self.client.get_paginated = pages
        result = gate.collect_codeql_analysis(
            self.client, run=self.run, head_sha=MERGE, repository=REPO
        )
        self.assertFalse(result["status"]["report_valid"])
        analysis["commit_sha"] = MERGE
        result = gate.collect_codeql_analysis(
            self.client, run=self.run, head_sha=MERGE, repository=REPO
        )
        self.assertTrue(result["status"]["report_valid"])
        self.assertEqual(result["status"]["head_sha"], MERGE)

    def test_stale_attached_pr_snapshot(self):
        self.run["pull_requests"] = [{"number": 214, "head": {"sha": "b" * 40}}]
        with self.assertRaises(gate.GitHubApiError):
            self.resolve()

    def test_collector_uses_merge_sha_for_artifacts(self):
        self.run["head_sha"] = MERGE
        self.run["created_at"] = "2026-11-12T12:00:00Z"
        original = self.client.get_paginated

        def pages(path, key):
            if key == "workflows":
                return [{"id": 12, "name": "Secret Scan"}]
            if key == "workflow_runs":
                self.assertIn(f"head_sha={MERGE}", path)
                return [self.run]
            return original(path, key)

        self.client.get_paginated = pages
        with patch.object(gate, "discover_run_artifact", return_value={"id": 99}) as discover:
            with patch.object(gate, "download_and_validate_artifact",
                              return_value={"valid": True, "findings": []}) as download:
                result = gate.collect_required_evidence(
                    self.client, head_sha=MERGE, base_sha=BASE,
                    repository=REPO, temp_root=Path("unused")
                )
        self.assertEqual(discover.call_args.kwargs["expected_head_sha"], MERGE)
        self.assertEqual(download.call_args.kwargs["head_sha"], MERGE)
        self.assertEqual(result["statuses"][-1]["head_sha"], MERGE)

    def test_failed_latest_scanner_cannot_reuse_success(self):
        self.run["created_at"] = "2026-11-12T12:00:00Z"
        failed = copy.deepcopy(self.run)
        failed.update(id=self.run["id"] + 1, conclusion="failure",
                      created_at="2026-11-12T13:00:00Z",
                      updated_at="2026-11-12T13:00:00Z")

        def pages(path, key):
            if key == "workflows":
                return [{"id": 12, "name": "Secret Scan"}]
            if key == "workflow_runs":
                return [self.run, failed]
            raise AssertionError(path)

        self.client.get_paginated = pages
        with patch.object(gate, "discover_run_artifact") as discover:
            result = gate.collect_required_evidence(
                self.client, head_sha=HEAD, base_sha=BASE,
                repository=REPO, temp_root=Path("unused")
            )
        discover.assert_not_called()
        self.assertEqual(result["statuses"][-1]["status"], "incomplete")
        self.assertFalse(result["statuses"][-1]["report_valid"])

    def test_validate_run_distinguishes_scanned_and_head(self):
        self.run["head_sha"] = MERGE
        result = gate.validate_workflow_run(
            self.run, self.pr, repository=REPO, workflow_id=12,
            run_id=43246159695, run_attempt=1, pr_number=214,
            head_sha=HEAD, base_sha=BASE, scanned_sha=MERGE,
            scanned_commit=self.client.commit,
        )
        self.assertTrue(result["valid"], result)
        result = gate.validate_workflow_run(
            self.run, self.pr, repository=REPO, workflow_id=12,
            run_id=43246159695, run_attempt=1, pr_number=214,
            head_sha=HEAD, base_sha=BASE,
        )
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
