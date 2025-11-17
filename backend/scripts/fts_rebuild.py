from sqlalchemy import text

try:
    from app import app, db
except Exception as e:
    raise SystemExit(f"Import failed: {e}")


def main():
    with app.app_context():
        # Rebuild FTS index if table exists
        try:
            db.session.execute(
                text(
                    "INSERT INTO help_requests_fts(help_requests_fts) VALUES('rebuild')"
                )
            )
            db.session.commit()
            print("FTS rebuild completed.")
        except Exception as e:
            db.session.rollback()
            print(f"FTS rebuild failed: {e}")


if __name__ == "__main__":
    main()
