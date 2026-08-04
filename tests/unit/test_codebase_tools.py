from pathlib import Path
from uuid import uuid4

import pytest

from app.tools.codebase_tool import (
    CodeWorkspaceError,
    apply_code_patch,
    create_code_workspace,
    discard_code_workspace,
    git_diff,
    list_repository,
    read_code_file,
    search_code,
)


def test_read_only_code_tools_find_real_symbols() -> None:
    files = list_repository(relative_path="app/agent", max_entries=50)
    assert "app/agent/graph.py" in files
    matches = search_code("async def run_agent", relative_path="app")
    assert any(row["path"] == "app/agent/graph.py" for row in matches)
    content = read_code_file("app/agent/graph.py", start_line=90, end_line=110)
    assert "run_agent" in content["content"]


def test_paths_cannot_escape_repository() -> None:
    with pytest.raises(CodeWorkspaceError):
        read_code_file("../../outside.txt")


def test_patch_is_applied_only_in_isolated_worktree() -> None:
    workspace_id = f"pytest-{uuid4().hex[:12]}"
    create_code_workspace(workspace_id)
    try:
        patch = """diff --git a/coding_demo.txt b/coding_demo.txt
new file mode 100644
--- /dev/null
+++ b/coding_demo.txt
@@ -0,0 +1 @@
+isolated coding workspace
"""
        result = apply_code_patch(workspace_id, patch)
        assert result["applied"] is True
        assert "coding_demo.txt" in git_diff(workspace_id)["diff"]
        assert not (Path.cwd() / "coding_demo.txt").exists()
    finally:
        discard_code_workspace(workspace_id)
