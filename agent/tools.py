import pathlib
import re
from langchain_core.tools import tool

# Anchored to this file's location — deterministic regardless of cwd
PROJECT_ROOT = pathlib.Path(__file__).parent / "generated_project"

# Allowlist: letters, digits, dots, hyphens, underscores, forward slashes only
_SAFE_PATH_RE = re.compile(r'^[a-zA-Z0-9._\-/]+$')
_MAX_PATH_LENGTH = 260
_WINDOWS_RESERVED = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
}
_MAX_READ_BYTES = 102_400  # 100 KB hard cap on file reads


def _validate_path_chars(path: str) -> None:
    """Reject paths with unsafe characters, reserved names, or excessive length."""
    if len(path) > _MAX_PATH_LENGTH:
        raise ValueError(f"Path too long ({len(path)} chars, max {_MAX_PATH_LENGTH})")
    if not _SAFE_PATH_RE.match(path):
        raise ValueError(f"Path contains unsafe characters: {path!r}")
    for part in pathlib.PurePosixPath(path).parts:
        if pathlib.Path(part).stem.upper() in _WINDOWS_RESERVED:
            raise ValueError(f"Path contains reserved name: {part!r}")


def safe_path_for_project(path: str) -> pathlib.Path:
    _validate_path_chars(path)
    resolved_root = PROJECT_ROOT.resolve()
    p = (PROJECT_ROOT / path).resolve()
    # is_relative_to (Python 3.9+) checks the resolved path, catching symlink escapes
    if not p.is_relative_to(resolved_root):
        raise ValueError("Attempt to access path outside project root")
    return p


@tool
def write_file(path: str, content: str) -> str:
    """Writes content to a file at the specified path within the project root."""
    p = safe_path_for_project(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return f"WROTE:{p}"


@tool
def read_file(path: str) -> str:
    """Reads content from a file at the specified path within the project root."""
    p = safe_path_for_project(path)
    if not p.exists():
        return ""
    with open(p, "r", encoding="utf-8") as f:
        content = f.read(_MAX_READ_BYTES)
    if len(content) == _MAX_READ_BYTES:
        content += "\n... [file truncated at 100 KB]"
    return content


@tool
def get_current_directory() -> str:
    """Returns the project root directory."""
    return str(PROJECT_ROOT)


@tool
def list_files(directory: str = ".") -> str:
    """Lists all files in the specified directory within the project root."""
    p = safe_path_for_project(directory)
    if not p.is_dir():
        return f"ERROR: {p} is not a directory"
    files = [str(f.relative_to(PROJECT_ROOT)) for f in p.glob("**/*") if f.is_file()]
    return "\n".join(files) if files else "No files found."


def init_project_root():
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    return str(PROJECT_ROOT)
