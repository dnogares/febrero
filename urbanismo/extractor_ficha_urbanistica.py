#!/usr/bin/env python3
"""
urbanismo/extractor_ficha_urbanistica.py

Extrae datos de fichas urbanísticas en PDF
Soporta múltiples formatos y plataformas (CARM, SIGPAC, etc)
Integrado con sistema de normativa urbanística
"""

import logging
import re
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DatosFichaUrbanistica:
    """Estructura de datos extraídos de ficha urbanística"""
    municipio: str = ""
    denominacion: str = ""
    clasificacion_suelo: str = ""
    uso_global: str = ""
    uso_dominante: str = ""
    referencias_normativas: List[str] = None
    superficie: Optional[float] = None
    observaciones: str = ""
    otros_datos: Dict = None
    fecha_extraccion: str = ""

    def __post_init__(self):
        if self.referencias_normativas is None:
            self.referencias_normativas = []
        if self.otros_datos is None:
            self.otros_datos = {}
        if not self.fecha_extraccion:
            self.fecha_extraccion = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Convierte a diccionario"""
        return {
            "municipio": self.municipio,
            "denominacion": self.denominacion,
            "clasificacion_suelo": self.clasificacion_suelo,
            "uso_global": self.uso_global,
            "uso_dominante": self.uso_dominante,
            "referencias_normativas": self.referencias_normativas,
            "superficie": self.superficie,
            "observaciones": self.observaciones,
            "otros_datos": self.otros_datos,
            "fecha_extraccion": self.fecha_extraccion,
        }


class ExtractorFichaUrbanistica:
    """Extrae información de fichas urbanísticas en PDF"""

    def __init__(self):
        logger.info("ExtractorFichaUrbanistica inicializado")
        self.patrones = self._configurar_patrones()

    def _configurar_patrones(self) -> Dict[str, str]:
        """Configura patrones de búsqueda para diferentes campos"""
        return {
            "municipio": r"(?:Municipio|MUNICIPIO):\s*([^\n]+)",
            "denominacion": r"(?:Denominación|DENOMINACIÓN):\s*([^\n]+)",
            "clasificacion": r"(?:Clasificación|CLASIFICACIÓN)(?:\s+del\s+Suelo)?:\s*([^\n]+)",
            "uso_global": r"(?:Uso\s+global|USO\s+GLOBAL):\s*([^\n]+)",
            "dominante": r"(?:Dominante|DOMINANTE):\s*([^\n]+)",
            "superficie": r"(?:Superficie|SUPERFICIE):\s*([\d.,]+)\s*(?:m²|m2|hectáreas|ha)",
            "nombre": r"(?:Nombre|NOMBRE):\s*([^\n]+)",
        }

    def extraer_pdf(self, pdf_path: str) -> DatosFichaUrbanistica:
        """
        Extrae datos de PDF de ficha urbanística

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            DatosFichaUrbanistica con datos extraídos
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            logger.error(f"Archivo no encontrado: {pdf_path}")
            return DatosFichaUrbanistica()

        # Intentar con pdfplumber primero
        try:
            import pdfplumber  # type: ignore
            return self._extraer_con_pdfplumber(str(pdf_path))
        except ImportError:
            logger.info("pdfplumber no disponible, intentando PyPDF2")
            try:
                return self._extraer_con_pypdf(str(pdf_path))
            except ImportError:
                logger.warning("No hay librerías de extracción PDF instaladas")
                return DatosFichaUrbanistica()

    def _extraer_con_pdfplumber(self, pdf_path: str) -> DatosFichaUrbanistica:
        """Extracción con pdfplumber (mejor calidad)"""
        try:
            import pdfplumber  # type: ignore

            datos = DatosFichaUrbanistica()
            texto_completo = ""
            tablas_encontradas = []

            with pdfplumber.open(pdf_path) as pdf:
                logger.info(f"Abierto PDF con {len(pdf.pages)} página(s)")

                # Extraer texto de todas las páginas
                for i, page in enumerate(pdf.pages):
                    texto_pagina = page.extract_text()
                    if texto_pagina:
                        texto_completo += texto_pagina + "\n"

                    # Extraer tablas
                    try:
                        tables = page.extract_tables()
                        if tables:
                            tablas_encontradas.extend(tables)
                            logger.debug(
                                f"Página {i+1}: {len(tables)} tabla(s) encontrada(s)"
                            )
                    except Exception as e:
                        logger.debug(
                            f"No se pudieron extraer tablas de página {i+1}: {e}"
                        )

            # Parsear texto extraído
            datos = self._parsear_texto(texto_completo)

            # Procesar tablas si existen
            if tablas_encontradas:
                datos.otros_datos["tablas_encontradas"] = len(tablas_encontradas)
                datos.otros_datos["contenido_tablas"] = self._procesar_tablas(
                    tablas_encontradas
                )

            logger.info(
                f"Datos extraídos: municipio={datos.municipio}, uso={datos.uso_global}"
            )
            return datos

        except Exception as e:
            logger.error(f"Error con pdfplumber: {e}")
            return DatosFichaUrbanistica()

    def _extraer_con_pypdf(self, pdf_path: str) -> DatosFichaUrbanistica:
        """Extracción con PyPDF2 (alternativa)"""
        try:
            from PyPDF2 import PdfReader  # type: ignore

            datos = DatosFichaUrbanistica()
            texto_completo = ""

            reader = PdfReader(pdf_path)
            logger.info(f"PDF con {len(reader.pages)} página(s)")

            for i, page in enumerate(reader.pages):
                texto_pagina = page.extract_text()
                if texto_pagina:
                    texto_completo += texto_pagina + "\n"

            datos = self._parsear_texto(texto_completo)
            logger.info(f"Datos extraídos con PyPDF2: {datos.municipio}")

            return datos

        except Exception as e:
            logger.error(f"Error con PyPDF2: {e}")
            return DatosFichaUrbanistica()

    def _parsear_texto(self, texto: str) -> DatosFichaUrbanistica:
        """Parsea el texto extraído del PDF"""
        datos = DatosFichaUrbanistica()

        # Limpiar texto
        texto = texto.replace("\\n", "\n").strip()

        # Buscar cada campo
        for campo, patron in self.patrones.items():
            match = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)

            if match:
                valor = match.group(1).strip()

                if campo == "municipio":
                    datos.municipio = valor
                elif campo == "denominacion":
                    datos.denominacion = valor
                elif campo == "clasificacion":
                    datos.clasificacion_suelo = valor
                elif campo == "uso_global":
                    datos.uso_global = valor
                elif campo == "dominante":
                    datos.uso_dominante = valor
                elif campo == "superficie":
                    # Convertir a número
                    try:
                        datos.superficie = float(valor.replace(".", "").replace(",", "."))
                    except ValueError:
                        pass
                elif campo == "nombre":
                    if not datos.uso_global:
                        datos.uso_global = valor

        # Extraer referencias normativas (PGOU, modificaciones, artículos, etc.)
        referencias = re.findall(
            r"(?:Revisión\s+PGOU|N[º°]\s*\d+[^\n]*|Modificación[^\n]+|art[ií]culo[^\n]+|nº\s*\d+[^\n]*)",
            texto,
            re.IGNORECASE,
        )
        datos.referencias_normativas = [ref.strip() for ref in referencias[:20] if ref.strip()]

        # Observaciones (últimas líneas)
        lineas = texto.split("\n")
        if len(lineas) > 5:
            datos.observaciones = " ".join(lineas[-5:]).strip()

        return datos

    def _procesar_tablas(self, tablas: List) -> Dict:
        """Procesa tablas extraídas (solo info básica)"""
        contenido = {}
        for i, tabla in enumerate(tablas):
            if tabla:
                contenido[f"tabla_{i+1}"] = {
                    "filas": len(tabla),
                    "columnas": len(tabla[0]) if tabla[0] else 0,
                }
        return contenido

    def exportar_csv(self, datos: DatosFichaUrbanistica, output_path: str) -> str:
        """Exporta datos a CSV (clave/valor)"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)

                # Encabezados
                writer.writerow(["Campo", "Valor"])

                # Datos
                datos_dict = datos.to_dict()
                for key, value in datos_dict.items():
                    if key != "otros_datos":
                        if isinstance(value, list):
                            value = "|".join(str(v) for v in value) if value else ""
                        writer.writerow([key, value])

                # Otros datos en sección aparte si existen
                if datos.otros_datos:
                    writer.writerow([])
                    writer.writerow(["Otros Datos"])
                    for key, value in datos.otros_datos.items():
                        writer.writerow([key, value])

            logger.info(f"CSV exportado: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Error exportando CSV: {e}")
            raise

    def exportar_json(self, datos: DatosFichaUrbanistica, output_path: str) -> str:
        """Exporta datos a JSON"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as jsonfile:
                json.dump(datos.to_dict(), jsonfile, indent=2, ensure_ascii=False)

            logger.info(f"JSON exportado: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Error exportando JSON: {e}")
            raise

    def exportar_html(self, datos: DatosFichaUrbanistica, output_path: str) -> str:
        """Exporta datos a HTML"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ficha Urbanística</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #2E5090; border-bottom: 2px solid #2E5090; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ background-color: #2E5090; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .field-label {{ font-weight: bold; color: #2E5090; width: 200px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Ficha Urbanística</h1>
        <table>
            <tr><td class="field-label">Municipio:</td><td>{datos.municipio}</td></tr>
            <tr><td class="field-label">Denominación:</td><td>{datos.denominacion}</td></tr>
            <tr><td class="field-label">Clasificación del Suelo:</td><td>{datos.clasificacion_suelo}</td></tr>
            <tr><td class="field-label">Uso Global:</td><td>{datos.uso_global}</td></tr>
            <tr><td class="field-label">Uso Dominante:</td><td>{datos.uso_dominante}</td></tr>
            <tr><td class="field-label">Superficie:</td><td>{datos.superficie if datos.superficie else 'N/A'} m²</td></tr>
            <tr><td class="field-label">Fecha de Extracción:</td><td>{datos.fecha_extraccion}</td></tr>
        </table>
        
        <h2>Referencias Normativas</h2>
        <ul>
            {''.join(f'<li>{ref}</li>' for ref in datos.referencias_normativas[:10])}
        </ul>
    </div>
</body>
</html>"""

            with open(output_path, "w", encoding="utf-8") as htmlfile:
                htmlfile.write(html_content)

            logger.info(f"HTML exportado: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"Error exportando HTML: {e}")
            raise

    # ============================================================================
    # INTEGRACIÓN CON SISTEMA DE NORMATIVA
    # ============================================================================

    def enlazar_normativa(self, datos_ficha: DatosFichaUrbanistica, 
                          gestor_normativa) -> Dict:
        """
        Enlaza referencias normativas extraídas con el catálogo

        Args:
            datos_ficha: Datos extraídos de la ficha
            gestor_normativa: Instancia de GestorNormativaUrbanistica

        Returns:
            Diccionario con referencias enlazadas
        """
        if not datos_ficha.referencias_normativas:
            return {'referencias': [], 'total': 0, 'encontradas': 0, 'porcentaje_match': 0}

        try:
            referencias_enlazadas = gestor_normativa.enlazar_referencias(
                datos_ficha.referencias_normativas,
                datos_ficha.municipio
            )

            total = len(referencias_enlazadas)
            encontradas = sum(1 for r in referencias_enlazadas if r['encontrada'])

            return {
                'referencias': referencias_enlazadas,
                'total': total,
                'encontradas': encontradas,
                'porcentaje_match': (encontradas / total * 100) if total > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error enlazando normativa: {e}")
            return {
                'referencias': [],
                'total': 0,
                'encontradas': 0,
                'porcentaje_match': 0,
                'error': str(e)
            }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    extractor = ExtractorFichaUrbanistica()

    # Ejemplo de prueba local
    pdf_in = "ficha-urb-SNUi.pdf"
    
    if Path(pdf_in).exists():
        datos = extractor.extraer_pdf(pdf_in)

        extractor.exportar_csv(datos, "ficha_urbanistica.csv")
        extractor.exportar_json(datos, "ficha_urbanistica.json")
        extractor.exportar_html(datos, "ficha_urbanistica.html")

        print("\n" + "="*60)
        print("DATOS EXTRAÍDOS")
        print("="*60)
        print(f"Municipio: {datos.municipio}")
        print(f"Clasificación: {datos.clasificacion_suelo}")
        print(f"Uso global: {datos.uso_global}")
        print(f"Uso dominante: {datos.uso_dominante}")
        print(f"\nReferencias normativas ({len(datos.referencias_normativas)}):")
        for i, ref in enumerate(datos.referencias_normativas, 1):
            print(f"  {i}. {ref}")
        print("="*60)
    else:
        print(f"⚠️ Archivo no encontrado: {pdf_in}")
