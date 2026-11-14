"""Fail-closed regression tests for extensible finding dispositions."""

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


class ExtendedDispositionTests(unittest.TestCase):
    def setUp(self):
        self.key = "codeql|py/unused-import|backend/models.py|1"
        self.entry = {
            "finding_id": self.key,
            "scanner": "CodeQL",
            "rule": "py/unused-import",
            "path": "backend/models.py",
            "line": 1,
            "disposition": "FALSE_POSITIVE",
            "expected_severity": "unclassified",
            "context_digest": "sha256:" + "a" * 64,
            "rationale": "Explicit owner review; illustrative test evidence only.",
            "evidence_ref": "docs/security/PR-224-SECURITY-GATE-REVIEW-2026-11-14.md",
            "expires_on": "2027-11-14",
        }
        self.document = {
            "schema_version": 1,
            "repository": "stellababy2004/HelpChain",
            "approval_model": "solo_owner_review",
            "independent_review": False,
            "owner": {
                "login": "stellababy2004",
                "name": "Security reviewer",
                "decision_date": "2026-11-14",
            },
            "dispositions": [self.entry],
        }

    def test_unreviewed_finding_remains_unresolved(self):
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            recognized, unresolved, errors = gate.apply_dispositions(
                [
                    {
                        "scanner": "CodeQL",
                        "rule": "py/unused-import",
                        "path": "backend/models.py",
                        "line": 1,
                        "severity": "unclassified",
                    }
                ],
                {**self.document, "dispositions": []},
                repository="stellababy2004/HelpChain",
            )
        self.assertFalse(recognized)
        self.assertTrue(unresolved)
        self.assertTrue(errors)

    def test_additional_review_requires_exact_source_digest(self):
        finding = {
            "scanner": "CodeQL",
            "rule": "py/unused-import",
            "path": "backend/models.py",
            "line": 1,
            "severity": "unclassified",
        }
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            recognized, unresolved, errors = gate.apply_dispositions(
                [finding], self.document, repository="stellababy2004/HelpChain"
            )
        self.assertFalse(recognized)
        self.assertTrue(
            any(
                x["reason"]
                in {"finding context changed", "trustworthy finding context unavailable"}
                for x in unresolved
            )
        )
        self.assertFalse(errors)

    def test_new_finding_cannot_use_historical_fixture_disposition(self):
        self.entry["disposition"] = "OWNER_REVIEWED_HISTORICAL_TEST_FIXTURE"
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            _, errors = gate.validate_dispositions(
                self.document, repository="stellababy2004/HelpChain"
            )
        self.assertIn("new finding requires explicit false-positive review", errors)

    def test_blocking_severity_never_accepted(self):
        self.entry["expected_severity"] = "unclassified"
        finding = {
            "scanner": "CodeQL",
            "rule": "py/unused-import",
            "path": "backend/models.py",
            "line": 1,
            "severity": "high",
        }
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()), patch.object(
            gate, "finding_context_digest", return_value=self.entry["context_digest"]
        ):
            recognized, unresolved, _ = gate.apply_dispositions(
                [finding], self.document, repository="stellababy2004/HelpChain"
            )
        self.assertFalse(recognized)
        self.assertEqual(
            unresolved[0]["reason"], "blocking severity cannot be dispositioned"
        )

    def test_duplicate_review_identity_is_rejected(self):
        self.document["dispositions"].append(dict(self.entry))
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            _, errors = gate.validate_dispositions(
                self.document, repository="stellababy2004/HelpChain"
            )
        self.assertIn("duplicate disposition finding identity", errors)

    def test_expired_review_is_rejected(self):
        self.entry["expires_on"] = "2026-01-01"
        with patch.object(gate, "EXPECTED_DISPOSITION_KEYS", set()):
            _, errors = gate.validate_dispositions(
                self.document, repository="stellababy2004/HelpChain",
                today=date(2026, 11, 14),
            )
        self.assertIn("disposition is expired", errors)


if __name__ == "__main__":
    unittest.main()
