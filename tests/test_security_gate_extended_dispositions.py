"""Fail-closed regression tests for additional finding dispositions."""

import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "security_release_gate_under_test", ROOT / "scripts/security_release_gate.py"
)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)

REPOSITORY = "stellababy2004/HelpChain"


class ExtendedDispositionTests(unittest.TestCase):
    def setUp(self):
        self.entry = {
            "finding_id": "codeql|py/unused-import|backend/models.py|1",
            "scanner": "CodeQL",
            "rule": "py/unused-import",
            "path": "backend/models.py",
            "line": 1,
            "disposition": "FALSE_POSITIVE",
            "expected_severity": "unclassified",
            "context_digest": "sha256:" + "a" * 64,
            "rationale": "Explicit owner review; test evidence only.",
            "evidence_ref": "docs/security/PR-224-SECURITY-GATE-REVIEW-2026-11-14.md",
            "expires_on": "2027-11-14",
        }
        self.document = {
            "schema_version": 1,
            "repository": REPOSITORY,
            "approval_model": "solo_owner_review",
            "independent_review": False,
            "owner": {
                "login": "stellababy2004",
                "name": "Security reviewer",
                "decision_date": "2026-11-14",
            },
            "dispositions": [self.entry],
        }
        self.finding = {
            "scanner": "CodeQL",
            "rule": "py/unused-import",
            "path": "backend/models.py",
            "line": 1,
            "severity": "unclassified",
        }

    def test_unreviewed_finding_remains_unresolved(self):
        self.document["dispositions"] = []
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            recognized, unresolved, errors = gate.apply_dispositions(
                [self.finding], self.document, repository=REPOSITORY
            )
        self.assertFalse(recognized)
        self.assertTrue(unresolved)
        self.assertTrue(errors)

    def test_additional_review_requires_exact_source_digest(self):
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            recognized, unresolved, errors = gate.apply_dispositions(
                [self.finding], self.document, repository=REPOSITORY
            )
        self.assertFalse(recognized)
        self.assertTrue(unresolved)
        self.assertFalse(errors)

    def test_valid_reviewed_finding_is_recognized(self):
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            with patch.object(
                gate,
                "finding_context_digest",
                return_value=self.entry["context_digest"],
            ):
                with patch.object(Path, "is_file", return_value=True):
                    recognized, unresolved, errors = gate.apply_dispositions(
                        [self.finding], self.document, repository=REPOSITORY
                    )
        self.assertEqual(len(recognized), 1)
        self.assertFalse(unresolved)
        self.assertFalse(errors)

    def test_missing_evidence_document_is_rejected(self):
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            with patch.object(Path, "is_file", return_value=False):
                _, errors = gate.validate_dispositions(
                    self.document, repository=REPOSITORY
                )
        self.assertIn(
            "disposition evidence document is missing or invalid",
            errors,
        )

    def test_new_finding_cannot_use_historical_fixture_disposition(self):
        self.entry["disposition"] = "OWNER_REVIEWED_HISTORICAL_TEST_FIXTURE"
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            _, errors = gate.validate_dispositions(self.document, repository=REPOSITORY)
        self.assertIn("new finding requires explicit false-positive review", errors)

    def test_blocking_severity_never_accepted(self):
        self.finding["severity"] = "high"
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            with patch.object(
                gate,
                "finding_context_digest",
                return_value=self.entry["context_digest"],
            ):
                recognized, unresolved, _ = gate.apply_dispositions(
                    [self.finding], self.document, repository=REPOSITORY
                )
        self.assertFalse(recognized)
        self.assertEqual(
            unresolved[0]["reason"], "blocking severity cannot be dispositioned"
        )

    def test_duplicate_review_identity_is_rejected(self):
        self.document["dispositions"].append(dict(self.entry))
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            _, errors = gate.validate_dispositions(self.document, repository=REPOSITORY)
        self.assertIn("duplicate disposition finding identity", errors)

    def test_expired_review_is_rejected(self):
        self.entry["expires_on"] = "2026-01-01"
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            _, errors = gate.validate_dispositions(
                self.document, repository=REPOSITORY, today=date(2026, 11, 14)
            )
        self.assertIn("disposition is expired", errors)

    def test_expired_disposition_cannot_pass(self):
        self.entry["expires_on"] = "2026-01-01"
        report = self._report(dict(self.finding, severity="medium"))
        self.assertEqual(report["status"], "REVIEW REQUIRED")
        self.assertIn("disposition is expired", report["disposition_errors"])

    def test_current_b104_disposition_is_recognized_exactly(self):
        document = json.loads(
            (
                ROOT / "docs/security/PR-203-FINDINGS-DISPOSITIONS-2026-11-11.json"
            ).read_text(encoding="utf-8")
        )
        finding = {
            "scanner": "Bandit",
            "rule": "B104",
            "path": "backend/helpchain_backend/src/routes/admin.py",
            "line": 2423,
            "severity": "unclassified",
        }
        recognized, unresolved, errors = gate.apply_dispositions(
            [finding], document, repository=REPOSITORY
        )
        self.assertEqual(len(recognized), 1)
        self.assertFalse(unresolved)
        self.assertFalse(errors)

    def _report(self, finding, document=None, scanner_status=None):
        return gate.evaluate(
            self._baseline(),
            [],
            api_ok=True,
            repository=REPOSITORY,
            head_sha="a" * 40,
            base_sha="b" * 40,
            scanner_findings=[finding],
            scanner_status=scanner_status
            or [
                {
                    "name": "CodeQL",
                    "status": "success",
                    "report_present": True,
                    "report_valid": True,
                    "run_id": 1,
                    "run_attempt": 1,
                    "head_sha": "a" * 40,
                    "event": "pull_request",
                    "findings_count": 1,
                }
            ],
            dispositions=document or self.document,
        )

    def _baseline(self):
        return {
            "schemaVersion": 1,
            "repository": REPOSITORY,
            "source": "github-code-scanning-api",
            "capturedAt": "2026-11-14T00:00:00+00:00",
            "alert_numbers": [1],
            "alert_records": [{"number": 1, "signature": "old"}],
        }

    def test_unreviewed_quality_finding_is_inventory_not_blocker(self):
        with patch.object(gate, "validate_dispositions", return_value=({}, [])):
            report = self._report(self.finding)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["quality_review_inventory"], [self.finding])

    def test_unclassified_security_sensitive_finding_blocks(self):
        finding = dict(self.finding, scanner="Bandit", rule="B104")
        report = self._report(finding)
        self.assertEqual(report["status"], "REVIEW REQUIRED")
        self.assertTrue(report["unresolved_security_dispositions"])

    def test_unresolved_medium_finding_blocks(self):
        report = self._report(dict(self.finding, severity="medium"))
        self.assertEqual(report["status"], "REVIEW REQUIRED")

    def test_valid_dispositioned_medium_finding_can_pass(self):
        self.entry["expected_severity"] = "medium"
        finding = dict(self.finding, severity="medium")
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            with patch.object(
                gate,
                "finding_context_digest",
                return_value=self.entry["context_digest"],
            ):
                with patch.object(Path, "is_file", return_value=True):
                    report = self._report(finding)
        self.assertEqual(report["status"], "PASS")

    def test_critical_finding_fails(self):
        report = self._report(dict(self.finding, severity="critical"))
        self.assertEqual(report["status"], "FAIL")

    def test_missing_scanner_evidence_is_incomplete(self):
        report = self._report(
            self.finding,
            scanner_status=[
                {
                    "name": "CodeQL",
                    "status": "success",
                    "report_present": False,
                    "findings_count": 1,
                }
            ],
        )
        self.assertEqual(report["status"], "INCOMPLETE")

    def test_duplicate_finding_identities_are_rejected(self):
        report = gate.evaluate(
            self._baseline(),
            [],
            api_ok=True,
            repository=REPOSITORY,
            head_sha="a" * 40,
            base_sha="b" * 40,
            scanner_findings=[self.finding, self.finding],
            scanner_status=[
                {
                    "name": "CodeQL",
                    "status": "success",
                    "report_present": True,
                    "report_valid": True,
                    "run_id": 1,
                    "run_attempt": 1,
                    "head_sha": "a" * 40,
                    "event": "pull_request",
                    "findings_count": 2,
                }
            ],
            dispositions=self.document,
        )
        self.assertIn(
            "scanner finding identities are ambiguous", report["disposition_errors"]
        )

    def test_scanner_count_mismatch_is_rejected(self):
        report = self._report(
            self.finding,
            scanner_status=[
                {
                    "name": "CodeQL",
                    "status": "success",
                    "report_present": True,
                    "report_valid": True,
                    "run_id": 1,
                    "run_attempt": 1,
                    "head_sha": "a" * 40,
                    "event": "pull_request",
                    "findings_count": 2,
                }
            ],
        )
        self.assertIn(
            "scanner finding count does not match evidence counts",
            report["disposition_errors"],
        )


if __name__ == "__main__":
    unittest.main()
