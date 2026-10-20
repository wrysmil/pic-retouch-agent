"""mock 模式端到端自检：生图链路 + 智能体规划链路。

只用本地 mock provider 与本地 mock 规划桩，不产生任何厂商调用。

    python scripts/check_mock_mode.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

BASE = "http://127.0.0.1:7302"
USER = {"username": "uitest", "password": "uitest123"}


async def _ensure_session(client: httpx.AsyncClient) -> None:
    resp = await client.post(f"{BASE}/api/auth/register", json=USER)
    if resp.status_code == 409:
        resp = await client.post(f"{BASE}/api/auth/login", json=USER)
    resp.raise_for_status()
    print(f"[ok] 登录成功：{USER['username']}")


async def main() -> int:
    async with httpx.AsyncClient(timeout=30) as client:
        await _ensure_session(client)

        print("\n[1] 文生图（mock 占位图）")
        resp = await client.post(
            f"{BASE}/api/generations",
            json={"prompt": "白色背景上的无线耳机", "ratio": "1:1", "count": 2},
        )
        resp.raise_for_status()
        run_id = resp.json()["id"]
        for _ in range(20):
            await asyncio.sleep(1)
            run = (await client.get(f"{BASE}/api/runs/{run_id}")).json()
            if run["status"] in ("succeeded", "failed", "canceled"):
                break
        print(
            f"    状态={run['status']} 进度={run['progress']}% 候选={len(run['candidates'])} 张"
        )
        if not run["candidates"]:
            print("    失败：没有候选图")
            return 1
        asset_id = run["candidates"][0]["id"]

        print("\n[2] 建会话")
        resp = await client.post(
            f"{BASE}/api/sessions",
            json={"title": "mock 自检", "current_asset_id": asset_id},
        )
        resp.raise_for_status()
        session_id = resp.json()["id"]
        print(f"    会话 {session_id}")

        print("\n[3] 智能体对话（mock 规划桩）")
        for goal in ("把背景去掉", "图片调色提亮一点", "[@tool=flip_layer][@tool=adjust_image]"):
            resp = await client.post(
                f"{BASE}/api/sessions/{session_id}/messages", json={"text": goal}
            )
            resp.raise_for_status()
            turn = resp.json()
            steps = " -> ".join(
                f"{s['tool']}({s['status']})" for s in (turn.get("steps") or [])
            )
            print(f"    「{goal}」 -> {turn['status']} | {steps}")
            if turn.get("error"):
                print(f"      错误：{turn['error']}")

    print("\nmock 模式端到端自检通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
