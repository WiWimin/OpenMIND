"""安全测试：认证、越权、上传限制、路径穿越、密钥泄漏、JWT 过期、归档只读、任务状态机、转任务幂等。

运行：docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/security_checks.py
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt

BASE = os.environ.get("TEST_API_BASE", "http://127.0.0.1:8000/api/v1")
STORAGE = os.environ.get("STORAGE_DIR", "/storage")
SECRET = os.environ.get("SECRET_KEY", "test-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz")
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))


def err(r: httpx.Response) -> str:
    try:
        return r.json().get("error_code", "")
    except Exception:
        return ""


def reg(c: httpx.Client, name: str) -> str:
    r = c.post("/auth/register", json={"name": name, "password": "sec-pass-123"})
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=180) as anon:
        # 1) 未登录
        r = anon.get("/meetings")
        check("未登录访问 401", r.status_code == 401 and err(r) == "AUTH_REQUIRED", f"{r.status_code}/{err(r)}")

    with httpx.Client(base_url=BASE, timeout=180) as a:
        ta = reg(a, f"secA-{uuid.uuid4().hex[:8]}")
        a.headers["Authorization"] = f"Bearer {ta}"
        mid = a.post("/meetings", json={"title": f"安全会议 {uuid.uuid4().hex[:6]}"}).json()["data"]["meeting_id"]

        # 2) 越权
        with httpx.Client(base_url=BASE, timeout=60) as b:
            tb = reg(b, f"secB-{uuid.uuid4().hex[:8]}")
            b.headers["Authorization"] = f"Bearer {tb}"
            r = b.get(f"/meetings/{mid}")
            check("跨用户访问会议 404", r.status_code == 404, str(r.status_code))

        # 3) 文件类型限制
        r = a.post(f"/meetings/{mid}/materials", files={"file": ("a.exe", b"MZ", "application/octet-stream")})
        check("材料类型限制 415", r.status_code == 415 and err(r) == "FILE_TYPE_NOT_SUPPORTED", f"{r.status_code}/{err(r)}")

        # 4) 文件大小限制
        big = b"x" * (21 * 1024 * 1024)
        r = a.post(f"/meetings/{mid}/materials", files={"file": ("big.txt", big, "text/plain")})
        check("材料大小限制 413", r.status_code == 413 and err(r) == "FILE_TOO_LARGE", f"{r.status_code}/{err(r)}")

        # 5) 路径穿越
        r = a.post(f"/meetings/{mid}/materials", files={"file": ("../../evil.txt", b"traversal", "text/plain")})
        escaped1 = os.path.exists(os.path.join(STORAGE, "evil.txt"))
        escaped2 = os.path.exists(os.path.join(STORAGE, "..", "evil.txt"))
        check("路径穿越被中和（201 且无越界文件）", r.status_code == 201 and not escaped1 and not escaped2,
              f"{r.status_code}/escape={escaped1 or escaped2}")

        # 6) BYOK 密钥不泄漏
        key = "sk-very-secret-987654321"
        a.put("/me/settings/model", json={"llm_api_base": "http://mock-ai:9000/v1", "llm_api_key": key, "llm_model": "mock-llm"})
        body = a.get("/me/settings/model").text
        check("BYOK 明文不泄漏", key not in body, "leaked" if key in body else "")

        # 7) JWT 过期
        expired = jwt.encode({"sub": "someone", "exp": datetime.now(UTC) - timedelta(minutes=5)}, SECRET, algorithm="HS256")
        r = a.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
        check("JWT 过期 401", r.status_code == 401 and err(r) == "AUTH_REQUIRED", f"{r.status_code}/{err(r)}")

        # 8) 归档后写入
        rid = a.post(f"/meetings/{mid}/records", json={"content": "归档前记录"}).json()["data"]["record_id"]
        r = a.post(f"/meetings/{mid}/archive")
        check("会议归档成功", r.status_code == 200, str(r.status_code))
        r = a.post(f"/meetings/{mid}/records", json={"content": "归档后写入"})
        check("归档后写入 409", r.status_code == 409 and err(r) == "BUSINESS_RULE_VIOLATION", f"{r.status_code}/{err(r)}")

        # 9/10) 任务状态机 + 转任务幂等（用另一会议，避免归档只读）
        mid2 = a.post("/meetings", json={"title": f"任务会议 {uuid.uuid4().hex[:6]}"}).json()["data"]["meeting_id"]
        a.post(f"/meetings/{mid2}/records", json={"content": "决议：周五前完成检查清单，李雷负责。"})
        r = a.post(f"/meetings/{mid2}/action-items/extract", json={"record_ids": []})
        items = r.json().get("data", {}).get("items", []) if r.status_code == 200 else []
        check("行动项提取", r.status_code == 200 and len(items) > 0, f"{r.status_code}/{len(items)}")
        aid = items[0]["action_id"]
        a.post(f"/action-items/{aid}/confirm")
        r1 = a.post(f"/action-items/{aid}/convert-to-task", json={"title": "完成检查清单"})
        task1 = r1.json().get("data", {}).get("task_id") if r1.status_code in (200, 201) else None
        check("确认后转任务", r1.status_code in (200, 201) and bool(task1), f"{r1.status_code}")
        r2 = a.post(f"/action-items/{aid}/convert-to-task", json={"title": "完成检查清单"})
        task2 = r2.json().get("data", {}).get("task_id") if r2.status_code in (200, 201) else None
        check("重复转任务幂等（同一 task_id）", task1 is not None and task1 == task2, f"{task1} vs {task2}")
        r = a.patch(f"/tasks/{task1}", json={"status": "completed"})
        check("非法任务流转 todo->completed 409", r.status_code == 409 and err(r) == "BUSINESS_RULE_VIOLATION", f"{r.status_code}/{err(r)}")
        r = a.patch(f"/tasks/{task1}", json={"status": "in_progress"})
        check("合法任务流转 todo->in_progress", r.status_code == 200, str(r.status_code))

    failed = [x for x in RESULTS if not x[1]]
    print(f"\nSUMMARY total={len(RESULTS)} passed={len(RESULTS)-len(failed)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
