from fastapi import FastAPI, Request,HTTPException
from sqlalchemy import text
from ..redis_engine.redis_engine import RedisEngine
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from ..postgres_engine.postgres_engine import PostgresEngine
from ..metatables.metatables import MetaTables
from ..schemas.schemas import SwarmTask
redis_engine = RedisEngine()

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_engine.schedule_starter_points()
    yield


app = FastAPI(lifespan=lifespan)


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# # Include the engine's router
# app.include_router(engine.router)

def create_app():
    return app

@app.get("/")
async def health_check():
    return {"message": "Server is running"}

@app.post("/forms/{form_name}")
async def execute_form(form_name: str, request: Request):
    def check_conditions(conditions: dict, results: list) -> bool:
        if not conditions:
            return True
            
        for result in results:
            table_conditions = conditions.get(result["table"], {})
            
            if not table_conditions:
                continue
                
            for field, expected_value in table_conditions.items():
                actual_value = result["data"].get(field)
                
                if callable(expected_value):
                    if not expected_value(actual_value):
                        return False
                elif actual_value != expected_value:
                    return False
                    
        return True
    payload = await request.json()
    meta_tables = MetaTables(PostgresEngine())
    redis_engine = RedisEngine()
    
    # Get form configuration from database
    # forms = meta_tables.get_all_forms()
    form =  meta_tables.get_form_by_name(form_name)
    
    if not form:
        raise HTTPException(status_code=404, detail=f"Form {form_name} not found")
    
    # Execute operations
    results = []
    engine = PostgresEngine()
    
    with engine.engine.connect() as connection:
        with connection.begin():
            for operation in form["operations"]:
                table = operation["table"]
                data = {k: payload[k] for k in operation["data"].keys() if k in payload}
                columns = ", ".join(data.keys())
                values = ", ".join([f":{k}" for k in data.keys()])
                sql = f"""
                INSERT INTO {table} ({columns})
                VALUES ({values})
                RETURNING *;
                """
                result = connection.execute(text(sql), data).mappings().first()
                results.append({"table": table, "data": dict(result)})

    # Handle next step logic
    next_step_status = "No Next Step"
    next_step = form["next_step"]
    print(next_step)
    if next_step and check_conditions(next_step.get("conditions", {}), results):
        # Create next task for Redis queue
        next_task = SwarmTask(
            description=f"Execute form {next_step['form_name']}",
            callback_url=f"http://test_app:8000/forms/{next_step['form_name']}",
            fields=next_step["fields"],
            tool=next_step.get("tool", ""),
            type=next_step.get("type", "ai"),
            external=next_step.get("external", False),
            report_url=next_step.get("report_url", "")
        )
        
        # Add task to Redis queue
        redis_engine.add_task(next_task)
        next_step_status = "Next step added to Redis queue"

    return {
        "status": "success", 
        "results": results,
        "next_step_status": next_step_status,
        "next_step": next_step
    }



@app.get("/reports/{report_name}")
async def execute_report(report_name: str):
    meta_tables = MetaTables(PostgresEngine())
    
    # Get report configuration from database
    report = meta_tables.get_report_by_name(report_name)
    # report = next((r for r in reports if r["name"] == report_name), None)
    
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_name} not found")
    
    # Execute report query using configuration
    engine = PostgresEngine()
    fields_str = ", ".join(report["fields"])
    
    with engine.engine.connect() as connection:
        query = f"SELECT {fields_str} FROM {report['table_name']}"
        
        if report.get("filters"):
            conditions = []
            params = {}
            for key, value in report["filters"].items():
                conditions.append(f"{key} = :{key}")
                params[key] = value
            query += " WHERE " + " AND ".join(conditions)
            result = connection.execute(text(query), params).mappings().all()
        else:
            result = connection.execute(text(query)).mappings().all()
            
        data = [dict(row) for row in result]
        
    return {"status": "success", "data": data}


# Define an endpoint to stream AI assistant responses using SSE
# @app.post("/ai-assistant/")
# async def ai_assistant(msg: str):
#     """
#     SSE endpoint to stream results from the AI engine.
#     """
    # from ..postgres_engine.postgres_engine import PostgresEngine
    # engine = PostgresEngine()
#     async def event_generator():
#         # Simulate streaming response from AIEngine
#         try:
#             # Assume AIEngine has a streaming API (modify as needed)
#             async for chunk in AIEngine.stream_architect(msg):
#                 yield f"data: {chunk}\n\n"  # SSE format: "data: <message>\n\n"
#         except Exception as e:
#             yield f"data: Error occurred: {str(e)}\n\n"

#     # Return the streaming response
#     return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)