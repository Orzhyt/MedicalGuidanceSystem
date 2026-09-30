"""ORM 模型：医院 / 科室 / 医生 / 排班规则 / 预约。"""
from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AppointmentStatus(str, PyEnum):
    """预约状态。"""

    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, comment="医院等级")
    address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    departments: Mapped[list[Department]] = relationship(
        back_populates="hospital", cascade="all, delete-orphan"
    )


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[int] = mapped_column(
        ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)

    hospital: Mapped[Hospital] = relationship(back_populates="departments")
    doctors: Mapped[list[Doctor]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(32), nullable=False, comment="职称")
    specialty: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)

    department: Mapped[Department] = relationship(back_populates="doctors")
    schedules: Mapped[list[Schedule]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="doctor", cascade="all, delete-orphan"
    )


class Schedule(Base):
    """医生每周重复的排班规则：某个星期几的某个时段，容量为 capacity 个号源。"""

    __tablename__ = "schedules"
    __table_args__ = (
        UniqueConstraint(
            "doctor_id", "weekday", "start_time", name="uq_schedule_doctor_slot"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="星期几，0=周一...6=周日"
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    doctor: Mapped[Doctor] = relationship(back_populates="schedules")


class Appointment(Base):
    """一次具体预约：某医生某天某时段。"""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False
    )
    slot_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    patient_name: Mapped[str] = mapped_column(String(32), nullable=False)
    patient_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.CONFIRMED
    )
    is_demo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0",
        comment="是否为示例预置数据（启动时按当前窗口刷新）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )

    doctor: Mapped[Doctor] = relationship(back_populates="appointments")
