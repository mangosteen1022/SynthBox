"""API 路由模块"""

from fastapi import APIRouter
from .health import router as health_router
from .accounts import router as accounts_router
from .mails import router as mails_router
from .folders import router as folders_router
from .aliases import router as aliases_router
from .tokens import router as tokens_router


def include_all_routers(app):
    """注册所有路由到 FastAPI 应用"""
    app.include_router(health_router, tags=["Health"])
    app.include_router(accounts_router, prefix="/accounts", tags=["Accounts"])
    app.include_router(mails_router, prefix="/mail", tags=["Mails"])
    app.include_router(folders_router, tags=["Folders"])
    app.include_router(aliases_router, tags=["Aliases"])
    app.include_router(tokens_router, tags=["Tokens"])


__all__ = ["include_all_routers"]
