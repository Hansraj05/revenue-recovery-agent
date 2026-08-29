import json
import time
from typing import TypedDict
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from app.core.config import settings

class AgentState(TypedDict):
    transaction_id: int
    failure_reason: str
    decision: dict | None

def analyze_failure(state: AgentState):
    # Enforce a short delay to respect Groq's free tier rate limit
    time.sleep(2.5)

    llm = ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0,
        api_key=settings.groq_api_key
    ).bind(response_format={"type": "json_object"})

    prompt = """You are a fintech AI recovery agent. 
    Analyze the failure reason and return ONLY a valid JSON object with exactly two keys: "action" and "explanation".
    
    Action Rules:
    - "SCHEDULE_RETRY_24H": For insufficient funds, low balance, limit exceeded.
    - "IMMEDIATE_RETRY": For network timeouts, gateway errors, 503.
    - "PERMANENT_FAILURE": For stolen/invalid cards, expired cards, closed accounts.
    
    Failure to analyze: {failure_reason}
    """

    try:
        response = llm.invoke(prompt.format(failure_reason=state["failure_reason"]))
        decision = json.loads(response.content)
        return {"decision": decision}
    except Exception as e:
        # An LLM/API failure is not evidence the payment is unrecoverable —
        # escalate for manual review rather than writing it off permanently.
        return {"decision": {
            "action": "NEEDS_MANUAL_REVIEW",
            "explanation": f"Classification failed, escalated for review: {e}"
        }}

def build_agent_graph():
    builder = StateGraph(AgentState)
    builder.add_node("analyze", analyze_failure)
    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", END)
    return builder.compile()

agent_graph = build_agent_graph()