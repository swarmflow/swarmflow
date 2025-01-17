import pytest
from core.postgres_engine.postgres_engine import PostgresEngine
from core.metatables.metatables import MetaTables

@pytest.fixture
def engine():
    return PostgresEngine()

@pytest.fixture
def meta_tables(engine):
    return MetaTables(engine)

def test_meta_tables_initialization(meta_tables):
    """Test that core tables are created during initialization"""
    required_tables = {'forms', 'reports', 'workflows', 'steps', 'agents', 'entities'}
    for table in required_tables:
        assert meta_tables.table_exists(table)

def test_entity_creation(meta_tables):
    """Test creating and retrieving entities"""
    test_schema = {
        "name": "VARCHAR(255)",
        "email": "VARCHAR(255)",
        "age": "INTEGER"
    }
    
    entity = meta_tables.add_entity(
        name="users",
        schema=test_schema,
        entity_type="table",
        created_by="test"
    )
    
    assert entity["name"] == "users"
    entities = meta_tables.get_all_entities()
    assert any(e["name"] == "users" for e in entities)

def test_form_creation(engine):
    """Test creating a form entity"""
    operations = [{"table": "users", "data": {"name": "text", "email": "email"}}]
    form = engine.create_form_entity("user_registration", operations)
    
    assert form["name"] == "user_registration"
    forms = engine.meta_tables.get_all_forms()
    assert any(f["name"] == "user_registration" for f in forms)

def test_report_creation(engine):
    """Test creating a report entity"""
    fields = ["name", "email"]
    filters = {"age": {"gt": 18}}
    report = engine.create_report_entity("user_list", "users", fields, filters)
    
    assert report["name"] == "user_list"
    reports = engine.meta_tables.get_all_reports()
    assert any(r["name"] == "user_list" for r in reports)

def test_workflow_creation(engine):
    """Test creating a workflow with steps"""
    triggers = [{"name": "after_insert", "timing": "AFTER", "event": "INSERT"}]
    workflow = engine.create_workflow_entity("email_notification", "users", triggers)
    
    step = engine.meta_tables.add_step(
        workflow_id=workflow["id"],
        name="send_email",
        sequence=1,
        action_type="notification",
        config={"template": "welcome_email"}
    )
    
    steps = engine.meta_tables.get_workflow_steps(workflow["id"])
    assert len(steps) == 1
    assert steps[0]["name"] == "send_email"

def test_agent_creation(engine):
    """Test creating an agent entity"""
    capabilities = ["send_email", "send_sms"]
    config = {"smtp_server": "smtp.test.com"}
    agent = engine.create_agent_entity("notifier", "communication", capabilities, config)
    
    assert agent["name"] == "notifier"
    agents = engine.meta_tables.get_all_agents()
    assert any(a["name"] == "notifier" for a in agents)

def test_entity_type_filtering(meta_tables):
    """Test filtering entities by type"""
    test_schemas = [
        {"name": "table1", "schema": {"field": "TEXT"}, "type": "table"},
        {"name": "view1", "schema": {"query": "SELECT"}, "type": "view"}
    ]
    
    for schema in test_schemas:
        meta_tables.add_entity(
            name=schema["name"],
            schema=schema["schema"],
            entity_type=schema["type"]
        )
    
    tables = meta_tables.get_entities_by_type("table")
    views = meta_tables.get_entities_by_type("view")
    
    assert len(tables) > 0
    assert len(views) > 0
    assert all(t["type"] == "table" for t in tables)
    assert all(v["type"] == "view" for v in views)
