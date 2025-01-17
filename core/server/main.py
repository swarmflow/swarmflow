from fastapi import FastAPI, Request
from ..redis_engine.redis_engine import RedisEngine
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

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