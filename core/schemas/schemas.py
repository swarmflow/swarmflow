from pydantic import BaseModel, Field, HttpUrl
from typing import Literal
class SwarmTask(BaseModel):
    description: str = Field(
        ..., 
        description="Detailed description of what the task needs to accomplish"
    )
    tool: str = Field(
        "",
        description="name of the tool to be used to complete the task"
    )
    report_url: str = Field(
        "",
        description="if provided, the url to generate a required report for the agent"
    )
    callback_url: HttpUrl = Field(
        ..., 
        description="URL to call when task is complete"
    )
    fields: dict[str, str | int | float | None] = Field(
        ..., 
        description="Dictionary of field names and their descriptions required for the task"
    )
    type: Literal["human", "ai"] = Field(
        ..., 
        description="whether task is meant to be completed by human or ai"
    )
    external: bool = Field(
        False,    
        description="Whether task is meant to be completed internally or externally"
    )
    starter: bool = Field(
        False,
        description="Whether task is a starter task"
    )