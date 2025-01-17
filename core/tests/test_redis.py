import pytest
from datetime import datetime, timedelta
import time
from core.redis_engine.redis_engine import RedisEngine
from core.schemas.schemas import SwarmTask
import json
@pytest.fixture
def redis_engine():
    engine = RedisEngine()
    # Clear any existing scheduled tasks
    engine.redis_client.delete(engine.scheduled_tasks_key)
    engine.redis_client.delete("swarm_tasks")
    return engine

def test_schedule_starter_task(redis_engine):
    task = SwarmTask(
        task_id="test-123",
        description="Test starter task",
        callback_url="/test/callback",
        type="test_type"
    )
    
    task_id = redis_engine.schedule_starter_task(task, "minutes", 5)
    
    # Verify task was scheduled
    scheduled_tasks = redis_engine.redis_client.zrange(redis_engine.scheduled_tasks_key, 0, -1)
    assert len(scheduled_tasks) == 1

def test_modify_starter_task(redis_engine):
    task = SwarmTask(
        task_id="test-123",
        description="Test starter task",
        callback_url="/test/callback",
        type="test_type"
    )
    
    task_id = redis_engine.schedule_starter_task(task, "minutes", 5)
    
    # Modify schedule
    success = redis_engine.modify_starter_task(task_id, "hours", 1)
    assert success
    
    # Verify modification
    tasks = redis_engine.redis_client.zrange(redis_engine.scheduled_tasks_key, 0, -1)
    task_info = json.loads(tasks[0])
    assert task_info["schedule_type"] == "hours"
    assert task_info["interval"] == 1

def test_remove_starter_task(redis_engine):
    task = SwarmTask(
        task_id="test-123",
        description="Test starter task",
        callback_url="/test/callback",
        type="test_type"
    )
    
    task_id = redis_engine.schedule_starter_task(task, "minutes", 5)
    
    # Remove task
    success = redis_engine.remove_starter_task(task_id)
    assert success
    
    # Verify removal
    tasks = redis_engine.redis_client.zrange(redis_engine.scheduled_tasks_key, 0, -1)
    assert len(tasks) == 0

def test_get_due_starter_tasks(redis_engine):
    task = SwarmTask(
        task_id="test-123",
        description="Test starter task",
        callback_url="/test/callback",
        type="test_type"
    )
    
    # Schedule task for immediate execution
    now = datetime.now().timestamp()
    schedule_info = {
        "task": task.model_dump_json(),
        "schedule_type": "minutes",
        "interval": 5
    }
    redis_engine.redis_client.zadd(redis_engine.scheduled_tasks_key, {json.dumps(schedule_info): now})
    
    # Get due tasks
    due_tasks = redis_engine.get_due_starter_tasks()
    
    # Verify task was processed
    assert len(due_tasks) == 1
    assert due_tasks[0].task_id == "test-123"
    
    # Verify task was added to main queue
    queued_task = redis_engine.get_task()
    assert queued_task.task_id == "test-123"
    
    # Verify task was rescheduled
    scheduled_tasks = redis_engine.redis_client.zrange(redis_engine.scheduled_tasks_key, 0, -1, withscores=True)
    assert len(scheduled_tasks) == 1
    next_run_time = scheduled_tasks[0][1]
    assert next_run_time > now

def test_scheduler_thread(redis_engine):
    task = SwarmTask(
        task_id="test-123",
        description="Test starter task",
        callback_url="/test/callback",
        type="test_type"
    )
    
    # Schedule task for immediate execution
    redis_engine.schedule_starter_task(task, "minutes", 1)
    
    # Let scheduler run
    time.sleep(65)  # Wait for scheduler cycle
    
    # Verify task was processed
    queued_task = redis_engine.get_task()
    assert queued_task is not None
    assert queued_task.task_id == "test-123"
