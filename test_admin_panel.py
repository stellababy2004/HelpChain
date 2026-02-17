#!/usr/bin/env python3
"""Legacy top-level wrapper (kept for backwards-compat). Do not run with pytest.

This file is intentionally inert: the real tests live under `tests/` and use
the test fixtures defined in `tests/conftest.py`. Keeping this file avoids
accidental side-effects for editors that execute it directly, but prevents
pytest from attempting to collect fixture-scoped tests here.
"""


def main():
    print(
        "This script is maintained for legacy/manual execution. Use pytest in the `tests/` folder."
    )


if __name__ == "__main__":
    main()
