from fastapi import FastAPI, BackgroundTasks
from core.redis_engine.redis_engine import RedisEngine
from core.schemas.schemas import SwarmTask
from core.config import Config
import httpx
import asyncio
import uuid
from openai import OpenAI
import json

app = FastAPI()
redis_engine = RedisEngine()
worker_id = str(uuid.uuid4())
client = OpenAI(api_key = Config().OPEN_AI_KEY)

async def generate_field_values(form_fields):
    """Generate values for empty form fields using OpenAI"""
    prompt = f"Generate realistic values for these form fields: {form_fields}"
    
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.5,
        top_p = 0.01,
        messages=[
            {"role": "system", "content": "You are a form data generator. Return only valid JSON, in plaintext."},
            {"role": "user", "content": prompt}
        ]
    )
    print(response.choices[0].message.content)
    return response.choices[0].message.content.replace("```", "").replace("json","").strip()

async def process_task(task: SwarmTask):
    """Process task and call callback URL with results"""
    await asyncio.sleep(2)
    
    # Generate values for empty fields
    if all(v is None for v in task.fields.values()):
        generated_values = await generate_field_values(task.fields)
        print(generated_values)
        task.fields = json.loads(generated_values)
    
    async with httpx.AsyncClient() as client:
        await client.post(str(task.callback_url), json=task.fields)
        redis_engine.redis_client.lpush("finished", task.model_dump_json())


async def process_queue():
    """Continuously process tasks from queue"""
    while True:
        # Atomic operation: move task from queue to processing set
        task_data = redis_engine.redis_client.rpoplpush(
            "swarm_tasks", 
            f"processing:{worker_id}"
        )
        if task_data:
            task = SwarmTask.model_validate_json(task_data)
            await process_task(task)
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    """Start queue processing when server starts"""
    asyncio.create_task(process_queue())

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up processing set on shutdown"""
    redis_engine.redis_client.delete(f"processing:{worker_id}")

@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "worker_agent"}

@app.get("/status")
async def worker_status():
    return {
        "status": "running",
        "queue_size": redis_engine.redis_client.llen("swarm_tasks"),
        "processing": redis_engine.redis_client.llen(f"processing:{worker_id}")
    }
