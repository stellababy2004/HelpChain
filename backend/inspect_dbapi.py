from sqlalchemy import create_engine

eng = create_engine("sqlite:///:memory:")
print("dbapi module for engine:", eng.dialect.dbapi)
print("dbapi name:", getattr(eng.dialect.dbapi, "__name__", None))
print("dbapi repr:", repr(eng.dialect.dbapi))
