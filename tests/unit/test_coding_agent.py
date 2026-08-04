from uuid import uuid4

import pytest

from app.coding.agent import run_coding_task
from app.coding.schemas import CodePatchProposal
from app.tools.codebase_tool import discard_code_workspace


@pytest.mark.asyncio
async def test_coding_agent_applies_patch_and_runs_checks() -> None:
    workspace_id = f"coding-{uuid4().hex[:12]}"

    async def propose(issue: str, context: str, feedback: str) -> CodePatchProposal:
        assert issue
        assert context
        assert feedback == ""
        return CodePatchProposal(
            summary="add isolated demo file",
            patch_text="""diff --git a/coding_agent_demo.txt b/coding_agent_demo.txt
new file mode 100644
--- /dev/null
+++ b/coding_agent_demo.txt
@@ -0,0 +1 @@
+coding agent isolated edit
""",
            test_path="tests/unit/test_security_guards.py",
        )

    try:
        result = await run_coding_task(
            "Add a small coding agent demo file", workspace_id, proposal_factory=propose
        )
        assert result["status"] == "passed"
        assert "coding_agent_demo.txt" in result["diff"]
        assert result["attempts"][0]["checks_passed"] is True
    finally:
        discard_code_workspace(workspace_id)
