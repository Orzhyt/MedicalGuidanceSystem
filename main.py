"""医疗挂号系统 FastAPI 入口。

启动：python main.py                       # 默认 127.0.0.1:9090
      python main.py --port 8080           # 自定义端口
      PORT=8080 python main.py             # 用环境变量自定义端口
      uvicorn main:app --port 9090 --reload
文档：启动后访问 /docs
"""
from __future__ import annotations

import argparse
import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse

from app import crud
from app.database import init_db
from app.routers import appointments, doctors, hospitals
from app.seed import seed_data

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 确定可预约窗口起点：优先用 START_DATE 环境变量，否则默认明天
    env_start = os.getenv("START_DATE")
    if env_start:
        try:
            start = date.fromisoformat(env_start)
        except ValueError:
            start = date.today() + timedelta(days=1)
            print(f"[警告] START_DATE={env_start!r} 解析失败，回退到默认起点 {start}")
    else:
        start = date.today() + timedelta(days=1)
    crud.set_booking_start(start)
    print(f"[启动] 可预约窗口起点：{start}（共 {crud.BOOKING_DAYS} 天，重启前固定不变）")
    # 建表 + 写入示例数据
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
    return {
        "status": "ok",
        "service": "医疗挂号系统",
        "docs": "/docs",
        "schedule_page": "/schedule",
    }


@app.get("/schedule", include_in_schema=False, summary="医生排期可视化页面")
def schedule_page():
    return FileResponse(str(STATIC_DIR / "schedule.html"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="医疗挂号系统")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"), help="监听地址")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "9090")),
        help="监听端口，默认 9090（可用环境变量 PORT 覆盖）",
    )
    parser.add_argument("--no-reload", action="store_true", help="关闭热重载")
    parser.add_argument(
        "--start-date",
        default=os.getenv("START_DATE"),
        help="可预约窗口起始日期 YYYY-MM-DD，默认明天（也可用环境变量 START_DATE）",
    )
    args = parser.parse_args()
    if args.start_date:
        os.environ["START_DATE"] = args.start_date
    uvicorn.run("main:app", host=args.host, port=args.port, reload=not args.no_reload)
