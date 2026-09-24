# -*- coding: utf-8 -*-
from fastapi import APIRouter
from flasheo.api.v1.endpoints import auth, onus, lotes, modelos, flasheo, ws

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(onus.router)
api_v1_router.include_router(lotes.router)
api_v1_router.include_router(modelos.router)
api_v1_router.include_router(flasheo.router)
