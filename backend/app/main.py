import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import storage
from app.config import get_settings
from app.queue import close_queue
from app.routers import (
    admin_config,
    admin_users,
    assets,
    auth,
    batches,
    events,
    health,
    runs,
    sessions,
)
from app.validation import localize_validation_errors

settings = get_settings()


# FastAPI 利用这个，把"你的启动逻辑"和"你的关闭逻辑"拆到了暂停点的两边
@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await asyncio.to_thread(storage.ensure_bucket)
    yield
    await close_queue()


app = FastAPI(
    title="AI 修图智能体",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": localize_validation_errors(exc.errors())},
    )

api = APIRouter(prefix="/api")
api.include_router(auth.router)
api.include_router(assets.router)
api.include_router(health.router)
api.include_router(runs.router)
api.include_router(sessions.router)
api.include_router(batches.router)
api.include_router(admin_users.router)
api.include_router(admin_config.router)
app.include_router(api)

# SSE 不挂在 /api 下，便于反向代理单独关闭缓冲
app.include_router(events.router)

# 生产环境下前端与 API 同源，静态产物由本服务托管；开发环境走 Vite dev proxy。
if settings.frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
