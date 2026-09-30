"""Pydantic v2 响应/请求模型。"""
from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models import AppointmentStatus


class ORMBase(BaseModel):
    """继承 ORM 对象的通用基类。"""

    model_config = ConfigDict(from_attributes=True)


# ---------- 医院 / 科室 / 医生 树状结构 ----------
class DoctorBrief(ORMBase):
    id: int
    name: str
    title: str
    specialty: str | None = None
    description: str | None = None


class DepartmentOut(ORMBase):
    id: int
    hospital_id: int
    name: str
    description: str | None = None
    doctors: list[DoctorBrief] = Field(default_factory=list)


class HospitalOut(ORMBase):
    id: int
    name: str
    level: str
    address: str | None = None
    phone: str | None = None
    departments: list[DepartmentOut] = Field(default_factory=list)


# ---------- 时段 ----------
class SlotOut(BaseModel):
    """单个可预约时段。"""

    slot_date: date
    weekday: int = Field(description="0=周一...6=周日")
    start_time: time
    end_time: time
    capacity: int
    booked_count: int
    available: int
    is_full: bool


class DoctorSlotsResponse(ORMBase):
    """医生两周内可预约时段汇总。"""

    doctor: DoctorBrief
    days: int = Field(description="查询天数")
    window_start: date = Field(description="可预约窗口起点（含）")
    window_end: date = Field(description="可预约窗口终点（含）")
    slots: list[SlotOut] = Field(default_factory=list)
    available_count: int = 0


# ---------- 预约 ----------
class AppointmentCreate(BaseModel):
    """创建预约请求：通过 id 定位医生与具体时段。"""

    doctor_id: int
    slot_date: date
    start_time: time
    patient_id: str = Field(min_length=1, max_length=32, description="病人编号/病历号")


class AppointmentOut(ORMBase):
    """预约详情（含医院-科室-医生-时间）。"""

    id: int
    doctor_id: int
    doctor_name: str
    title: str
    department_id: int
    department_name: str
    hospital_id: int
    hospital_name: str
    slot_date: date
    start_time: time
    end_time: time
    patient_id: str
    status: AppointmentStatus
    created_at: datetime


class AppointmentCreateResponse(BaseModel):
    """创建预约结果：成功返回预约，失败返回可预约时段。"""

    success: bool
    message: str
    appointment: AppointmentOut | None = None
    available_slots: list[SlotOut] = Field(default_factory=list)
