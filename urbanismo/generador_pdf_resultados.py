#!/usr/bin/env python3
"""
Generador de PDF para resultados urbanísticos
"""

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import logging

logger = logging.getLogger(__name__)

class GeneradorPDFResultados:
    """Genera PDFs con resultados urbanísticos"""
    
    def generar_pdf_ficha_urbanistica(self, datos_ficha: dict, output_path: str):
        """Genera el PDF de la ficha urbanística"""
        try:
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()
            
            # Título
            story.append(Paragraph(f"Ficha Urbanística: {datos_ficha.get('referencia', 'N/A')}", styles['Title']))
            story.append(Spacer(1, 12))
            
            # Tabla de datos básicos
            data = [
                ["Municipio", datos_ficha.get('municipio', '')],
                ["Clasificación", datos_ficha.get('clasificacion_suelo', '')],
                ["Uso Global", datos_ficha.get('uso_global', '')],
                ["Superficie", str(datos_ficha.get('superficie', ''))],
                ["Uso Dominante", datos_ficha.get('uso_dominante', '')]
            ]
            
            t = Table(data, colWidths=[150, 300])
            t.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 1, colors.black),
                ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(t)
            
            doc.build(story)
            return True
        except Exception as e:
            logger.error(f"Error generando PDF: {e}")
            raise