import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from redis.asyncio import Redis

from app.config import get_settings

IDLE_TICK = 15.0


@lru_cache
def redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def _channel(run_id: uuid.UUID) -> str:
    return f"run:{run_id}"


def _turn_channel(turn_id: uuid.UUID) -> str:
    return f"turn:{turn_id}"


async def publish(run_id: uuid.UUID, payload: dict) -> None:
    await redis_client().publish(_channel(run_id), json.dumps(payload))


async def publish_turn(turn_id: uuid.UUID, payload: dict) -> None:
    """只做唤醒：断线补齐以 agent_events 表为准。"""
    await redis_client().publish(_turn_channel(turn_id), json.dumps(payload))


@asynccontextmanager
async def subscribe(run_id: uuid.UUID) -> AsyncIterator[AsyncIterator[dict | None]]:
    """订阅进度。空闲超过 IDLE_TICK 秒时产出 None，供调用方发送心跳。"""
    async with _subscribe(_channel(run_id)) as messages:
        yield messages


@asynccontextmanager
async def subscribe_turn(turn_id: uuid.UUID) -> AsyncIterator[AsyncIterator[dict | None]]:
    async with _subscribe(_turn_channel(turn_id)) as messages:
        yield messages


@asynccontextmanager
async def _subscribe(channel: str) -> AsyncIterator[AsyncIterator[dict | None]]:
    pubsub = redis_client().pubsub()
    await pubsub.subscribe(channel)

    async def messages() -> AsyncIterator[dict | None]:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=IDLE_TICK)
            yield json.loads(message["data"]) if message else None

    try:
        yield messages()
    finally:
        await pubsub.aclose()