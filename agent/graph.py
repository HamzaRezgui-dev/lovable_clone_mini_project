from dotenv import load_dotenv

load_dotenv()

from langchain_groq import ChatGroq
from prompts import *
from states import *
from langgraph.constants import END
from langgraph.graph import StateGraph

llm = ChatGroq(model="openai/gpt-oss-120b")

user_prompt = "Create a simple calculator web application"

def planner_agent(State: dict) -> dict:
    user_prompt = State["user_prompt"]
    resp = llm.with_structured_output(Plan).invoke(planner_prompt(user_prompt))
    return {"plan": resp}

def architect_agent(State: dict) -> dict:
    plan: Plan = State["plan"]
    resp = llm.with_structured_output(TaskPlan).invoke(architect_prompt(plan))
    if resp is None:
        raise ValueError("Architect did not return a valid response")

    return {"task_plan": resp}

graph = StateGraph(dict)
graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)
graph.add_edge("planner", "architect")

graph.set_entry_point("planner")

agent = graph.compile()

user_prompt = "create a simple calculator web application"

def taskplan_to_markdown(task_plan: TaskPlan) -> str:
    md = "# Implementation Plan\n\n"

    for i, step in enumerate(task_plan.implementation_steps, 1):
        md += f"## Step {i}: `{step.filepath}`\n\n"
        md += f"{step.task_description}\n\n"
        md += "---\n\n"

    return md

result = agent.invoke({"user_prompt": user_prompt})

task_plan = result["task_plan"]

markdown_output = taskplan_to_markdown(task_plan)

print(markdown_output)