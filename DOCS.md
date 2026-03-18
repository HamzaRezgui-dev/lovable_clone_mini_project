# Coder Buddy — Documentation

Coder Buddy is a LangGraph-powered multi-agent pipeline that takes a plain-English project description and generates a working codebase from scratch. It chains three specialized AI agents — Planner, Architect, and Coder — each building on the previous agent's output until all files are written.

---

## Table of Contents

1. [Setup](#setup)
2. [Usage](#usage)
3. [How It Works](#how-it-works)
4. [Agent Pipeline](#agent-pipeline)
   - [Planner Agent](#1-planner-agent)
   - [Architect Agent](#2-architect-agent)
   - [Coder Agent](#3-coder-agent)
5. [State Model](#state-model)
6. [Tools](#tools)
7. [Prompts](#prompts)
8. [File Sandbox](#file-sandbox)
9. [Project Structure](#project-structure)
10. [Configuration & Environment](#configuration--environment)
11. [Known Limitations & Notes](#known-limitations--notes)

---

## Setup

**Requirements:** Python 3.11–3.13, [uv](https://github.com/astral-sh/uv)

```bash
# Clone and enter the repo
git clone <repo-url>
cd app_builder

# Install dependencies
uv sync

# Create a .env file and add your Groq API key
echo "GROQ_API_KEY=your_key_here" > .env
```

---

## Usage

```bash
# Start the interactive CLI
python main.py

# Enter your project prompt when asked, e.g.:
# "Build a colourful modern todo app in HTML, CSS, and JS"
```

The generated project files will be written to `agent/generated_project/`.

**Optional flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--recursion-limit`, `-r` | `100` | Max LangGraph recursion depth. Raise this for projects with many implementation steps. |

```bash
python main.py --recursion-limit 200
```

You can also invoke the graph directly (useful for quick testing):

```bash
python agent/graph.py
```

This runs a hardcoded prompt: `"Build a colourful modern todo app in html css and js"`.

---

## How It Works

At a high level:

1. You provide a natural language description of a project.
2. The **Planner** converts it into a structured plan (tech stack, features, file list).
3. The **Architect** breaks that plan into ordered, file-level implementation tasks.
4. The **Coder** executes each task one by one, writing the actual code using file I/O tools.

All three agents use the same underlying LLM: **Groq `llama-3.3-70b-versatile`** with structured output via Pydantic models where applicable.

---

## Agent Pipeline

The pipeline is a [LangGraph](https://github.com/langchain-ai/langgraph) `StateGraph` with the following topology:

```
[START] → planner → architect → coder ──(loop)──┐
                                    ↑            │
                                    └────────────┘
                                         ↓ (when done)
                                        [END]
```

The coder node uses a **self-loop with a conditional edge**: it processes one implementation step per invocation and routes back to itself until all steps are exhausted.

### 1. Planner Agent

**Node:** `planner`
**Function:** `planner_agent(state) -> dict`
**Input state key:** `user_prompt`
**Output state key:** `plan`

Calls the LLM with `structured_output(Plan)` to convert the raw user prompt into a validated `Plan` object. The plan includes the app name, a one-line description, the tech stack, a list of features, and a list of file paths to be created.

**Example output (Plan):**
```json
{
  "name": "Todo App",
  "description": "A colourful modern todo application",
  "techStack": "HTML, CSS, JavaScript",
  "features": ["Add tasks", "Delete tasks", "Mark complete"],
  "files": ["index.html", "style.css", "src/js/utils.js"]
}
```

---

### 2. Architect Agent

**Node:** `architect`
**Function:** `architect_agent(state) -> dict`
**Input state key:** `plan`
**Output state key:** `task_plan`

Takes the `Plan` and calls the LLM with `structured_output(TaskPlan)` to produce an ordered list of `ImplementationTask` objects. Each task is tied to a specific file and includes a detailed description of what to implement — including variable names, function signatures, imports, and integration points with other files.

Tasks are ordered so that dependencies are implemented first (e.g., utility functions before the module that uses them).

**Example output (TaskPlan):**
```json
{
  "implementation_steps": [
    {
      "filepath": "src/js/utils.js",
      "task_description": "Implement addTask(title), deleteTask(id), toggleComplete(id)..."
    },
    {
      "filepath": "index.html",
      "task_description": "Create the HTML skeleton, import style.css and src/js/utils.js..."
    }
  ]
}
```

---

### 3. Coder Agent

**Node:** `coder`
**Function:** `coder_agent(state) -> dict`
**Input state keys:** `task_plan`, `coder_state`
**Output state keys:** `coder_state`, `status`

The coder is a **ReAct agent** (LangChain `create_agent`) that receives one `ImplementationTask` at a time and uses file tools to read existing content and write the completed implementation.

**Loop logic:**

```
Enter coder node
  │
  ├─ coder_state is None? → initialize with current_step_idx = 0
  │
  ├─ current_step_idx >= total steps? → set status = "DONE" → exit to END
  │
  ├─ Read existing file content (if any)
  ├─ Build system + user prompt for current task
  ├─ Invoke ReAct agent (LLM + tools)
  ├─ Increment current_step_idx
  └─ Return → conditional edge → loop back to coder
```

The conditional edge routing:

```python
lambda s: "END" if s.get("status") == "DONE" else "coder"
```

---

## State Model

Defined in `agent/states.py` using Pydantic v2.

### `Plan`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | App name |
| `description` | `str` | One-line app description |
| `techStack` | `str` | Technology stack (e.g. "Python, FastAPI") |
| `features` | `list[str]` | Feature list |
| `files` | `list[str]` | File paths to be created |

### `ImplementationTask`

| Field | Type | Description |
|-------|------|-------------|
| `filepath` | `str` | Path to the file (relative to project root) |
| `task_description` | `str` | Detailed description of what to implement |

### `TaskPlan`

| Field | Type | Description |
|-------|------|-------------|
| `implementation_steps` | `list[ImplementationTask]` | Ordered list of tasks |

Configured with `model_config = ConfigDict(extra="allow")` so the LLM can return additional fields without validation errors.

### `CoderState`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task_plan` | `TaskPlan` | — | The full task plan |
| `current_step_idx` | `int` | `0` | Index of the next step to execute |
| `current_file_content` | `Optional[str]` | `None` | Content of file being edited (unused currently) |

---

## Tools

Defined in `agent/tools.py`. All tools are decorated with `@tool` (LangChain) and exposed to the coder's ReAct agent. All file paths are sandboxed to `agent/generated_project/` via `safe_path_for_project()`.

### `write_file(path, content)`

Writes `content` to the given `path` within the project root. Creates parent directories as needed.

Returns: `"WROTE:<absolute_path>"`

### `read_file(path)`

Reads and returns the content of the file at `path`. Returns an empty string if the file does not exist.

### `list_files(directory=".")`

Recursively lists all files under `directory` within the project root.

Returns: newline-separated relative paths, or `"No files found."`.

### `get_current_directory()`

Returns the absolute path of the project root (`agent/generated_project/`).

### `run_cmd(cmd, cwd=None, timeout=30)`

Runs a shell command inside the project root (or a subdirectory). Returns `(returncode, stdout, stderr)`.

> **Note:** `run_cmd` is defined but not currently included in the tools list passed to the coder's ReAct agent.

### `safe_path_for_project(path)`

Internal utility. Resolves `path` relative to `PROJECT_ROOT` and raises `ValueError` if the resolved path escapes the project root (path traversal protection).

---

## Prompts

Defined in `agent/prompts.py`.

### `planner_prompt(user_prompt)`

Instructs the LLM to act as a PLANNER and convert the user request into a complete engineering project plan.

### `architect_prompt(plan)`

Instructs the LLM to act as an ARCHITECT and break the plan into explicit, ordered engineering tasks. Key rules enforced in the prompt:
- One or more tasks per file
- Each task must name specific variables, functions, classes, and components
- Dependencies must be declared between tasks
- Tasks must be ordered so dependencies come first

### `coder_system_prompt()`

Instructs the LLM to act as a CODER implementing a specific task. Key rules enforced:
- Review all existing files before writing
- Implement the full file content, not just the changed portion
- Maintain consistent naming across modules
- Ensure imported symbols actually exist in their source files

---

## File Sandbox

All generated output is confined to `agent/generated_project/` (resolved relative to `cwd` at runtime).

```python
PROJECT_ROOT = pathlib.Path.cwd() / "generated_project"
```

`safe_path_for_project()` resolves any given path and checks that it is a descendant of `PROJECT_ROOT`. Any attempt to write outside this directory (e.g., via `../../` path traversal) raises a `ValueError` before any I/O occurs.

> **Note:** `PROJECT_ROOT` is computed from `cwd` at import time. If you run the script from a directory other than `agent/`, the sandbox root will move accordingly. Run from the repo root (`python main.py`) or from `agent/` (`python graph.py`) for predictable behavior.

---

## Project Structure

```
app_builder/
├── main.py                  # CLI entry point
├── pyproject.toml           # Project metadata and dependencies (uv/PEP 517)
├── uv.lock                  # Locked dependency versions
├── .env                     # GROQ_API_KEY (not committed)
└── agent/
    ├── graph.py             # LangGraph graph definition + node functions
    ├── states.py            # Pydantic state models
    ├── prompts.py           # Prompt templates
    ├── tools.py             # LangChain file I/O tools
    └── generated_project/   # Output directory — all generated code goes here
```

---

## Configuration & Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | API key for the Groq LLM provider |

The `.env` file is loaded automatically at startup via `python-dotenv`.

**LLM:** `llama-3.3-70b-versatile` via `langchain-groq`. To change the model, update the `llm` initialization in `agent/graph.py`:

```python
llm = ChatGroq(model="llama-3.3-70b-versatile")
```

---

## Known Limitations & Notes

- **Import paths in `graph.py`:** The file uses `from prompts import *` and `from states import *` (bare imports without the `agent.` prefix). These only resolve correctly when `agent/` is on `sys.path` — which happens automatically when running `python agent/graph.py` directly, but not when imported as a module. `main.py` imports `from agent.graph import agent`, so this is a latent bug if the bare imports are not resolved by the time the module loads.

- **`CoderState.current_file_content`** is declared in the state model but not populated during execution — it is reserved for future use.

- **`run_cmd` tool** is implemented but not passed to the coder's ReAct agent in the current tool list.

- **Recursion limit:** LangGraph's recursion limit applies to the number of node invocations. For projects with many implementation steps, increase it via `--recursion-limit`.

- **No retry logic:** If the LLM returns `None` for the architect step, the pipeline raises a `ValueError` immediately. There is no retry or fallback.
