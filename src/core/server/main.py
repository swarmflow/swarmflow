from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ..ai_engine import AIEngine

# Create the FastAPI app
app = FastAPI()

# Define allowed origins for CORS
origins = [
    '*'
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # List of allowed origins
    allow_credentials=True,  # Allow cookies to be included in requests
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Define an endpoint to stream AI assistant responses using SSE
@app.post("/ai-assistant/")
async def ai_assistant(msg: str):
    """
    SSE endpoint to stream results from the AI engine.
    """

    async def event_generator():
        # Simulate streaming response from AIEngine
        try:
            # Assume AIEngine has a streaming API (modify as needed)
            async for chunk in AIEngine.stream_architect(msg):
                yield f"data: {chunk}\n\n"  # SSE format: "data: <message>\n\n"
        except Exception as e:
            yield f"data: Error occurred: {str(e)}\n\n"

    # Return the streaming response
    return StreamingResponse(event_generator(), media_type="text/event-stream")
