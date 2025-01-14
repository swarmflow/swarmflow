import pytest
from httpx import AsyncClient
from core.server.main import app
from core.postgres_engine.postgres_engine import PostgresEngine

# Initialize Supabase Engine
engine = PostgresEngine()

@pytest.mark.asyncio
async def test_health_check():
    """
    Test the health check endpoint.
    """
    async with AsyncClient(app=app, base_url="http://localhost:8000") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Server is running"}


@pytest.mark.asyncio
async def test_define_entity():
    """
    Test defining a table using define_entity.
    """
    table_name = "users"
    columns = {
        "id": "SERIAL PRIMARY KEY",
        "name": "TEXT NOT NULL",
        "email": "TEXT UNIQUE NOT NULL",
        "status": "TEXT DEFAULT 'active'",
        "created_at": "TIMESTAMP DEFAULT NOW()"
    }

    # Call define_entity to create the table
    result = engine.define_entity(table_name, columns, engine.config.postgres_url)
    assert result == f"Table '{table_name}' successfully defined on Supabase"

    # Verify the table exists by retrieving the schema
    schema = engine.retrieve_schema(table_name, engine.config.postgres_url)
    assert isinstance(schema, list)
    assert len(schema) == len(columns)


@pytest.mark.asyncio
async def test_migrate_entity():
    """
    Test applying migrations to the users table.
    """
    table_name = "users"
    migrations = [
        {"action": "add_column", "name": "age", "definition": "INTEGER"},
        {"action": "modify_column", "name": "status", "definition": "TEXT NOT NULL"},
        {"action": "drop_column", "name": "created_at"}
    ]

    # Call migrate_entity to apply migrations
    result = engine.migrate_entity(table_name, migrations, engine.config.postgres_url)
    assert result == f"Table '{table_name}' successfully migrated."

    # Verify the changes in the schema
    schema = engine.retrieve_schema(table_name, engine.config.postgres_url)
    assert isinstance(schema, list)

    # Check that the new column was added
    age_column = next((col for col in schema if col["column_name"] == "age"), None)
    assert age_column is not None
    assert age_column["data_type"] == "integer"

    # Check that the modified column has the correct constraints
    status_column = next((col for col in schema if col["column_name"] == "status"), None)
    assert status_column is not None
    assert status_column["is_nullable"] == "NO"

    # Check that the dropped column no longer exists
    created_at_column = next((col for col in schema if col["column_name"] == "created_at"), None)
    assert created_at_column is None


@pytest.mark.asyncio
async def test_define_form():
    """
    Test defining a form and submitting data.
    """
    form_name = "register_user"
    operations = [
        {"table": "users", "data": {"id": None, "name": None, "email": None, "age": None}}
    ]
    engine.define_form(form_name, operations)

    async with AsyncClient(app=app, base_url="http://localhost:8000") as client:
        payload = {"id": 1, "name": "Test User", "email": "test@example.com", "age": 25}
        response = await client.post(f"/forms/{form_name}", json=payload)
    
    assert response.status_code == 200
    assert response.json()["message"] == "Form processed successfully"
    assert "results" in response.json


@pytest.mark.asyncio
async def test_define_report():
    """
    Test defining a report and retrieving data.
    """
    report_name = "active_users"
    table = "users"
    fields = ["id", "name", "email", "age"]
    filters = {"status": "active"}
    engine.define_reports(report_name, table, fields, filters)

    async with AsyncClient(app=app, base_url="http://localhost:8000") as client:
        response = await client.get(f"/reports/{report_name}")
    
    assert response.status_code == 200
    assert "data" in response.json
    assert len(response.json()["data"]) > 0
    assert response.json()["data"][0]["name"] == "Test User"


@pytest.mark.asyncio
async def test_define_and_migrate_entity():
    """
    Test defining a table and applying migrations in sequence.
    """
    # Step 1: Define the table
    table_name = "orders"
    columns = {
        "id": "SERIAL PRIMARY KEY",
        "user_id": "INTEGER NOT NULL",
        "amount": "NUMERIC(10, 2) NOT NULL",
        "status": "TEXT DEFAULT 'pending'",
        "created_at": "TIMESTAMP DEFAULT NOW()"
    }
    define_result = engine.define_entity(table_name, columns, engine.config.postgres_url)
    assert define_result == f"Table '{table_name}' successfully defined on Supabase"

    # Step 2: Apply migrations
    migrations = [
        {"action": "add_column", "name": "shipped_at", "definition": "TIMESTAMP"},
        {"action": "modify_column", "name": "status", "definition": "TEXT NOT NULL"}
    ]
    migrate_result = engine.migrate_entity(table_name, migrations, engine.config.postgres_url)
    assert migrate_result == f"Table '{table_name}' successfully migrated."

    # Step 3: Verify schema after migrations
    schema = engine.retrieve_schema(table_name, engine.config.postgres_url)
    assert isinstance(schema, list)

    # Check the new column was added
    shipped_at_column = next((col for col in schema if col["column_name"] == "shipped_at"), None)
    assert shipped_at_column is not None
    assert shipped_at_column["data_type"] == "timestamp without time zone"

    # Check that the modified column has the correct constraints
    status_column = next((col for col in schema if col["column_name"] == "status"), None)
    assert status_column is not None
    assert status_column["is_nullable"] == "NO"
