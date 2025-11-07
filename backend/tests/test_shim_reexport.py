def test_shim_reexports_db():
    """Verify that the compatibility shim re-exports the canonical `db` instance.

    This test expects the shim at `helpchain_backend.src.extensions` to import and re-export
    the `db` object provided by the canonical `backend.extensions` module.
    """
    import importlib

    canonical = importlib.import_module("backend.extensions")
    shim = importlib.import_module("helpchain_backend.src.extensions")

    assert hasattr(canonical, "db"), "canonical module must provide db"
    assert hasattr(shim, "db"), "shim must re-export db"
    assert (
        canonical.db is shim.db
    ), "shim.db must be the same object as backend.extensions.db"
