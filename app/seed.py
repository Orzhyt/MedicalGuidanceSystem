"""初始化示例数据：医院/科室/医生/排班（含演示满号）。

- 医院/科室/医生/排班仅首次写入，幂等。
- 演示满号通过排班规则上的 demo_booked 字段表达（按时段而非具体日期），
  窗口内每个匹配该时段的日期都会显示已占 demo_booked 个号。
- 运行时使用内存库，每次启动重新写入；快照由 scripts/export_db.py 生成到 data/medical.db。
"""
from __future__ import annotations

from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Department, Doctor, Hospital, Schedule

MORNING = (time(8, 0), time(12, 0))
AFTERNOON = (time(14, 0), time(17, 0))


def _has_base_data(db: Session) -> bool:
    return db.scalars(select(Hospital).limit(1)).first() is not None


def _seed_base_data(db: Session) -> None:
    """写入医院/科室/医生/排班（含演示满号），已有则跳过。"""
    if _has_base_data(db):
        return

    # ---------- 医院（虚构省市：云岭省星海市） ----------
    hospitals = [
        Hospital(name="云岭省星海市第一人民医院", level="三甲", address="云岭省星海市星海区人民路1号", phone="0571-88001000"),
        Hospital(name="云岭省星海市中心医院", level="三甲", address="云岭省星海市星海区中山路100号", phone="0571-88002000"),
        Hospital(name="云岭省星海市第二人民医院", level="三甲", address="云岭省星海市星海区解放路88号", phone="0571-88003000"),
    ]
    db.add_all(hospitals)
    db.flush()

    # ---------- 科室 ----------
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

    # ---------- 医生 ----------
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

    # ---------- 排班规则（含演示满号 demo_booked） ----------
    # (医生序号, 星期几, 时段, capacity, demo_booked)
    schedule_specs = [
        # 张建国(0): 周一/三上午满，周五上午空；周二/四下午空
        (0, 0, MORNING, 3, 3), (0, 2, MORNING, 3, 3), (0, 4, MORNING, 3, 0),
        (0, 1, AFTERNOON, 2, 0), (0, 3, AFTERNOON, 2, 0),
        # 李慧敏(1): 周二/四上午满，其余上午空
        (1, 0, MORNING, 5, 0), (1, 1, MORNING, 5, 5), (1, 2, MORNING, 5, 0),
        (1, 3, MORNING, 5, 5), (1, 4, MORNING, 5, 0),
        # 王志强(2): 周二上午满、周三下午满，周四上午空
        (2, 1, MORNING, 2, 2), (2, 3, MORNING, 2, 0), (2, 2, AFTERNOON, 2, 2),
        # 赵丽华(3): 周一/五下午满，周三下午空
        (3, 0, AFTERNOON, 4, 4), (3, 2, AFTERNOON, 4, 0), (3, 4, AFTERNOON, 4, 4),
        # 陈伟民(4): 周二/四上午满，其余空
        (4, 0, MORNING, 3, 0), (4, 1, MORNING, 3, 3), (4, 2, MORNING, 3, 0),
        (4, 3, MORNING, 3, 3), (4, 4, MORNING, 3, 0), (4, 5, MORNING, 3, 0),
        # 刘海洋(5): 周二下午满，周四下午空
        (5, 1, AFTERNOON, 2, 2), (5, 3, AFTERNOON, 2, 0),
        # 周明(6): 周一/四上午满，周二/五上午空
        (6, 0, MORNING, 2, 2), (6, 1, MORNING, 2, 0), (6, 3, MORNING, 2, 2), (6, 4, MORNING, 2, 0),
        # 吴小燕(7): 周三上午满、周一下午满，周五上午/周四下午空
        (7, 2, MORNING, 3, 3), (7, 4, MORNING, 3, 0), (7, 0, AFTERNOON, 3, 3), (7, 3, AFTERNOON, 3, 0),
        # 孙建华(8): 周一上午满、周五上午 5/6，其余空
        (8, 0, MORNING, 6, 6), (8, 1, MORNING, 6, 0), (8, 2, MORNING, 6, 0),
        (8, 3, MORNING, 6, 0), (8, 4, MORNING, 6, 5), (8, 5, MORNING, 4, 0),
    ]
    for doc_idx, wd, (st, et), cap, demo in schedule_specs:
        db.add(
            Schedule(
                doctor_id=doctors[doc_idx].id,
                weekday=wd,
                start_time=st,
                end_time=et,
                capacity=cap,
                demo_booked=demo,
            )
        )
    db.flush()


def seed_data() -> None:
    db = SessionLocal()
    try:
        _seed_base_data(db)
        db.commit()
    finally:
        db.close()
