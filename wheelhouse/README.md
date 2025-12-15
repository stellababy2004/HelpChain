# wheelhouse

This directory is intended to contain pre-built wheel (.whl) files for packages
that are difficult to build in the Vercel build environment (native extensions
like `greenlet` or other binary wheels). Commit wheels here and Vercel will
install them using `--no-index --find-links wheelhouse`.

How to build wheels locally (Linux/macOS):

```bash
# create an isolated build dir
python -m venv .venv-build
source .venv-build/bin/activate
pip install --upgrade pip wheel
# build wheels into wheelhouse
pip wheel -w wheelhouse SQLAlchemy==1.4.46 greenlet==3.2.4
```

Notes:
- Building wheels for C-extensions may require system build tools (gcc, musl, etc.).
- For maximum compatibility with Linux serverless environments use `cibuildwheel` or
  manylinux builders to produce manylinux-compatible wheels.

After producing wheels, commit the `wheelhouse/` directory and push; Vercel will
use these wheels during the deploy (see `vercel.json` installCommand).
