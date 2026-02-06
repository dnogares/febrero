#!/usr/bin/env python3
"""
urbanismo/analisisurbano_mejorado.py

Análisis urbanístico mejorado con clase, caché y manejo robusto de errores
Incluye generación de PDF y CSV con resultados
"""

import os
import tempfile
import logging
import csv
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from dataclasses import dataclass

import geopandas as gpd
import matplotlib.pyplot as plt
import requests
from io import BytesIO
from owslib.wms import WebMapService

# Configuración de logging
logger = logging.getLogger(__name__)


@dataclass
class ResultadosUrbanismo:
    """Estructura de datos para resultados del análisis urbanístico"""
    referencia: str
    area_total_m2: float
    porcentajes: Dict[str, float]
    areas_m2: Dict[str, float]
    mapa_path: Optional[str] = None
    txt_path: Optional[str] = None
    csv_path: Optional[str] = None
    timestamp: Optional[str] = None


class AnalisisUrbano:
    """
    Clase principal para análisis urbanístico de parcelas

    Integra descarga WFS/WMS, cálculo de porcentajes y generación de mapas
    """

    def __init__(self, output_dir: str = "resultados_urbanismo", encuadre_factor: float = 4.0):
        """
        Inicializa el analizador urbanístico

        Args:
            output_dir: Directorio base para resultados
            encuadre_factor: Factor de zoom para mapas (menor = más cerca)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.encuadre_factor = encuadre_factor

        # Caché para evitar descargas repetidas
        self._wfs_cache = {}
        self._wms_cache = {}

        # URLs de servicios (configurables) - DESACTIVADAS para usar GPKG local
        self.wfs_carm_url = "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs?"
        self.wms_carm_url = "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wms?"
        self.wms_ign_url = "https://www.ign.es/wms-inspire/pnoa-ma"

        # Nombres de capas - DESACTIVADAS para usar GPKG local
        self.wfs_layer = "SIT_USU_PLA_URB_CARM:clases_plu_ze_37mun"
        self.wms_layer = "SIT_USU_PLA_URB_CARM:clases_plu_ze_37mun"

        # Configuración para usar GPKG local
        self.usar_gpkg_local = True
        self.gpkg_consolidado = None

        logger.info(f"AnalisisUrbano inicializado. Output: {self.output_dir}")
        logger.info("AnalisisUrbano configurado para usar GPKG local")

    def cargar_parcela(self, path_geojson: str) -> gpd.GeoDataFrame:
        """
        Carga parcela desde GeoJSON y reprojecta a Web Mercator

        Args:
            path_geojson: Ruta al archivo GeoJSON

        Returns:
            GeoDataFrame de la parcela en EPSG:3857

        Raises:
            FileNotFoundError: Si no existe el archivo
            ValueError: Si el archivo está vacío o no es válido
        """
        try:
            if not Path(path_geojson).exists():
                raise FileNotFoundError(f"No existe el archivo: {path_geojson}")

            gdf = gpd.read_file(path_geojson)

            if gdf.empty:
                raise ValueError(f"El archivo GeoJSON está vacío: {path_geojson}")

            logger.info(f"Parcela cargada: {path_geojson} ({len(gdf)} geometrías)")
            return gdf.to_crs(epsg=3857)  # Web Mercator para visualización

        except Exception as e:
            logger.error(f"Error cargando parcela {path_geojson}: {e}")
            raise

    def descargar_capa_wfs(self, base_url: str, typename: str, use_cache: bool = True) -> gpd.GeoDataFrame:
        """
        Descarga capa WFS como GeoDataFrame con caché optimizado
        O usa GPKG local si está configurado para ello

        Args:
            base_url: URL base del servicio WFS (ignorado si usar_gpkg_local=True)
            typename: Nombre de la capa a descargar
            use_cache: Si usar caché para evitar descargas repetidas

        Returns:
            GeoDataFrame en EPSG:25830 para cálculos de área

        Raises:
            requests.RequestException: Si falla la descarga
            ValueError: Si la respuesta no es válida
        """
        # Si está configurado para usar GPKG local, cargar desde ahí
        if self.usar_gpkg_local:
            return self._cargar_capa_gpkg_local(typename)

        cache_key = f"{base_url}_{typename}"

        # Usar caché si está disponible
        if use_cache and cache_key in self._wfs_cache:
            logger.info(f"Usando capa WFS desde caché: {typename}")
            return self._wfs_cache[cache_key]

        try:
            params = {
                "service": "WFS",
                "version": "1.0.0",
                "request": "GetFeature",
                "typename": typename,
                "outputFormat": "json",
                "srsName": "EPSG:4326",
            }

            logger.info(f"Descargando capa WFS: {typename}")
            response = requests.get(base_url, params=params, timeout=60)
            response.raise_for_status()

            if not response.content:
                raise ValueError("Respuesta vacía del servicio WFS")

            gdf = gpd.read_file(BytesIO(response.content))

            if gdf.empty:
                raise ValueError(f"La capa WFS está vacía: {typename}")

            # Estandarizar nombres de columnas a minúsculas
            gdf.columns = [c.lower() for c in gdf.columns]

            # Reproyectar a EPSG:25830 para cálculos de área precisos
            gdf = gdf.to_crs(epsg=25830)

            # Guardar en caché
            if use_cache:
                self._wfs_cache[cache_key] = gdf

            return gdf

        except Exception as e:
            logger.error(f"Error descargando capa WFS {typename}: {e}")
            raise

    def _cargar_capa_gpkg_local(self, typename: str) -> gpd.GeoDataFrame:
        """
        Carga una capa desde los archivos disponibles en CAPAS_DIR (GeoJSON, SHP, GML)

        Args:
            typename: Nombre de la capa (formato: "SIT_USU_PLA_URB_CARM:nombre_capa")

        Returns:
            GeoDataFrame en EPSG:25830 para cálculos de área
        """
        try:
            # Extraer nombre de capa del typename
            if ":" in typename:
                layer_name = typename.split(":")[1]
            else:
                layer_name = typename

            # Buscar en CAPAS_DIR sin usar GPKG consolidado
            from config.paths import CAPAS_DIR

            # Extensiones a buscar
            extensiones = [".geojson", ".shp", ".gml"]
            capa_encontrada = None

            for ext in extensiones:
                candidate_path = CAPAS_DIR / f"{layer_name}{ext}"
                if candidate_path.exists():
                    capa_encontrada = candidate_path
                    break

            if not capa_encontrada:
                logger.warning(f"No se encuentra la capa {layer_name} en CAPAS_DIR")
                return gpd.GeoDataFrame()

            logger.info(f"Cargando capa desde archivo local: {capa_encontrada.name}")
            gdf = gpd.read_file(capa_encontrada)

            if gdf.empty:
                logger.warning(f"La capa está vacía: {layer_name}")
                return gpd.GeoDataFrame()

            # Estandarizar nombres de columnas a minúsculas
            gdf.columns = [c.lower() for c in gdf.columns]

            # Reproyectar a EPSG:25830 para cálculos de área precisos
            gdf = gdf.to_crs(epsg=25830)

            logger.info(f"Capa '{layer_name}' cargada: {len(gdf)} geometrías")
            return gdf

        except Exception as e:
            logger.error(f"Error cargando capa {typename}: {e}")
            return gpd.GeoDataFrame()

    def calcular_porcentajes(
        self, gdf_parcela: gpd.GeoDataFrame, gdf_planeamiento: gpd.GeoDataFrame
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Calcula porcentajes reales de intersección entre parcela y capa

        Args:
            gdf_parcela: GeoDataFrame de la parcela
            gdf_planeamiento: GeoDataFrame de la capa de análisis

        Returns:
            Tuple: (areas_m2, porcentajes) con resultados por tipo
        """
        try:
            # Validar que ambos GeoDataFrames tengan geometría
            if gdf_parcela.empty or gdf_planeamiento.empty:
                logger.warning("Uno de los GeoDataFrames está vacío")
                return {}, {}

            # Asegurar que tienen geometría activa
            if gdf_parcela.geometry.isna().all():
                logger.warning("La parcela no tiene geometría válida")
                return {}, {}

            if gdf_planeamiento.geometry.isna().all():
                logger.warning("La capa de análisis no tiene geometría válida")
                return {}, {}

            # Asegurar CRS para cálculos de área
            if gdf_parcela.crs:
                gdf_parcela_calc = gdf_parcela.to_crs(epsg=25830)
            else:
                gdf_parcela_calc = gdf_parcela.set_crs(epsg=25830)

            if gdf_planeamiento.crs:
                gdf_planeamiento_calc = gdf_planeamiento.to_crs(epsg=25830)
            else:
                gdf_planeamiento_calc = gdf_planeamiento.set_crs(epsg=25830)

            # Calcular intersección
            interseccion = gpd.overlay(
                gdf_planeamiento_calc, gdf_parcela_calc, how="intersection"
            )

            if interseccion.empty:
                logger.warning("No hay intersección entre parcela y capa")
                return {}, {}

            # Calcular áreas en m²
            interseccion["area_m2"] = interseccion.geometry.area

            # Buscar campo de clasificación o usar nombre de la capa
            campo_clasificacion = None
            posibles_campos = [
                "clasificacion",
                "clase",
                "tipo",
                "uso",
                "category",
                "name",
                "nombre",
                "denominacion",
            ]

            for campo in posibles_campos:
                if campo in interseccion.columns:
                    campo_clasificacion = campo
                    break

            # Si no hay campo de clasificación, usar el nombre de la capa
            if campo_clasificacion is None:
                interseccion["tipo_suelo"] = "General"
                logger.info(
                    "Usando clasificación 'General' (no se encontró campo específico)"
                )
            else:
                # Limpiar valores nulos y normalizar
                interseccion[campo_clasificacion] = interseccion[
                    campo_clasificacion
                ].fillna("Sin clasificar")
                interseccion["tipo_suelo"] = interseccion[campo_clasificacion].astype(
                    str
                )

            # Agrupar por tipo y sumar áreas
            resumen = interseccion.groupby("tipo_suelo")["area_m2"].sum()
            total_area = resumen.sum()

            if total_area == 0:
                logger.warning("El área total de intersección es 0")
                return {}, {}

            # Calcular porcentajes
            porcentajes = (resumen / total_area) * 100

            logger.info(f"Calculados {len(resumen)} tipos. Total: {total_area:.2f} m²")
            return resumen.to_dict(), porcentajes.to_dict()

        except Exception as e:
            logger.error(f"Error calculando porcentajes: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return {}, {}

    def descargar_ortofoto(
        self, extent: Tuple[float, float, float, float], wms_url: Optional[str] = None
    ) -> str:
        """
        Descarga ortofoto WMS (IGN PNOA) usando archivo temporal

        Args:
            extent: Tupla (minx, maxx, miny, maxy) en EPSG:3857
            wms_url: URL del servicio WMS (opcional, usa IGN por defecto)

        Returns:
            Ruta al archivo temporal de la ortofoto

        Raises:
            requests.RequestException: Si falla la descarga
        """
        wms_url = wms_url or self.wms_ign_url
        minx, maxx, miny, maxy = extent

        try:
            wms = WebMapService(wms_url, version="1.3.0")
            img = wms.getmap(
                layers=["OI.OrthoimageCoverage"],
                srs="EPSG:3857",
                bbox=(minx, miny, maxx, maxy),
                size=(1000, 1000),
                format="image/jpeg",
                transparent=True,
            )

            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(img.read())
                ortofoto_path = f.name

            logger.debug(f"Ortofoto descargada: {ortofoto_path}")
            return ortofoto_path

        except Exception as e:
            logger.error(f"Error descargando ortofoto: {e}")
            raise

    def descargar_urbanismo(
        self, extent: Tuple[float, float, float, float], wms_url: Optional[str] = None
    ) -> str:
        """
        Descarga capa de urbanismo WMS (colores oficiales CARM)

        Args:
            extent: Tupla (minx, maxx, miny, maxy) en EPSG:3857
            wms_url: URL del servicio WMS (opcional, usa CARM por defecto)

        Returns:
            Ruta al archivo temporal de la capa de urbanismo
        """
        wms_url = wms_url or self.wms_carm_url
        minx, maxx, miny, maxy = extent

        try:
            wms = WebMapService(wms_url, version="1.3.0")
            img = wms.getmap(
                layers=[self.wms_layer],
                srs="EPSG:3857",
                bbox=(minx, miny, maxx, maxy),
                size=(1000, 1000),
                format="image/png",
                transparent=True,
            )

            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(img.read())
                urbanismo_path = f.name

            logger.debug(f"Capa urbanismo descargada: {urbanismo_path}")
            return urbanismo_path

        except Exception as e:
            logger.error(f"Error descargando capa urbanismo: {e}")
            raise

    def descargar_leyenda(self, wms_url: Optional[str] = None) -> Optional[str]:
        """
        Descarga leyenda oficial WMS

        Args:
            wms_url: URL del servicio WMS (opcional, usa CARM por defecto)

        Returns:
            Ruta al archivo temporal de la leyenda o None si falla
        """
        wms_url = wms_url or self.wms_carm_url

        try:
            url = f"{wms_url}service=WMS&version=1.1.0&request=GetLegendGraphic&layer={self.wms_layer}&format=image/png"
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(response.content)
                leyenda_path = f.name

            logger.debug(f"Leyenda descargada: {leyenda_path}")
            return leyenda_path

        except Exception as e:
            logger.warning(f"No se pudo descargar la leyenda oficial: {e}")
            return None

    def generar_mapa(
        self,
        parcela: gpd.GeoDataFrame,
        ortofoto_path: str,
        urbanismo_path: str,
        leyenda_path: Optional[str],
        extent: Tuple[float, float, float, float],
        salida: str,
    ) -> str:
        """
        Genera mapa final con ortofoto + urbanismo + leyenda

        Args:
            parcela: GeoDataFrame de la parcela
            ortofoto_path: Ruta a la ortofoto
            urbanismo_path: Ruta a la capa de urbanismo
            leyenda_path: Ruta a la leyenda (opcional)
            extent: Extent del mapa en EPSG:3857
            salida: Ruta de salida para el mapa

        Returns:
            Ruta al mapa generado
        """
        try:
            fig, ax = plt.subplots(figsize=(10, 10))

            # Cargar y mostrar ortofoto
            ortofoto = plt.imread(ortofoto_path)
            ax.imshow(ortofoto, extent=extent, origin="upper")

            # Superponer capa de urbanismo con transparencia
            urbanismo_img = plt.imread(urbanismo_path)
            ax.imshow(urbanismo_img, extent=extent, origin="upper", alpha=0.5)

            # Dibujar límite de parcela en rojo
            parcela.boundary.plot(ax=ax, color="red", linewidth=2)

            # Configuración del mapa
            plt.title(
                "Parcela sobre ortofoto + urbanismo (colores oficiales)",
                fontsize=14,
                pad=20,
            )
            plt.axis("off")

            # Añadir leyenda si está disponible
            if leyenda_path and Path(leyenda_path).exists():
                leyenda_img = plt.imread(leyenda_path)
                ax_leyenda = fig.add_axes([0.75, 0.05, 0.2, 0.2])
                ax_leyenda.imshow(leyenda_img)
                ax_leyenda.axis("off")

            # Guardar mapa con alta calidad
            plt.savefig(salida, dpi=200, bbox_inches="tight", pad_inches=0.1)
            plt.close()

            logger.info(f"Mapa generado: {salida}")
            return salida

        except Exception as e:
            logger.error(f"Error generando mapa: {e}")
            raise

    def calcular_extent(
        self, parcela: gpd.GeoDataFrame
    ) -> Tuple[float, float, float, float]:
        """
        Calcula extent con factor de encuadre

        Args:
            parcela: GeoDataFrame de la parcela

        Returns:
            Tupla (minx, maxx, miny, maxy) en EPSG:3857
        """
        minx, miny, maxx, maxy = parcela.total_bounds
        ancho = maxx - minx
        alto = maxy - miny

        # Aplicar factor de encuadre
        minx -= (self.encuadre_factor - 1) * ancho / 2
        maxx += (self.encuadre_factor - 1) * ancho / 2
        miny -= (self.encuadre_factor - 1) * alto / 2
        maxy += (self.encuadre_factor - 1) * alto / 2

        return (minx, maxx, miny, maxy)

    def procesar_parcela(
        self, geojson_path: str, referencia: Optional[str] = None
    ) -> ResultadosUrbanismo:
        """
        Procesa una parcela completa: análisis urbanístico + mapa

        Args:
            geojson_path: Ruta al archivo GeoJSON de la parcela
            referencia: Referencia catastral (opcional, se extrae del nombre)

        Returns:
            Objeto ResultadosUrbanismo con todos los resultados
        """
        # Extraer referencia del nombre del archivo si no se proporciona
        if not referencia:
            referencia = Path(geojson_path).stem

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Crear directorio de salida (DIRECTO en la referencia, sin timestamp)
        carpeta_salida = self.output_dir / referencia
        carpeta_salida.mkdir(exist_ok=True, parents=True)

        logger.info(f"Procesando parcela: {referencia}")

        try:
            # 1. Cargar parcela
            parcela = self.cargar_parcela(geojson_path)

            # 2. Calcular extent para mapas
            extent = self.calcular_extent(parcela)

            # 3. Descargar capa de planeamiento (con caché)
            gdf_planeamiento = self.descargar_capa_wfs(self.wfs_carm_url, self.wfs_layer)

            # 4. Calcular porcentajes
            areas_m2, porcentajes = self.calcular_porcentajes(parcela, gdf_planeamiento)

            # 5. Generar archivos de salida
            salida_mapa = carpeta_salida / f"{referencia}_mapa.png"
            salida_txt = carpeta_salida / f"{referencia}_porcentajes.txt"
            salida_csv = carpeta_salida / f"{referencia}_porcentajes.csv"

            # 6. Guardar resultados textuales
            self._guardar_resultados_textuales(
                salida_txt, salida_csv, referencia, timestamp, areas_m2, porcentajes
            )

            # 7. Generar mapa visual
            ortofoto_path = self.descargar_ortofoto(extent)
            urbanismo_path = self.descargar_urbanismo(extent)
            leyenda_path = self.descargar_leyenda()

            try:
                self.generar_mapa(
                    parcela,
                    ortofoto_path,
                    urbanismo_path,
                    leyenda_path,
                    extent,
                    str(salida_mapa),
                )
            finally:
                # Limpiar archivos temporales
                self._limpiar_temporales([ortofoto_path, urbanismo_path, leyenda_path])

            # 8. Crear objeto de resultados
            resultados = ResultadosUrbanismo(
                referencia=referencia,
                area_total_m2=sum(areas_m2.values()),
                porcentajes=porcentajes,
                areas_m2=areas_m2,
                mapa_path=str(salida_mapa),
                txt_path=str(salida_txt),
                csv_path=str(salida_csv),
                timestamp=timestamp,
            )

            logger.info(
                f"Análisis completado para {referencia}. Resultados en: {carpeta_salida}"
            )
            return resultados

        except Exception as e:
            logger.error(f"Error procesando parcela {referencia}: {e}")
            raise

    def analizar(self, gml_path: str, referencia: str) -> Dict[str, any]:
        """
        Analiza una parcela usando las capas de planeamiento disponibles

        Args:
            gml_path: Ruta al archivo GML de la parcela
            referencia: Referencia catastral

        Returns:
            Diccionario con resultados del análisis
        """
        try:
            # Cargar parcela
            gdf_parcela = gpd.read_file(gml_path)

            if gdf_parcela.empty:
                return self._resultados_vacios(referencia, "Parcela vacía")

            # Reproyectar a EPSG:25830
            if gdf_parcela.crs:
                gdf_parcela = gdf_parcela.to_crs(epsg=25830)
            else:
                gdf_parcela = gdf_parcela.set_crs(epsg=25830)

            # Calcular área de la parcela
            area_parcela_m2 = gdf_parcela.geometry.area.sum()

            # Inicializar resultados
            resultados = {
                "referencia": referencia,
                "area_parcela_m2": area_parcela_m2,
                "urbanismo": True,
                "detalle": {},
                "analisis_avanzado": {
                    "superficie_parcela": {
                        "valor": round(area_parcela_m2, 2),
                        "unidad": "m²",
                        "valor_ha": round(area_parcela_m2 / 10000, 4),
                    },
                    "zonas_afectadas": [],
                    "parametros_urbanisticos": {},
                    "afecciones_detectadas": [],
                    "recomendaciones": [],
                },
            }

            # Buscar capas de planeamiento disponibles
            from config.paths import CAPAS_DIR

            capas_urbanisticas = []
            extensiones = [".geojson", ".shp", ".gml"]

            # Buscar capas con nombres que sugieren planeamiento
            for ext in extensiones:
                for file_path in CAPAS_DIR.glob(f"*{ext}"):
                    nombre = file_path.stem.lower()
                    if any(
                        palabra in nombre
                        for palabra in [
                            "planeamiento",
                            "urbanismo",
                            "suelo",
                            "clasificacion",
                            "plu",
                            "pgou",
                            "urbanizable",
                            "rustico",
                            "urbano",
                            "iepf",
                            "cmup",
                            "poligono",
                            "sector",
                            "zona",
                        ]
                    ):
                        capas_urbanisticas.append(file_path)

            # Si no hay capas específicas, usar todas las capas disponibles
            if not capas_urbanisticas:
                logger.info(
                    "No se encontraron capas urbanísticas específicas, usando capas disponibles"
                )
                for ext in extensiones:
                    for file_path in CAPAS_DIR.glob(f"*{ext}"):
                        nombre = file_path.stem.lower()
                        if not any(
                            palabra in nombre
                            for palabra in ["puntos", "amojonamiento", "limite", "lineas"]
                        ):
                            capas_urbanisticas.append(file_path)

            if not capas_urbanisticas:
                logger.warning("No se encontraron capas para análisis urbanístico")
                resultados["mensaje"] = "No hay capas disponibles para análisis"
                return resultados

            # Analizar contra cada capa urbanística encontrada
            for capa_path in capas_urbanisticas:
                try:
                    logger.info(
                        f"Analizando contra capa urbanística: {capa_path.name}"
                    )

                    try:
                        gdf_capa = gpd.read_file(capa_path)
                    except Exception as e:
                        logger.warning(f"Error cargando {capa_path.name}: {e}")
                        continue

                    if gdf_capa.empty:
                        logger.warning(f"Capa vacía: {capa_path.name}")
                        continue

                    if gdf_capa.geometry.isna().all():
                        logger.warning(f"Capa sin geometría válida: {capa_path.name}")
                        continue

                    try:
                        if gdf_capa.crs:
                            gdf_capa = gdf_capa.to_crs(epsg=25830)
                        else:
                            gdf_capa = gdf_capa.set_crs(epsg=25830)
                    except Exception as e:
                        logger.warning(f"Error reproyectando {capa_path.name}: {e}")
                        continue

                    try:
                        areas_m2, porcentajes = self.calcular_porcentajes(
                            gdf_parcela, gdf_capa
                        )
                    except Exception as e:
                        logger.warning(
                            f"Error calculando porcentajes para {capa_path.name}: {e}"
                        )
                        continue

                    if areas_m2:
                        # Agregar a resultados
                        for tipo, area in areas_m2.items():
                            clave = f"{capa_path.stem} - {tipo}"
                            resultados["detalle"][clave] = porcentajes.get(tipo, 0)

                        # Agregar zona afectada
                        resultados["analisis_avanzado"]["zonas_afectadas"].append(
                            {
                                "capa": capa_path.stem,
                                "elementos": len(gdf_capa),
                                "tipos_encontrados": list(areas_m2.keys()),
                            }
                        )

                        logger.info(
                            f"Análisis completado para {capa_path.name}: {len(areas_m2)} tipos"
                        )
                    else:
                        logger.info(f"No hay intersección con {capa_path.name}")

                except Exception as e:
                    logger.warning(f"Error analizando capa {capa_path.name}: {e}")
                    continue

            # Calcular parámetros urbanísticos genéricos
            if resultados["detalle"]:
                superficie_ha = area_parcela_m2 / 10000
                if superficie_ha > 0:
                    resultados["analisis_avanzado"]["parametros_urbanisticos"] = {
                        "coeficiente_ocupacion": {
                            "valor": 0.5,
                            "nota": "50% (valor genérico)",
                        },
                        "edificabilidad": {
                            "valor": round(superficie_ha * 1.5, 2),
                            "nota": "1.5 m²/m² (valor genérico)",
                        },
                        "altura_maxima": {"valor": 12, "nota": "12 metros (valor genérico)"},
                    }

            # Generar recomendaciones
            if resultados["detalle"]:
                resultados["analisis_avanzado"]["recomendaciones"] = [
                    "Consultar el Plan General de Ordenación Urbana vigente.",
                    "Verificar correspondencia con el registro de la propiedad.",
                    "Confirmar parámetros con el ayuntamiento.",
                    "Este análisis tiene carácter informativo.",
                ]

            logger.info(f"Análisis urbanístico completado para {referencia}")
            return resultados

        except Exception as e:
            logger.error(f"Error en análisis urbanístico: {e}")
            return self._resultados_vacios(referencia, str(e))

    def _guardar_resultados_textuales(
        self,
        txt_path: Path,
        csv_path: Path,
        referencia: str,
        timestamp: str,
        areas_m2: Dict[str, float],
        porcentajes: Dict[str, float],
    ):
        """Guarda resultados en formatos TXT y CSV"""
        # Guardar TXT
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"Resultados para {referencia} ({timestamp}):\n")
            f.write(f"Área total afectada: {sum(areas_m2.values()):.2f} m²\n")
            f.write("-" * 50 + "\n")
            for tipo, pct in porcentajes.items():
                area = areas_m2.get(tipo, 0)
                f.write(f"{tipo}: {area:.2f} m² ({pct:.2f}%)\n")

        # Guardar CSV
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("Clase,Area_m2,Porcentaje\n")
            for tipo in areas_m2.keys():
                f.write(f'"{tipo}",{areas_m2[tipo]:.2f},{porcentajes[tipo]:.2f}\n')

    def _limpiar_temporales(self, temp_files: List[Optional[str]]):
        """Limpia archivos temporales"""
        for temp_file in temp_files:
            if temp_file and Path(temp_file).exists():
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"No se pudo eliminar temporal {temp_file}: {e}")

    def _resultados_vacios(self, referencia: str, mensaje: str) -> Dict[str, any]:
        """Genera resultados vacíos en caso de error"""
        return {
            "referencia": referencia,
            "area_parcela_m2": 0.0,
            "urbanismo": False,
            "detalle": {},
            "mensaje": mensaje,
        }

    def procesar_lote(self, geojson_dir: str) -> List[ResultadosUrbanismo]:
        """
        Procesa todos los GeoJSON de un directorio

        Args:
            geojson_dir: Directorio con archivos GeoJSON

        Returns:
            Lista de resultados para todas las parcelas
        """
        geojson_dir = Path(geojson_dir)

        if not geojson_dir.exists():
            raise FileNotFoundError(f"No existe el directorio: {geojson_dir}")

        geojson_files = list(geojson_dir.glob("*.geojson"))

        if not geojson_files:
            logger.warning(f"No se encontraron archivos GeoJSON en: {geojson_dir}")
            return []

        logger.info(f"Procesando {len(geojson_files)} parcelas...")

        resultados = []
        for geojson_path in geojson_files:
            try:
                resultado = self.procesar_parcela(str(geojson_path))
                resultados.append(resultado)
            except Exception as e:
                logger.error(f"Error procesando {geojson_path.name}: {e}")
                continue

        logger.info(f"Completado. {len(resultados)} parcelas procesadas exitosamente")
        return resultados

    def limpiar_cache(self):
        """Limpia caché de descargas"""
        self._wfs_cache.clear()
        self._wms_cache.clear()
        logger.info("Caché limpiado")

    # ============================================================================
    # NUEVOS MÉTODOS: Exportación a PDF y CSV con reportlab
    # ============================================================================

    def generar_pdf_resultados(self, resultados: Dict, output_path: str) -> str:
        """
        Genera PDF profesional con resultados del análisis urbanístico

        Args:
            resultados: Diccionario con resultados del análisis
            output_path: Ruta donde guardar el PDF

        Returns:
            Ruta al PDF generado
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import (
                SimpleDocTemplate,
                Table,
                TableStyle,
                Paragraph,
                Spacer,
            )
            from reportlab.lib.units import inch
            from reportlab.lib.enums import TA_CENTER

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=letter,
                rightMargin=0.75 * inch,
                leftMargin=0.75 * inch,
                topMargin=0.75 * inch,
                bottomMargin=0.75 * inch,
            )

            story = []
            styles = getSampleStyleSheet()

            # Estilo de título personalizado
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=18,
                textColor=colors.HexColor("#2E5090"),
                spaceAfter=12,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            )

            heading_style = ParagraphStyle(
                "CustomHeading",
                parent=styles["Heading2"],
                fontSize=13,
                textColor=colors.HexColor("#2E5090"),
                spaceAfter=10,
                spaceBefore=10,
                fontName="Helvetica-Bold",
            )

            # Título
            story.append(
                Paragraph(
                    f"Análisis Urbanístico - {resultados.get('referencia', 'N/A')}",
                    title_style,
                )
            )
            story.append(Spacer(1, 0.3 * inch))

            # Información General
            story.append(Paragraph("Información General", heading_style))

            info_data = [
                ["Campo", "Valor"],
                ["Referencia Catastral", resultados.get("referencia", "N/A")],
                ["Fecha Análisis", resultados.get("timestamp", "N/A")],
                [
                    "Área Total (m²)",
                    f"{resultados.get('area_total_m2', resultados.get('area_parcela_m2', 0)):.2f}",
                ],
            ]

            info_table = Table(info_data, colWidths=[2.5 * inch, 3 * inch])
            info_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E5090")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 11),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#F5F5F5")],
                        ),
                    ]
                )
            )
            story.append(info_table)
            story.append(Spacer(1, 0.3 * inch))

            # Distribución por Clase de Suelo
            story.append(Paragraph("Distribución por Clase de Suelo", heading_style))

            porcentajes = resultados.get("porcentajes", resultados.get("detalle", {}))
            areas = resultados.get("areas_m2", {})

            if porcentajes:
                pct_data = [["Clase de Suelo", "Área (m²)", "Porcentaje (%)"]]

                items_ordenados = sorted(
                    porcentajes.items(), key=lambda x: x[1], reverse=True
                )

                for clase, pct in items_ordenados:
                    area = areas.get(clase, 0)
                    pct_data.append([clase, f"{area:.2f}", f"{pct:.2f}%"])

                pct_table = Table(pct_data, colWidths=[3 * inch, 1.75 * inch, 1.75 * inch])
                pct_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E5090")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                            ("ALIGN", (0, 0), (0, -1), "LEFT"),
                            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                            (
                                "ROWBACKGROUNDS",
                                (0, 1),
                                (-1, -1),
                                [colors.white, colors.HexColor("#F5F5F5")],
                            ),
                        ]
                    )
                )
                story.append(pct_table)

            story.append(Spacer(1, 0.3 * inch))

            # Análisis Avanzado si existe
            if "analisis_avanzado" in resultados:
                adv = resultados["analisis_avanzado"]

                if adv.get("recomendaciones"):
                    story.append(Paragraph("Recomendaciones", heading_style))
                    for rec in adv["recomendaciones"]:
                        story.append(Paragraph(f"• {rec}", styles["Normal"]))
                    story.append(Spacer(1, 0.2 * inch))

                if adv.get("zonas_afectadas"):
                    story.append(Paragraph("Zonas Afectadas", heading_style))
                    for zona in adv["zonas_afectadas"]:
                        if "capa" in zona:
                            story.append(
                                Paragraph(
                                    f"• {zona.get('capa', 'N/A')}: {zona.get('elementos', 0)} elementos",
                                    styles["Normal"],
                                )
                            )
                    story.append(Spacer(1, 0.2 * inch))

            # Pie de página
            story.append(Spacer(1, 0.3 * inch))
            footer_text = f"Generado por Suite Tasación | {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            story.append(Paragraph(footer_text, styles["Normal"]))

            doc.build(story)

            logger.info(f"PDF generado exitosamente: {output_path}")
            return str(output_path)

        except ImportError:
            logger.error(
                "reportlab no instalado. Instala con: pip install reportlab"
            )
            raise
        except Exception as e:
            logger.error(f"Error generando PDF: {e}")
            raise

    def generar_csv_resultados(self, resultados: Dict, output_path: str) -> str:
        """
        Genera CSV con resultados del análisis

        Args:
            resultados: Diccionario con resultados
            output_path: Ruta donde guardar el CSV

        Returns:
            Ruta al CSV generado
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                writer.writerow(["Referencia", "Clase_Suelo", "Area_m2", "Porcentaje", "Fecha"])

                referencia = resultados.get("referencia", "N/A")
                timestamp = resultados.get("timestamp", "N/A")
                porcentajes = resultados.get("porcentajes", resultados.get("detalle", {}))
                areas = resultados.get("areas_m2", {})

                for clase, pct in porcentajes.items():
                    area = areas.get(clase, 0)
                    writer.writerow([referencia, clase, f"{area:.2f}", f"{pct:.2f}", timestamp])

            logger.info(f"CSV generado: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Error generando CSV: {e}")
            raise


# Función de compatibilidad con el código original
def procesar_parcelas_legacy(
    geojson_dir: str, resultados_dir: str, encuadre_factor: float = 4.0
):
    """
    Función legacy para compatibilidad con el código original
    """
    analizador = AnalisisUrbano(encuadre_factor=encuadre_factor)
    return analizador.procesar_lote(geojson_dir)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    script_dir = Path(__file__).parent
    geojson_dir = script_dir / "GEOJSONs"
    resultados_dir = script_dir / "RESULTADOS-MAPAS"

    geojson_dir.mkdir(exist_ok=True)
    resultados_dir.mkdir(exist_ok=True)

    geojson_files = list(geojson_dir.glob("*.geojson"))

    if not geojson_files:
        print(f"❌ No se encontraron archivos GeoJSON en: {geojson_dir}")
        print("💡 Coloca tus archivos GeoJSON en la carpeta 'GEOJSONs'")
        sys.exit(1)

    print(f"📁 Encontrados {len(geojson_files)} archivos GeoJSON")
    print(f"📂 Directorio de salida: {resultados_dir}")

    try:
        analizador = AnalisisUrbano(output_dir=str(resultados_dir))
        resultados = analizador.procesar_lote(str(geojson_dir))

        if resultados:
            print(f"\n✅ Proceso completado exitosamente")
            print(f"📊 {len(resultados)} parcelas procesadas")
            print(f"📁 Resultados guardados en: {resultados_dir}")

            print("\n📋 Resumen de resultados:")
            for resultado in resultados:
                print(
                    f"  • {resultado.referencia}: {resultado.area_total_m2:.2f} m² afectados"
                )
        else:
            print("⚠️ No se procesó ninguna parcela exitosamente")

    except KeyboardInterrupt:
        print("\n⏹️ Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error durante el procesamiento: {e}")
        logger.exception("Error detallado:")
        sys.exit(1)
