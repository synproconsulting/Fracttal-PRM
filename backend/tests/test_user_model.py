from sqlalchemy import inspect

from database import engine


def test_users_table_exists():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "users" in tables


def test_users_table_columns():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("users")}
    required = {
        "id",
        "email",
        "hashed_password",
        "full_name",
        "is_active",
        "is_verified",
        "role",
        "partner_org_id",
        "created_at",
        "updated_at",
    }
    assert required.issubset(columns)
