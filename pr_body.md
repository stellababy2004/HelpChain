🔧 PR Title

tests: isolate authenticated_volunteer_client to prevent session leakage between fixtures

📝 PR Description

Summary

This PR fixes intermittent session-related side effects in the test suite by isolating the authenticated_volunteer_client fixture.
Previously, it mutated the shared client fixture, causing session/cookie leakage when a test simultaneously used client and authenticated_volunteer_client.

What was changed

authenticated_volunteer_client now:

- creates its own app.test_client() instance instead of inheriting/mutating the shared client
- performs session setup in its own session context
- mirrors the Set-Cookie header correctly into its own environment (via environ_base), preventing cross-fixture contamination

Why this fix

Using a shared test client across multiple authentication fixtures can leak:

- session cookie values
- server-side session state
- volunteer/admin authentication flags

especially in scenarios where multiple fixtures are injected into the same test.

Isolating the client ensures strict fixture independence and deterministic test behavior.

Results

Before: 1 failed, 140 passed, 1 skipped

After fix: 141 passed, 1 skipped (0 failures)

No regressions introduced

CI stability improved

No changes to production code

Next Steps (optional)

- Apply the same isolation pattern to additional auth fixtures (admin, staff) if needed.
- Remove legacy helpers once session stability is fully verified across environments.
