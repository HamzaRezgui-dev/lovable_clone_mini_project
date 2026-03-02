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

graph = StateGraph(dict)
graph.add_node("planner", planner_agent)
graph.set_entry_point("planner")

agent = graph.compile()

user_prompt = "create a simple calculator web application"

result = agent.invoke({"user_prompt": user_prompt})
print(result)