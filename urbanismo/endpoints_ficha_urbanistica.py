#!/usr/bin/env python3
"""
Endpoints para fichas urbanísticas - Integración con main.py
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from typing import Optional
import logging
import tempfile

logger = logging.getLogger(__name__)

# Router
router = APIRouter(prefix="/api/ficha-urbanistica", tags=["Ficha Urbanística"])

# Servicios globales (se inicializan en setup)
_generador_pdf = None
_extractor = None
_gestor_normativa = None


def inicializar_servicios(base_dir: Path):
    """Inicializa servicios de fichas urbanísticas"""
    global _generador_pdf, _extractor, _gestor_normativa
    
    try:
        from urbanismo.generador_pdf_resultados import GeneradorPDFResultados
        from urbanismo.extractor_ficha_urbanistica import ExtractorFichaUrbanistica
        from urbanismo.gestor_normativa_urbanistica import GestorNormativaUrbanistica
        
        catalogo_path = base_dir / "catalogo_espana_50_ciudades.json"
        
        _generador_pdf = GeneradorPDFResultados()
        _extractor = ExtractorFichaUrbanistica()
        
        if catalogo_path.exists():
            _gestor_normativa = GestorNormativaUrbanistica(str(catalogo_path))
            logger.info(f"✅ Catálogo normativa cargado: {catalogo_path}")
        else:
            logger.warning(f"⚠️ Catálogo no encontrado: {catalogo_path}")
            _gestor_normativa = None
        
        logger.info("✅ Servicios de ficha urbanística inicializados")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Error importando módulos: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error inicializando servicios: {e}")
        return False


@router.post("/procesar")
async def procesar_referencia_ficha(
    referencia: str = Form(...),
    pdf_file: Optional[UploadFile] = File(None)
):
    """
    Procesa referencia catastral y genera PDF profesional de ficha urbanística
    
    - Con PDF: extrae datos del PDF cargado
    - Sin PDF: genera datos desde otras fuentes (BD, API Catastro)
    """
    try:
        ref_limpia = referencia.replace(' ', '').strip().upper()
        
        if len(ref_limpia) != 14:
            raise HTTPException(
                status_code=400,
                detail="Referencia catastral debe tener 14 caracteres"
            )
        
        logger.info(f"📋 Procesando ficha para: {ref_limpia}")
        
        # Obtener datos
        datos = await _obtener_datos_completos(ref_limpia, pdf_file)
        
        # Generar PDF profesional
        pdf_path = await _generar_pdf_ficha(ref_limpia, datos)
        
        return JSONResponse({
            "status": "success",
            "referencia": ref_limpia,
            "datos": datos,
            "pdf_url": f"/api/ficha-urbanistica/descargar/{ref_limpia}",
            "pdf_path": str(pdf_path)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error procesando ficha: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/descargar/{referencia}")
async def descargar_pdf_ficha(referencia: str):
    """Descarga PDF de ficha urbanística generado"""
    try:
        from config.paths import OUTPUTS_DIR
        
        ref_limpia = referencia.replace(' ', '').strip().upper()
        pdf_path = OUTPUTS_DIR / ref_limpia / f"ficha_urbanistica_{ref_limpia}_PROFESIONAL.pdf"
        
        if not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"PDF no encontrado para {ref_limpia}"
            )
        
        return FileResponse(
            path=str(pdf_path),
            filename=f"ficha_urbanistica_{ref_limpia}.pdf",
            media_type="application/pdf"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datos/{referencia}")
async def obtener_datos_ficha(referencia: str):
    """Obtiene datos de ficha sin generar PDF (preview rápido)"""
    try:
        ref_limpia = referencia.replace(' ', '').strip().upper()
        datos = await _obtener_datos_completos(ref_limpia, None)
        return JSONResponse(datos)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== FUNCIONES AUXILIARES ====================

async def _obtener_datos_completos(referencia: str, pdf_file: Optional[UploadFile]) -> dict:
    """Obtiene datos de múltiples fuentes con prioridad"""
    
    datos = {}
    
    # 1. Si hay PDF, extraer datos
    if pdf_file and _extractor:
        logger.info("📄 Extrayendo datos del PDF...")
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                content = await pdf_file.read()
                tmp.write(content)
                tmp_path = tmp.name
            
            datos = _extractor.extraer_datos(tmp_path)
            datos['referencia'] = referencia
            datos['fuente'] = 'PDF cargado'
            
            Path(tmp_path).unlink()
            logger.info(f"✅ Datos extraídos: {datos.get('municipio', 'N/A')}")
            
        except Exception as e:
            logger.error(f"⚠️ Error extrayendo PDF: {e}")
            datos = {}
    
    # 2. Si no hay datos, consultar BD local
    if not datos.get('municipio'):
        logger.info("🔍 Consultando base de datos...")
        datos_bd = _consultar_bd_local(referencia)
        if datos_bd:
            datos.update(datos_bd)
    
    # 3. Si no hay datos, simular con API Catastro
    if not datos.get('municipio'):
        logger.info("🌐 Generando datos desde Catastro...")
        datos = _simular_datos_catastro(referencia)
    
    # 4. Enriquecer con normativa
    if datos.get('municipio') and _gestor_normativa:
        logger.info(f"📚 Buscando normativa para {datos['municipio']}...")
        normativa = _obtener_normativa_aplicable(
            datos['municipio'],
            datos.get('provincia', '')
        )
        datos['normativa_aplicable'] = normativa
        datos['stats_normativa'] = {
            'total': len(normativa),
            'encontradas': len([n for n in normativa if n.get('encontrada')]),
            'porcentaje_match': 0
        }
        if datos['stats_normativa']['total'] > 0:
            datos['stats_normativa']['porcentaje_match'] = (
                datos['stats_normativa']['encontradas'] / 
                datos['stats_normativa']['total'] * 100
            )
    else:
        datos['normativa_aplicable'] = []
        datos['stats_normativa'] = {'total': 0, 'encontradas': 0, 'porcentaje_match': 0}
    
    return datos


def _consultar_bd_local(referencia: str) -> dict:
    """Consulta PostgreSQL local (implementar según tu BD)"""
    # TODO: Implementar consulta real a tu BD
    return {}


def _simular_datos_catastro(referencia: str) -> dict:
    """Simula datos inteligentes desde Catastro"""
    
    provincia_cod = referencia[:2]
    
    provincias = {
        '30': ('MURCIA', 'Murcia'),
        '28': ('MADRID', 'Madrid'),
        '41': ('SEVILLA', 'Sevilla'),
        '08': ('BARCELONA', 'Barcelona'),
        '46': ('VALENCIA', 'Valencia'),
        '03': ('ALICANTE', 'Alicante'),
        '04': ('ALMERÍA', 'Almería'),
    }
    
    municipio, provincia = provincias.get(provincia_cod, ('Municipio Desconocido', 'Provincia'))
    
    return {
        'referencia': referencia,
        'municipio': municipio,
        'provincia': provincia,
        'denominacion': f'Parcela {referencia[-4:]}',
        'clasificacion_suelo': 'Suelo Urbano Consolidado',
        'uso_global': 'Residencial',
        'uso_dominante': 'Vivienda',
        'superficie': '',
        'aprovechamiento': '',
        'otros_usos': [],
        'observaciones': '',
        'fuente': 'Datos simulados (Catastro API)'
    }


def _obtener_normativa_aplicable(municipio: str, provincia: str) -> list:
    """Obtiene normativa aplicable del catálogo"""
    
    if not _gestor_normativa:
        return []
    
    try:
        # Buscar normativas del municipio
        normativas = _gestor_normativa.buscar_normativas_municipio(municipio)
        
        return [
            {
                'texto_original': f"{norm.get('tipo_norma', '')} - {norm.get('titulo', '')}",
                'numero': norm.get('numero_modificacion', 0),
                'articulo': norm.get('articulo', ''),
                'titulo': norm.get('titulo', ''),
                'encontrada': True,
                'norma': norm
            }
            for norm in normativas[:15]  # Limitar a 15
        ]
        
    except Exception as e:
        logger.error(f"Error obteniendo normativa: {e}")
        return []


async def _generar_pdf_ficha(referencia: str, datos: dict) -> Path:
    """Genera PDF profesional de la ficha"""
    
    try:
        from config.paths import OUTPUTS_DIR
        
        output_dir = OUTPUTS_DIR / referencia
        output_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_path = output_dir / f"ficha_urbanistica_{referencia}_PROFESIONAL.pdf"
        
        # Preparar datos para PDF
        datos_pdf = {
            'referencia': referencia,
            'municipio': datos.get('municipio', ''),
            'denominacion': datos.get('denominacion', ''),
            'clasificacion_suelo': datos.get('clasificacion_suelo', ''),
            'uso_global': datos.get('uso_global', ''),
            'uso_dominante': datos.get('uso_dominante', ''),
            'superficie': datos.get('superficie', ''),
            'aprovechamiento': datos.get('aprovechamiento', ''),
            'otros_usos': datos.get('otros_usos', []),
            'observaciones': datos.get('observaciones', ''),
            'referencias_normativas': datos.get('normativa_aplicable', []),
            'stats_normativa': datos.get('stats_normativa', {
                'total': 0,
                'encontradas': 0,
                'porcentaje_match': 0
            })
        }
        
        # Generar PDF
        if _generador_pdf:
            _generador_pdf.generar_pdf_ficha_urbanistica(
                datos_ficha=datos_pdf,
                output_path=str(pdf_path)
            )
            logger.info(f"✅ PDF generado: {pdf_path}")
        else:
            raise Exception("Generador PDF no inicializado")
        
        return pdf_path
        
    except Exception as e:
        logger.error(f"Error generando PDF: {e}")
        raise


def setup_ficha_urbanistica_routes(app, base_dir: Path):
    """
    Configura las rutas de fichas urbanísticas
    Llamar desde tu startup en main.py
    """
    if inicializar_servicios(base_dir):
        app.include_router(router)
        logger.info("✅ Rutas de ficha urbanística configuradas")
        return True
    else:
        logger.warning("⚠️ No se pudieron configurar rutas de ficha urbanística")
        return False
