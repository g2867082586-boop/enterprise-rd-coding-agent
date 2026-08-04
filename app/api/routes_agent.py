from fastapi import APIRouter, Depends, HTTPException

from app.agent.graph import run_agent
from app.auth.dependencies import admin_user
from app.database.models import AppUser
from app.api.schemas import AgentRunRequest, AgentRunResponse
from app.config import get_settings
from app.tracing.recorder import read_traces


router = APIRouter(prefix="/api")


@router.post("/agent/run", response_model=AgentRunResponse)
async def agent_run(
    payload: AgentRunRequest, _: AppUser = Depends(admin_user)
) -> AgentRunResponse:
    state = await run_agent(payload.query, payload.session_id)
    sources = sorted({doc.get("source", "") for doc in state.get("retrieved_documents", []) if doc.get("source")})
    return AgentRunResponse(
        request_id=state["request_id"],
        status=state["status"],
        answer=state.get("final_answer") or "",
        sources=sources,
        tool_calls=state.get("tool_results", []),
        trace_summary={"events": len(read_traces(state["request_id"])), "thread_id": state["thread_id"]},
        runtime_mode={"llm": state.get("provider_mode", get_settings().llm_provider),
                      "retrieval": (state.get("retrieved_documents") or [{}])[0].get("retrieval_mode", get_settings().embedding_provider),
                      "database": get_settings().database_provider},
    )


@router.get("/agent/traces/{request_id}")
def traces(request_id: str, _: AppUser = Depends(admin_user)) -> dict[str, object]:
    events = read_traces(request_id)
    if not events:
        raise HTTPException(status_code=404, detail="trace not found")
    return {"request_id": request_id, "events": events}

