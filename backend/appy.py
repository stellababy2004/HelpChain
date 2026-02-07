import os
from backend.extensions import db  # re-export the bound SQLAlchemy instance
from backend.helpchain_backend.src.app import create_app

app = create_app()

# За Render health: ако искаш бърз sanity
@app.get("/health")
def health():
	return {"ok": True}, 200

__all__ = ["app", "db"]
