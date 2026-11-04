"""AI 全链路检查：真实 HTTP 调用本地 OpenAI 兼容 Mock（mock-ai:9000）。

运行：docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/ai_mock_checks.py
"""
from __future__ import annotations

import os
import uuid

import httpx

BASE = os.environ.get("TEST_API_BASE", "http://127.0.0.1:8000/api/v1")
MOCK = os.environ.get("MOCK_CTL", "http://mock-ai:9000")
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))


def mock_mode(mode: str) -> None:
    httpx.post(f"{MOCK}/__mock/mode", json={"mode": mode}, timeout=10)


def reg(c: httpx.Client, name: str) -> str:
    r = c.post("/auth/register", json={"name": name, "password": "mock-pass-123"})
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def err_code(r: httpx.Response) -> str:
    try:
        return r.json().get("error_code", "")
    except Exception:
        return ""


def main() -> int:
    mock_mode("normal")
    name = f"ai-{uuid.uuid4().hex[:8]}"
    with httpx.Client(base_url=BASE, timeout=90) as c:
        token = reg(c, name)
        c.headers["Authorization"] = f"Bearer {token}"

        # 1) 默认（fallback=true，全局 Mock）来源
        cfg = c.get("/me/settings/model").json()["data"]
        check("默认模型来源=global（测试环境 fallback=true）", cfg["llm_source"] == "global", cfg["llm_source"])

        # 2) BYOK 保存 + 掩码
        put = c.put("/me/settings/model", json={
            "llm_api_base": "http://mock-ai:9000/v1",
            "llm_api_key": "sk-mock-1234567890",
            "llm_model": "mock-llm",
        })
        check("BYOK 保存成功", put.status_code == 200, str(put.status_code))
        cfg = c.get("/me/settings/model").json()["data"]
        check("BYOK 来源=user", cfg["llm_source"] == "user", cfg["llm_source"])
        check("密钥掩码回传", cfg["llm_api_key_masked"].startswith("sk-") and "..." in cfg["llm_api_key_masked"], cfg["llm_api_key_masked"])
        check("明文密钥不回传", "sk-mock-1234567890" not in str(cfg))

        # 3) 建会
        mtg = c.post("/meetings", json={"title": f"AI 测试会议 {uuid.uuid4().hex[:6]}", "topic": "灰度发布"}).json()["data"]
        mid = mtg["meeting_id"]

        # 4) LLM 正常：会前准备（结构化 JSON）
        r = c.post(f"/meetings/{mid}/prepare", json={"include_history": True})
        prep = r.json().get("data", {}) if r.status_code == 200 else {}
        check("LLM 正常-会前准备", r.status_code == 200 and bool(prep.get("summary")), f"{r.status_code}")

        # 5) LLM 异常映射
        for mode, code, status in [("429", "RATE_LIMITED", 429), ("500", "INTERNAL_ERROR", 500),
                                   ("401", "MODEL_CONFIG_INVALID", 400), ("402", "MODEL_QUOTA_EXCEEDED", 402),
                                   ("invalid_json", "MODEL_OUTPUT_INVALID", 502)]:
            mock_mode(mode)
            r = c.post(f"/meetings/{mid}/prepare", json={"include_history": True})
            check(f"LLM 异常 {mode} -> {code}", err_code(r) == code and r.status_code == status,
                  f"{r.status_code}/{err_code(r)}")
        mock_mode("normal")

        # 6) Embedding 正常 -> 材料 processed
        files = {"file": ("mat-a.txt", b"\xe6\x9c\x89\xe5\x85\xb3\xe7\x81\xb0\xe5\xba\xa6\xe5\x8f\x91\xe5\xb8\x83\xe7\x9a\x84\xe6\x9d\x90\xe6\x96\x99", "text/plain")}
        r = c.post(f"/meetings/{mid}/materials", files=files)
        mat_ok = r.status_code == 201 and r.json()["data"]["processing_status"] == "processed"
        check("Embedding 正常-材料已索引", mat_ok, f"{r.status_code}/{r.json().get('data',{}).get('processing_status')}")

        # 7) Embedding 维度错误 -> 材料 failed
        mock_mode("dim_mismatch")
        files = {"file": ("mat-b.txt", b"dim mismatch material", "text/plain")}
        r = c.post(f"/meetings/{mid}/materials", files=files)
        st = r.json().get("data", {}).get("processing_status") if r.status_code == 201 else ""
        check("Embedding 维度错误-材料 failed", st == "failed", f"{r.status_code}/{st}")
        mock_mode("normal")

        # 8) RAG 问答（current_meeting，带来源）
        r = c.post(f"/meetings/{mid}/chat", json={"question": "本次会议确定了什么？", "context_scope": "current_meeting", "include_sources": True})
        data = r.json().get("data", {}) if r.status_code == 200 else {}
        check("RAG 问答返回答案", r.status_code == 200 and bool(data.get("answer")), f"{r.status_code}")
        check("RAG 返回来源", len(data.get("sources", [])) > 0, f"sources={len(data.get('sources', []))}")
        check("RAG Top-K<=5", len(data.get("sources", [])) <= 5, f"sources={len(data.get('sources', []))}")

        # 9) knowledge_base scope 无知识 -> 证据不足
        r = c.post(f"/meetings/{mid}/chat", json={"question": "知识库里有相关内容吗？", "context_scope": "knowledge_base", "include_sources": True})
        data = r.json().get("data", {}) if r.status_code == 200 else {}
        check("knowledge_base 无证据-拒答", r.status_code == 200 and data.get("insufficient_evidence") is True, str(data.get("insufficient_evidence")))

        # 10) 整理链 summary / brief / polish / organize
        r = c.post(f"/meetings/{mid}/organize", json={"task": "summary", "text": "确认周五前完成灰度发布检查清单，李雷负责。"})
        s = r.json().get("data", {}) if r.status_code == 200 else {}
        check("整理链 summary 结构化", r.status_code == 200 and isinstance(s.get("structured"), dict), f"{r.status_code}")
        r = c.post(f"/meetings/{mid}/organize", json={"task": "brief", "text": "确认周五前完成灰度发布检查清单。"})
        s = r.json().get("data", {}) if r.status_code == 200 else {}
        check("整理链 brief 正文", r.status_code == 200 and bool(s.get("organized_content")) and s.get("structured") is None, f"{r.status_code}")
        r = c.post(f"/meetings/{mid}/organize", json={"task": "polish", "text": "这个方案我觉得可以搞一下。"})
        s = r.json().get("data", {}) if r.status_code == 200 else {}
        check("整理链 polish 结构化列表", r.status_code == 200 and isinstance(s.get("structured"), list), f"{r.status_code}")
        r = c.post(f"/meetings/{mid}/organize", json={"task": "organize", "text": "嗯 那个 我们周五前搞定检查清单"})
        s = r.json().get("data", {}) if r.status_code == 200 else {}
        check("整理链 organize 正文", r.status_code == 200 and bool(s.get("organized_content")), f"{r.status_code}")

        # 11) 删除 BYOK
        d = c.delete("/me/settings/model")
        cfg = c.get("/me/settings/model").json()["data"]
        check("删除 BYOK 后回退 global", d.status_code == 200 and cfg["llm_source"] == "global", cfg["llm_source"])

    failed = [x for x in RESULTS if not x[1]]
    print(f"\nSUMMARY total={len(RESULTS)} passed={len(RESULTS)-len(failed)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
