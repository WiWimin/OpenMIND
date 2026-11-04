"""Local OpenAI-compatible mock used only by the 5.0 test stack.

Implements the endpoints the backend clients call:
  POST /v1/chat/completions
  POST /v1/embeddings
  GET  /v1/models
  POST /v1/audio/transcriptions

Control endpoint (test-only):
  POST /__mock/mode   {"mode": "normal|429|500|401|402|invalid_json|dim_mismatch"}
  POST /__mock/reset
  GET  /health

It is NOT production code and must never be deployed.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from fastapi import FastAPI, File, Form, Header, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI(title="OpenMIND Mock AI", version="1.0")
DIM = int(os.environ.get("MOCK_EMBEDDING_DIM", "1024"))
_STATE: dict[str, str] = {"mode": "normal"}


def _content_for_chat(system: str, user: str) -> str:
    s = system
    if "conclusion" in s and "action_items" in s:
        return json.dumps(
            {
                "conclusion": ["确认周五前完成灰度发布检查清单。"],
                "key_discussions": [
                    {"topic": "灰度发布", "points": ["需要在周五前完成检查清单"]}
                ],
                "action_items": [
                    {
                        "task": "完成灰度发布检查清单",
                        "assignee": "李雷",
                        "deadline": "2026-11-06",
                        "priority": "high",
                        "source_quote": "本周五前完成灰度发布检查清单",
                    }
                ],
                "open_questions": ["灰度发布是否按计划在周五开始？"],
            },
            ensure_ascii=False,
        )
    if "校对助手" in s or ("suggested" in s and "口误" in s):
        return "[]"
    if "提取待办行动项" in s:
        return json.dumps(
            {
                "items": [
                    {
                        "content": "完成灰度发布检查清单",
                        "assignee": "李雷",
                        "due_date": "2026-11-06",
                        "source_record_id": None,
                        "source_excerpt": "本周五前完成灰度发布检查清单",
                    }
                ]
            },
            ensure_ascii=False,
        )
    if "尚未解决的问题" in s:
        return json.dumps(
            {
                "items": [
                    {
                        "description": "灰度发布是否按计划在周五开始？",
                        "follow_up": "产品与研发共同确认",
                        "source_record_id": None,
                    }
                ]
            },
            ensure_ascii=False,
        )
    if "生成会前准备稿" in s:
        return json.dumps(
            {
                "summary": "本次会议围绕灰度发布检查清单与风险确认展开。",
                "checklist": [
                    "确认灰度发布检查清单负责人与截止时间",
                    "核实模型额度与上线风险",
                ],
            },
            ensure_ascii=False,
        )
    if "会议纪要助手" in s:
        return (
            "# 会议纪要\n\n"
            "## 议题\n灰度发布\n\n"
            "## 结论\n- 确认周五前完成灰度发布检查清单。\n\n"
            "## 待办\n- 李雷：周五前完成灰度发布检查清单。\n\n"
            "## 遗留\n- 灰度发布是否按计划在周五开始，待确认。"
        )
    if "简短摘要" in s:
        return "本次会议确认了灰度发布检查清单，并明确了负责人和截止时间。"
    if "整理会议记录" in s:
        return "整理后的会议记录：确认周五前完成灰度发布检查清单，负责人李雷。"
    if "个人会议助理" in s:
        return (
            "根据会议记录与材料：本次确认了“完成灰度发布检查清单”等行动项，"
            "并留有“灰度发布是否在周五开始”的待确认问题。"
        )
    return "Mock 回答：已收到请求。"


def _err(code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=code, content={"error": {"message": message}})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": _STATE["mode"]}


@app.post("/__mock/mode")
async def set_mode(request: Request) -> dict[str, str]:
    body: dict[str, Any] = await request.json()
    _STATE["mode"] = str(body.get("mode", "normal"))
    return {"mode": _STATE["mode"]}


@app.post("/__mock/reset")
def reset() -> dict[str, str]:
    _STATE["mode"] = "normal"
    return {"mode": "normal"}


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {"data": [{"id": "mock-llm", "object": "model"}, {"id": "mock-embedding"}]}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Any:
    mode = _STATE["mode"]
    if mode == "429":
        return _err(429, "mock rate limited")
    if mode == "500":
        return _err(500, "mock upstream error")
    if mode == "401":
        return _err(401, "mock invalid key")
    if mode == "402":
        return _err(402, "mock quota exceeded")
    body: dict[str, Any] = await request.json()
    messages = body.get("messages") or []
    system = " ".join(m.get("content", "") for m in messages if m.get("role") == "system")
    user = " ".join(m.get("content", "") for m in messages if m.get("role") == "user")
    content = _content_for_chat(system, user)
    if mode == "invalid_json":
        content = "这不是 JSON"
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", "mock-llm"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    }


@app.post("/v1/embeddings")
async def embeddings(request: Request) -> Any:
    mode = _STATE["mode"]
    if mode == "429":
        return _err(429, "mock rate limited")
    if mode == "500":
        return _err(500, "mock upstream error")
    if mode == "401":
        return _err(401, "mock invalid key")
    if mode == "402":
        return _err(402, "mock quota exceeded")
    body: dict[str, Any] = await request.json()
    inputs = body.get("input") or []
    if isinstance(inputs, str):
        inputs = [inputs]
    dim = DIM if mode != "dim_mismatch" else max(1, DIM - 1)
    data = [
        {"object": "embedding", "index": i, "embedding": [0.1] * dim}
        for i in range(len(inputs))
    ]
    return {"object": "list", "data": data, "model": body.get("model", "mock-embedding")}


@app.post("/v1/audio/transcriptions")
async def transcriptions(
    file: UploadFile = File(...),
    model: str = Form(default="mock-asr"),
    authorization: str | None = Header(default=None),
) -> Any:
    mode = _STATE["mode"]
    if mode == "429":
        return _err(429, "mock rate limited")
    if mode == "500":
        return _err(500, "mock upstream error")
    if mode == "401":
        return _err(401, "mock invalid key")
    await file.read()
    return {
        "text": "这是 Mock ASR 转写文本：决议周五前完成灰度发布检查清单，负责人李雷。"
    }
