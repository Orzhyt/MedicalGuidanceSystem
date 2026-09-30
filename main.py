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
    parser = argparse.ArgumentParser(description="医疗挂号系统")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"), help="监听地址")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "9090")),
        help="监听端口，默认 9090（可用环境变量 PORT 覆盖）",
    )
    parser.add_argument("--no-reload", action="store_true", help="关闭热重载")
    args = parser.parse_args()
    uvicorn.run("main:app", host=args.host, port=args.port, reload=not args.no_reload)
