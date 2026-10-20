"""Simulated evidence analysis only: never an actual credit decision."""
from typing import TypedDict
from fastapi import FastAPI
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
import ray

ray.init(num_cpus=2, include_dashboard=False, ignore_reinit_error=True)
app = FastAPI(title="VietPay Lending AI Demo")

class Request(BaseModel):
    application_id: int
    borrower_alias: str

@ray.remote
def document_task(application_id: int):
    return {"documents": "NOT_CHECKED", "message": "Demo only; no identity documents collected"}

@ray.remote
def fraud_task(application_id: int):
    return {"fraud_screening": "NOT_PERFORMED", "message": "No production fraud/credit decision"}

class State(TypedDict, total=False):
    application_id: int
    evidence: dict
    recommendation: str

def evidence_node(state: State):
    d, f = ray.get([document_task.remote(state["application_id"]), fraud_task.remote(state["application_id"])])
    return {"evidence": {"document": d, "fraud": f}}

def review_node(state: State):
    return {"recommendation": "HUMAN_REVIEW_REQUIRED"}

graph = StateGraph(State)
graph.add_node("gather_evidence", evidence_node)
graph.add_node("request_review", review_node)
graph.add_edge(START,"gather_evidence")
graph.add_edge("gather_evidence","request_review")
graph.add_edge("request_review",END)
workflow = graph.compile()

@app.get("/health")
def health(): return {"status": "ok", "mode": "simulation"}

@app.post("/analyze")
def analyze(request: Request):
    return workflow.invoke({"application_id": request.application_id})
