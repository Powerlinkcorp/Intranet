# -*- coding: utf-8 -*-
"""
api.v1.endpoints.modelos — Gestión de Modelos de ONUs y Carga de Firmware.
"""
import os
import shutil
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
import profiles
from api.v1.endpoints.auth import require_operator

router = APIRouter(tags=["Modelos y Firmwares"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FIRMWARES_DIR = os.path.join(PROJECT_ROOT, "firmwares")
os.makedirs(FIRMWARES_DIR, exist_ok=True)


@router.get("/models", summary="Listar modelos soportados de ONU")
def get_models() -> List[Dict[str, Any]]:
    return profiles.get_models_list()


@router.get("/firmwares", summary="Listar archivos de firmware disponibles")
def get_firmwares() -> List[str]:
    files = [f for f in os.listdir(FIRMWARES_DIR) if f.lower().endswith(".bin")]
    return sorted(files)


@router.post("/firmwares/upload", summary="Subir un nuevo archivo de firmware (.bin)")
async def upload_firmware(
    file: UploadFile = File(...),
    operator: dict = Depends(require_operator)
):
    filename = os.path.basename(file.filename)
    if not filename.lower().endswith(".bin"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos de firmware con extensión .bin")
    
    dest = os.path.join(FIRMWARES_DIR, filename)
    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    size_mb = round(os.path.getsize(dest) / (1024 * 1024), 2)
    return {
        "success": True,
        "filename": filename,
        "size_mb": size_mb,
        "message": f"Firmware '{filename}' ({size_mb} MB) cargado exitosamente."
    }
