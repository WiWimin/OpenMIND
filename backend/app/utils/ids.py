from uuid import uuid4


def new_id(prefix: str) -> str:
    """生成带前缀的业务主键，例如 ``usr_8f3a...``（`database.md 二`）。"""
    return f"{prefix}_{uuid4().hex}"
