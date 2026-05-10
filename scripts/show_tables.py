from sqlalchemy import create_engine, inspect
import os

# Локална база
db_url = "sqlite:///../instance/hc_local_dev.db"
# Ако използваш Neon/Postgres, смени db_url

engine = create_engine(db_url)
inspector = inspect(engine)

print("\n=== Всички таблици и колони ===\n")
for table_name in inspector.get_table_names():
    print(f"Table: {table_name}")
    columns = inspector.get_columns(table_name)
    for col in columns:
        print(f"  - {col['name']} ({col['type']})")
    print()
