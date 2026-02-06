#!/usr/bin/env python3
"""
catastro/lote_manager.py
Gestor de procesamiento de lotes de referencias catastrales
"""

import json
import time
import csv
import zipfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class LoteManager:
    """
    Gestiona el procesamiento de múltiples referencias catastrales
    Mantiene estado y genera reportes de progreso
    """
    
    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Estado de lotes
        self.lotes_dir = self.output_dir / "_lotes"
        self.lotes_dir.mkdir(exist_ok=True)
        
        self.lote_id = None
        self.estado_actual = {}
    
    def generar_lote_id(self) -> str:
        """Genera ID único para el lote"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"lote_{timestamp}"
    
    def guardar_estado(self, lote_id: str, estado: dict):
        """Guarda estado del lote en archivo JSON"""
        try:
            estado_path = self.lotes_dir / f"{lote_id}_estado.json"
            with open(estado_path, 'w', encoding='utf-8') as f:
                json.dump(estado, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando estado: {e}")
    
    def obtener_estado(self, lote_id: str) -> Optional[dict]:
        """Recupera estado de un lote"""
        try:
            estado_path = self.lotes_dir / f"{lote_id}_estado.json"
            if estado_path.exists():
                with open(estado_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error leyendo estado: {e}")
        return None
    
    def procesar_lista(
        self, 
        referencias: List[str], 
        downloader, 
        analyzer=None, 
        pdf_gen=None,
        lote_id: str = None
    ) -> Dict:
        """
        Procesa una lista de referencias catastrales
        
        Args:
            referencias: Lista de referencias a procesar
            downloader: Instancia de CatastroDownloader
            analyzer: Instancia de VectorAnalyzer (opcional)
            pdf_gen: Instancia de AfeccionesPDF (opcional)
            lote_id: ID del lote pre-generado (opcional)
        
        Returns:
            dict: Resumen del procesamiento
        """
        if lote_id:
            self.lote_id = lote_id
        else:
            self.lote_id = self.generar_lote_id()
            
        logger.info(f"📦 Iniciando lote: {self.lote_id}")
        
        total = len(referencias)
        resultados = {
            "lote_id": self.lote_id,
            "fecha_inicio": datetime.now().isoformat(),
            "total_referencias": total,
            "procesadas": 0,
            "exitosas": 0,
            "fallidas": 0,
            "referencias": {}
        }
        
        # Guardar estado inicial
        self.guardar_estado(self.lote_id, resultados)
        
        for idx, ref in enumerate(referencias, 1):
            ref_limpia = ref.replace(' ', '').strip().upper()
            logger.info(f"\n[{idx}/{total}] Procesando: {ref_limpia}")
            
            resultado_ref = {
                "referencia": ref_limpia,
                "estado": "procesando",
                "inicio": datetime.now().isoformat(),
                "archivos": {}
            }
            
            try:
                # 1. Descargar datos catastrales
                logger.info("  📥 Descargando datos...")
                exito, zip_path = downloader.descargar_todo_completo(ref_limpia)
                
                if exito:
                    resultado_ref["estado"] = "exitoso"
                    resultado_ref["zip"] = str(zip_path) if zip_path else None
                    
                    # Recopilar archivos generados
                    ref_dir = self.output_dir / ref_limpia
                    resultado_ref["archivos"] = self._recopilar_archivos(ref_dir)
                    
                    # 2. Análisis de afecciones (DEACTIVADO por defecto)
                    # Desactivado para mejorar rendimiento en lotes grandes
                    # Para activar, cambiar ANALISIS_AFECCIONES_ACTIVO = True
                    ANALISIS_AFECCIONES_ACTIVO = False
                    
                    if ANALISIS_AFECCIONES_ACTIVO and analyzer:
                        logger.info("  🔍 Analizando afecciones...")
                        try:
                            gml_path = ref_dir / "gml" / f"{ref_limpia}_parcela.gml"
                            if gml_path.exists():
                                afecciones = analyzer.analizar(
                                    gml_path,
                                    "afecciones_totales.gpkg",
                                    "tipo"
                                )
                                resultado_ref["afecciones"] = afecciones
                                logger.info("    ✅ Afecciones analizadas")
                        except Exception as e:
                            logger.warning(f"    ⚠️ Error analizando afecciones: {e}")
                    else:
                        logger.info(f"  📋 Análisis de afecciones desactivado para {ref_limpia}")
                        resultado_ref["afecciones"] = {
                            "detalle": {},
                            "total": 0.0,
                            "area_total_m2": 0.0,
                            "afecciones_detectadas": False,
                            "mensaje": "Análisis de afecciones desactivado. Use el panel 'Análisis Afecciones' para análisis manual."
                        }
                    
                    # 3. Generar PDF (si está disponible)
                    if pdf_gen and analyzer:
                        logger.info("  📄 Generando PDF...")
                        try:
                            mapas = []
                            images_dir = ref_dir / "images"
                            if images_dir.exists():
                                for img in images_dir.glob(f"{ref_limpia}*zoom4*.png"):
                                    mapas.append(str(img))
                                    break
                            
                            afecciones = resultado_ref.get("afecciones", {})
                            
                            pdf_path = pdf_gen.generar(
                                referencia=ref_limpia,
                                resultados=afecciones,
                                mapas=mapas,
                                incluir_tabla=bool(afecciones)
                            )
                            
                            if pdf_path:
                                resultado_ref["archivos"]["pdf_informe"] = str(pdf_path)
                                logger.info("    ✅ PDF generado")
                        except Exception as e:
                            logger.warning(f"    ⚠️ Error generando PDF: {e}")
                    
                    resultados["exitosas"] += 1
                    logger.info(f"  ✅ {ref_limpia} completado")
                    
                else:
                    resultado_ref["estado"] = "error"
                    resultado_ref["error"] = "No se pudieron descargar los datos"
                    resultados["fallidas"] += 1
                    logger.error(f"  ❌ {ref_limpia} falló")
                
            except Exception as e:
                resultado_ref["estado"] = "error"
                resultado_ref["error"] = str(e)
                resultados["fallidas"] += 1
                logger.error(f"  ❌ Error en {ref_limpia}: {e}")
            
            finally:
                resultado_ref["fin"] = datetime.now().isoformat()
                resultados["referencias"][ref_limpia] = resultado_ref
                resultados["procesadas"] += 1
                
                # Actualizar estado
                self.guardar_estado(self.lote_id, resultados)
                
                # Generar resumen HTML actualizado en tiempo real
                self._generar_resumen_html(resultados)
                self._generar_resumen_csv(resultados)
                
                # Pausa entre referencias
                if idx < total:
                    time.sleep(1)
        
        # Estado final
        resultados["fecha_fin"] = datetime.now().isoformat()
        resultados["estado"] = "completado"
        self.guardar_estado(self.lote_id, resultados)
        
        # Generar resumen
        self._generar_resumen_html(resultados)
        self._generar_resumen_csv(resultados)
        self._generar_mapa_global(resultados)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 LOTE COMPLETADO: {self.lote_id}")
        logger.info(f"{'='*70}")
        logger.info(f"  ✅ Exitosas: {resultados['exitosas']}/{total}")
        logger.info(f"  ❌ Fallidas: {resultados['fallidas']}/{total}")
        logger.info(f"{'='*70}\n")
        
        return resultados
    
    def empaquetar_lote(self, lote_id: str) -> Optional[Path]:
        """Empaqueta todos los resultados de un lote en un único ZIP"""
        try:
            estado = self.obtener_estado(lote_id)
            if not estado:
                return None
            
            # Asegurar que existen los resúmenes actualizados
            self._generar_resumen_html(estado)
            self._generar_resumen_csv(estado)
            self._generar_mapa_global(estado)
            
            zip_filename = self.lotes_dir / f"{lote_id}_full.zip"
            
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 1. Incluir resumen HTML
                resumen_html = self.lotes_dir / f"{lote_id}_resumen.html"
                if resumen_html.exists():
                    zipf.write(resumen_html, arcname=f"Resumen_{lote_id}.html")
                
                # 2. Incluir resumen CSV
                resumen_csv = self.lotes_dir / f"{lote_id}_resumen.csv"
                if resumen_csv.exists():
                    zipf.write(resumen_csv, arcname=f"Resumen_{lote_id}.csv")
                
                # 3. Incluir Mapa Global
                mapa_global = self.lotes_dir / f"{lote_id}_mapa_global.png"
                if mapa_global.exists():
                    zipf.write(mapa_global, arcname=f"Mapa_Global_{lote_id}.png")
                
                # 4. Organizar archivos por carpetas de tipo (GML, PDF, Imagenes)
                referencias = estado.get("referencias", {})
                for ref, info in referencias.items():
                    if info.get("estado") != "exitoso":
                        continue
                        
                    ref_limpia = info.get("referencia", ref)
                    ref_dir = self.output_dir / ref_limpia
                    
                    if not ref_dir.exists():
                        continue
                        
                    # Recorrer todos los archivos de la referencia
                    for file_path in ref_dir.rglob("*"):
                        if not file_path.is_file():
                            continue
                            
                        filename = file_path.name
                        filename_lower = filename.lower()
                        arcname = None
                        
                        # GML / KML
                        if filename_lower.endswith((".gml", ".kml")):
                            arcname = f"GML/{filename}"
                            
                        # PDF
                        elif filename_lower.endswith(".pdf"):
                            arcname = f"PDF/{filename}"
                            
                        # Imágenes: SOLO con contorno o plano perfecto
                        elif filename_lower.endswith((".jpg", ".jpeg", ".png")):
                            # Filtro estricto: solo contorno o plano perfecto
                            if "contorno" in filename_lower or "plano_perfecto" in filename_lower:
                                arcname = f"Imagenes/{filename}"
                            # Ignorar el resto de imágenes (originales sin contorno)
                        
                        # Agregar al ZIP si corresponde
                        if arcname:
                            zipf.write(file_path, arcname=arcname)
            
            logger.info(f"📦 ZIP de lote generado: {zip_filename}")
            return zip_filename
            
        except Exception as e:
            logger.error(f"Error empaquetando lote {lote_id}: {e}")
            return None

    def regenerar_resumen(self, lote_id: str):
        """Regenera los archivos de resumen (HTML y CSV) desde el estado guardado"""
        estado = self.obtener_estado(lote_id)
        if estado:
            self._generar_resumen_html(estado)
            self._generar_resumen_csv(estado)
            self._generar_mapa_global(estado)
            return True
        return False

    def _recopilar_archivos(self, ref_dir: Path) -> Dict:
        """Recopila información de archivos generados"""
        archivos = {
            "gml_parcela": None,
            "gml_edificio": None,
            "ficha_catastral": None,
            "imagenes": [],
            "json": [],
            "html": []
        }
        
        if not ref_dir.exists():
            return archivos
        
        # GML
        gml_dir = ref_dir / "gml"
        if gml_dir.exists():
            for gml in gml_dir.glob("*.gml"):
                if "parcela" in gml.name:
                    archivos["gml_parcela"] = str(gml)
                elif "edificio" in gml.name:
                    archivos["gml_edificio"] = str(gml)
        
        # PDFs
        pdf_dir = ref_dir / "pdf"
        if pdf_dir.exists():
            for pdf in pdf_dir.glob("*.pdf"):
                if "ficha_catastral" in pdf.name:
                    archivos["ficha_catastral"] = str(pdf)
        
        # Imágenes
        images_dir = ref_dir / "images"
        if images_dir.exists():
            archivos["imagenes"] = [str(img) for img in images_dir.glob("*.png")]
        
        # JSON
        json_dir = ref_dir / "json"
        if json_dir.exists():
            archivos["json"] = [str(j) for j in json_dir.glob("*.json")]
        
        # HTML
        html_dir = ref_dir / "html"
        if html_dir.exists():
            archivos["html"] = [str(h) for h in html_dir.glob("*.html")]
        
        return archivos
    
    def _generar_resumen_csv(self, resultados: Dict):
        """Genera resumen CSV del lote con datos clave de todas las parcelas"""
        try:
            lote_id = resultados.get("lote_id", "unknown")
            csv_path = self.lotes_dir / f"{lote_id}_resumen.csv"
            
            # Definir columnas del CSV
            fieldnames = [
                "referencia", "estado", "fecha_inicio", "fecha_fin", 
                "error", "num_archivos", "afecciones_detectadas", 
                "area_parcela_m2", "porcentaje_afeccion",
                "suelo_urbano_pct", "edificabilidad", "clasificacion_principal"
            ]
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                referencias = resultados.get("referencias", {})
                for ref, datos in referencias.items():
                    # Calcular número de archivos generados
                    archivos = datos.get("archivos", {})
                    num_archivos = 0
                    if archivos:
                        num_archivos = sum([
                            1 if archivos.get("gml_parcela") else 0,
                            1 if archivos.get("ficha_catastral") else 0,
                            len(archivos.get("imagenes", [])),
                            len(archivos.get("json", []))
                        ])
                    
                    # Datos de afecciones (si existen)
                    afecciones = datos.get("afecciones", {})
                    if not isinstance(afecciones, dict): afecciones = {}

                    # Extraer datos urbanísticos (Suelo Urbano y Edificabilidad)
                    detalle = afecciones.get("detalle", {})
                    suelo_urbano_pct = 0.0
                    clasificacion_principal = ""
                    max_pct = -1.0

                    for k, v in detalle.items():
                        try:
                            val = float(v)
                            # Sumar porcentaje si es Urbano (excluyendo No Urbano)
                            if "urbano" in k.lower() and "no" not in k.lower():
                                suelo_urbano_pct += val
                            # Detectar clasificación mayoritaria
                            if val > max_pct:
                                max_pct = val
                                clasificacion_principal = k
                        except (ValueError, TypeError):
                            continue

                    # Extraer Edificabilidad de parámetros urbanísticos
                    avanzado = afecciones.get("analisis_avanzado", {})
                    params = avanzado.get("parametros_urbanisticos", {})
                    edificabilidad = params.get("edificabilidad", {}).get("valor", "") if params else ""

                    row = {
                        "referencia": ref,
                        "estado": datos.get("estado", "desconocido"),
                        "fecha_inicio": datos.get("inicio", ""),
                        "fecha_fin": datos.get("fin", ""),
                        "error": datos.get("error", ""),
                        "num_archivos": num_archivos,
                        "afecciones_detectadas": "Sí" if afecciones.get("afecciones_detectadas") else "No",
                        "area_parcela_m2": afecciones.get("area_total_m2", 0.0),
                        "porcentaje_afeccion": afecciones.get("total", 0.0),
                        "suelo_urbano_pct": round(suelo_urbano_pct, 2),
                        "edificabilidad": edificabilidad,
                        "clasificacion_principal": clasificacion_principal
                    }
                    writer.writerow(row)
            
            logger.info(f"📄 Resumen CSV generado: {csv_path}")
            
        except Exception as e:
            logger.error(f"Error generando resumen CSV: {e}")

    def _generar_mapa_global(self, resultados: Dict):
        """Genera un mapa global visualizando todas las parcelas juntas sobre PNOA"""
        try:
            # Importaciones locales para evitar dependencias circulares si no se usan
            import geopandas as gpd
            import pandas as pd
            import matplotlib
            matplotlib.use('Agg') # Usar backend no interactivo
            import matplotlib.pyplot as plt
            import contextily as cx
            
            lote_id = resultados.get("lote_id")
            if not lote_id: return None
            
            referencias = resultados.get("referencias", {})
            gdfs = []
            
            # Recopilar GMLs de parcelas exitosas
            for ref, datos in referencias.items():
                if datos.get("estado") == "exitoso":
                    archivos = datos.get("archivos", {})
                    gml = archivos.get("gml_parcela")
                    if gml and Path(gml).exists():
                        try:
                            df = gpd.read_file(gml)
                            if df.crs is None: df.set_crs(epsg=4326, inplace=True)
                            # Añadir referencia para etiquetado
                            df['ref_label'] = ref
                            gdfs.append(df)
                        except: continue
            
            if not gdfs: return None
                
            gdf_total = pd.concat(gdfs, ignore_index=True)
            # Reproyectar a Web Mercator para mapa base
            gdf_total = gdf_total.to_crs(epsg=3857)
            
            # Configurar figura
            fig, ax = plt.subplots(figsize=(20, 20))
            
            # Calcular bounds con margen del 10%
            minx, miny, maxx, maxy = gdf_total.total_bounds
            ancho, alto = maxx - minx, maxy - miny
            margen = max(ancho, alto) * 0.1 if max(ancho, alto) > 0 else 100
            ax.set_xlim(minx - margen, maxx + margen)
            ax.set_ylim(miny - margen, maxy + margen)
            
            # Añadir mapa base (PNOA)
            try:
                cx.add_basemap(ax, source=cx.providers.Ign.PNOA_M, attribution=False)
            except:
                try: cx.add_basemap(ax, source=cx.providers.OpenStreetMap.Mapnik)
                except: pass
            
            # Dibujar parcelas (Rojo semitransparente con borde sólido)
            gdf_total.plot(ax=ax, facecolor="red", alpha=0.3, edgecolor="red", linewidth=2)
            
            # Añadir etiquetas con referencia catastral
            for idx, row in gdf_total.iterrows():
                # Usar punto representativo para asegurar que la etiqueta esté dentro o cerca
                pt = row.geometry.representative_point()
                ax.annotate(
                    text=row['ref_label'],
                    xy=(pt.x, pt.y),
                    ha='center', va='center',
                    fontsize=10, fontweight='bold', color='white',
                    bbox=dict(boxstyle="round,pad=0.3", fc="black", alpha=0.6, ec="none")
                )
            
            plt.title(f"Vista Global del Lote: {lote_id} ({len(gdfs)} parcelas)", fontsize=20)
            ax.axis("off")
            
            # Guardar
            mapa_path = self.lotes_dir / f"{lote_id}_mapa_global.png"
            plt.savefig(mapa_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            logger.info(f"🗺️ Mapa global generado: {mapa_path}")
            return mapa_path
            
        except Exception as e:
            logger.error(f"Error generando mapa global: {e}")
            return None

    def _generar_resumen_html(self, resultados: Dict):
        """Genera resumen HTML del lote"""
        try:
            lote_id = resultados["lote_id"]
            html_path = self.lotes_dir / f"{lote_id}_resumen.html"
            
            # Script para auto-recargar la página si el lote sigue procesando
            script_reload = ""
            if resultados.get("estado") != "completado":
                script_reload = """
    <script>
        setTimeout(function() { window.location.reload(); }, 2000);
    </script>"""
            
            html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resumen Lote {lote_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; margin-bottom: 20px; }}
        h1 {{ color: #333; margin: 0; }}
        .btn-download {{ 
            background-color: #2196F3; color: white; padding: 10px 20px; 
            text-decoration: none; border-radius: 5px; font-weight: bold; 
            transition: background 0.3s;
            display: inline-block; cursor: pointer;
        }}
        .btn-download:hover {{ background-color: #1976D2; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat-card {{ flex: 1; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-card.success {{ background: #4CAF50; color: white; }}
        .stat-card.error {{ background: #f44336; color: white; }}
        .stat-card.total {{ background: #2196F3; color: white; }}
        .stat-number {{ font-size: 48px; font-weight: bold; }}
        .stat-label {{ font-size: 14px; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f0f0f0; font-weight: bold; }}
        .exitoso {{ color: #4CAF50; }}
        .error {{ color: #f44336; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
        .badge.success {{ background: #4CAF50; color: white; }}
        .badge.fail {{ background: #f44336; color: white; }}
        .badge.processing {{ background: #FF9800; color: white; }}
    </style>
    {script_reload}
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 Resumen Lote: {lote_id}</h1>
            <a href="/api/v1/lote/{lote_id}/zip" class="btn-download" target="_blank">⬇️ Descargar ZIP Completo</a>
        </div>
        
        <!-- Mapa Global -->
        <div style="margin: 20px 0; text-align: center; background: #fff; padding: 15px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <h2 style="margin-top: 0;">🗺️ Vista Global del Lote</h2>
            <p style="color: #666; font-size: 0.9em;">Visualización conjunta de todas las parcelas procesadas sobre ortofoto PNOA</p>
            <img src="/outputs/_lotes/{lote_id}_mapa_global.png" style="max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #ddd;" onerror="this.style.display='none'">
        </div>

        <div class="stats">
            <div class="stat-card total">
                <div class="stat-number">{resultados['total_referencias']}</div>
                <div class="stat-label">Total Referencias</div>
            </div>
            <div class="stat-card success">
                <div class="stat-number">{resultados['exitosas']}</div>
                <div class="stat-label">Exitosas</div>
            </div>
            <div class="stat-card error">
                <div class="stat-number">{resultados['fallidas']}</div>
                <div class="stat-label">Fallidas</div>
            </div>
        </div>
        
        <h2>Detalle de Referencias</h2>
        <table>
            <thead>
                <tr>
                    <th>Referencia</th>
                    <th>Estado</th>
                    <th>Archivos Generados</th>
                </tr>
            </thead>
            <tbody>
"""
            
            for ref, datos in resultados["referencias"].items():
                if datos["estado"] == "exitoso":
                    estado_badge, estado_texto = "success", "✅ Exitoso"
                elif datos["estado"] == "procesando":
                    estado_badge, estado_texto = "processing", "⏳ Procesando..."
                else:
                    estado_badge, estado_texto = "fail", "❌ Error"
                
                archivos = datos.get("archivos", {})
                num_archivos = sum([
                    1 if archivos.get("gml_parcela") else 0,
                    1 if archivos.get("ficha_catastral") else 0,
                    len(archivos.get("imagenes", [])),
                    len(archivos.get("json", []))
                ])
                
                html += f"""
                <tr>
                    <td><strong>{ref}</strong></td>
                    <td><span class="badge {estado_badge}">{estado_texto}</span></td>
                    <td>{num_archivos} archivos</td>
                </tr>
"""
            
            html += """
            </tbody>
        </table>
        
        <p style="text-align: center; color: #666; margin-top: 40px;">
            Generado automáticamente por Suite Tasación dnogares
        </p>
    </div>
</body>
</html>
"""
            
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            
            logger.info(f"📄 Resumen HTML generado: {html_path}")
            
        except Exception as e:
            logger.error(f"Error generando resumen HTML: {e}")


# Testing
if __name__ == "__main__":
    import sys
    
    # Simulación - sin referencias de prueba
    referencias = []  # Agrega aquí tus referencias reales
    
    manager = LoteManager()
    print(f"📦 Lote ID: {manager.generar_lote_id()}")
    print(f"📁 Directorio lotes: {manager.lotes_dir}")
    
    if referencias:
        print(f"📋 Procesando {len(referencias)} referencias...")
        # Aquí iría el procesamiento real
    else:
        print("📝 No hay referencias configuradas. Agrega tus referencias reales.")