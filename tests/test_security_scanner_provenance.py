"""Regression fixtures reproduce PR216 API and checkout log shapes from run 43272883546."""

import copy
import hashlib
import io
import json
import tempfile
import zipfile
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "provenance_collector",
    Path(__file__).resolve().parents[1] / "scripts/security_release_gate_collect.py",
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
HEAD = "c2777e99215f470b694eda8acf031d4d0f3795bc"
BASE = "3017d312a32a71b33adfabd6b77452bf13dd9b45"
MERGE = "0c096470bb4207f589383a446261f77ad16c6d2d"
REPO = "stellababy2004/HelpChain"
CHECKOUT = "11bd71901bbe5b1630ceea73d27597364c9af683"


class ApiFixture:
    repository = REPO

    def __init__(self):
        self.pr = {
            "number": 216,
            "state": "open",
            "merged": False,
            "head": {
                "sha": HEAD,
                "ref": "fix/trusted-gate-pr-context-20261112",
                "repo": {"full_name": REPO},
            },
            "base": {"sha": BASE, "ref": "main", "repo": {"full_name": REPO}},
            "merge_commit_sha": MERGE,
        }
        self.commit = {"sha": MERGE, "parents": [{"sha": BASE}, {"sha": HEAD}]}
        definitions = [
            (
                "CodeQL Advanced Security",
                196169671,
                43272899532,
                "codeql-analysis.yml",
                ["Analyze (python)"],
            ),
            (
                "Trivy Security Scan",
                196169672,
                43272899649,
                "trivy-scan.yml",
                ["Trivy IaC Scan", "Trivy Repository Scan"],
            ),
            (
                "Security Scans (Bandit & pip-audit)",
                196169238,
                43272899640,
                "security-scans.yml",
                ["Bandit (SAST)", "pip-audit (Dependencies)"],
            ),
            ("Secret Scan", 243857287, 43272899156, "secret-scan.yml", ["scan"]),
        ]
        self.workflows = []
        self.runs = {}
        self.jobs = {}
        self.logs = {}
        self.artifacts = {}
        self.sources = {}
        self.archives = {}
        for name, workflow_id, run_id, filename, job_names in definitions:
            path = ".github/workflows/" + filename
            self.workflows.append({"id": workflow_id, "name": name, "path": path})
            self.runs[run_id] = {
                "id": run_id,
                "name": name,
                "path": path,
                "workflow_id": workflow_id,
                "run_attempt": 1,
                "event": "pull_request",
                "status": "completed",
                "conclusion": "success",
                "head_sha": HEAD,
                "head_branch": self.pr["head"]["ref"],
                "repository": {"full_name": REPO},
                "head_repository": {"full_name": REPO},
                "updated_at": "2026-11-12T17:49:08Z",
                "pull_requests": [
                    {"number": 216, "head": {"sha": HEAD}, "base": {"sha": BASE}}
                ],
            }
            self.sources[(path, BASE)] = {"type": "file", "path": path, "sha": "d" * 40}
            self.sources[(path, MERGE)] = copy.deepcopy(self.sources[(path, BASE)])
            self.sources[(path, HEAD)] = copy.deepcopy(self.sources[(path, BASE)])
            self.jobs[run_id] = []
            self.artifacts[run_id] = []
            for index, job_name in enumerate(job_names):
                job_id = run_id * 10 + index
                steps = [
                    {
                        "name": (
                            "Checkout repository"
                            if filename == "codeql-analysis.yml"
                            else "Checkout"
                        ),
                        "number": 2,
                        "status": "completed",
                        "conclusion": "success",
                        "started_at": "2026-11-12T17:46:16Z",
                        "completed_at": "2026-11-12T17:46:19Z",
                    },
                    {
                        "name": "Perform CodeQL Analysis",
                        "number": 5,
                        "status": "completed",
                        "conclusion": "success",
                        "started_at": "2026-11-12T17:46:41Z",
                        "completed_at": "2026-11-12T17:49:04Z",
                    },
                ]
                self.jobs[run_id].append(
                    {
                        "id": job_id,
                        "name": job_name,
                        "run_id": run_id,
                        "run_attempt": 1,
                        "run_url": f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}",
                        "head_sha": HEAD,
                        "status": "completed",
                        "conclusion": "success",
                        "steps": steps,
                        "started_at": "2026-11-12T17:46:14Z",
                        "completed_at": "2026-11-12T17:49:06Z",
                    }
                )
                self.logs[job_id] = (
                    f"2026-11-12T17:46:16.6260170Z ##[group]Run actions/checkout@{CHECKOUT}\n"
                    f"2026-11-12T17:46:16.6261924Z   repository: {REPO}\n"
                    f"2026-11-12T17:46:18.4453578Z [command]/usr/bin/git checkout --progress --force refs/remotes/pull/216/merge\n"
                    f"2026-11-12T17:46:19.8864363Z [command]/usr/bin/git log -1 --format=%H\n"
                    f"2026-11-12T17:46:19.8903165Z {MERGE}\n"
                    "2026-11-12T17:46:20.9241614Z ##[group]Run scanner\n"
                )
                artifact_specs = gate.EXPECTED_EVIDENCE.get(name, [])
                if artifact_specs:
                    artifact_name = artifact_specs[index][0]
                    artifact_id = job_id + 1
                    self.artifacts[run_id].append(
                        {
                            "id": artifact_id,
                            "name": artifact_name,
                            "expired": False,
                            "digest": "sha256:" + "e" * 64,
                            "created_at": "2026-11-12T17:48:00Z",
                            "updated_at": "2026-11-12T17:48:00Z",
                            "workflow_run": {"id": run_id, "head_sha": HEAD},
                        }
                    )
                    self.logs[
                        job_id
                    ] += f"2026-11-12T17:48:00.5632969Z Artifact {artifact_name}.zip successfully finalized. Artifact ID {artifact_id}\n"
                    scanner = artifact_specs[index][1]
                    if scanner == "pip-audit":
                        report = {"dependencies": []}
                        report_name = "report.json"
                    else:
                        report = {
                            "version": "2.1.0",
                            "runs": [
                                {"tool": {"driver": {"name": scanner}}, "results": []}
                            ],
                        }
                        if scanner == "Bandit":
                            report["runs"][0]["results"] = [
                                {
                                    "ruleId": "B101",
                                    "level": "warning",
                                    "locations": [
                                        {
                                            "physicalLocation": {
                                                "artifactLocation": {
                                                    "uri": "sample.py"
                                                },
                                                "region": {"startLine": 2},
                                            }
                                        }
                                    ],
                                }
                            ]
                        report_name = "report.sarif"
                    payload = io.BytesIO()
                    with zipfile.ZipFile(payload, "w") as archive:
                        archive.writestr(
                            zipfile.ZipInfo(report_name), json.dumps(report)
                        )
                    self.archives[artifact_id] = payload.getvalue()
                    self.artifacts[run_id][-1]["digest"] = (
                        "sha256:" + hashlib.sha256(payload.getvalue()).hexdigest()
                    )
        self.analyses = [
            {
                "id": 2154461358,
                "commit_sha": MERGE,
                "ref": "refs/pull/216/merge",
                "analysis_key": ".github/workflows/codeql-analysis.yml:analyze",
                "category": "/language:python",
                "tool": {"name": "CodeQL"},
                "error": "",
                "created_at": "2026-11-12T17:48:56Z",
            }
        ]

    def download_artifact(self, artifact_id, destination):
        destination.write_bytes(self.archives[artifact_id])

    def get(self, path):
        if path == "pulls/216":
            return copy.deepcopy(self.pr)
        if path == f"commits/{MERGE}":
            return copy.deepcopy(self.commit)
        if path.startswith("contents/"):
            filename, ref = path[len("contents/") :].split("?ref=")
            return copy.deepcopy(self.sources[(filename, ref)])
        if path.startswith("actions/workflows/"):
            return next(
                copy.deepcopy(w)
                for w in self.workflows
                if str(w["id"]) == path.split("/")[2]
            )
        if path.startswith("actions/runs/"):
            return copy.deepcopy(self.runs[int(path.split("/")[2])])
        raise AssertionError(path)

    def get_text(self, path):
        return self.logs[int(path.split("/")[2])]

    def get_paginated(self, path, key):
        if key == "pulls":
            return [{"number": 216}]
        if key == "workflows":
            return copy.deepcopy(self.workflows)
        if key == "jobs":
            return copy.deepcopy(self.jobs[int(path.split("/")[2])])
        if key == "artifacts":
            return copy.deepcopy(self.artifacts[int(path.split("/")[2])])
        if key == "workflow_runs":
            workflow_id = int(path.split("/")[2])
            sha = path.split("head_sha=")[1].split("&")[0]
            return [
                copy.deepcopy(r)
                for r in self.runs.values()
                if r["workflow_id"] == workflow_id and r["head_sha"] == sha
            ]
        if key == "analyses":
            return copy.deepcopy(self.analyses)
        if key == "alerts":
            return []
        raise AssertionError((path, key))


class ScannerProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.client = ApiFixture()
        self.run = self.client.runs[43272899532]

    def test_real_api_head_metadata_with_merge_checkout(self):
        identity = gate.resolve_pr_identity(self.client, self.run)
        self.assertEqual(identity["scanned_sha"], MERGE)
        self.assertEqual(identity["pr_head_sha"], HEAD)
        self.assertEqual(identity["workflow_run_head_sha"], HEAD)
        self.assertEqual(identity["scanned_ref"], "refs/pull/216/merge")
        result = gate.collect_codeql_analysis(
            self.client, run=self.run, head_sha=MERGE, repository=REPO
        )
        self.assertTrue(result["status"]["report_valid"], result)
        self.assertEqual(result["status"]["head_sha"], MERGE)

    def collect(self):
        with tempfile.TemporaryDirectory() as root:
            return gate.collect_required_evidence(
                self.client,
                head_sha=MERGE,
                pr_head_sha=HEAD,
                base_sha=BASE,
                repository=REPO,
                temp_root=Path(root),
            )

    def test_all_six_reports_and_findings_use_verified_merge(self):
        result = self.collect()
        self.assertEqual(len(result["statuses"]), 6)
        for status in result["statuses"]:
            self.assertEqual(status["status"], "success", status)
            self.assertTrue(status["report_valid"], status)
            self.assertEqual(status["head_sha"], MERGE)
            self.assertEqual(status["scanned_sha"], MERGE)
            self.assertEqual(status["workflow_run_head_sha"], HEAD)
            self.assertEqual(status["pr_head_sha"], HEAD)
        self.assertTrue(result["findings"])
        self.assertEqual({item["head_sha"] for item in result["findings"]}, {MERGE})

    def assert_identity_rejected(self):
        with self.assertRaises(gate.GitHubApiError):
            gate.resolve_pr_identity(self.client, self.run)

    def test_missing_checkout_evidence(self):
        job_id = self.client.jobs[self.run["id"]][0]["id"]
        self.client.logs[job_id] = ""
        self.assert_identity_rejected()

    def test_ambiguous_checkout_evidence(self):
        job_id = self.client.jobs[self.run["id"]][0]["id"]
        self.client.logs[job_id] *= 2
        self.assert_identity_rejected()

    def test_stale_base_or_head(self):
        for field in ("base", "head"):
            with self.subTest(field=field):
                original = copy.deepcopy(self.client.pr)
                self.client.pr[field]["sha"] = "a" * 40
                self.assert_identity_rejected()
                self.client.pr = original

    def test_wrong_ordered_merge_parents(self):
        self.client.commit["parents"].reverse()
        self.assert_identity_rejected()

    def test_wrong_pr_ref_or_checkout_repository(self):
        job_id = self.client.jobs[self.run["id"]][0]["id"]
        original = self.client.logs[job_id]
        for old, new in [
            ("pull/216/merge", "pull/999/merge"),
            (REPO, "other/repository"),
        ]:
            with self.subTest(new=new):
                self.client.logs[job_id] = original.replace(old, new)
                self.assert_identity_rejected()

    def test_wrong_run_attempt_or_repository(self):
        job = self.client.jobs[self.run["id"]][0]
        job["run_attempt"] = 2
        self.assert_identity_rejected()
        job["run_attempt"] = 1
        self.run["repository"]["full_name"] = "other/repository"
        self.assert_identity_rejected()

    def test_changed_workflow_source(self):
        path = self.run["path"]
        self.client.sources[(path, MERGE)]["sha"] = "a" * 40
        self.assert_identity_rejected()

    def test_conflicting_scanner_job_checkouts(self):
        self.run = self.client.runs[43272899649]
        job_id = self.client.jobs[self.run["id"]][1]["id"]
        self.client.logs[job_id] = self.client.logs[job_id].replace(MERGE, HEAD)
        self.assert_identity_rejected()

    def test_codeql_analysis_from_old_attempt_or_other_ref(self):
        for field, value in [
            ("created_at", "2026-11-12T16:48:56Z"),
            ("ref", "refs/pull/999/merge"),
            ("commit_sha", HEAD),
            ("analysis_key", ".github/workflows/other.yml:analyze"),
        ]:
            with self.subTest(field=field):
                original = copy.deepcopy(self.client.analyses)
                self.client.analyses[0][field] = value
                result = gate.collect_codeql_analysis(
                    self.client, run=self.run, head_sha=MERGE, repository=REPO
                )
                self.assertFalse(result["status"]["report_valid"])
                self.client.analyses = original

    def test_ambiguous_codeql_analyses(self):
        self.client.analyses *= 2
        result = gate.collect_codeql_analysis(
            self.client, run=self.run, head_sha=MERGE, repository=REPO
        )
        self.assertFalse(result["status"]["report_valid"])

    def test_artifact_from_old_attempt_missing_upload_or_wrong_digest(self):
        artifact = self.client.artifacts[43272899649][0]
        for field, value in [
            ("created_at", "2026-11-12T16:48:00Z"),
            ("id", 999),
            ("digest", "sha256:" + "0" * 64),
        ]:
            with self.subTest(field=field):
                original = copy.deepcopy(artifact)
                artifact[field] = value
                result = self.collect()
                status = next(
                    item
                    for item in result["statuses"]
                    if item["name"] == artifact["name"]
                )
                self.assertFalse(status["report_valid"], status)
                artifact.clear()
                artifact.update(original)

    def test_failed_latest_run_is_not_accepted(self):
        self.run["conclusion"] = "failure"
        result = self.collect()
        self.assertFalse(result["statuses"][0]["report_valid"])

    def test_empty_pr_array_uses_real_commit_association(self):
        self.run["pull_requests"] = []
        self.assertEqual(
            gate.resolve_pr_identity(self.client, self.run)["scanned_sha"], MERGE
        )

    def test_multiline_scanner_output_is_not_checkout_evidence(self):
        job_id = self.client.jobs[self.run["id"]][0]["id"]
        self.client.logs[job_id] += "{\n}\n"
        self.assertEqual(
            gate.resolve_pr_identity(self.client, self.run)["scanned_sha"], MERGE
        )
        self.client.logs[job_id] = self.client.logs[job_id].replace(
            f"2026-11-12T17:46:19.8903165Z {MERGE}", MERGE
        )
        self.assert_identity_rejected()

    def test_stale_run_snapshot(self):
        snapshot = copy.deepcopy(self.run)
        self.run["run_attempt"] = 2
        with self.assertRaises(gate.GitHubApiError):
            gate.resolve_pr_identity(self.client, snapshot)

    def test_duplicate_jobs_and_wrong_workflow(self):
        self.client.jobs[self.run["id"]] *= 2
        self.assert_identity_rejected()
        self.client.jobs[self.run["id"]] = self.client.jobs[self.run["id"]][:1]
        self.run["path"] = ".github/workflows/other.yml"
        self.assert_identity_rejected()

    def test_conflicting_artifact_repository_metadata(self):
        self.client.artifacts[43272899649][0]["workflow_run"]["repository_id"] = 999
        result = self.collect()
        status = next(
            item for item in result["statuses"] if item["name"] == "trivy-iac-sarif"
        )
        self.assertFalse(status["report_valid"], status)

    def test_new_failed_run_wins_over_old_successful_rerun(self):
        older = {
            "id": 1,
            "created_at": "2026-11-12T12:00:00Z",
            "updated_at": "2026-11-12T14:00:00Z",
            "run_attempt": 2,
            "conclusion": "success",
        }
        newer = {
            "id": 2,
            "created_at": "2026-11-12T13:00:00Z",
            "updated_at": "2026-11-12T13:10:00Z",
            "run_attempt": 1,
            "conclusion": "failure",
        }
        self.assertEqual(gate.select_latest_run([older, newer])["id"], 2)


if __name__ == "__main__":
    unittest.main()
