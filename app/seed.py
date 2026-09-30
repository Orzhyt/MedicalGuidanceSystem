"""初始化示例数据：医院/科室/医生/排班 + 演示用已约满时段。

- 基础数据（医院/科室/医生/排班）仅首次写入，幂等。
- 演示预约每次启动按"明天起两周"的当前窗口刷新，保证任意日期运行都有已满时段可演示。
  演示预约以 is_demo=True 标记，刷新只动演示行，不影响真实用户预约。
"""
from __future__ import annotations

from datetime import date, time, timedelta

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.crud import booking_window
from app.database import SessionLocal
from app.models import (
    Appointment,
    AppointmentStatus,
    Department,
    Doctor,
    Hospital,
    Schedule,
)

MORNING = (time(8, 0), time(12, 0))
AFTERNOON = (time(14, 0), time(17, 0))


# 演示目标：(医生序号, 星期几, 时段, 欲占满号数)
DEMO_TARGETS: list[tuple[int, int, tuple[time, time], int]] = [
    (0, 0, MORNING, 3),   # 张建国 周一上午 满
    (0, 2, MORNING, 3),   # 张建国 周三上午 满
    (2, 1, MORNING, 2),   # 王志强 周二上午 满
    (6, 0, MORNING, 2),   # 周明 周一上午 满
    (8, 4, MORNING, 5),   # 孙建华 周五上午 5/6（剩1）
]


def _has_base_data(db: Session) -> bool:
    return db.scalars(select(Hospital).limit(1)).first() is not None


def _seed_base_data(db: Session) -> None:
    """首次写入医院/科室/医生/排班，已有则跳过。"""
    if _has_base_data(db):
        return

    hospitals = [
        Hospital(name="北京协和医院", level="三甲", address="北京市东城区帅府园1号", phone="010-69151188"),
        Hospital(name="上海瑞金医院", level="三甲", address="上海市黄浦区瑞金二路197号", phone="021-64370045"),
        Hospital(name="杭州市第一人民医院", level="三甲", address="杭州市上城区浣纱路261号", phone="0571-87065701"),
    ]
    db.add_all(hospitals)
    db.flush()

    dept_specs = [
        (0, "内科", "消化、呼吸、心血管等常见内科疾病"),
        (0, "外科", "普外、胸外、泌尿外科手术"),
        (0, "妇产科", "妇科与产前产后诊疗"),
        (1, "内科", "消化、内分泌、风湿免疫"),
        (1, "骨科", "创伤、关节、脊柱外科"),
        (1, "神经内科", "脑血管病、癫痫、头痛"),
        (2, "内科", "常见内科疾病综合诊疗"),
        (2, "儿科", "儿童常见病与保健"),
    ]
    departments: list[Department] = []
    for h_idx, name, desc in dept_specs:
        departments.append(Department(hospital_id=hospitals[h_idx].id, name=name, description=desc))
    db.add_all(departments)
    db.flush()

    doctor_specs = [
        (0, "张建国", "主任医师", "心血管内科"),
        (0, "李慧敏", "主治医师", "消化内科"),
        (1, "王志强", "主任医师", "普外科"),
        (2, "赵丽华", "副主任医师", "高危产科"),
        (3, "陈伟民", "主任医师", "内分泌科"),
        (4, "刘海洋", "主治医师", "关节外科"),
        (5, "周明", "主任医师", "脑血管病"),
        (6, "吴小燕", "副主任医师", "呼吸内科"),
        (7, "孙建华", "主任医师", "儿童保健"),
    ]
    doctors: list[Doctor] = []
    for d_idx, name, title, spec in doctor_specs:
        doctors.append(
            Doctor(
                department_id=departments[d_idx].id,
                name=name,
                title=title,
                specialty=spec,
                description=f"{title}，擅长{spec}方向",
            )
        )
    db.add_all(doctors)
    db.flush()

    schedule_specs = [
        (0, 0, MORNING, 3), (0, 2, MORNING, 3), (0, 4, MORNING, 3),
        (0, 1, AFTERNOON, 2), (0, 3, AFTERNOON, 2),
        (1, 0, MORNING, 5), (1, 1, MORNING, 5), (1, 2, MORNING, 5),
        (1, 3, MORNING, 5), (1, 4, MORNING, 5),
        (2, 1, MORNING, 2), (2, 3, MORNING, 2), (2, 2, AFTERNOON, 2),
        (3, 0, AFTERNOON, 4), (3, 2, AFTERNOON, 4), (3, 4, AFTERNOON, 4),
        (4, 0, MORNING, 3), (4, 1, MORNING, 3), (4, 2, MORNING, 3),
        (4, 3, MORNING, 3), (4, 4, MORNING, 3), (4, 5, MORNING, 3),
        (5, 1, AFTERNOON, 2), (5, 3, AFTERNOON, 2),
        (6, 0, MORNING, 2), (6, 1, MORNING, 2), (6, 3, MORNING, 2), (6, 4, MORNING, 2),
        (7, 2, MORNING, 3), (7, 4, MORNING, 3), (7, 0, AFTERNOON, 3), (7, 3, AFTERNOON, 3),
        (8, 0, MORNING, 6), (8, 1, MORNING, 6), (8, 2, MORNING, 6),
        (8, 3, MORNING, 6), (8, 4, MORNING, 6), (8, 5, MORNING, 4),
    ]
    for doc_idx, wd, (st, et), cap in schedule_specs:
        db.add(Schedule(doctor_id=doctors[doc_idx].id, weekday=wd, start_time=st, end_time=et, capacity=cap))
    db.flush()


def _first_date_in_window(start: date, end: date, weekday: int) -> date:
    d = start
    while d <= end:
        if d.weekday() == weekday:
            return d
        d += timedelta(days=1)
    return start


def _count_booked(
    db: Session, doctor_id: int, slot_date: date, start_time: time, demo: bool | None
) -> int:
    stmt = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.slot_date == slot_date,
        Appointment.start_time == start_time,
        Appointment.status == AppointmentStatus.CONFIRMED,
    )
    if demo is True:
        stmt = stmt.where(Appointment.is_demo.is_(True))
    elif demo is False:
        stmt = stmt.where(Appointment.is_demo.is_(False))
    return len(list(db.scalars(stmt)))


def _refresh_demo_appointments(db: Session) -> None:
    """按当前可预约窗口刷新演示预约：清理窗口外的旧演示行，并将目标时段补满到期望数。"""
    start, end = booking_window()

    # 1. 清理落在当前窗口之外的演示预约（已过期或窗口滚动后失效）
    db.execute(
        delete(Appointment).where(
            Appointment.is_demo.is_(True),
            or_(Appointment.slot_date < start, Appointment.slot_date > end),
        )
    )

    doctors = list(db.scalars(select(Doctor).order_by(Doctor.id)))
    if not doctors:
        return

    for doc_idx, wd, (st, et), fill_count in DEMO_TARGETS:
        if doc_idx >= len(doctors):
            continue
        doctor = doctors[doc_idx]
        slot_date = _first_date_in_window(start, end, wd)

        # 该时段的号源容量（用于 clamp）
        schedule = next(
            (s for s in doctor.schedules if s.weekday == wd and s.start_time == st),
            None,
        )
        if schedule is None:
            continue
        desired_total = min(fill_count, schedule.capacity)
        real_booked = _count_booked(db, doctor.id, slot_date, st, demo=False)
        desired_demo = max(0, desired_total - real_booked)
        current_demo = _count_booked(db, doctor.id, slot_date, st, demo=True)

        if current_demo < desired_demo:
            for k in range(desired_demo - current_demo):
                db.add(
                    Appointment(
                        doctor_id=doctor.id,
                        slot_date=slot_date,
                        start_time=st,
                        end_time=et,
                        patient_name=f"示例患者{k + 1}",
                        patient_phone="13800000000",
                        status=AppointmentStatus.CONFIRMED,
                        is_demo=True,
                    )
                )
        elif current_demo > desired_demo:
            excess = list(
                db.scalars(
                    select(Appointment).where(
                        Appointment.doctor_id == doctor.id,
                        Appointment.slot_date == slot_date,
                        Appointment.start_time == st,
                        Appointment.status == AppointmentStatus.CONFIRMED,
                        Appointment.is_demo.is_(True),
                    )
                )
            )
            for appt in excess[: current_demo - desired_demo]:
                db.delete(appt)


def seed_data() -> None:
    db = SessionLocal()
    try:
        _seed_base_data(db)
        _refresh_demo_appointments(db)
        db.commit()
    finally:
        db.close()
