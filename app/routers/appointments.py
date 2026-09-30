"""接口3：创建预约；接口4：查询预约详情；接口5：取消预约。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

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
    "/{appointment_id}",
    response_model=schemas.AppointmentOut,
    summary="根据预约id查询预约详情",
)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = crud.get_appointment(db, appointment_id)
    if appt is None:
        raise HTTPException(
            status_code=404, detail=f"预约不存在: id={appointment_id}"
        )
    return crud._to_appointment_out(appt)


@router.delete(
    "/{appointment_id}",
    response_model=schemas.AppointmentOut,
    summary="取消预约（软取消，释放号源）",
)
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = crud.cancel_appointment(db, appointment_id)
    if appt is None:
        raise HTTPException(
            status_code=404, detail=f"预约不存在: id={appointment_id}"
        )
    return crud._to_appointment_out(appt)
