from sqlalchemy import create_engine, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)

def run():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE question_responses ADD COLUMN score FLOAT NULL;"))
            print("Successfully added score column to question_responses")
        except Exception as e:
            print("Failed to add score column (might already exist):", e)

if __name__ == "__main__":
    run()
