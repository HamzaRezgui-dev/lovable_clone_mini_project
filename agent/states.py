from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

MAX_IMPLEMENTATION_STEPS = 50


class File(BaseModel):
    path: str = Field(description="The path to the file to be created or modified")
    purpose: str = Field(description="The purpose of the file, e.g. 'main application logic', 'data processing module', etc.")

class Plan(BaseModel):
    name: str = Field(description="The name of the app to be built")
    description: str = Field(description="A oneline description of the app to be built, e.g. 'A web application for managing personal finances'")
    techStack: str = Field(description="The technical stack to be used for the app, e.g. 'python', 'javascript', etc.")
    features: list[str] = Field(description="A list of features that the app should have, e.g. 'user authentication','data visualization', etc.")
    files: list[str] = Field(description="A list of files to be created, each with a 'path' and 'purpose'")

class ImplementationTask(BaseModel):
    filepath: str = Field(description="The path to the file to be modified")
    task_description: str = Field(description="A detailed description of the task to be performed on the file, e.g. 'add user authentication', 'implement data processing logic', etc.")

class TaskPlan(BaseModel):
    implementation_steps: list[ImplementationTask] = Field(description="A list of steps to be taken to implement the task")
    model_config = ConfigDict(extra="ignore")

    @field_validator("implementation_steps")
    @classmethod
    def cap_steps(cls, v: list) -> list:
        if len(v) > MAX_IMPLEMENTATION_STEPS:
            raise ValueError(
                f"Too many implementation steps: {len(v)} (max {MAX_IMPLEMENTATION_STEPS}). "
                "Reduce scope or split into multiple runs."
            )
        return v

class CoderState(BaseModel):
    task_plan: TaskPlan = Field(description="The plan for the task to be implemented")
    current_step_idx: int = Field(0, description="The index of the current step in the implementation steps")
    current_file_content: Optional[str] = Field(None, description="The content of the file currently being edited or created")
