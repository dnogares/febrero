import os
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
import geopandas as gpd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

class MotorUrbanisticoHibrido:
    def __init__(self, data_dir: str = "/app/data", output_dir: str = "/app/outputs"):
        self.base_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Extensiones soportadas
        self.extensions = ["fgb", "gpkg", "shp", "geojson"]
        
        # Configuración PostGIS
        self.db_url = os.getenv("DATABASE_URL")
        self.engine = create_engine(self.db_url) if self.db_url else None

    def check_connection(self) -> Dict:
        """Verifica la conexión a la base de datos"""
        if not self.engine:
            return {"connected": False, "message": "No configurado (DATABASE_URL no encontrada)"}
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT version()")).fetchone()
                return {"connected": True, "version": str(result[0])}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def obtener_capa(self, nombre: str, es_referencia: bool = False) -> Optional[gpd.GeoDataFrame]:
        """Busca en FGB -> GPKG -> SHP -> PostGIS"""
        # 1. Archivos Locales
        # Buscar en raíz y subcarpetas por extensión
        search_dirs = [self.base_dir] + [self.base_dir / ext for ext in self.extensions]
        
        for folder in search_dirs:
            if not folder.exists(): continue
            
            for ext in self.extensions:
                patron = f"*{nombre}*.{ext}" if es_referencia else f"{nombre}.{ext}"
                archivos = list(folder.glob(patron))
                if archivos:
                    logger.info(f"💾 Cargando {ext.upper()} local: {archivos[0].name}")
                    return gpd.read_file(archivos[0])

        # 2. PostGIS (Ready)
        if self.engine:
            try:
                table = "parcelas" if es_referencia else nombre
                where = f"WHERE ref_catastral = '{nombre}'" if es_referencia else ""
                return gpd.read_postgis(f"SELECT * FROM {table} {where}", self.engine, geom_col='geom')
            except Exception as e:
                logger.warning(f"⚠️ Error PostGIS: {e}")

        return None

    def ejecutar_analisis(self, referencia: str):
        """Proceso completo: Carga, Intersección y Reporte"""
        gdf_parcela = self.obtener_capa(referencia, es_referencia=True)
        gdf_urbanismo = self.obtener_capa("planeamiento") # Nombre de tu capa base

        if gdf_parcela is None or gdf_urbanismo is None:
            return {"status": "error", "message": "Datos no encontrados"}

        try:
            # 1. Proyección a métrico (EPSG:25830)
            p = gdf_parcela.to_crs(epsg=25830)
            u = gdf_urbanismo.to_crs(epsg=25830)

            # 2. Intersección
            inter = gpd.overlay(u, p, how="intersection")
            inter["area_m2"] = inter.geometry.area
            
            # 3. Resumen
            resumen = inter.groupby(inter.columns[0])["area_m2"].sum().to_dict()
            total_m2 = p.geometry.area.sum()
            porcentajes = {k: (v/total_m2)*100 for k, v in resumen.items()}

            # 4. Generar Informe PNG
            ruta_png = self.output_dir / f"informe_{referencia}.png"
            self._crear_png_hibrido(p, inter, resumen, porcentajes, str(ruta_png))

            return {
                "status": "success",
                "referencia": referencia,
                "superficie_total": round(total_m2, 2),
                "resultados": resumen,
                "porcentajes": porcentajes,
                "mapa_url": str(ruta_png)
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _crear_png_hibrido(self, p, inter, res, porc, path):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
        p.plot(ax=ax1, facecolor="none", edgecolor="black", lw=2)
        if not inter.empty:
            inter.plot(ax=ax1, column=inter.columns[0], cmap='Set3', alpha=0.7, legend=True)
        ax1.axis('off')
        ax1.set_title("Mapa de Afecciones")

        datos = [[k, f"{v:,.2f} m²", f"{porc[k]:.1f}%"] for k, v in res.items()]
        ax2.axis('off')
        ax2.table(cellText=datos, colLabels=["Zona", "Área", "%"], loc='center').scale(1, 2)
        
        plt.savefig(path, dpi=200, bbox_inches='tight')
        plt.close(fig)