"""PostgreSQL 真实集成测试（独立测试库，不触碰生产库）。

运行：docker exec openmind-test-backend-test-1 python /tests/scripts/pg_integration.py
环境：DATABASE_URL 指向 db-test（compose.test.yml 注入）。
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401  注册 ORM 模型
from app.db.base import Base
from app.models.action_item import ActionItem
from app.models.audio import MeetingAudio
from app.models.material import MeetingMaterial
from app.models.meeting import Meeting
from app.models.task import PersonalTask
from app.models.user import User

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def seed(db: Session) -> tuple[str, str]:
    ua, ub = uid("usrA"), uid("usrB")
    db.add_all([
        User(user_id=ua, name=f"userA-{uuid.uuid4().hex[:8]}", password_hash="x"),
        User(user_id=ub, name=f"userB-{uuid.uuid4().hex[:8]}", password_hash="x"),
    ])
    db.commit()
    ma, mb = uid("mtgA"), uid("mtgB")
    db.add_all([
        Meeting(meeting_id=ma, user_id=ua, title="A 的会议", status="scheduled"),
        Meeting(meeting_id=mb, user_id=ub, title="B 的会议", status="scheduled"),
    ])
    db.commit()
    return ua, ub


def main() -> int:
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    check("迁移 head = 0022_audio_segments", version == "0022_audio_segments", version)

    insp = inspect(engine)
    db_tables = set(insp.get_table_names()) - {"alembic_version"}
    orm_tables = set(Base.metadata.tables.keys())
    check("ORM 表与迁移表一致", db_tables == orm_tables, f"db={len(db_tables)} orm={len(orm_tables)}")
    missing = orm_tables - db_tables
    extra = db_tables - orm_tables
    if missing or extra:
        check("表差异", False, f"missing={sorted(missing)} extra={sorted(extra)}")

    col_ok = True
    col_detail = []
    for table in sorted(orm_tables):
        db_cols = {c["name"] for c in insp.get_columns(table)}
        orm_cols = set(Base.metadata.tables[table].columns.keys())
        if db_cols != orm_cols:
            col_ok = False
            col_detail.append(f"{table}: only_db={sorted(db_cols - orm_cols)} only_orm={sorted(orm_cols - db_cols)}")
    check("ORM 列与迁移列一致", col_ok, "; ".join(col_detail)[:400])

    with Session(engine) as db:
        ua, ub = seed(db)

        # 用户隔离
        a_meetings = db.query(Meeting).filter(Meeting.user_id == ua).all()
        b_meetings = db.query(Meeting).filter(Meeting.user_id == ub).all()
        check("用户数据隔离（会议）", len(a_meetings) == 1 and len(b_meetings) == 1,
              f"A={len(a_meetings)} B={len(b_meetings)}")
        cross = db.query(Meeting).filter(Meeting.user_id == ua, Meeting.meeting_id == b_meetings[0].meeting_id).all()
        check("跨用户查询返回空", len(cross) == 0)

        # CRUD：材料 / 行动项 / 任务
        mat = MeetingMaterial(material_id=uid("mat"), meeting_id=a_meetings[0].meeting_id,
                              user_id=ua, file_name="a.txt", type="txt",
                              storage_key="materials/a.txt", content="内容", processing_status="processed")
        act = ActionItem(action_id=uid("act"), meeting_id=a_meetings[0].meeting_id,
                         content="完成检查清单", status="confirmed")
        db.add_all([mat, act]); db.commit()
        task = PersonalTask(task_id=uid("tsk"), user_id=ua, meeting_id=a_meetings[0].meeting_id,
                            action_id=act.action_id, title="转任务", status="todo",
                            due_date=date(2026, 11, 6))
        db.add(task); db.commit()
        task.status = "in_progress"; db.commit()
        check("会议/材料/行动项/任务 CRUD", db.get(PersonalTask, task.task_id).status == "in_progress")

        # JSONB 分段
        audio = MeetingAudio(
            audio_id=uid("aud"), meeting_id=a_meetings[0].meeting_id, user_id=ua,
            file_name="a.webm", type="webm", storage_key="audio/a.webm",
            status="transcribed", transcript="第一段\n第二段",
            segments=[
                {"seq": 1, "offset_seconds": 0, "text": "第一段", "marker_type": "decision", "error": None},
                {"seq": 2, "offset_seconds": 30, "text": "第二段", "marker_type": None, "error": None},
            ],
        )
        db.add(audio); db.commit()
        got = db.get(MeetingAudio, audio.audio_id)
        check("JSONB 分段读回一致", got.segments == [
            {"seq": 1, "offset_seconds": 0, "text": "第一段", "marker_type": "decision", "error": None},
            {"seq": 2, "offset_seconds": 30, "text": "第二段", "marker_type": None, "error": None},
        ])
        with engine.connect() as conn:
            ptype = conn.execute(text("SELECT pg_typeof(segments)::text FROM meeting_audio WHERE audio_id=:i"),
                                 {"i": audio.audio_id}).scalar_one()
            seg_text = conn.execute(text("SELECT segments->1->>'text' FROM meeting_audio WHERE audio_id=:i"),
                                    {"i": audio.audio_id}).scalar_one()
        check("segments 列为 JSONB", ptype == "jsonb", ptype)
        check("JSONB 路径查询 segments->1->>'text'", seg_text == "第二段", str(seg_text))

        # 外键约束
        bad = ActionItem(action_id=uid("act"), meeting_id="not-exist", content="x", status="pending_confirmation")
        db.add(bad)
        try:
            db.commit(); check("外键约束（无效 meeting_id）", False, "未抛错")
        except IntegrityError:
            db.rollback(); check("外键约束（无效 meeting_id）", True)
        finally:
            db.rollback()

        # 唯一约束（action_id）
        dup1 = PersonalTask(task_id=uid("tsk"), user_id=ua, action_id=act.action_id, title="dup", status="todo")
        db.add(dup1)
        try:
            db.commit(); check("唯一约束（action_id）", False, "未抛错")
        except IntegrityError:
            db.rollback(); check("唯一约束（action_id）", True)
        finally:
            db.rollback()

        # 事务回滚
        rollback_user = uid("rollback")
        db.add(User(user_id=rollback_user, name=f"rb-{uuid.uuid4().hex[:8]}", password_hash="x"))
        db.rollback()
        check("事务回滚后未持久化", db.get(User, rollback_user) is None)

        # 持久化标记（供重启后复查）
        marker = os.environ.get("PERSIST_MARKER", "persist-check")
        existing = db.get(User, marker)
        if existing is None:
            db.add(User(user_id=marker, name=f"persist-{uuid.uuid4().hex[:8]}", password_hash="x"))
            db.commit()
        check("写入持久化标记", db.get(User, marker) is not None, marker)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\nSUMMARY total={len(RESULTS)} passed={len(RESULTS)-len(failed)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
