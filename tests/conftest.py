import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure settings load a test DB url before importing app modules.
tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db.name}"
os.environ["ENV"] = "test"
os.environ["ENABLE_DEV_ADMIN_BYPASS"] = "false"

from app.main import app  # noqa: E402
from app.db.database import Base, get_db  # noqa: E402


@pytest.fixture(scope="session")
def db_engine():
  engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
  Base.metadata.create_all(bind=engine)
  yield engine
  Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_engine):
  TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

  def override_get_db():
    db = TestingSessionLocal()
    try:
      yield db
    finally:
      db.close()

  app.dependency_overrides[get_db] = override_get_db
  with TestClient(app) as c:
    yield c
  app.dependency_overrides.clear()
