from ..config import Config
import redis
from typing import Any, Optional
from ..schemas.schemas import SwarmTask
import json
import uuid
import datetime
import time
from datetime import timedelta
from threading import Thread
class RedisEngine:
    def __init__(self):
        self.config = Config()
        self.redis_client = redis.Redis(
            host=self.config.REDIS_HOST,
            port=self.config.REDIS_PORT,
            decode_responses=True
        )
        self.scheduled_tasks_key = "scheduled_starter_tasks"
    
    def add_task(self, task: SwarmTask | dict) -> bool:
        validated_task = SwarmTask.model_validate(task)
        return self.redis_client.lpush("swarm_tasks", validated_task.model_dump_json())

    def get_task(self) -> Optional[SwarmTask]:
        task = self.redis_client.rpop("swarm_tasks")
        if task:
            return SwarmTask.model_validate_json(task)
        else:
            return None
    def schedule_task(self, task: SwarmTask, schedule_type: str, interval: int) -> str:
        """Schedule a task for future execution"""
        task_id = str(uuid.uuid4())
        schedule_info = {
            "task_id": task_id,
            "task": task.model_dump_json(),
            "schedule_type": schedule_type,
            "interval": interval,
            "last_run": None
        }
        
        next_run = self._calculate_next_run(schedule_type, interval)
        self.redis_client.zadd(self.scheduled_tasks_key, {json.dumps(schedule_info): next_run})
        
        return task_id

    def execute_task(self, task: SwarmTask) -> bool:
        """Execute a task immediately"""
        return self.add_task(task)

    
    def modify_starter_task(self, task_id: str, schedule_type: str = None, interval: int = None) -> bool:
        """Modify existing starter task schedule"""
        tasks = self.redis_client.zrange(self.scheduled_tasks_key, 0, -1, withscores=True)
        
        for task_data, score in tasks:
            task_info = json.loads(task_data)
            if task_info.get("task_id") == task_id:
                # Update schedule
                if schedule_type:
                    task_info["schedule_type"] = schedule_type
                if interval:
                    task_info["interval"] = interval
                
                # Remove old entry and add updated one
                self.redis_client.zrem(self.scheduled_tasks_key, task_data)
                next_run = self._calculate_next_run(task_info["schedule_type"], task_info["interval"])
                self.redis_client.zadd(self.scheduled_tasks_key, {json.dumps(task_info): next_run})
                return True
        return False
    
    def remove_starter_task(self, task_id: str) -> bool:
        """Remove a starter task"""
        tasks = self.redis_client.zrange(self.scheduled_tasks_key, 0, -1)
        for task_data in tasks:
            task_info = json.loads(task_data)
            if task_info.get("task_id") == task_id:
                return bool(self.redis_client.zrem(self.scheduled_tasks_key, task_data))
        return False
    
    def get_due_tasks(self) -> list[SwarmTask]:
        current_time = time.time()
        due_tasks = self.redis_client.zrangebyscore(
            self.scheduled_tasks_key,
            0,
            current_time
        )
        
        tasks_to_run = []
        for task_data in due_tasks:
            task_info = json.loads(task_data)
            task = SwarmTask.model_validate_json(task_info["task"])
            
            # Only process starter tasks
            if task.starter:
                # Update last run time
                task_info["last_run"] = current_time
                
                # Calculate next run based on last execution
                next_run = self._calculate_next_run(
                    task_info["schedule_type"],
                    task_info["interval"]
                )
                
                # Update schedule
                self.redis_client.zrem(self.scheduled_tasks_key, task_data)
                if task_info["interval"] != -1:
                    self.redis_client.zadd(self.scheduled_tasks_key, {json.dumps(task_info): next_run})
                
                tasks_to_run.append(task)
        
        return tasks_to_run

    
    def _calculate_next_run(self, schedule_type: str, interval: int) -> float:
        """Calculate next run time based on schedule type"""
        now = datetime.datetime.now()
        interval = 0 if interval == -1 else interval
        
        if schedule_type == "minutes":
            next_time = now + timedelta(minutes=interval)
        elif schedule_type == "hours":
            next_time = now + timedelta(hours=interval)
        elif schedule_type == "days":
            next_time = now + timedelta(days=interval)
        else:
            next_time = now + timedelta(minutes=interval)  # Default to minutes
            
        return next_time.timestamp()
    def get_task_status(self, task_id: str) -> dict:
        """Get status of a scheduled task"""
        tasks = self.redis_client.zrange(self.scheduled_tasks_key, 0, -1)
        for task_data in tasks:
            task_info = json.loads(task_data)
            if task_info.get("task_id") == task_id:
                return {
                    "task_id": task_id,
                    "last_run": task_info.get("last_run"),
                    "next_run": self.redis_client.zscore(self.scheduled_tasks_key, task_data),
                    "schedule_type": task_info["schedule_type"],
                    "interval": task_info["interval"]
                }
        return None

    def schedule_starter_points(self):
        """Initialize and start the scheduler thread"""
        self.scheduler_thread = Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()

    def _run_scheduler(self):
        """Continuous scheduler loop that processes due tasks"""
        while True:
            try:
                # Get and process due tasks
                due_tasks = self.get_due_tasks()
                for task in due_tasks:
                    self.execute_task(task)
                
                # Check every second for new due tasks
                time.sleep(1)
                
            except Exception as e:
                print(f"Scheduler error: {e}")
                # Continue running even if there's an error
                time.sleep(1)
