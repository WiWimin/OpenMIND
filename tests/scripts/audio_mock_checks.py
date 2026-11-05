"""音频能力检查：真实 HTTP + Mock ASR（mock-ai:9000）。

运行：docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/audio_mock_checks.py
"""
from __future__ import annotations

import os
import uuid

import httpx

BASE = os.environ.get("TEST_API_BASE", "http://127.0.0.1:8000/api/v1")
MOCK = os.environ.get("MOCK_CTL", "http://mock-ai:9000")
STORAGE = os.environ.get("STORAGE_DIR", "/storage")
RESULTS: list[tuple[str, bool, str]] = []
WAV = b"RIFF$\x00\x00\x00WAVEfmt " + b"\x00" * 64


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" | {detail}" if detail else ""))


def mock_mode(mode: str) -> None:
    httpx.post(f"{MOCK}/__mock/mode", json={"mode": mode}, timeout=10)


def reg(c: httpx.Client, name: str) -> str:
    r = c.post("/auth/register", json={"name": name, "password": "audio-pass-123"})
    r.raise_for_status()
    return r.json()["data"]["access_token"]


def err(r: httpx.Response) -> str:
    try:
        return r.json().get("error_code", "")
    except Exception:
        return ""


def main() -> int:
    mock_mode("normal")
    with httpx.Client(base_url=BASE, timeout=120) as c:
        token = reg(c, f"aud-{uuid.uuid4().hex[:8]}")
        c.headers["Authorization"] = f"Bearer {token}"
        mid = c.post("/meetings", json={"title": f"音频测试 {uuid.uuid4().hex[:6]}"}).json()["data"]["meeting_id"]

        # A) 上传音频 + 整段转写
        r = c.post(f"/meetings/{mid}/audio", files={"file": ("a.wav", WAV, "audio/wav")})
        d = r.json().get("data", {}) if r.status_code == 201 else {}
        check("音频上传并转写", r.status_code == 201 and d.get("status") == "transcribed" and bool(d.get("transcript")),
              f"{r.status_code}/{d.get('status')}")
        whole_id = d.get("audio_id")

        # B) 类型限制
        r = c.post(f"/meetings/{mid}/audio", files={"file": ("a.txt", b"x", "text/plain")})
        check("音频类型限制 415", r.status_code == 415 and err(r) == "FILE_TYPE_NOT_SUPPORTED", f"{r.status_code}/{err(r)}")

        # C) 大小限制（>20MB）
        big = b"x" * (21 * 1024 * 1024)
        r = c.post(f"/meetings/{mid}/audio", files={"file": ("big.wav", big, "audio/wav")})
        check("音频大小限制 413", r.status_code == 413 and err(r) == "FILE_TOO_LARGE", f"{r.status_code}/{err(r)}")

        # D) 实时会话
        r = c.post(f"/meetings/{mid}/audio/live/start", json={"file_type": "webm"})
        live = r.json().get("data", {}) if r.status_code == 201 else {}
        live_id = live.get("audio_id")
        check("实时会话创建", r.status_code == 201 and live.get("status") == "processing", f"{r.status_code}/{live.get('status')}")

        # E) 分片上传 + 逐片转写
        r = c.post(f"/audio/{live_id}/live/chunk", files={"file": ("c1.webm", b"chunk-1", "audio/webm")},
                   data={"seq": "1", "offset_seconds": "0"})
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        check("分片1上传并转写", r.status_code == 200 and len(d.get("segments") or []) == 1 and bool(d.get("transcript")),
              f"{r.status_code}/seg={len(d.get('segments') or [])}")

        # F) 序号不连续
        r = c.post(f"/audio/{live_id}/live/chunk", files={"file": ("c3.webm", b"chunk-3", "audio/webm")},
                   data={"seq": "3", "offset_seconds": "20"})
        check("分片序号不连续 422", r.status_code == 422 and err(r) == "VALIDATION_ERROR", f"{r.status_code}/{err(r)}")

        # G) 单片失败（Mock 500）不中断 + 重试
        mock_mode("500")
        r = c.post(f"/audio/{live_id}/live/chunk", files={"file": ("c2.webm", b"chunk-2", "audio/webm")},
                   data={"seq": "2", "offset_seconds": "10"})
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        seg2 = [s for s in (d.get("segments") or []) if s.get("seq") == 2]
        check("分片失败记录 error 且不中断", r.status_code == 200 and bool(seg2) and bool(seg2[0].get("error")),
              f"{r.status_code}/err={seg2[0].get('error') if seg2 else None}")
        mock_mode("normal")
        r = c.post(f"/audio/{live_id}/segments/2/retry")
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        seg2 = [s for s in (d.get("segments") or []) if s.get("seq") == 2]
        check("分片重试成功", r.status_code == 200 and bool(seg2) and bool(seg2[0].get("text")) and not seg2[0].get("error"),
              f"{r.status_code}/text={'y' if seg2 and seg2[0].get('text') else 'n'}")

        # H) 分段标记
        r = c.patch(f"/audio/{live_id}/segments/marker", json={"seq": 1, "marker_type": "decision"})
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        seg1 = [s for s in (d.get("segments") or []) if s.get("seq") == 1]
        check("分段标记", r.status_code == 200 and seg1 and seg1[0].get("marker_type") == "decision", f"{r.status_code}")

        # I) 结束合并 + 清理
        r = c.post(f"/audio/{live_id}/live/finish")
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        check("结束合并为 transcribed", r.status_code == 200 and d.get("status") == "transcribed", f"{r.status_code}/{d.get('status')}")
        check("临时分片目录已清理", not os.path.isdir(os.path.join(STORAGE, "audio", live_id)), os.path.join(STORAGE, "audio", live_id))

        # J) 转写编辑
        r = c.patch(f"/audio/{live_id}", json={"transcript": "第一行\n第二行\n第三行"})
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        check("转写编辑并按行重拆段", r.status_code == 200 and len(d.get("segments") or []) == 3 and d.get("status") == "transcribed",
              f"{r.status_code}/seg={len(d.get('segments') or [])}")

        # K) 确认生成记录 + 幂等
        r = c.post(f"/audio/{live_id}/confirm")
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        rec1 = d.get("record_id")
        check("确认生成会议记录", r.status_code == 200 and bool(rec1) and d.get("status") == "confirmed", f"{r.status_code}/{d.get('status')}")
        r = c.post(f"/audio/{live_id}/confirm")
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        check("重复确认幂等", r.status_code == 200 and d.get("record_id") == rec1, f"{r.status_code}")

        # L) 已确认不可删除
        r = c.delete(f"/audio/{live_id}")
        check("已确认音频不可删除 409", r.status_code == 409 and err(r) == "BUSINESS_RULE_VIOLATION", f"{r.status_code}/{err(r)}")

        # M) 用户隔离
        with httpx.Client(base_url=BASE, timeout=30) as other:
            t2 = reg(other, f"aud2-{uuid.uuid4().hex[:8]}")
            other.headers["Authorization"] = f"Bearer {t2}"
            r = other.get(f"/audio/{live_id}")
            check("跨用户访问音频 404", r.status_code == 404, str(r.status_code))

        # N) 未确认音频可删除（整段上传的那条）
        r = c.delete(f"/audio/{whole_id}")
        check("未确认音频可删除", r.status_code == 200, str(r.status_code))

    failed = [x for x in RESULTS if not x[1]]
    print(f"\nSUMMARY total={len(RESULTS)} passed={len(RESULTS)-len(failed)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
