from ..config import Config
import redis
from typing import Any, Optional
from ..schemas.schemas import SwarmTask

class RedisEngine:
    def __init__(self):
        self.config = Config()
        self.redis_client = redis.Redis(
            host=self.config.REDIS_HOST,
            port=self.config.REDIS_PORT,
            decode_responses=True
        )
    
    def add_task(self, task: SwarmTask | dict) -> bool:
        validated_task = SwarmTask.model_validate(task)
        return self.redis_client.lpush("swarm_tasks", validated_task.model_dump_json())

    def get_task(self) -> Optional[SwarmTask]:
        task = self.redis_client.rpop("swarm_tasks")
        if task:
            return SwarmTask.model_validate_json(task)
        else:
            return None
