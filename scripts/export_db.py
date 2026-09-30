"""生成 data/medical.db 快照（基础数据 + 排班含 demo_booked，无预约行）。

仅手动运行以刷新提交到 git 的参考快照；运行时服务使用内存库，不读写此文件。
用法：python scripts/export_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  注册模型
from app.database import DB_PATH, Base
from app.seed import _seed_base_data


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    engine = create_engine(f"sqlite:///{DB_PATH.as_posix()}")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)
    db = session()
    try:
        _seed_base_data(db)
        db.commit()
    finally:
        db.close()
    engine.dispose()
    print(f"快照已生成: {DB_PATH}")


if __name__ == "__main__":
    main()
