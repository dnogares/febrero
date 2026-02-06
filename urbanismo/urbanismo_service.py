#!/usr/bin/env python3
"""
urbanismo/urbanismo_service.py

Servicio de urbanismo integrado con el sistema SuiteTasacion

Incluye:
- Análisis avanzado con AnalizadorUrbanistico
- Extracción de fichas urbanísticas PDF
- Sistema de normativa urbanística (PGOU, modificaciones)
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dataclasses import asdict

from .analisisurbano_mejorado import AnalisisUrbano, ResultadosUrbanismo
from .analizador_urbanistico import AnalizadorUrbanistico
from .extractor_ficha_urbanistica import ExtractorFichaUrbanistica

logger = logging.getLogger(__name__)


class UrbanismoService:
    """
    Servicio de urbanismo para integración con el sistema principal

    Proporciona interfaz compatible con LoteManager y PDFGenerator
    Incluye análisis avanzado de parámetros urbanísticos y afecciones
    """

    def __init__(self, output_base_dir: str = "resultados", catalogo_normativa_path: Optional[str] = None):
        """
        Inicializa el servicio de urbanismo

        Args:
            output_base_dir: Directorio base para resultados
            catalogo_normativa_path: Ruta al catálogo de normativa (opcional)
        """
        self.output_base_dir = Path(output_base_dir)

        # Analizador básico (para compatibilidad) - ahora usa directorio base directamente
        self.analizador = AnalisisUrbano(
            output_dir=str(self.output_base_dir),  # ya no usa subcarpeta urbanismo
            encuadre_factor=4.0,
        )

        # Analizador avanzado (nuevas funcionalidades)
        self.analizador_avanzado = AnalizadorUrbanistico(
            normativa_dir=str(self.output_base_dir / "normativa"),
            capas_service=self,  # Pasar el mismo servicio para usar CAPAS_DIR local
        )

        # Extractor de fichas urbanísticas (PDF)
        self.extractor_fichas = ExtractorFichaUrbanistica()

        # Gestor de normativa urbanística
        self._inicializar_gestor_normativa(catalogo_normativa_path)

        logger.info(f"UrbanismoService inicializado. Output: {self.output_base_dir}")

    def _inicializar_gestor_normativa(self, catalogo_path: Optional[str]):
        """Inicializa el gestor de normativa urbanística"""
        try:
            from .gestor_normativa_urbanistica import GestorNormativaUrbanistica

            if catalogo_path and Path(catalogo_path).exists():
                self.gestor_normativa = GestorNormativaUrbanistica(catalogo_path)
                logger.info(f"Catálogo de normativa cargado desde: {catalogo_path}")
            else:
                # Crear catálogo por defecto con Murcia
                self.gestor_normativa = GestorNormativaUrbanistica()
                self.gestor_normativa.crear_catalogo_murcia_ejemplo()

                # Guardar catálogo por defecto
                catalogo_default = self.output_base_dir / "normativa" / "catalogo_normativa.json"
                catalogo_default.parent.mkdir(parents=True, exist_ok=True)
                self.gestor_normativa.guardar_catalogo(str(catalogo_default))
                logger.info(f"Catálogo de normativa creado en: {catalogo_default}")

            logger.info(f"Gestor de normativa inicializado con {len(self.gestor_normativa.normas)} normas")

        except ImportError:
            logger.warning("GestorNormativaUrbanistica no disponible, funcionalidad de normativa deshabilitada")
            self.gestor_normativa = None

    # --- Métodos de CapasService para usar directorio local de capas ---

    def _get_db_engine(self):
        """Obtiene el motor de base de datos PostGIS si está configurado"""
        try:
            from sqlalchemy import create_engine
            
            host = os.getenv("POSTGRES_HOST")
            db = os.getenv("POSTGRES_DB")
            user = os.getenv("POSTGRES_USER")
            password = os.getenv("POSTGRES_PASSWORD")
            port = os.getenv("POSTGRES_PORT", "5432")
            
            if all([host, db, user, password]):
                url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
                return create_engine(url)
        except ImportError:
            logger.warning("SQLAlchemy no instalado. Soporte PostGIS desactivado.")
        except Exception as e:
            logger.error(f"Error conectando a PostGIS: {e}")
        return None

    def listar_capas_postgis(self) -> List[Dict]:
        """Lista capas disponibles en PostGIS"""
        capas = []
        engine = self._get_db_engine()
        if not engine:
            return []
            
        try:
            import pandas as pd
            query = "SELECT f_table_name, f_geometry_column, srid, type FROM geometry_columns WHERE f_table_schema = 'public'"
            df = pd.read_sql(query, engine)
            
            for _, row in df.iterrows():
                capas.append({
                    "nombre": row['f_table_name'],
                    "tipo": "postgis",
                    "geom_col": row['f_geometry_column'],
                    "srid": row['srid'],
                    "origen": "PostGIS",
                    "ruta_completa": f"postgis://{row['f_table_name']}",
                    "archivo": row['f_table_name'],
                    "extension": ""
                })
        except Exception as e:
            logger.error(f"Error listando capas PostGIS: {e}")
            
        return capas

    def listar_capas(self) -> List[Dict]:
        """
        Lista las capas disponibles en el directorio CAPAS_DIR.

        Busca archivos .geojson, .shp y .gml (excluyendo .gpkg).
        """
        try:
            from config.paths import CAPAS_DIR

            capas_disponibles = []

            extensiones = {".geojson", ".shp", ".gml"}

            for extension in extensiones:
                for file_path in CAPAS_DIR.glob(f"*{extension}"):
                    if (
                        file_path.suffix.lower() in extensiones
                        and not any(
                            suffix in file_path.name.lower()
                            for suffix in [
                                ".cpg",
                                ".dbf",
                                ".prj",
                                ".shx",
                                ".qix",
                                ".qmd",
                                ".gfs",
                            ]
                        )
                    ):
                        nombre_capa = file_path.stem
                        capas_disponibles.append(
                            {
                                "nombre": nombre_capa,
                                "tipo": "vectorial",
                                "ruta_completa": str(file_path),
                                "archivo": file_path.name,
                                "extension": file_path.suffix.lower(),
                            }
                        )

            # Agregar capas de PostGIS
            capas_postgis = self.listar_capas_postgis()
            if capas_postgis:
                capas_disponibles.extend(capas_postgis)
                logger.info(f"Capas encontradas en PostGIS: {len(capas_postgis)}")

            logger.info(
                f"Capas encontradas en CAPAS_DIR (sin GPKG): "
                f"{[c['nombre'] for c in capas_disponibles]}"
            )
            return capas_disponibles

        except Exception as e:
            logger.error(f"Error listando capas del CAPAS_DIR: {e}")
            return []

    def descargar_capa(self, nombre_capa: str, url_descarga: str) -> Optional[Path]:
        """
        Descarga una capa vectorial de una URL y la guarda en CAPAS_DIR.
        """
        try:
            from config.paths import CAPAS_DIR
            import requests

            download_dir = CAPAS_DIR / "descargadas"
            download_dir.mkdir(parents=True, exist_ok=True)

            local_file_name = f"{nombre_capa}.gpkg"
            local_path = download_dir / local_file_name

            logger.info(
                f"Descargando capa '{nombre_capa}' desde {url_descarga} a {local_path}"
            )

            response = requests.get(url_descarga, stream=True)
            response.raise_for_status()

            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(
                f"Capa '{nombre_capa}' descargada exitosamente a {local_path}"
            )
            return local_path

        except Exception as e:
            logger.error(
                f"Error descargando capa '{nombre_capa}' desde {url_descarga}: {e}"
            )
            return None

    def obtener_o_descargar_capa(
        self, nombre_capa: str, url_descarga: Optional[str] = None, layer: Optional[str] = None
    ):
        """
        Intenta cargar una capa localmente desde GeoJSON, SHP o GML.
        """
        from config.paths import CAPAS_DIR
        import geopandas as gpd

        extensiones = {".geojson", ".shp", ".gml"}

        for extension in extensiones:
            for file_path in CAPAS_DIR.glob(f"*{extension}"):
                if file_path.stem == nombre_capa:
                    try:
                        logger.info(
                            f"Capa '{nombre_capa}' encontrada localmente en {file_path.name}. Cargando..."
                        )
                        capa_gdf = gpd.read_file(file_path)

                        if capa_gdf.crs and capa_gdf.crs != "EPSG:25830":
                            capa_gdf = capa_gdf.to_crs("EPSG:25830")

                        return capa_gdf
                    except Exception as e:
                        logger.warning(
                            f"Error al intentar cargar '{nombre_capa}' de {file_path.name}: {e}"
                        )

        # Intentar cargar desde PostGIS
        engine = self._get_db_engine()
        if engine:
            try:
                from sqlalchemy import inspect
                insp = inspect(engine)
                if insp.has_table(nombre_capa):
                    logger.info(f"Cargando capa '{nombre_capa}' desde PostGIS...")
                    # Usar consulta SQL directa para evitar ambigüedades
                    capa_gdf = gpd.read_postgis(f'SELECT * FROM "{nombre_capa}"', engine)
                    if capa_gdf.crs and capa_gdf.crs != "EPSG:25830":
                        capa_gdf = capa_gdf.to_crs("EPSG:25830")
                    return capa_gdf
            except Exception as e:
                logger.debug(f"No se pudo cargar '{nombre_capa}' desde PostGIS: {e}")

        if url_descarga:
            logger.info(
                f"Capa '{nombre_capa}' no encontrada localmente. "
                f"Intentando descargar de {url_descarga}..."
            )
            local_path = self.descargar_capa(nombre_capa, url_descarga)
            if local_path:
                try:
                    import geopandas as gpd

                    logger.info(
                        f"Capa '{nombre_capa}' descargada. Cargando desde {local_path}..."
                    )
                    capa_gdf = gpd.read_file(local_path)
                    if capa_gdf.crs and capa_gdf.crs != "EPSG:25830":
                        capa_gdf = capa_gdf.to_crs("EPSG:25830")
                    return capa_gdf
                except Exception as e:
                    logger.error(
                        f"Error cargando capa '{nombre_capa}' después de descargar: {e}"
                    )
                    return None
            else:
                logger.error(
                    f"No se pudo descargar la capa '{nombre_capa}'."
                )
                return None

        logger.error(
            f"Capa '{nombre_capa}' no encontrada localmente y no se proporcionó URL de descarga."
        )
        return None

    def cargar_capa(self, nombre_capa: str):
        """
        Alias para compatibilidad con AnalizadorUrbanistico.
        """
        return self.obtener_o_descargar_capa(nombre_capa)

    # --- Análisis de parcelas ---

    def analizar_parcela(self, parcela_path: str, referencia: str) -> Dict[str, any]:
        """
        Analiza una parcela y devuelve resultados completos

        Args:
            parcela_path: Ruta al archivo de la parcela (GML/GeoJSON)
            referencia: Referencia catastral

        Returns:
            Diccionario con resultados completos (básicos + avanzados)
        """
        try:
            # 1. Análisis básico
            geojson_path = self._asegurar_geojson(parcela_path)
            resultados_basicos = self.analizador.procesar_parcela(
                geojson_path, referencia
            )

            # 2. Análisis avanzado
            resultados_avanzados = self.analizador_avanzado.analizar_referencia(
                referencia=referencia,
                geometria_path=geojson_path,
            )

            # 3. Combinar resultados
            resultado_final = self._combinar_resultados(
                resultados_basicos, resultados_avanzados
            )

            # 4. Certificado avanzado
            if resultados_avanzados and not resultados_avanzados.get("error"):
                self._generar_certificado_avanzado(resultados_avanzados, referencia)

            return resultado_final

        except Exception as e:
            logger.error(f"Error en análisis urbanístico para {referencia}: {e}")
            return self._resultados_vacios(referencia, str(e))

    def _combinar_resultados(
        self, basicos: ResultadosUrbanismo, avanzados: Dict
    ) -> Dict[str, any]:
        """
        Combina resultados básicos y avanzados en un solo diccionario
        """
        resultado = {
            "total": sum(basicos.porcentajes.values()),
            "detalle": basicos.porcentajes,
            "area_parcela_m2": basicos.area_total_m2,
            "area_afectada_m2": basicos.area_total_m2,
            "urbanismo": True,
            "mapa_urbano": basicos.mapa_path,
            "referencia": basicos.referencia,
            "timestamp": basicos.timestamp,
            "csv_path": basicos.csv_path,
            "txt_path": basicos.txt_path,
        }

        if avanzados and not avanzados.get("error"):
            resultado.update(
                {
                    "analisis_avanzado": True,
                    "superficie": avanzados.get("superficie"),
                    "zonas_afectadas": avanzados.get("zonas_afectadas", []),
                    "parametros_urbanisticos": avanzados.get(
                        "parametros_urbanisticos", {}
                    ),
                    "afecciones_detectadas": avanzados.get("afecciones", []),
                    "recomendaciones": avanzados.get("recomendaciones", []),
                }
            )

        return resultado

    def _generar_certificado_avanzado(self, analisis: Dict, referencia: str):
        """
        Genera certificado de análisis avanzado (txt)
        """
        try:
            ref_dir = self.output_base_dir / referencia
            ref_dir.mkdir(parents=True, exist_ok=True)

            cert_path = ref_dir / f"certificado_{referencia}.txt"

            self.analizador_avanzado.generar_certificado(analisis, str(cert_path))
            logger.info(f"Certificado avanzado generado: {cert_path}")
        except Exception as e:
            logger.error(f"Error generando certificado avanzado: {e}")

    def _asegurar_geojson(self, parcela_path: str) -> str:
        """
        Convierte GML a GeoJSON si es necesario
        """
        parcela_path = Path(parcela_path)

        if parcela_path.suffix.lower() == ".geojson":
            return str(parcela_path)

        if parcela_path.suffix.lower() == ".gml":
            import geopandas as gpd
            import tempfile

            try:
                gdf = gpd.read_file(parcela_path)

                with tempfile.NamedTemporaryFile(
                    suffix=".geojson", delete=False
                ) as f:
                    temp_path = f.name

                gdf.to_file(temp_path, driver="GeoJSON")
                logger.debug(f"GML convertido a GeoJSON: {parcela_path} -> {temp_path}")
                return temp_path

            except Exception as e:
                logger.error(f"Error convirtiendo GML a GeoJSON: {e}")
                raise

        raise ValueError(f"Formato de archivo no soportado: {parcela_path.suffix}")

    def _resultados_vacios(self, referencia: str, error: str) -> Dict[str, any]:
        """
        Genera resultados vacíos en caso de error
        """
        return {
            "total": 0.0,
            "detalle": {},
            "area_parcela_m2": 0.0,
            "area_afectada_m2": 0.0,
            "urbanismo": True,
            "error": error,
            "referencia": referencia,
        }

    def obtener_mapas(self, referencia: str) -> List[str]:
        """
        Obtiene lista de mapas generados para una referencia
        """
        mapas = []

        ref_dir = self.output_base_dir / referencia
        if ref_dir.exists():
            mapa_files = list(ref_dir.glob("*_mapa.png"))
            mapas.extend([str(m) for m in mapa_files])

            otros_mapas = list(ref_dir.glob("*.png"))
            mapas.extend([str(m) for m in otros_mapas if "mapa" in m.name.lower()])

        if not mapas:
            urbanismo_dir = self.output_base_dir / "urbanismo"
            if urbanismo_dir.exists():
                for carpeta in urbanismo_dir.glob(f"{referencia}_*"):
                    mapa_files = list(carpeta.glob("*_mapa.png"))
                    mapas.extend([str(m) for m in mapa_files])

        return sorted(mapas)

    def limpiar_cache(self):
        """Limpia caché del analizador básico"""
        self.analizador.limpiar_cache()

    def get_estadisticas_globales(self) -> Dict[str, any]:
        """
        Obtiene estadísticas globales de todos los análisis realizados
        """
        urbanismo_dir = self.output_base_dir / "urbanismo"
        if not urbanismo_dir.exists():
            return {"total_analisis": 0}

        tipos_suelo = {}
        total_analisis = 0

        for carpeta in urbanismo_dir.iterdir():
            if not carpeta.is_dir():
                continue

            csv_files = list(carpeta.glob("*_porcentajes.csv"))
            for csv_file in csv_files:
                try:
                    import pandas as pd

                    df = pd.read_csv(csv_file)
                    for _, row in df.iterrows():
                        clase = row.get("Clase", "Desconocido")
                        area = row.get("Area_m2", 0)
                        if clase not in tipos_suelo:
                            tipos_suelo[clase] = 0
                        tipos_suelo[clase] += area
                        total_analisis += 1
                except Exception as e:
                    logger.warning(f"Error leyendo CSV {csv_file}: {e}")

        return {
            "total_analisis": total_analisis,
            "tipos_suelo": tipos_suelo,
            "area_total_analizada": sum(tipos_suelo.values()),
        }

    # ============================================================================
    # PROCESAMIENTO DE FICHAS URBANÍSTICAS (PDF)
    # ============================================================================

    def procesar_ficha_urbanistica(self, pdf_path: str, referencia: str) -> Dict:
        """
        Procesa ficha urbanística PDF y genera CSV/JSON con los datos extraídos
        (SIN enlazado de normativa)

        Args:
            pdf_path: Ruta al PDF de la ficha
            referencia: Referencia catastral

        Returns:
            Diccionario con datos extraídos y rutas de salida
        """
        try:
            ref_dir = self.output_base_dir / referencia
            ref_dir.mkdir(parents=True, exist_ok=True)

            datos_ficha = self.extractor_fichas.extraer_pdf(pdf_path)

            csv_path = ref_dir / f"ficha_urbanistica_{referencia}.csv"
            json_path = ref_dir / f"ficha_urbanistica_{referencia}.json"

            self.extractor_fichas.exportar_csv(datos_ficha, str(csv_path))
            self.extractor_fichas.exportar_json(datos_ficha, str(json_path))

            logger.info(f"Ficha urbanística procesada para {referencia}")

            return {
                "referencia": referencia,
                "datos_extraidos": datos_ficha.to_dict(),
                "csv_path": str(csv_path),
                "json_path": str(json_path),
            }

        except Exception as e:
            logger.error(f"Error procesando ficha urbanística: {e}")
            return {
                "referencia": referencia,
                "error": str(e),
            }

    def procesar_ficha_urbanistica_completa(self, pdf_path: str, referencia: str) -> Dict:
        """
        Procesa ficha urbanística PDF CON enlazado de normativa

        Args:
            pdf_path: Ruta al PDF de la ficha
            referencia: Referencia catastral

        Returns:
            Diccionario con datos extraídos + normativa enlazada
        """
        try:
            ref_dir = self.output_base_dir / referencia
            ref_dir.mkdir(parents=True, exist_ok=True)

            # 1. Extraer datos del PDF
            datos_ficha = self.extractor_fichas.extraer_pdf(pdf_path)

            # 2. Enlazar normativa (si el gestor está disponible)
            normativa_enlazada = {'referencias': [], 'total': 0, 'encontradas': 0, 'porcentaje_match': 0}
            
            if self.gestor_normativa:
                normativa_enlazada = self.extractor_fichas.enlazar_normativa(
                    datos_ficha,
                    self.gestor_normativa
                )

            # 3. Exportar datos básicos
            csv_path = ref_dir / f"ficha_urbanistica_{referencia}.csv"
            json_path = ref_dir / f"ficha_urbanistica_{referencia}.json"

            self.extractor_fichas.exportar_csv(datos_ficha, str(csv_path))
            self.extractor_fichas.exportar_json(datos_ficha, str(json_path))

            # 4. Generar informe de normativa (si hay referencias)
            informe_path = None
            if self.gestor_normativa and normativa_enlazada['referencias']:
                informe_path = ref_dir / f"normativa_aplicable_{referencia}.txt"
                self.gestor_normativa.generar_informe_normativa(
                    normativa_enlazada['referencias'],
                    str(informe_path)
                )

            logger.info(f"Ficha urbanística procesada (con normativa) para {referencia}")
            if self.gestor_normativa:
                logger.info(f"Normativa: {normativa_enlazada['encontradas']}/{normativa_enlazada['total']} referencias encontradas")

            return {
                'referencia': referencia,
                'datos_extraidos': datos_ficha.to_dict(),
                'normativa': normativa_enlazada,
                'csv_path': str(csv_path),
                'json_path': str(json_path),
                'informe_normativa_path': str(informe_path) if informe_path else None
            }

        except Exception as e:
            logger.error(f"Error procesando ficha urbanística completa: {e}")
            return {
                'referencia': referencia,
                'error': str(e)
            }

    # ============================================================================
    # GENERACIÓN DE PDF COMPLETO
    # ============================================================================

    def generar_pdf_completo(self, analisis_resultados: Dict, referencia: str) -> str:
        """
        Genera PDF completo con resultados del análisis urbanístico

        Args:
            analisis_resultados: Diccionario con resultados del análisis
            referencia: Referencia catastral

        Returns:
            Ruta al PDF generado
        """
        try:
            ref_dir = self.output_base_dir / referencia
            ref_dir.mkdir(parents=True, exist_ok=True)

            pdf_path = ref_dir / f"analisis_urbanistico_{referencia}.pdf"

            # Usar el método del analizador para generar PDF
            self.analizador.generar_pdf_resultados(analisis_resultados, str(pdf_path))

            logger.info(f"PDF completo generado: {pdf_path}")
            return str(pdf_path)

        except Exception as e:
            logger.error(f"Error generando PDF completo: {e}")
            raise


def crear_servicio_urbanismo(output_dir: str = "resultados", 
                             catalogo_normativa: Optional[str] = None) -> UrbanismoService:
    """
    Crea instancia del servicio de urbanismo para integración

    Args:
        output_dir: Directorio base de resultados
        catalogo_normativa: Ruta al catálogo de normativa (opcional)

    Returns:
        Instancia de UrbanismoService
    """
    return UrbanismoService(
        output_base_dir=output_dir,
        catalogo_normativa_path=catalogo_normativa
    )


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Uso: python urbanismo_service.py <parcela.gml/geojson>")
        sys.exit(1)

    parcela_path = sys.argv[1]
    referencia = Path(parcela_path).stem

    servicio = crear_servicio_urbanismo("test_urbanismo")

    resultados = servicio.analizar_parcela(parcela_path, referencia)
    
    print("\n" + "="*60)
    print("RESULTADOS DEL ANÁLISIS URBANÍSTICO")
    print("="*60)
    for key, value in resultados.items():
        print(f"  {key}: {value}")

    mapas = servicio.obtener_mapas(referencia)
    print(f"\nMapas generados: {mapas}")
    print("="*60)