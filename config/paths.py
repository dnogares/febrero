#!/usr/bin/env python3
"""
config/paths.py
Configuración centralizada de rutas del proyecto
Compatible con Docker / Easypanel
"""

from pathlib import Path
import os
import sys

# Proyecto / repo root (dos niveles arriba desde este archivo)
REPO_ROOT = Path(__file__).resolve().parents[1]

# Raíz de datos: variable de entorno con fallback a <repo>/data
DATA_ROOT = Path(os.getenv("TASACION_DATA_ROOT", REPO_ROOT / "data")).resolve()

# Directorios configurables mediante variables de entorno (más flexibles)
OUTPUTS_DIR = Path(os.getenv("TASACION_OUTPUTS_DIR", DATA_ROOT / "outputs")).resolve()
CAPAS_DIR = Path(os.getenv("TASACION_CAPAS_DIR", DATA_ROOT / "capas")).resolve()
STATIC_DIR = Path(os.getenv("TASACION_STATIC_DIR", REPO_ROOT / "static")).resolve()
TEMP_DIR = Path(os.getenv("TASACION_TEMP_DIR", DATA_ROOT / "temp")).resolve()

# Subdirectorios de capas (mantener consistencia)
CAPAS_AMBIENTAL_DIR = CAPAS_DIR / "ambiental"
CAPAS_RIESGOS_DIR = CAPAS_DIR / "riesgos"
CAPAS_INFRAESTRUCTURAS_DIR = CAPAS_DIR / "infraestructuras"


def _ensure_writable_dir(path: Path) -> Path:
    """Asegura que `path` exista y sea escribible; si no, intenta fallback al home."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_test"
        with open(test_file, "w") as f:
            f.write("ok")
        test_file.unlink()
        return path
    except Exception:
        home_fallback = Path.home() / ".tasacion_data" / path.name
        home_fallback.mkdir(parents=True, exist_ok=True)
        return home_fallback


def inicializar_directorios():
    """Crea todos los directorios necesarios y configura variables temporales.

    También exporta `TEMP`, `TMP` y `TMPDIR` apuntando a `TEMP_DIR` para ayudar
    a herramientas que usan el directorio temporal (pip/meson durante builds).
    """
    global DATA_ROOT, OUTPUTS_DIR, CAPAS_DIR, STATIC_DIR, TEMP_DIR

    # Asegurar root de datos
    DATA_ROOT = _ensure_writable_dir(DATA_ROOT)

    # Asegurar directorios principales
    OUTPUTS_DIR = _ensure_writable_dir(OUTPUTS_DIR)
    CAPAS_DIR = _ensure_writable_dir(CAPAS_DIR)
    STATIC_DIR = _ensure_writable_dir(STATIC_DIR)
    TEMP_DIR = _ensure_writable_dir(TEMP_DIR)

    # Subdirectorios de capas
    _ensure_writable_dir(CAPAS_DIR / "ambiental")
    _ensure_writable_dir(CAPAS_DIR / "riesgos")
    _ensure_writable_dir(CAPAS_DIR / "infraestructuras")

    # Forzar variables de entorno temporales para procesos de build
    os.environ.setdefault("TMPDIR", str(TEMP_DIR))
    os.environ.setdefault("TEMP", str(TEMP_DIR))
    os.environ.setdefault("TMP", str(TEMP_DIR))

    print(f"✅ Directorios inicializados. DATA_ROOT={DATA_ROOT}")


# Inicializar por defecto al importar el módulo para compatibilidad simple
try:
    inicializar_directorios()
except Exception:
    # Si por alguna razón falla la inicialización automática, no crashar la importación
    print("⚠️ Inicialización de directorios fallida al importar config.paths", file=sys.stderr)
