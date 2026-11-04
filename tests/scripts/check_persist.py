import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])
with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT count(*) FROM users WHERE user_id = :u"), {"u": "persist-check"}
    ).scalar_one()
print("persist-check rows =", rows)
