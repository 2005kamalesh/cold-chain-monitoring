"""FastAPI backend.  Run:  uvicorn coldchain.api:app --reload   (docs at http://localhost:8000/docs)"""
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import service

app = FastAPI(title="Cold Chain Monitoring API", version="1.0")


def guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


class ActionIn(BaseModel):
    excursion_id: str
    assigned_role: str = "QUALITY_ENGINEER"
    action_description: str
    priority: str = Field("MEDIUM", pattern="^(LOW|MEDIUM|HIGH)$")
    created_by: str = "API"


class StatusIn(BaseModel):
    new_status: str = Field(pattern="^(OPEN|ASSIGNED|IN_PROGRESS|RESOLVED|VERIFIED)$")
    changed_by: str
    reason: Optional[str] = None
    resolution_text: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard/summary")
def summary():
    return service.summary()


@app.get("/shipments")
def shipments(compliance_status: Optional[str] = None, limit: int = 1000):
    return service.list_shipments(compliance_status, limit)


@app.get("/shipments/{shipment_id}")
def shipment(shipment_id: str):
    return guard(service.shipment_detail, shipment_id)


@app.get("/shipments/{shipment_id}/readings")
def shipment_readings(shipment_id: str):
    return service.readings(shipment_id)


@app.get("/sensors")
def sensors():
    return service.sensors()


@app.get("/excursions")
def excursions(severity: Optional[str] = None, excursion_type: Optional[str] = None, status: Optional[str] = None, shipment_id: Optional[str] = None):
    return service.excursions(severity, excursion_type, status, shipment_id)


@app.get("/gaps")
def gaps(exceeds_tolerance: Optional[int] = None):
    return service.gaps(exceeds_tolerance)


@app.get("/issues")
def issues(issue_type: Optional[str] = None):
    return service.issues(issue_type)


@app.get("/notifications")
def notifications(recipient_role: Optional[str] = None):
    return service.notifications(recipient_role)


@app.get("/corrective-actions")
def corrective_actions(status: Optional[str] = None, excursion_id: Optional[str] = None):
    return service.corrective_actions(status, excursion_id)


@app.get("/corrective-actions/{action_id}/history")
def action_history(action_id: str):
    return service.action_history(action_id)


@app.post("/corrective-actions", status_code=201)
def create_action(body: ActionIn):
    return guard(service.create_action, body.excursion_id, body.assigned_role, body.action_description, body.priority, None, body.created_by)


@app.patch("/corrective-actions/{action_id}/status")
def advance_action(action_id: str, body: StatusIn):
    return guard(service.advance_action, action_id, body.new_status, body.changed_by, body.reason, body.resolution_text)


@app.get("/evaluation")
def evaluation():
    return guard(service.evaluation)
