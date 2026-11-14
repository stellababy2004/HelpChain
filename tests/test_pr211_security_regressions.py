"""Regression coverage for the two CodeQL High findings reported on PR211."""

import re

import pytest

from backend.helpchain_backend.src.routes.admin import (
    _audience_source_label,
    _valid_onboarding_email,
)


@pytest.mark.parametrize(
    "value",
    [
        "alice@example.com",
        "a+b@sub.example.org",
        "a@a..b",
        "a@.a.b",
        "a@a.b.",
        "a@b",
        "a@.b",
        "a@b.",
        "missing-at",
        "@a.b",
        "a@@b.c",
        "a b@c.d",
        "a@b.c d",
        "a@b.\u00a0c",
    ],
)
def test_email_validator_preserves_existing_stripped_input_semantics(value):
    original = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    assert _valid_onboarding_email(value) == bool(original.match(value))


def test_email_validator_handles_adversarial_dot_heavy_input():
    assert not _valid_onboarding_email("!@!." * 50000)
    assert not _valid_onboarding_email("a@" + "!." * 100000 + " ")
    assert _valid_onboarding_email("a@" + "!." * 100000 + "b")


@pytest.mark.parametrize(
    "host", ["linkedin.com", "www.linkedin.com", "fr.linkedin.com"]
)
def test_linkedin_source_matches_real_domain_and_subdomains(host):
    assert _audience_source_label(f"https://{host}/company/helpchain") == "LinkedIn"


@pytest.mark.parametrize(
    "host",
    ["evil-linkedin.com", "linkedin.com.evil.test", "linkedin.evil", "notlinkedin.com"],
)
def test_linkedin_source_rejects_lookalike_domains(host):
    assert _audience_source_label(f"https://{host}/") == host
