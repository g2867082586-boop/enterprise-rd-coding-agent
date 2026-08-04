from pydantic import BaseModel, Field


class CodePatchProposal(BaseModel):
    summary: str = Field(min_length=2, max_length=500)
    patch_text: str = Field(min_length=10, max_length=100_000)
    test_path: str = Field(default="tests/unit", pattern=r"^tests(?:[/\\][A-Za-z0-9_.\-/\\]+)?$")
