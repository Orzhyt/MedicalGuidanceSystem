"""核心业务逻辑：查询树、时段生成、创建/查询预约。"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import models, schemas
from app.models import Appointment, AppointmentStatus, Department, Doctor, Hospital, Schedule

# 可预约窗口：从明天起 BOOKING_DAYS 天
BOOKING_DAYS = 14
BOOKING_START_OFFSET = 1


def booking_window(days: int = BOOKING_DAYS) -> tuple[date, date]:
    """返回可预约窗口 [start, end]（含端点），起点为明天。"""
    start = date.today() + timedelta(days=BOOKING_START_OFFSET)
    end = start + timedelta(days=days - 1)
    return start, end


# ---------------- 医院-科室-医生 树 ----------------
def get_hospitals_tree(db: Session, hospital_id: int | None = None) -> list[Hospital]:
    """一次性加载 医院->科室->医生 树状结构。"""
    stmt = (
        select(Hospital)
        .options(
            selectinload(Hospital.departments).selectinload(Department.doctors),
        )
        .order_by(Hospital.id)
    )
    if hospital_id is not None:
        stmt = stmt.where(Hospital.id == hospital_id)
    return list(db.scalars(stmt).unique())


# ---------------- 医生时段 ----------------
def get_doctor(db: Session, doctor_id: int) -> Doctor | None:
    return db.get(Doctor, doctor_id)


def _booked_count(db: Session, doctor_id: int, slot_date: date, start_time) -> int:
    """统计某医生某天某时段已确认预约数。"""
    stmt = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.slot_date == slot_date,
        Appointment.start_time == start_time,
        Appointment.status == AppointmentStatus.CONFIRMED,
    )
    return len(list(db.scalars(stmt)))


def _build_slot(
    db: Session, doctor_id: int, slot_date: date, schedule: Schedule
) -> schemas.SlotOut:
    booked = _booked_count(db, doctor_id, slot_date, schedule.start_time)
    available = schedule.capacity - booked
    return schemas.SlotOut(
        slot_date=slot_date,
        weekday=schedule.weekday,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        capacity=schedule.capacity,
        booked_count=booked,
        available=available,
        is_full=available <= 0,
    )


def get_doctor_slots(
    db: Session, doctor_id: int, days: int = BOOKING_DAYS
) -> list[schemas.SlotOut]:
    """生成医生可预约窗口内（明天起 days 天）的所有时段及余号。"""
    doctor = get_doctor(db, doctor_id)
    if doctor is None:
        return []

    schedules = list(doctor.schedules)
    if not schedules:
        return []

    start, _ = booking_window(days)
    slots: list[schemas.SlotOut] = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        wd = d.weekday()
        for sch in schedules:
            if sch.weekday == wd:
                slots.append(_build_slot(db, doctor_id, d, sch))
    slots.sort(key=lambda s: (s.slot_date, s.start_time))
    return slots


# ---------------- 创建预约 ----------------
def create_appointment(
    db: Session, payload: schemas.AppointmentCreate
) -> schemas.AppointmentCreateResponse:
    doctor = get_doctor(db, payload.doctor_id)
    if doctor is None:
        return schemas.AppointmentCreateResponse(
            success=False,
            message=f"医生不存在: id={payload.doctor_id}",
            available_slots=[],
        )

    today = date.today()
    start, end = booking_window()
    if payload.slot_date < start:
        return schemas.AppointmentCreateResponse(
            success=False,
            message="预约日期不能早于明天",
            available_slots=get_doctor_slots(db, payload.doctor_id),
        )
    if payload.slot_date > end:
        return schemas.AppointmentCreateResponse(
            success=False,
            message=f"预约日期超出可预约窗口（{end}）",
            available_slots=get_doctor_slots(db, payload.doctor_id),
        )

    # 匹配排班规则（星期几 + 开始时间）
    wd = payload.slot_date.weekday()
    schedule = next(
        (s for s in doctor.schedules if s.weekday == wd and s.start_time == payload.start_time),
        None,
    )
    if schedule is None:
        return schemas.AppointmentCreateResponse(
            success=False,
            message="该时段不在医生的排班规则中",
            available_slots=get_doctor_slots(db, payload.doctor_id),
        )

    # 容量校验
    booked = _booked_count(db, payload.doctor_id, payload.slot_date, payload.start_time)
    if booked >= schedule.capacity:
        return schemas.AppointmentCreateResponse(
            success=False,
            message="该时段已约满，请选择其他时段",
            available_slots=get_doctor_slots(db, payload.doctor_id),
        )

    # 创建预约
    appointment = Appointment(
        doctor_id=payload.doctor_id,
        slot_date=payload.slot_date,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
        patient_name=payload.patient_name,
        patient_phone=payload.patient_phone,
        status=AppointmentStatus.CONFIRMED,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return schemas.AppointmentCreateResponse(
        success=True,
        message="预约成功",
        appointment=_to_appointment_out(appointment),
    )


# ---------------- 查询预约 ----------------
def get_appointment(db: Session, appointment_id: int) -> Appointment | None:
    stmt = (
        select(Appointment)
        .options(
            selectinload(Appointment.doctor).selectinload(Doctor.department).selectinload(Department.hospital),
        )
        .where(Appointment.id == appointment_id)
    )
    return db.scalars(stmt).first()


def _to_appointment_out(appt: Appointment) -> schemas.AppointmentOut:
    doctor = appt.doctor
    dept = doctor.department
    hospital = dept.hospital
    return schemas.AppointmentOut(
        id=appt.id,
        doctor_id=doctor.id,
        doctor_name=doctor.name,
        title=doctor.title,
        department_id=dept.id,
        department_name=dept.name,
        hospital_id=hospital.id,
        hospital_name=hospital.name,
        slot_date=appt.slot_date,
        start_time=appt.start_time,
        end_time=appt.end_time,
        patient_name=appt.patient_name,
        patient_phone=appt.patient_phone,
        status=appt.status,
        created_at=appt.created_at,
    )
