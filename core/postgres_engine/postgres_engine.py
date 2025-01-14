from ..config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from ..server.main import app
from flask import Flask, request, jsonify
import psycopg2

class PostgresEngine:
    '''
    Utilize AI, PKL, and YAML to power PostgreSQL Configuration and Management.
    '''
    def __init__(self):
        self.config = Config()
        self.engine = create_engine(self.config.postgres_url)
        
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
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        DROP TRIGGER IF EXISTS update_timestamp ON {table_name};
        CREATE TRIGGER update_timestamp
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION update_timestamp();
        """

        try:
            with self.engine.connect() as connection:
                connection.execute(text(create_table_sql))
                return f"Table '{table_name}' successfully defined with timestamps and triggers."
        except SQLAlchemyError as e:
            return f"Error defining table '{table_name}': {str(e)}"

    def migrate_entity(self, table_name: str, migrations: list, db_url: str):
        """
        Modify entities using PostgreSQL's robust ALTER TABLE capabilities.
        """
        try:
            with self.engine.connect() as connection:
                for migration in migrations:
                    if migration["action"] == "add_column":
                        sql = f"ALTER TABLE {table_name} ADD COLUMN {migration['name']} {migration['definition']};"
                    elif migration["action"] == "drop_column":
                        sql = f"ALTER TABLE {table_name} DROP COLUMN {migration['name']} CASCADE;"
                    elif migration["action"] == "modify_column":
                        sql = f"ALTER TABLE {table_name} ALTER COLUMN {migration['name']} TYPE {migration['definition']} USING {migration['name']}::{migration['definition']};"
                    elif migration["action"] == "add_index":
                        sql = f"CREATE INDEX idx_{table_name}_{migration['name']} ON {table_name} ({migration['columns']});"
                    elif migration["action"] == "add_constraint":
                        sql = f"ALTER TABLE {table_name} ADD CONSTRAINT {migration['name']} {migration['definition']};"
                    connection.execute(text(sql))
                return f"Table '{table_name}' successfully migrated."
        except SQLAlchemyError as e:
            return f"Error migrating table '{table_name}': {str(e)}"

    def retrieve_schema(self, table_name: str, db_url: str):
        """
        Retrieve comprehensive schema information using PostgreSQL system catalogs.
        """
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
                schema = [dict(row) for row in result]
                return schema if schema else f"Table '{table_name}' does not exist in the database."
        except SQLAlchemyError as e:
            return f"Error retrieving schema for table '{table_name}': {str(e)}"

    def define_workflow(self, workflow_name: str, table: str, triggers: list, db_url: str):
        """
        Define advanced PostgreSQL triggers with full procedural capabilities.
        """
        try:
            with self.engine.connect() as connection:
                for trigger in triggers:
                    function_sql = f"""
                    CREATE OR REPLACE FUNCTION {workflow_name}_{trigger['name']}_fn()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        {trigger['logic']}
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                    
                    DROP TRIGGER IF EXISTS {trigger['name']} ON {table};
                    CREATE TRIGGER {trigger['name']}
                    {trigger['timing']} {trigger['event']} ON {table}
                    FOR EACH ROW
                    WHEN ({trigger.get('condition', 'TRUE')})
                    EXECUTE FUNCTION {workflow_name}_{trigger['name']}_fn();
                    """
                    connection.execute(text(function_sql))
                return f"Workflow '{workflow_name}' defined successfully with triggers."
        except SQLAlchemyError as e:
            return f"Error defining workflow '{workflow_name}': {str(e)}"

    def define_form(self, form_name: str, operations: list):
        """
        Register a new form with PostgreSQL-specific features like RETURNING clause.
        """
        @app.route(f"/forms/{form_name}", methods=["POST"])
        def form_endpoint():
            try:
                payload = request.json
                results = []
                with self.engine.connect() as connection:
                    for operation in operations:
                        table = operation["table"]
                        data = {key: payload[key] for key in operation["data"].keys() if key in payload}
                        columns = ", ".join(data.keys())
                        values = ", ".join([f":{k}" for k in data.keys()])
                        sql = f"""
                        INSERT INTO {table} ({columns}) 
                        VALUES ({values})
                        RETURNING id, created_at;
                        """
                        result = connection.execute(text(sql), data)
                        results.append({"table": table, "data": dict(result.first())})
                return jsonify({"message": "Form processed successfully", "results": results}), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        return f"Form '{form_name}' registered successfully."

    def define_reports(self, report_name: str, table: str, fields: list, filters: dict = None):
        """
        Register a new report with PostgreSQL-specific features like window functions.
        """
        @app.route(f"/reports/{report_name}", methods=["GET"])
        def report_endpoint():
            try:
                fields_with_analytics = [
                    *fields,
                    "ROW_NUMBER() OVER (ORDER BY created_at) as row_num",
                    "COUNT(*) OVER () as total_count"
                ]
                query = f"SELECT {', '.join(fields_with_analytics)} FROM {table}"
                params = {}
                if filters:
                    conditions = []
                    for key, value in filters.items():
                        conditions.append(f"{key} = :{key}")
                        params[key] = value
                    query += " WHERE " + " AND ".join(conditions)
                
                with self.engine.connect() as connection:
                    result = connection.execute(text(query), params)
                    data = [dict(row) for row in result]
                return jsonify({"data": data}), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        return f"Report '{report_name}' registered successfully."
