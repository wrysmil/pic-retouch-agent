"""验证「启用/停用即热更新」与「一键切换」。

    python scripts/check_hot_update.py
"""

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

BASE = "http://127.0.0.1:7302"
ADMIN = {"username": "admin", "password": "Admin@123456"}


async def main() -> int:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{BASE}/api/auth/login", json=ADMIN)
        r.raise_for_status()

        async def current() -> dict:
            return (await c.get(f"{BASE}/api/admin/model-config/current")).json()

        async def models() -> list[dict]:
            return (await c.get(f"{BASE}/api/admin/model-config/models")).json()

        async def conns() -> list[dict]:
            return (await c.get(f"{BASE}/api/admin/model-config/connections")).json()

        async def show(tag: str) -> dict:
            cur = await current()
            ms = await models()
            by_id = {m["id"]: m["slug"] for m in ms}
            active = [m["slug"] for m in ms if m["status"] == "active"]
            print(
                f"  [{tag}] 生效 v{cur['current_version_seq']} "
                f"文本={by_id.get(cur['text_model_id'], '?')} "
                f"生图={by_id.get(cur['image_model_id'], '?')} | 启用中={active}"
            )
            return cur

        ms = await models()
        cs = await conns()
        conn_by_id = {x["id"]: x for x in cs}
        mock_image = next(
            (
                m
                for m in ms
                if m["model_type"] == "image"
                and conn_by_id.get(m["connection_id"], {}).get("adapter_type") == "mock"
            ),
            None,
        )
        # 真实生图模型 = 当前启用的那个非 mock 模型（没有启用态就退而取第一个非 mock 的）
        real_image = next(
            (m for m in ms if m["model_type"] == "image" and m["status"] == "active"),
            None,
        ) or next(
            (
                m
                for m in ms
                if m["model_type"] == "image"
                and conn_by_id.get(m["connection_id"], {}).get("adapter_type") != "mock"
            ),
            None,
        )
        if not mock_image or not real_image:
            print("缺少 mock / 真实生图模型，跳过")
            return 1

        await show("初始")

        print("\n[1] 启用 mock 生图模型 -> 期望自动重发布并立即切到 mock")
        r = await c.post(f"{BASE}/api/admin/model-config/models/{mock_image['id']}/activate")
        r.raise_for_status()
        body = r.json()
        print(f"  published_seq = {body['published_seq']}")
        cur = await show("启用 mock 后")
        ok1 = (
            body["published_seq"] is not None
            and cur["image_model_id"] == mock_image["id"]
        )

        print("\n[2] 启用真实生图模型 -> 期望自动重发布并切回真实")
        r = await c.post(f"{BASE}/api/admin/model-config/models/{real_image['id']}/activate")
        r.raise_for_status()
        body = r.json()
        print(f"  published_seq = {body['published_seq']}")
        cur = await show("启用真实后")
        ok2 = (
            body["published_seq"] is not None
            and cur["image_model_id"] == real_image["id"]
        )

        print("\n[3] 一键切换接口 /apply")
        cur = await current()
        ms = await models()
        text_model = next(m for m in ms if m["model_type"] == "text")
        r = await c.post(
            f"{BASE}/api/admin/model-config/apply",
            json={
                "text_model_id": text_model["id"],
                "image_model_id": mock_image["id"],
                "note": "自检：切到 mock",
                "expected_revision": cur["revision"],
            },
        )
        r.raise_for_status()
        applied = r.json()
        print(f"  已发布 v{applied['current_version_seq']}")
        cur = await show("apply 后")
        ok3 = cur["image_model_id"] == mock_image["id"]

        print("\n[4] 切回真实（再用 apply）")
        cur = await current()
        ms = await models()
        cs = await conns()
        conn_by_id = {x["id"]: x for x in cs}
        # 真实的文本模型 = 当前启用的那个非本机模型（没有启用态就退而取第一个非本机的）
        def _is_local(m: dict) -> bool:
            url = conn_by_id.get(m["connection_id"], {}).get("base_url") or ""
            return bool(re.search(r"localhost|127\.0\.0\.1", url))

        real_text = next(
            (
                m
                for m in ms
                if m["model_type"] == "text"
                and m["status"] == "active"
                and not _is_local(m)
            ),
            None,
        ) or next(
            (m for m in ms if m["model_type"] == "text" and not _is_local(m)),
            None,
        )
        r = await c.post(
            f"{BASE}/api/admin/model-config/apply",
            json={
                "text_model_id": real_text["id"],
                "image_model_id": real_image["id"],
                "note": "自检：切回真实",
                "expected_revision": cur["revision"],
            },
        )
        r.raise_for_status()
        cur = await show("apply 切回后")
        ok4 = cur["image_model_id"] == real_image["id"]

        print("\n[5] 停用当前在用的生图模型 -> 该类型无启用模型时保持当前版本不动")
        cur = await current()
        r = await c.post(f"{BASE}/api/admin/model-config/models/{real_image['id']}/disable")
        r.raise_for_status()
        print(f"  published_seq = {r.json()['published_seq']}")
        after = await show("停用后")
        ok5 = after["current_version_seq"] == cur["current_version_seq"]

        print("\n[6] 复位：重新启用真实生图模型")
        r = await c.post(f"{BASE}/api/admin/model-config/models/{real_image['id']}/activate")
        r.raise_for_status()
        await show("复位后")

        results = [ok1, ok2, ok3, ok4, ok5]
        print(f"\n结果：{sum(results)}/{len(results)} 通过")
        return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
