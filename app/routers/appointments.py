"""接口3：创建预约；接口4：按病人编号查询预约；接口5：取消预约。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.models import AppointmentStatus

router = APIRouter(prefix="/api/appointments", tags=["预约"])


@router.post(
    "",
    response_model=schemas.AppointmentCreateResponse,
    summary="创建预约（时间冲突则失败并返回可预约时段）",
)
def create_appointment(
    payload: schemas.AppointmentCreate, db: Session = Depends(get_db)
):
    return crud.create_appointment(db, payload)


@router.get(
    "",
    response_model=list[schemas.AppointmentOut],
    summary="按病人编号查询其全部预约",
)
def list_appointments_by_patient(
    patient_id: str = Query(..., description="病人编号/病历号"),
    db: Session = Depends(get_db),
):
    appts = crud.list_appointments_by_patient(db, patient_id)
    return [crud._to_appointment_out(a) for a in appts]


@router.delete(
    "",
    response_model=schemas.AppointmentOut,
    summary="取消预约（预约id+病人id均放query，归属匹配才取消）",
)
def cancel_appointment(
    appointment_id: int = Query(..., description="预约id"),
    patient_id: str = Query(..., description="病人编号，须与预约归属匹配"),
    db: Session = Depends(get_db),
):
    appt = crud.get_appointment(db, appointment_id)
    if appt is None:
        raise HTTPException(
            status_code=404, detail=f"预约不存在: id={appointment_id}"
        )
    if appt.patient_id != patient_id:
        raise HTTPException(
            status_code=403, detail="无权取消: patient_id 与该预约不匹配"
        )
    if appt.status != AppointmentStatus.CANCELLED:
        appt.status = AppointmentStatus.CANCELLED
        db.commit()
        db.refresh(appt)
    return crud._to_appointment_out(appt)
