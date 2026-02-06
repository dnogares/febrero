from fastapi import APIRouter, HTTPException
from .motor_urbanistico import MotorUrbanisticoHibrido
from pathlib import Path
from config.paths import CAPAS_DIR, OUTPUTS_DIR

router = APIRouter(prefix="/api/v1/urbanismo", tags=["Análisis Urbanístico"])

# Inicialización única del motor
motor = MotorUrbanisticoHibrido(
    data_dir=str(CAPAS_DIR), 
    output_dir=str(OUTPUTS_DIR)
)

@router.get("/analizar/{referencia}")
async def analizar_catastro(referencia: str):
    """
    Punto de entrada principal para el análisis de una parcela.
    Busca automáticamente en carpetas locales o PostGIS.
    """
    resultado = motor.ejecutar_analisis(referencia)
    
    if resultado["status"] == "error":
        raise HTTPException(status_code=404, detail=resultado["message"])
        
    return resultado

@router.get("/status")
async def health_check():
    # Verificar conexión a DB
    db_status = motor.check_connection()
    return {"status": "online", "motor": "Híbrido (Files/PostGIS)", "database": db_status}