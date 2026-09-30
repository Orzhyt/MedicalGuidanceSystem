"""接口1：查询 医院-科室-医生 列表（树状）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/api/hospitals", tags=["医院/科室/医生"])


@router.get("", response_model=list[schemas.HospitalOut], summary="查询所有医院树")
def list_hospitals(db: Session = Depends(get_db)):
    """返回所有医院，嵌套科室与医生，构成 医院->科室->医生 树。"""
    return crud.get_hospitals_tree(db)


@router.get(
    "/{hospital_id}",
    response_model=schemas.HospitalOut,
    summary="查询单个医院树",
)
def get_hospital(hospital_id: int, db: Session = Depends(get_db)):
    trees = crud.get_hospitals_tree(db, hospital_id=hospital_id)
    if not trees:
        raise HTTPException(status_code=404, detail=f"医院不存在: id={hospital_id}")
    return trees[0]
