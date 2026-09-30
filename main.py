"""医疗挂号系统 FastAPI 入口。

启动：python main.py  或  uvicorn main:app --reload
文档：启动后访问 /docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from app.database import init_db
from app.routers import appointments, doctors, hospitals
from app.seed import seed_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：建表 + 写入示例数据
    init_db()
    seed_data()
    yield


app = FastAPI(
    title="医疗挂号系统",
    description="模拟 医院-科室-医生 的预约流程，支持查询时段、创建预约、查询预约。",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(hospitals.router)
app.include_router(doctors.router)
app.include_router(appointments.router)


@app.get("/", tags=["健康检查"], summary="健康检查")
def root():
    return {"status": "ok", "service": "医疗挂号系统", "docs": "/docs"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
