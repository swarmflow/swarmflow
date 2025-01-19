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
import json
from fastapi.testclient import TestClient

# @pytest.fixture
# def client():
#     # This creates a fresh client for each test
#     return TestClient(app)


def run_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, reload=True)
    server = uvicorn.Server(config)
    server.run()

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
async def test_metatables_creation():
    """Test creation of core metatables (forms and reports)"""
    postgres_engine = PostgresEngine()
    meta_tables = postgres_engine.meta_tables
    
    # Check if tables exist
    with postgres_engine.engine.connect() as connection:
        # Get list of all tables
        tables_query = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        existing_tables = [row[0] for row in connection.execute(tables_query)]
        
        print("\n=== Existing Tables ===")
        print(existing_tables)
        print("=====================\n")
        
        # Verify core tables exist
        assert 'forms' in existing_tables
        assert 'reports' in existing_tables
        
        # Verify table structures
        forms_schema = connection.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'forms'
        """)).fetchall()
        
        reports_schema = connection.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'reports'
        """)).fetchall()
        
        print("\n=== Forms Schema ===")
        print(forms_schema)
        print("\n=== Reports Schema ===")
        print(reports_schema)
        print("=====================\n")

    # Verify minimum required columns exist
    forms_columns = {col[0] for col in forms_schema}
    reports_columns = {col[0] for col in reports_schema}
    
    required_forms_columns = {'id', 'name', 'operations', 'status'}
    required_reports_columns = {'id', 'name', 'table_name', 'fields', 'filters', 'status'}
    
    assert required_forms_columns.issubset(forms_columns)
    assert required_reports_columns.issubset(reports_columns)


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
        },
        type="ai",
        external=False,
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
async def test_define_form():
    """Test form definition and execution using MetaTables"""
    postgres_engine = PostgresEngine()
    
    # Define test form configuration
    form_config = {
        "operations": [
            {
                "table": "users",
                "data": {"name": None, "email": None}
            }
        ],
        "fields": ["name", "email"],
        "type": "manual",
        "external": False
    }
    
    # Define form using MetaTables
    form = postgres_engine.define_form("register_user", form_config)
    print(f"\nCreated form: {form}")

    # Test form execution
    async with AsyncClient(base_url="http://test_app:8000") as client:
        payload = {"name": "Test User", "email": "test@example.com"}
        response = await client.post(f"/forms/register_user", json=payload)
        if response.status_code == 404:
            print(response.text)

    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "results" in response.json()

@pytest.mark.asyncio
async def test_define_2_form_chain():
    """Test chaining two forms using MetaTables"""
    postgres_engine = PostgresEngine()
    redis_engine = RedisEngine()
    with postgres_engine.engine.connect() as connection:
        with connection.begin():
            connection.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
            connection.execute(text("DROP TABLE IF EXISTS forms CASCADE;"))
    postres_engine = PostgresEngine()
    # Clear Redis queue
    redis_engine.redis_client.delete("finished")

    table_name = "users"
    columns = {
        "id": "SERIAL PRIMARY KEY",
        "name": "TEXT NOT NULL",
        "email": "TEXT UNIQUE NOT NULL",
        "status": "TEXT DEFAULT 'active'",
        # "created_at": "TIMESTAMP DEFAULT NOW()"
    }

    # Create profiles table
    profiles_columns = {
        "id": "SERIAL PRIMARY KEY",
        "user_id": "INTEGER NOT NULL",
        "bio": "TEXT",
        "avatar": "TEXT",
        "status": "TEXT DEFAULT 'active'"
    }
    postgres_engine.define_entity("profiles", profiles_columns, postgres_engine.config.postgres_url)


    # Call define_entity to create the table
    result = engine.define_entity(table_name, columns, engine.config.postgres_url)

    # Define first form with next step
    form1_config = {
        "operations": [
            {
                "table": "users",
                "data": {"name": None, "email": None}
            }
        ],
        "fields": ["name", "email"],
        "next_step": {
            "form_name": "create_profile",
            "fields": {
                "user_id": None,
                "bio": None,
                "avatar": None
            },
            "type": "ai"
        }
    }
    
    # Define second form
    form2_config = {
        "operations": [
            {
                "table": "profiles",
                "data": {"user_id": None, "bio": None, "avatar": None}
            }
        ],
        "fields": ["user_id", "bio", "avatar"]
    }
    
    # Create forms using MetaTables
    postgres_engine.define_form("register_user", form1_config)
    postgres_engine.define_form("create_profile", form2_config)
    
    # Test form chain execution
    async with AsyncClient(base_url="http://test_app:8000") as client:
        # Execute first form
        form1_payload = {"name": "Test User", "email": "test@example.com"}
        response = await client.post("/forms/register_user", json=form1_payload)
        
        assert response.status_code == 200
        user_id = response.json()["results"][0]["data"]["id"]
        assert response.json()["next_step"] is not None
        
        # Verify task creation in Redis
        await asyncio.sleep(5)
        tasks = redis_engine.redis_client.lrange("finished", 0, -1)
        assert len(tasks) == 1
        task = SwarmTask.model_validate_json(tasks[0])
        assert str(task.callback_url) == "http://test_app:8000/forms/create_profile"

@pytest.mark.asyncio
async def test_define_report():
    """Test report definition and execution using MetaTables"""
    postgres_engine = PostgresEngine()
    
    # Clear test data first
    with postgres_engine.engine.connect() as connection:
        with connection.begin():
            connection.execute(text("TRUNCATE users RESTART IDENTITY CASCADE;"))
    
    # Define report configuration
    report_config = {
        "table_name": "users",
        "fields": ["id", "name", "email"],
        "filters": {"status": "active"},
        "sorting": {"field": "name", "order": "asc"},
        "pagination": {"page_size": 10}
    }
    
    # Create report using MetaTables
    report = postgres_engine.define_report("active_users", report_config)
    print(f"\nCreated report: {report}")
    
    # Verify report exists in database
    meta_tables = postgres_engine.meta_tables
    stored_report = meta_tables.get_report_by_name("active_users")
    print(f"Retrieved report: {stored_report}")
    
    # Add test data
    with postgres_engine.engine.connect() as connection:
        with connection.begin():
            connection.execute(text("""
                INSERT INTO users (name, email, status)
                VALUES ('Test User', 'test@example.com', 'active')
            """))
    
    # Test report execution
    async with AsyncClient(base_url="http://test_app:8000") as client:
        response = await client.get("/reports/active_users")
    
    assert response.status_code == 200


# @pytest.mark.asyncio
# async def test_define_and_migrate_entity():
#     """
#     Test defining a table and applying migrations in sequence.
#     """
#     # Step 1: Define the table
#     table_name = "orders"
#     columns = {
#         "id": "SERIAL PRIMARY KEY",
#         "user_id": "INTEGER NOT NULL",
#         "amount": "NUMERIC(10, 2) NOT NULL",
#         "status": "TEXT DEFAULT 'pending'",
#     }
#     define_result = engine.define_entity(table_name, columns, engine.config.postgres_url)
#     assert define_result == f"Table '{table_name}' successfully defined with timestamps and triggers."

#     # Step 2: Apply migrations
#     migrations = [
#         {"action": "add_column", "name": "shipped_at", "definition": "TIMESTAMP"},
#         {"action": "modify_column", "name": "status", "definition": "TEXT NOT NULL"}
#     ]
#     migrate_result = engine.migrate_entity(table_name, migrations, engine.config.postgres_url)
#     assert migrate_result == f"Table '{table_name}' successfully migrated."

#     # Step 3: Verify schema after migrations
#     schema = engine.retrieve_schema(table_name, engine.config.postgres_url)
#     assert isinstance(schema, list)

#     # Check the new column was added
#     shipped_at_column = next((col for col in schema if col["column_name"] == "shipped_at"), None)
#     assert shipped_at_column is not None
#     assert shipped_at_column["data_type"] == "timestamp without time zone"

#     # Check that the modified column has the correct constraints
#     status_column = next((col for col in schema if col["column_name"] == "status"), None)
#     assert status_column is not None
#     assert status_column["is_nullable"] == "NO"

# @pytest.mark.asyncio
# async def test_define_workflow():
#     """Test basic workflow definition and execution"""
#     postgres_engine = PostgresEngine()
    
#     with postgres_engine.engine.connect() as connection:
#         with connection.begin():
#             connection.execute(text("DROP TABLE IF EXISTS orders CASCADE;"))
    
#     # Define table
#     columns = {
#         "id": "SERIAL PRIMARY KEY",
#         "amount": "NUMERIC(10,2)",
#         "status": "TEXT DEFAULT 'pending'"
#     }
#     postgres_engine.define_entity("orders", columns, postgres_engine.config.postgres_url)
    
#     # Define simple workflow
#     workflow_steps = [
#         {
#             "form_name": "create_order",
#             "operations": [
#                 {"table": "orders", "data": {
#                     "amount": None,
#                     "status": None
#                 }}
#             ],
#             "conditions": {"orders": {"status": "pending"}}
#         }
#     ]
    
#     result = postgres_engine.define_workflow("basic_workflow", workflow_steps)
#     assert "registered successfully" in result

#     # Test workflow execution
#     async with AsyncClient(base_url="http://test_app:8000") as client:
#         response = await client.post("/forms/create_order", 
#                                    json={"amount": 100.00, "status": "pending"})
#         assert response.status_code == 200


# @pytest.mark.asyncio
# async def test_complex_workflow():
#     """Test complex workflow with multiple steps and conditions"""
#     postgres_engine = PostgresEngine()
#     redis_engine = RedisEngine()

#     # Setup tables
#     tables = {
#         "orders": {
#             "id": "SERIAL PRIMARY KEY",
#             "product_id": "INTEGER NOT NULL",
#             "quantity": "INTEGER NOT NULL",
#             "status": "TEXT DEFAULT 'pending'"
#         },
#         "inventory": {
#             "id": "SERIAL PRIMARY KEY",
#             "product_id": "INTEGER NOT NULL",
#             "quantity": "INTEGER NOT NULL"
#         },
#         "order_history": {
#             "id": "SERIAL PRIMARY KEY",
#             "order_id": "INTEGER NOT NULL",
#             "status": "TEXT NOT NULL"
#         }
#     }
    
#     for table_name, columns in tables.items():
#         postgres_engine.define_entity(table_name, columns, postgres_engine.config.postgres_url)
    
#     # Define complex workflow
#     workflow_steps = [
#         {
#             "form_name": "create_order",
#             "operations": [
#                 {"table": "orders", "data": {
#                     "product_id": None,
#                     "quantity": None,
#                     "status": None
#                 }}
#             ],
#             "conditions": {"orders": {"status": "pending"}}
#         },
#         {
#             "form_name": "update_inventory",
#             "operations": [
#                 {"table": "inventory", "data": {
#                     "product_id": None,
#                     "quantity": None
#                 }}
#             ]
#         },
#         {
#             "form_name": "record_history",
#             "operations": [
#                 {"table": "order_history", "data": {
#                     "order_id": None,
#                     "status": None
#                 }}
#             ]
#         }
#     ]
    
#     postgres_engine.define_workflow("complex_workflow", workflow_steps)

#     # Test workflow execution
#     async with AsyncClient(base_url="http://test_app:8000") as client:
#         response = await client.post("/forms/create_order", 
#                                    json={
#                                        "product_id": 1,
#                                        "quantity": 5,
#                                        "status": "pending"
#                                    })
#         assert response.status_code == 200
#         order_id = response.json()["results"][0]["data"]["id"]

#         await asyncio.sleep(2)  # Wait for task processing

#         # Verify task creation
#         tasks = redis_engine.redis_client.lrange("swarm_tasks", 0, -1)
#         assert len(tasks) > 0


# @pytest.mark.asyncio
# async def test_order_processing_with_ai():
#     """Test AI-driven order processing workflow"""
#     postgres_engine = PostgresEngine()
#     redis_engine = RedisEngine()

#     # Define workflow with AI processing
#     workflow_steps = [
#         {
#             "form_name": "process_order",
#             "operations": [
#                 {"table": "orders", "data": {
#                     "product_name": None,
#                     "quantity": None,
#                     "total_price": None
#                 }}
#             ],
#             "type": "ai",
#             "report": {
#                 "table": "orders",
#                 "fields": ["id", "product_name", "total_price"],
#                 "filters": {}
#             }
#         }
#     ]
    
#     postgres_engine.define_workflow("ai_workflow", workflow_steps)

#     # Create AI task
#     test_task = SwarmTask(
#         description="Generate order details",
#         callback_url="http://test_app:8000/forms/process_order",
#         fields={
#             "product_name": None,
#             "quantity": None,
#             "total_price": None
#         },
#         type="ai",
#         external=False
#     )
#     redis_engine.add_task(test_task)

#     await asyncio.sleep(5)  # Wait for AI processing

#     # Verify results
#     with postgres_engine.engine.connect() as connection:
#         result = connection.execute(text("SELECT * FROM orders")).fetchone()
#         assert result is not None
#         assert isinstance(result.product_name, str)
#         assert isinstance(result.quantity, int)
#         assert isinstance(float(result.total_price), float)

# @pytest.mark.asyncio
# async def test_multiple_workers_ai_processing():
#     """Test multiple AI workers processing workflow tasks"""
#     postgres_engine = PostgresEngine()
#     redis_engine = RedisEngine()
    
#     redis_engine.redis_client.delete("finished")

#     # Define workflow for multiple AI tasks
#     workflow_steps = [
#         {
#             "form_name": "process_orders",
#             "operations": [
#                 {"table": "orders", "data": {
#                     "product_name": None,
#                     "quantity": None,
#                     "total_price": None
#                 }}
#             ],
#             "type": "ai"
#         }
#     ]
    
#     postgres_engine.define_workflow("multi_ai_workflow", workflow_steps)

#     # Create multiple AI tasks
#     tasks = [
#         SwarmTask(
#             description=f"Process order {i}",
#             callback_url="http://test_app:8000/forms/process_orders",
#             fields={
#                 "product_name": None,
#                 "quantity": None,
#                 "total_price": None
#             },
#             type="ai",
#             external=False
#         ) for i in range(3)
#     ]

#     for task in tasks:
#         redis_engine.add_task(task)

#     await asyncio.sleep(7)  # Wait for parallel processing

#     # Verify all tasks completed
#     finished_count = redis_engine.redis_client.llen("finished")
#     assert finished_count == 3

#     # Verify all orders created
#     with postgres_engine.engine.connect() as connection:
#         results = connection.execute(text("SELECT * FROM orders")).mappings().all()
#         assert len(results) == 3

# @pytest.mark.asyncio
# async def test_workflow_chain():
#     """Test complete workflow chain execution"""
#     redis_engine = RedisEngine()
#     postgres_engine = PostgresEngine()

#     # Clear test tables and Redis queues
#     with postgres_engine.engine.connect() as connection:
#         with connection.begin():
#             connection.execute(text("DROP TABLE IF EXISTS orders CASCADE;"))
#             connection.execute(text("DROP TABLE IF EXISTS inventory CASCADE;"))
#             connection.execute(text("DROP TABLE IF EXISTS payments CASCADE;"))
    
#     redis_engine.redis_client.delete("finished")

#     # Define tables for workflow
#     tables = {
#         "orders": {
#             "id": "SERIAL PRIMARY KEY",
#             "product_id": "INTEGER NOT NULL",
#             "quantity": "INTEGER NOT NULL",
#             "status": "TEXT DEFAULT 'pending'"
#         },
#         "inventory": {
#             "id": "SERIAL PRIMARY KEY",
#             "product_id": "INTEGER NOT NULL",
#             "available": "BOOLEAN DEFAULT true"
#         },
#         "payments": {
#             "id": "SERIAL PRIMARY KEY",
#             "order_id": "INTEGER NOT NULL",
#             "amount": "NUMERIC(10,2) NOT NULL"
#         }
#     }
    
#     for table_name, columns in tables.items():
#         postgres_engine.define_entity(table_name, columns, postgres_engine.config.postgres_url)

#     # Define workflow steps
#     workflow_steps = [
#         {
#             "form_name": "create_order",
#             "operations": [
#                 {"table": "orders", "data": {
#                     "product_id": None, 
#                     "quantity": None,
#                     "status": None
#                 }}
#             ],
#             "report": {
#                 "table": "orders",
#                 "fields": ["id", "status", "quantity"],
#                 "filters": {"status": "pending"}
#             },
#             "conditions": {
#                 "orders": {"status": "pending"}
#             }
#         },
#         {
#             "form_name": "check_inventory",
#             "operations": [
#                 {"table": "inventory", "data": {
#                     "product_id": None,
#                     "available": None
#                 }}
#             ],
#             "conditions": {
#                 "inventory": {"available": True}
#             }
#         },
#         {
#             "form_name": "process_payment",
#             "operations": [
#                 {"table": "payments", "data": {
#                     "order_id": None,
#                     "amount": None
#                 }}
#             ]
#         }
#     ]

#     # Register workflow
#     postgres_engine.define_workflow("order_processing", workflow_steps)

#     # Test workflow execution
#     async with AsyncClient(base_url="http://test_app:8000") as client:
#         # Step 1: Create Order
#         order_payload = {
#             "product_id": 1,
#             "quantity": 5,
#             "status": "pending"
#         }
#         response = await client.post("/forms/create_order", json=order_payload)
#         assert response.status_code == 200
#         order_id = response.json()["results"][0]["data"]["id"]

#         # Wait for task processing
#         await asyncio.sleep(2)

#         # Step 2: Check Inventory
#         inventory_payload = {
#             "product_id": 1,
#             "available": True
#         }
#         response = await client.post("/forms/check_inventory", json=inventory_payload)
#         assert response.status_code == 200

#         # Wait for task processing
#         await asyncio.sleep(2)

#         # Step 3: Process Payment
#         payment_payload = {
#             "order_id": order_id,
#             "amount": 100.00
#         }
#         response = await client.post("/forms/process_payment", json=payment_payload)
#         assert response.status_code == 200

#     # Verify workflow completion
#     with postgres_engine.engine.connect() as connection:
#         # Verify order created
#         order = connection.execute(text(
#             "SELECT * FROM orders WHERE id = :id"
#         ), {"id": order_id}).mappings().first()
#         assert order is not None
#         assert order["status"] == "pending"

#         # Verify inventory check
#         inventory = connection.execute(text(
#             "SELECT * FROM inventory WHERE product_id = :product_id"
#         ), {"product_id": 1}).mappings().first()
#         assert inventory is not None
#         assert inventory["available"] is True

#         # Verify payment processed
#         payment = connection.execute(text(
#             "SELECT * FROM payments WHERE order_id = :order_id"
#         ), {"order_id": order_id}).mappings().first()
#         assert payment is not None
#         assert payment["amount"] == 100.00

#     # Verify Redis task completion
#     finished_tasks = redis_engine.redis_client.lrange("finished", 0, -1)
#     assert len(finished_tasks) > 0

# @pytest.mark.asyncio
# async def test_workflow_branching():
#     """Test workflow with conditional branching"""
#     postgres_engine = PostgresEngine()
#     redis_engine = RedisEngine()

#     # Setup test tables
#     with postgres_engine.engine.connect() as connection:
#         with connection.begin():
#             connection.execute(text("DROP TABLE IF EXISTS orders CASCADE;"))
#             connection.execute(text("DROP TABLE IF EXISTS inventory CASCADE;"))

#     tables = {
#         "orders": {
#             "id": "SERIAL PRIMARY KEY",
#             "amount": "NUMERIC(10,2)",
#             "status": "TEXT DEFAULT 'pending'"
#         },
#         "inventory": {
#             "id": "SERIAL PRIMARY KEY",
#             "stock": "INTEGER",
#             "status": "TEXT"
#         }
#     }
    
#     for table_name, columns in tables.items():
#         postgres_engine.define_entity(table_name, columns, postgres_engine.config.postgres_url)

#     # Define workflow with branches
#     workflow_steps = [
#         {
#             "form_name": "create_order",
#             "operations": [{"table": "orders", "data": {"amount": None}}],
#             "conditions": {"orders": {"status": "pending"}},
#             "report": {
#                 "table": "orders",
#                 "fields": ["id", "amount", "status"],
#                 "filters": {"status": "pending"}
#             }
#         },
#         {
#             "form_name": "check_inventory",
#             "operations": [{"table": "inventory", "data": {"stock": None}}],
#             "conditions": {"inventory": {"stock": lambda x: x > 0}}
#         }
#     ]

#     postgres_engine.define_workflow("branching_workflow", workflow_steps)

#     # Test workflow execution
#     async with AsyncClient(base_url="http://test_app:8000") as client:
#         # Create order
#         response = await client.post("/forms/create_order", json={"amount": 100.00})
#         assert response.status_code == 200
        
#         await asyncio.sleep(1)
        
#         # Verify task creation based on condition
#         tasks = redis_engine.redis_client.lrange("swarm_tasks", 0, -1)
#         assert len(tasks) > 0

# @pytest.mark.asyncio
# async def test_workflow_reporting():
#     """Test workflow with integrated reporting"""
#     postgres_engine = PostgresEngine()
    
#     # Setup test table
#     with postgres_engine.engine.connect() as connection:
#         with connection.begin():
#             connection.execute(text("DROP TABLE IF EXISTS sales CASCADE;"))

#     columns = {
#         "id": "SERIAL PRIMARY KEY",
#         "amount": "NUMERIC(10,2)",
#         "region": "TEXT"
#     }
#     postgres_engine.define_entity("sales", columns, postgres_engine.config.postgres_url)

#     # Define workflow with report
#     workflow_steps = [
#         {
#             "form_name": "record_sale",
#             "operations": [
#                 {"table": "sales", "data": {"amount": None, "region": None}}
#             ],
#             "report": {
#                 "table": "sales",
#                 "fields": ["id", "amount", "region"],
#                 "filters": {"region": "north"}
#             }
#         }
#     ]

#     postgres_engine.define_workflow("sales_workflow", workflow_steps)

#     # Test form submission and report generation
#     async with AsyncClient(base_url="http://test_app:8000") as client:
#         # Submit form
#         response = await client.post("/forms/record_sale", 
#                                    json={"amount": 500.00, "region": "north"})
#         assert response.status_code == 200

#         # Check report
#         response = await client.get("/reports/record_sale_report")
#         assert response.status_code == 200
#         assert len(response.json()["data"]) > 0
