from ..config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from ..server.main import app
import psycopg2
from fastapi import Request

class PostgresEngine:
    def __init__(self):
        self.config = Config()
        self.engine = create_engine(self.config.postgres_url)
        self.router = app.router

        
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


    def define_workflow(self, workflow_name: str, table: str, triggers: list, db_url: str):
        try:
            with self.engine.connect() as connection:
                with connection.begin():
                    for trigger in triggers:
                        function_name = f"{workflow_name}_{trigger['name']}_fn"
                        function_sql = f"CREATE OR REPLACE FUNCTION {function_name}() RETURNS TRIGGER AS $$ {trigger['logic']} $$ LANGUAGE plpgsql;"
                        connection.execute(text(function_sql))
                        trigger_name = f"{workflow_name}_{trigger['name']}"
                        trigger_sql = f"DROP TRIGGER IF EXISTS {trigger_name} ON {table}; CREATE TRIGGER {trigger_name} {trigger['timing']} {trigger['event']} ON {table} FOR EACH ROW EXECUTE FUNCTION {function_name}();"
                        connection.execute(text(trigger_sql))
                    return f"Workflow '{workflow_name}' defined successfully with triggers."
        except SQLAlchemyError as e:
            return f"Error defining workflow '{workflow_name}': {str(e)}"

    def define_form(self, form_name: str, operations: list):
        async def form_endpoint(request: Request):
            payload = await request.json()
            results = []
            with self.engine.connect() as connection:
                with connection.begin():
                    for operation in operations:
                        table = operation["table"]
                        data = {key: payload[key] for key in operation["data"].keys() if key in payload}
                        columns = ", ".join(data.keys())
                        values = ", ".join([f":{k}" for k in data.keys()])
                        sql = f"""
                        INSERT INTO {table} ({columns})
                        VALUES ({values})
                        RETURNING id;
                        """
                        # In postgres_engine.py, form_endpoint
                        result = connection.execute(text(sql), data).mappings().first()
                        results.append({"table": table, "data": dict(result)})


            return {"message": "Form processed successfully", "results": results}

        print(f"Registering form route: /forms/{form_name}")
        app.router.add_api_route(f"/forms/{form_name}", form_endpoint, methods=["POST"])
        print(f"Available routes after registration: {[route.path for route in app.routes]}")
        return f"Form '{form_name}' registered successfully."


    def define_reports(self, report_name: str, table: str, fields: list, filters: dict = None):
        async def report_endpoint():
            fields_with_analytics = [
                *fields,
                "ROW_NUMBER() OVER (ORDER BY id) as row_num",
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
                with connection.begin():
                    result = connection.execute(text(query), params).mappings().all()
                    data = [dict(row) for row in result]
            return {"data": data}

        self.router.add_api_route(f"/reports/{report_name}", report_endpoint, methods=["GET"])
        return f"Report '{report_name}' registered successfully."