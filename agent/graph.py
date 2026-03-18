import os

from dotenv import load_dotenv
from langchain.agents import create_agent

from agent.tools import read_file, write_file, list_files, get_current_directory

load_dotenv()

if not os.environ.get("GROQ_API_KEY"):
    raise EnvironmentError(
        "GROQ_API_KEY is not set. Add it to your .env file or environment before running."
    )

from langchain_groq import ChatGroq
from prompts import *
from states import *
from langgraph.constants import END
from langgraph.graph import StateGraph

_MAX_FILE_PREVIEW_CHARS = 8_000

llm = ChatGroq(model="llama-3.3-70b-versatile")


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

def coder_agent(state: dict) -> dict:
    """LangGraph tool-using coder agent."""
    coder_state: CoderState = state.get("coder_state")
    if coder_state is None:
        coder_state = CoderState(task_plan=state["task_plan"], current_step_idx=0)

    steps = coder_state.task_plan.implementation_steps
    if coder_state.current_step_idx >= len(steps):
        return {"coder_state": coder_state, "status": "DONE"}

    current_task = steps[coder_state.current_step_idx]

    existing_content = read_file.run(current_task.filepath)
    if len(existing_content) > _MAX_FILE_PREVIEW_CHARS:
        existing_content = existing_content[:_MAX_FILE_PREVIEW_CHARS] + "\n... [truncated for context]"

    system_prompt = coder_system_prompt()
    user_prompt = (
        f"<task_description>\n{current_task.task_description}\n</task_description>\n"
        f"<filepath>\n{current_task.filepath}\n</filepath>\n"
        f"<existing_content>\n{existing_content}\n</existing_content>\n"
        "Use write_file(path, content) to save your changes."
    )

    coder_tools = [read_file, write_file, list_files, get_current_directory]
    react_agent = create_agent(llm, coder_tools)

    react_agent.invoke({"messages": [{"role": "system", "content": system_prompt},
                                     {"role": "user", "content": user_prompt}]})

    coder_state.current_step_idx += 1
    return {"coder_state": coder_state}

graph = StateGraph(dict)

graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)
graph.add_node("coder", coder_agent)

graph.add_edge("planner", "architect")
graph.add_edge("architect", "coder")
graph.add_conditional_edges(
    "coder",
    lambda s: "END" if s.get("status") == "DONE" else "coder",
    {"END": END, "coder": "coder"}
)

graph.set_entry_point("planner")

agent = graph.compile()
if __name__ == "__main__":
    result = agent.invoke({"user_prompt": "Build a colourful modern todo app in html css and js"},
                          {"recursion_limit": 100})
    print("Final State:", result)
