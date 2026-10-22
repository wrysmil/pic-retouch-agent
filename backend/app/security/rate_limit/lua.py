"""Redis Lua scripts for atomic rate-limit decisions."""

from __future__ import annotations

from dataclasses import dataclass

# One invocation checks every scope first and only writes after every scope has
# capacity. This avoids the user bucket being incremented for a request that is
# then rejected by the IP bucket.
SLIDING_WINDOW_SCRIPT = r"""
local window = tonumber(ARGV[1])
local member = ARGV[2]
local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local oldest = now - window

for i, key in ipairs(KEYS) do
  local limit = tonumber(ARGV[i + 2])
  redis.call('ZREMRANGEBYSCORE', key, '-inf', oldest)
  local count = redis.call('ZCARD', key)
  if count >= limit then
    local first = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local reset = now + window
    if first[2] then
      reset = tonumber(first[2]) + window
    end
    return {0, i, limit, 0, reset, math.max(0, reset - now)}
  end
end

local remaining = 0
local reset = now + window
for i, key in ipairs(KEYS) do
  local limit = tonumber(ARGV[i + 2])
  redis.call('ZADD', key, now, member)
  redis.call('PEXPIRE', key, window + 1000)
  local left = limit - redis.call('ZCARD', key)
  if i == 1 or left < remaining then
    remaining = left
  end
end
return {1, 0, tonumber(ARGV[3]), remaining, reset, window}
"""

# Concurrent connections use a ZSET as a lease table. The score is a
# heartbeat timestamp; stale members are removed before capacity is checked.
SSE_SLOT_SCRIPT = r"""
local stale = tonumber(ARGV[1])
local member = ARGV[2]
local enforce = tonumber(ARGV[3])
local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local oldest = now - stale

for i, key in ipairs(KEYS) do
  local limit = tonumber(ARGV[i + 3])
  redis.call('ZREMRANGEBYSCORE', key, '-inf', oldest)
  local count = redis.call('ZCARD', key)
  if enforce == 1 and count >= limit then
    return {0, i, limit, 0, now + stale, stale}
  end
end

for i, key in ipairs(KEYS) do
  redis.call('ZADD', key, now, member)
  redis.call('PEXPIRE', key, stale + 5000)
end
return {1, 0, tonumber(ARGV[4]), 0, now + stale, stale}
"""


@dataclass(frozen=True, slots=True)
class LuaResult:
    allowed: bool
    scope_index: int
    limit: int
    remaining: int
    reset_at_ms: int
    retry_after_ms: int


def parse_result(raw: list | tuple) -> LuaResult:
    if len(raw) != 6:
        raise ValueError(f"限流脚本返回值长度异常：{len(raw)}")
    return LuaResult(
        allowed=bool(int(raw[0])),
        scope_index=int(raw[1]),
        limit=int(raw[2]),
        remaining=int(raw[3]),
        reset_at_ms=int(raw[4]),
        retry_after_ms=max(0, int(raw[5])),
    )
