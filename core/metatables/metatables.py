from sqlalchemy import text, inspect
from typing import Dict, List, Any

class MetaTables:
    def __init__(self, engine):
        self.pg = engine
        self.initialize_if_needed()
    
    def initialize_if_needed(self):
        """Check and create core tables if they don't exist"""
        inspector = inspect(self.pg.engine)
        required_tables = {'forms', 'reports', 'workflows', 'steps', 'agents', 'entitites'}
        existing_tables = set(inspector.get_table_names())
        
        if not required_tables.issubset(existing_tables):
            self.create_core_tables()
            
    def table_exists(self, table_name: str) -> bool:
        """Check if a specific table exists"""
        inspector = inspect(self.pg.engine)
        return table_name in inspector.get_table_names()
        
    def create_core_tables(self):
        # Forms table
        if not self.table_exists('forms'):
            self.pg.define_entity("forms", {
                "id": "SERIAL PRIMARY KEY",
                "name": "VARCHAR(255) NOT NULL",
                "operations": "JSONB NOT NULL",
                "status": "VARCHAR(50) DEFAULT 'active'"
            }, self.pg.config.postgres_url)

        # Reports table
        if not self.table_exists('reportss'):
            self.pg.define_entity("reports", {
                "id": "SERIAL PRIMARY KEY",
                "name": "VARCHAR(255) NOT NULL",
                "table_name": "VARCHAR(255) NOT NULL",
                "fields": "JSONB NOT NULL",
                "filters": "JSONB",
                "status": "VARCHAR(50) DEFAULT 'active'"
            }, self.pg.config.postgres_url)

        # Workflows table
        if not self.table_exists('workflows'):
            self.pg.define_entity("workflows", {
                "id": "SERIAL PRIMARY KEY",
                "name": "VARCHAR(255) NOT NULL",
                "table_name": "VARCHAR(255) NOT NULL",
                "triggers": "JSONB NOT NULL",
                "status": "VARCHAR(50) DEFAULT 'active'"
            }, self.pg.config.postgres_url)

        # Steps table
        if not self.table_exists('steps'):
            self.pg.define_entity("steps", {
                "id": "SERIAL PRIMARY KEY",
                "workflow_id": "INTEGER REFERENCES workflows(id)",
                "name": "VARCHAR(255) NOT NULL",
                "sequence": "INTEGER NOT NULL",
                "action_type": "VARCHAR(100) NOT NULL",
                "config": "JSONB NOT NULL",
                "status": "VARCHAR(50) DEFAULT 'active'"
            }, self.pg.config.postgres_url)

        # Agents table
        if not self.table_exists('agents'):
            self.pg.define_entity("agents", {
                "id": "SERIAL PRIMARY KEY",
                "name": "VARCHAR(255) NOT NULL",
                "type": "VARCHAR(100) NOT NULL",
                "capabilities": "JSONB NOT NULL",
                "config": "JSONB NOT NULL",
                "status": "VARCHAR(50) DEFAULT 'active'"
            }, self.pg.config.postgres_url)

        if not self.table_exists('entities'):
            self.pg.define_entity("entities", {
                "id": "SERIAL PRIMARY KEY",
                "name": "VARCHAR(255) NOT NULL",
                "schema": "JSONB NOT NULL",
                "type": "VARCHAR(100) NOT NULL",
                "created_by": "VARCHAR(255)",
                "status": "VARCHAR(50) DEFAULT 'active'"
            }, self.pg.config.postgres_url)

    def add_entity(self, name: str, schema: Dict, entity_type: str, created_by: str = None) -> Dict:
        with self.pg.engine.connect() as conn:
            result = conn.execute(
                text("""
                INSERT INTO entities (name, schema, type, created_by)
                VALUES (:name, :schema, :type, :created_by)
                RETURNING id
                """),
                {"name": name, "schema": schema, "type": entity_type, "created_by": created_by}
            )
            return {"id": result.scalar(), "name": name}

    def get_all_entities(self) -> List[Dict]:
        with self.pg.engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM entities WHERE status = 'active'"))
            return [dict(row) for row in result]
        
    def add_form(self, name: str, operations: List[Dict[str, Any]]) -> Dict:
        with self.pg.engine.connect() as conn:
            result = conn.execute(
                text("""
                INSERT INTO forms (name, operations)
                VALUES (:name, :operations)
                RETURNING id
                """),
                {"name": name, "operations": operations}
            )
            return {"id": result.scalar(), "name": name}

    def add_report(self, name: str, table_name: str, fields: List[str], filters: Dict = None) -> Dict:
        with self.pg.engine.connect() as conn:
            result = conn.execute(
                text("""
                INSERT INTO reports (name, table_name, fields, filters)
                VALUES (:name, :table_name, :fields, :filters)
                RETURNING id
                """),
                {"name": name, "table_name": table_name, "fields": fields, "filters": filters}
            )
            return {"id": result.scalar(), "name": name}

    def add_workflow(self, name: str, table_name: str, triggers: List[Dict]) -> Dict:
        with self.pg.engine.connect() as conn:
            result = conn.execute(
                text("""
                INSERT INTO workflows (name, table_name, triggers)
                VALUES (:name, :table_name, :triggers)
                RETURNING id
                """),
                {"name": name, "table_name": table_name, "triggers": triggers}
            )
            return {"id": result.scalar(), "name": name}

    def add_step(self, workflow_id: int, name: str, sequence: int, 
                 action_type: str, config: Dict) -> Dict:
        with self.pg.engine.connect() as conn:
            result = conn.execute(
                text("""
                INSERT INTO steps (workflow_id, name, sequence, action_type, config)
                VALUES (:workflow_id, :name, :sequence, :action_type, :config)
                RETURNING id
                """),
                {"workflow_id": workflow_id, "name": name, "sequence": sequence,
                 "action_type": action_type, "config": config}
            )
            return {"id": result.scalar(), "name": name}

    def add_agent(self, name: str, agent_type: str, capabilities: List[str], 
                 config: Dict) -> Dict:
        with self.pg.engine.connect() as conn:
            result = conn.execute(
                text("""
                INSERT INTO agents (name, type, capabilities, config)
                VALUES (:name, :type, :capabilities, :config)
                RETURNING id
                """),
                {"name": name, "type": agent_type, "capabilities": capabilities, "config": config}
            )
            return {"id": result.scalar(), "name": name}

    def get_all_forms(self) -> List[Dict]:
        with self.pg.engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM forms WHERE status = 'active'"))
            return [dict(row) for row in result]

    def get_all_reports(self) -> List[Dict]:
        with self.pg.engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM reports WHERE status = 'active'"))
            return [dict(row) for row in result]

    def get_all_workflows(self) -> List[Dict]:
        with self.pg.engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM workflows WHERE status = 'active'"))
            return [dict(row) for row in result]

    def get_workflow_steps(self, workflow_id: int) -> List[Dict]:
        with self.pg.engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM steps WHERE workflow_id = :workflow_id ORDER BY sequence"),
                {"workflow_id": workflow_id}
            )
            return [dict(row) for row in result]

    def get_all_agents(self) -> List[Dict]:
        with self.pg.engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM agents WHERE status = 'active'"))
            return [dict(row) for row in result]
