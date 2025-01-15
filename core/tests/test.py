"""
Copyright (c) 2025 Swarmflow
Licensed under Elastic License 2.0 or Commercial License
See LICENSE file for details
"""

import pytest
from httpx import AsyncClient
import httpx
from core.server.main import app
from core.postgres_engine.postgres_engine import PostgresEngine
from core.redis_engine.redis_engine import RedisEngine
from core.schemas.schemas import SwarmTask
import uvicorn
import threading
import asyncio
from sqlalchemy import text


def run_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Start server in a thread before tests
server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

# Initialize Supabase Engine
engine = PostgresEngine()

@pytest.mark.asyncio
async def test_health_check():
    """
    Test the health check endpoint.
    """
    print("Starting health check test...")
    async with AsyncClient(base_url="http://test_app:8000") as client:
        print("Sending request to test_app:8000")
        response = await client.get("/")
        print(f"Response received: {response.status_code}")
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
        # "created_at": "TIMESTAMP DEFAULT NOW()"
    }

    # Call define_entity to create the table
    result = engine.define_entity(table_name, columns, engine.config.postgres_url)
    assert result == f"Table '{table_name}' successfully defined with timestamps and triggers."

    # Verify the table exists by retrieving the schema
    schema = engine.retrieve_schema(table_name, engine.config.postgres_url)
    assert isinstance(schema, list)
    assert len(schema) == len(columns)+2


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

    async with AsyncClient(base_url="http://test_app:8000") as client:
        payload = {"id": 1, "name": "Test User", "email": "test@example.com", "age": 25}
        response = await client.post(f"/forms/{form_name}", json=payload)
    
    assert response.status_code == 200
    assert response.json()["message"] == "Form processed successfully"
    assert "results" in response.json()


@pytest.mark.asyncio
async def test_define_report():
    # Clean up any existing test data
    with engine.engine.connect() as connection:
        with connection.begin():
            connection.execute(text("TRUNCATE users RESTART IDENTITY CASCADE;"))
    
    # Now continue with your existing test code
    with engine.engine.connect() as connection:
        with connection.begin():
            sql = """
            INSERT INTO users (name, email, age, status)
            VALUES ('Test User', 'test@example.com', 25, 'active')
            """
            connection.execute(text(sql))

    
    # Continue with existing report test
    report_name = "active_users"
    table = "users"
    fields = ["id", "name", "email", "age"]
    filters = {"status": "active"}
    engine.define_reports(report_name, table, fields, filters)


    async with AsyncClient(base_url="http://test_app:8000") as client:
        response = await client.get(f"/reports/{report_name}")
    
    assert response.status_code == 200
    assert "data" in response.json()
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
    }
    define_result = engine.define_entity(table_name, columns, engine.config.postgres_url)
    assert define_result == f"Table '{table_name}' successfully defined with timestamps and triggers."

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

@pytest.mark.asyncio
async def test_define_workflow():
    with engine.engine.connect() as connection:
        with connection.begin():
            connection.execute(text("DROP TABLE IF EXISTS orders CASCADE;"))
    
    table_name = "orders"
    columns = {"id": "SERIAL PRIMARY KEY","user_id": "INTEGER NOT NULL","amount": "NUMERIC(10, 2) NOT NULL","status": "TEXT DEFAULT 'pending'","total_with_tax": "NUMERIC(10, 2)"}
    engine.define_entity(table_name, columns, engine.config.postgres_url)
    
    workflow_name = "order_processing"
    triggers = [{"name": "calculate_tax","timing": "BEFORE","event": "INSERT","logic": "BEGIN NEW.total_with_tax := NEW.amount * 1.2; RETURN NEW; END;","condition": "TRUE"}]
    engine.define_workflow(workflow_name, table_name, triggers, engine.config.postgres_url)
    
    with engine.engine.connect() as connection:
        with connection.begin():
            result = connection.execute(text("INSERT INTO orders (user_id, amount) VALUES (1, 100.00) RETURNING user_id, amount, total_with_tax;")).mappings().first()
            assert result['amount'] == 100.00
            assert result['total_with_tax'] == 120.00

@pytest.mark.asyncio
async def test_complex_workflow():
    """
    Test defining a complex workflow across multiple related tables
    """
    with engine.engine.connect() as connection:
        with connection.begin():
            connection.execute(text("DROP TABLE IF EXISTS orders CASCADE;"))
            connection.execute(text("DROP TABLE IF EXISTS inventory CASCADE;"))
            connection.execute(text("DROP TABLE IF EXISTS order_history CASCADE;"))
    
    # Define tables
    tables = {
        "orders": {
            "id": "SERIAL PRIMARY KEY",
            "product_id": "INTEGER NOT NULL",
            "quantity": "INTEGER NOT NULL",
            "status": "TEXT DEFAULT 'pending'",
            "total_price": "NUMERIC(10, 2)"
        },
        "inventory": {
            "id": "SERIAL PRIMARY KEY",
            "product_id": "INTEGER NOT NULL",
            "quantity": "INTEGER NOT NULL",
            "last_updated": "TIMESTAMP"
        },
        "order_history": {
            "id": "SERIAL PRIMARY KEY",
            "order_id": "INTEGER NOT NULL",
            "status": "TEXT NOT NULL",
            "timestamp": "TIMESTAMP"
        }
    }
    
    for table_name, columns in tables.items():
        engine.define_entity(table_name, columns, engine.config.postgres_url)
    
    # Define complex workflow
    workflow_name = "order_processing"
    triggers = [
        {
            "name": "update_inventory",
            "timing": "AFTER",
            "event": "INSERT",
            "logic": """
                BEGIN
                    UPDATE inventory 
                    SET quantity = quantity - NEW.quantity,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE product_id = NEW.product_id;
                    RETURN NEW;
                END;
            """,
            "condition": "NEW.status = 'pending'"
        },
        {
            "name": "create_history",
            "timing": "AFTER",
            "event": "INSERT OR UPDATE",
            "logic": """
                BEGIN
                    INSERT INTO order_history (order_id, status, timestamp)
                    VALUES (NEW.id, NEW.status, CURRENT_TIMESTAMP);
                    RETURN NEW;
                END;
            """,
            "condition": "TRUE"
        }
    ]
    
    engine.define_workflow(workflow_name, "orders", triggers, engine.config.postgres_url)
    
    # Test the workflow
    with engine.engine.connect() as connection:
        with connection.begin():
            # Setup initial inventory
            connection.execute(text("""
                INSERT INTO inventory (product_id, quantity)
                VALUES (1, 100);
            """))
            
            # Create order
            connection.execute(text("""
                INSERT INTO orders (product_id, quantity, status)
                VALUES (1, 5, 'pending');
            """))
            
            # Verify inventory updated
            inventory_result = connection.execute(text("""
                SELECT quantity FROM inventory WHERE product_id = 1;
            """)).mappings().first()
            assert inventory_result['quantity'] == 95
            
            # Verify order history created
            history_result = connection.execute(text("""
                SELECT COUNT(*) as count FROM order_history;
            """)).mappings().first()
            assert history_result['count'] == 1

@pytest.mark.asyncio
async def test_redis_task_queue():
    """
    Test Redis task queue operations
    """
    from core.redis_engine.redis_engine import RedisEngine
    from core.redis_engine.redis_engine import SwarmTask
    
    # Initialize Redis Engine
    redis_engine = RedisEngine()
    
    # Create a test task
    test_task = SwarmTask(
        description="Analyze sentiment of customer review",
        callback_url="https://api.example.com/callback",
        fields={
            "review_text": "The text content of the review",
            "language": "The language code of the review"
        }
    )
    
    # Test adding task
    add_result = redis_engine.add_task(test_task)
    assert isinstance(add_result, int)
    assert add_result > 0
    
    # Test retrieving task
    retrieved_task = redis_engine.get_task()
    assert isinstance(retrieved_task, SwarmTask)
    assert retrieved_task.description == test_task.description
    assert retrieved_task.callback_url == test_task.callback_url
    assert retrieved_task.fields == test_task.fields

@pytest.mark.asyncio
async def test_redis_task_validation():
    """
    Test Redis task validation
    """
    from core.redis_engine.redis_engine import RedisEngine
    from pydantic import ValidationError
    
    redis_engine = RedisEngine()
    
    # Test invalid task (missing required fields)
    invalid_task = {
        "description": "Invalid task"
        # missing callback_url and fields
    }
    
    with pytest.raises((ValidationError, Exception)):
        redis_engine.add_task(invalid_task)
    
    # Test invalid URL format
    invalid_url_task = {
        "description": "Task with invalid URL",
        "callback_url": "not-a-valid-url",
        "fields": {"test": "test description"}
    }
    
    with pytest.raises((ValidationError, Exception)):
        redis_engine.add_task(invalid_url_task)


@pytest.mark.asyncio
async def test_order_processing_with_ai():
    """Test order processing with AI field generation"""
    print("\nStarting order processing test with AI generation...")
    redis_engine = RedisEngine()
    postgres_engine = PostgresEngine()

    with postgres_engine.engine.connect() as connection:
        with connection.begin():
            print("Cleaning up existing orders table...")
            connection.execute(text("DROP TABLE IF EXISTS orders CASCADE;"))

    # Setup table and form as before
    table_name = "orders"
    columns = {
        "id": "SERIAL PRIMARY KEY",
        "product_name": "VARCHAR(255) NOT NULL",
        "quantity": "INTEGER NOT NULL",
        "total_price": "NUMERIC(10,2) NOT NULL"
    }
    
    postgres_engine.define_entity(table_name, columns, postgres_engine.config.postgres_url)

    form_name = "create_order"
    operations = [
        {"table": "orders", "data": {
            "product_name": "VARCHAR(255)",
            "quantity": "INTEGER",
            "total_price": "NUMERIC(10,2)"
        }}
    ]
    
    postgres_engine.define_form(form_name, operations)

    # Create task with empty fields
    test_task = SwarmTask(
        description="Fill out this new order form object with random data",
        callback_url="http://test_app:8000/forms/create_order",
        fields={
            "product_name": None,
            "quantity": None,
            "total_price": None
        }
    )
    redis_engine.add_task(test_task)

    async with httpx.AsyncClient() as client:
        # Initial checks
        response = await client.get("http://worker_agent:8002/status")
        initial_queue_size = response.json()["queue_size"]
        assert initial_queue_size > 0

        # Wait for AI processing
        await asyncio.sleep(5)  # Longer wait for AI processing

        # Verify completion
        finished_count = redis_engine.redis_client.llen("finished")
        assert finished_count > 0, "Task should be marked as finished"

        # Verify order creation with AI-generated values
        with postgres_engine.engine.connect() as connection:
            result = connection.execute(text("SELECT * FROM orders")).fetchone()
            assert result is not None
            print(f"AI-generated order: {result._asdict()}")
            
            # Verify generated values match expected types
            assert isinstance(result.product_name, str)
            assert isinstance(result.quantity, int)
            assert isinstance(float(result.total_price), float)
