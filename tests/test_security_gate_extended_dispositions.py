"""Fail-closed regression tests for additional finding dispositions."""

import importlib.util
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
                gate, "finding_context_digest",
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
        self.assertIn("disposition evidence document is missing or invalid", errors)

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


if __name__ == "__main__":
    unittest.main()
