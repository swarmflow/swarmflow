from pydantic import BaseModel, Field, HttpUrl

class SwarmTask(BaseModel):
    description: str = Field(
        ..., 
        description="Detailed description of what the task needs to accomplish"
    )
    callback_url: HttpUrl = Field(
        ..., 
        description="URL to call when task is complete"
    )
    fields: dict[str, str | int | float | None] = Field(
        ..., 
        description="Dictionary of field names and their descriptions required for the task"
    )