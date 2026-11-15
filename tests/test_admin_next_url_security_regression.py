"""Regression coverage for the actual admin next-url helpers.

Extract only the function definitions from admin.py so these checks do not
require initializing the database or importing the entire admin blueprint.
"""

import ast
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pytest
from flask import Flask, request

ROOT = Path(__file__).resolve().parents[1]
ADMIN_SOURCE = ROOT / "backend/helpchain_backend/src/routes/admin.py"


@pytest.fixture
def redirects():
    tree = ast.parse(ADMIN_SOURCE.read_text(encoding="utf-8"))
    wanted = {"is_safe_url", "_safe_next_url"}
    functions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in wanted
    ]
    assert {node.name for node in functions} == wanted
    module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    namespace = {
        "request": request,
        "urlparse": urlparse,
        "urljoin": urljoin,
    }
    exec(compile(module, str(ADMIN_SOURCE), "exec"), namespace)
    app = Flask(__name__)
    with app.test_request_context("/", base_url="https://helpchain.live/"):
        yield namespace["_safe_next_url"]


@pytest.mark.parametrize(
    "candidate",
    [
        "https://evil.example/admin",
        "http://evil.example/",
        "//evil.example/admin",
        r"/\\evil.example/admin",
        "/admin\\evil.example",
        "javascript:alert(1)",
        "https:evil.example",
        "/administrator",
        "/ops-other",
        "/public",
        " /admin\\evil.example ",
    ],
)
def test_external_and_out_of_scope_next_urls_are_rejected(redirects, candidate):
    assert redirects(candidate) == ""


@pytest.mark.parametrize(
    "candidate",
    ["/admin", "/admin/dashboard", "/ops", "/ops/workspace"],
)
def test_allowed_local_admin_paths_remain_usable(redirects, candidate):
    assert redirects(candidate) == candidate


def test_empty_next_url_is_rejected(redirects):
    assert redirects(None) == ""
    assert redirects("") == ""
