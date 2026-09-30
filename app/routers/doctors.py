"""接口2：查询某医生未来两周可预约时段。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/api/doctors", tags=["医生时段"])


@router.get(
    "/{doctor_id}/slots",
    response_model=schemas.DoctorSlotsResponse,
    summary="查询医生可预约时段（默认两周）",
)
def get_doctor_slots(
    doctor_id: int,
    db: Session = Depends(get_db),
    days: int = Query(14, ge=1, le=30, description="查询未来天数，默认14"),
):
    doctor = crud.get_doctor(db, doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail=f"医生不存在: id={doctor_id}")

    slots = crud.get_doctor_slots(db, doctor_id, days=days)
    available_count = sum(1 for s in slots if not s.is_full)
    return schemas.DoctorSlotsResponse(
        doctor=schemas.DoctorBrief.model_validate(doctor),
        days=days,
        slots=slots,
        available_count=available_count,
    )
