import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from backend.database import SessionLocal
from sqlalchemy import text

def test_connection():
    try:
        with SessionLocal() as db:
            result = db.execute(text("SELECT 1")).scalar_one()
            print("✅ Connected to PostgreSQL – SELECT 1 returned:", result)
    except Exception as e:
        print("❌ Database connection failed:", e)

if __name__ == "__main__":
    test_connection()
