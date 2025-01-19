from ..config import Config
from ..metatables.metatables import MetaTables
from typing import Dict, List
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import psycopg2
from fastapi import Request
import json
from ..schemas.schemas import SwarmTask
from ..redis_engine.redis_engine import RedisEngine
from copy import deepcopy

class PostgresEngine:
    def __init__(self):
        self.config = Config()
        self.engine = create_engine(self.config.postgres_url)
        self.meta_tables = MetaTables(self)
        # self.setup_redis_fdw()

        
    def define_entity(self, table_name: str, columns: dict, db_url: str):
        """
        Define entities on PostgreSQL with advanced features like SERIAL, UUID, etc.
        """
        column_definitions = ", ".join([f"{col} {definition}" for col, definition in columns.items()])
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {column_definitions},
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Add update trigger for updated_at
        CREATE OR REPLACE FUNCTION update_timestamp()
        RETURNS TRIGGER AS $body$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $body$ language 'plpgsql';
        
        DROP TRIGGER IF EXISTS update_timestamp ON {table_name};
        CREATE TRIGGER update_timestamp
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION update_timestamp();
        """

        try:
            with self.engine.connect() as connection:
                with connection.begin():
                    connection.execute(text(create_table_sql))
                return f"Table '{table_name}' successfully defined with timestamps and triggers."
        except SQLAlchemyError as e:
            return f"Error defining table '{table_name}': {str(e)}"


    def migrate_entity(self, table_name: str, migrations: list, db_url: str):
        try:
            with self.engine.connect() as connection:
                with connection.begin():
                    for migration in migrations:
                        if migration["action"] == "add_column":
                            sql = f"ALTER TABLE {table_name} ADD COLUMN {migration['name']} {migration['definition']};"
                        elif migration["action"] == "drop_column":
                            sql = f"ALTER TABLE {table_name} DROP COLUMN {migration['name']} CASCADE;"
                        elif migration["action"] == "modify_column":
                            # Split type modification and constraint modification
                            type_sql = f"ALTER TABLE {table_name} ALTER COLUMN {migration['name']} TYPE TEXT;"
                            connection.execute(text(type_sql))
                            constraint_sql = f"ALTER TABLE {table_name} ALTER COLUMN {migration['name']} SET NOT NULL;"
                            connection.execute(text(constraint_sql))
                            continue
                        elif migration["action"] == "add_index":
                            sql = f"CREATE INDEX idx_{table_name}_{migration['name']} ON {table_name} ({migration['columns']});"
                        elif migration["action"] == "add_constraint":
                            sql = f"ALTER TABLE {table_name} ADD CONSTRAINT {migration['name']} {migration['definition']};"
                        connection.execute(text(sql))
                return f"Table '{table_name}' successfully migrated."
        except SQLAlchemyError as e:
            return f"Error migrating table '{table_name}': {str(e)}"



    def retrieve_schema(self, table_name: str, db_url: str):
        try:
            schema_query = """
            SELECT 
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                tc.constraint_type,
                i.indexdef as index_def
            FROM information_schema.columns c
            LEFT JOIN information_schema.table_constraints tc 
                ON tc.table_name = c.table_name 
                AND tc.constraint_name = (
                    SELECT constraint_name 
                    FROM information_schema.key_column_usage 
                    WHERE column_name = c.column_name 
                    AND table_name = c.table_name
                )
            LEFT JOIN pg_indexes i 
                ON i.tablename = c.table_name 
                AND i.indexdef LIKE '%' || c.column_name || '%'
            WHERE c.table_name = :table_name;
            """
            
            with self.engine.connect() as connection:
                result = connection.execute(text(schema_query), {"table_name": table_name})
                schema = [dict(zip(result.keys(), row)) for row in result]
                print(schema)
                return schema if schema else f"Table '{table_name}' does not exist in the database."
        except SQLAlchemyError as e:
            return f"Error retrieving schema for table '{table_name}': {str(e)}"


    def define_form(self, form_name: str, config: Dict) -> Dict:
        """
        Define form using MetaTables storage
        
        Args:
            form_name: Name of the form
            config: Dictionary containing:
                - operations: List of database operations
                - next_step: Next form configuration
                - fields: Required form fields
                - tool: Processing tool
                - type: Form type (ai/manual/external)
                - external: External integration flag
                - report_url: Associated report URL
        """
        return self.meta_tables.add_form(form_name, config)

    def define_report(self, report_name: str, config: Dict) -> Dict:
        """
        Define report using MetaTables storage
        
        Args:
            report_name: Name of the report
            config: Dictionary containing:
                - table_name: Source table
                - fields: Fields to display
                - filters: Filter conditions
                - sorting: Sort configuration
                - aggregations: Aggregation settings
                - pagination: Pagination config
                - permissions: Access control
        """
        return self.meta_tables.add_report(report_name, config)

    def define_workflow(self, workflow_name: str, steps: List[Dict]) -> Dict:
        """
        Define workflow by creating linked forms and reports
        
        Args:
            workflow_name: Name of the workflow
            steps: List of step configurations containing form and report definitions
        """
        workflow_components = []
        
        for i, step in enumerate(steps):
            # Get next step if not the last step
            next_step = steps[i + 1] if i < len(steps) - 1 else None
            
            # Define form
            form_config = {
                "operations": step["operations"],
                "fields": step.get("fields", []),
                "tool": step.get("tool"),
                "type": step.get("type", "manual"),
                "external": step.get("external", False)
            }
            
            # Add next step configuration if exists
            if next_step:
                form_config["next_step"] = {
                    "form_name": next_step["form_name"],
                    "conditions": step.get("conditions", {}),
                    "fields": next_step.get("fields", [])
                }
                
            # Add report configuration if specified
            if "report" in step:
                report = self.define_report(
                    f"{workflow_name}_{step['form_name']}_report",
                    step["report"]
                )
                form_config["report_url"] = f"/reports/{report['name']}"
                workflow_components.append({"type": "report", "id": report["id"]})
                
            # Create the form
            form = self.define_form(step["form_name"], form_config)
            workflow_components.append({"type": "form", "id": form["id"]})
        
        return {
            "name": workflow_name,
            "components": workflow_components
        }


    def validate_redis_fdw(self):
        """
        Validates the Redis Foreign Data Wrapper setup by checking:
        1. Extension installation
        2. Server configuration 
        3. User mapping
        4. Foreign table creation
        5. Connection functionality
        """
        try:
            with self.engine.connect() as connection:
                with connection.begin():
                    # 1. Check if redis_fdw extension exists
                    extension_check = """
                        SELECT EXISTS (
                            SELECT 1 FROM pg_extension WHERE extname = 'redis_fdw'
                        );
                    """
                    has_extension = connection.execute(text(extension_check)).scalar()
                    if not has_extension:
                        raise Exception("redis_fdw extension is not installed")

                    # 2. Verify Redis server configuration
                    server_check = """
                        SELECT EXISTS (
                            SELECT 1 FROM pg_foreign_server 
                            WHERE address = 'test_redis'
                        );
                    """
                    has_server = connection.execute(text(server_check)).scalar()
                    if not has_server:
                        raise Exception("Redis server foreign data wrapper is not configured")

                    # 3. Check user mapping
                    user_mapping_check = """
                        SELECT EXISTS (
                            SELECT 1 FROM pg_user_mappings 
                            WHERE srvname = 'test_redis'
                        );
                    """
                    has_mapping = connection.execute(text(user_mapping_check)).scalar()
                    if not has_mapping:
                        raise Exception("User mapping for Redis server is not configured")

                    # 4. Verify foreign table existence
                    table_check = """
                        SELECT EXISTS (
                            SELECT 1 FROM pg_foreign_table ft
                            JOIN pg_class c ON ft.ftrelid = c.oid
                            WHERE c.relname = 'swarm_tasks'
                        );
                    """
                    has_table = connection.execute(text(table_check)).scalar()
                    if not has_table:
                        raise Exception("Foreign table 'swarm_tasks' does not exist")

                    # 5. Test Redis connection functionality
                    connection_test = """
                        SELECT COUNT(*) FROM redis_swarm_tasks;
                    """
                    try:
                        connection.execute(text(connection_test))
                    except Exception as e:
                        raise Exception(f"Cannot query Redis foreign table: {str(e)}")

                    # Additional validation: Test insert functionality
                    insert_test = """
                        INSERT INTO swarm_tasks VALUES ('{"test": "connection"}');
                        DELETE FROM swarm_tasks WHERE task::jsonb->>'test' = 'connection';
                    """
                    try:
                        connection.execute(text(insert_test))
                    except Exception as e:
                        raise Exception(f"Cannot insert/delete from Redis foreign table: {str(e)}")

                    return {
                        "status": "success",
                        "message": "Redis FDW setup is valid and functional",
                        "details": {
                            "extension_installed": has_extension,
                            "server_configured": has_server,
                            "user_mapping_exists": has_mapping,
                            "foreign_table_exists": has_table,
                            "connection_functional": True
                        }
                    }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "details": None
            }
