#!/usr/bin/env python3
"""
urbanismo/gestor_normativa_urbanistica.py

Sistema de gestión de normativa urbanística española
Soporta PGOU, modificaciones, adaptaciones y referencias normativas
"""

import logging
import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import re

logger = logging.getLogger(__name__)


@dataclass
class NormaUrbanistica:
    """Representa una norma urbanística individual"""
    id_norma: str  # Ej: "PGOU_MURCIA_MOD_7_ART_5_14_2_1"
    municipio: str  # Ej: "Murcia"
    codigo_ine: str  # Ej: "30030"
    provincia: str  # Ej: "Murcia"
    ccaa: str  # Ej: "Región de Murcia"
    ambito: str  # municipal / provincial / autonomico / estatal
    tipo_norma: str  # PGOU / NNSS / PlanParcial / Modificacion / TRLSRU / etc
    numero_modificacion: Optional[int] = None  # Ej: 7, 35, 95, etc.
    plan_base: str = "PGOU"  # PGOU, NNSS, etc.
    articulo: Optional[str] = None  # Ej: "5.14.2.1"
    apartado: Optional[str] = None  # Ej: "c"
    titulo: str = ""  # Título corto
    descripcion: str = ""  # Descripción breve (2-3 líneas)
    url_oficial: Optional[str] = None  # URL del documento oficial
    fecha_aprobacion: Optional[str] = None  # YYYY-MM-DD
    vigente: bool = True
    observaciones: str = ""
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NormaUrbanistica':
        """Crea instancia desde diccionario"""
        return cls(**data)


class GestorNormativaUrbanistica:
    """
    Gestor del catálogo de normativa urbanística
    
    Funcionalidades:
    - Cargar/guardar catálogo desde JSON/CSV
    - Buscar normas por municipio, tipo, artículo
    - Parsear referencias del estilo "N° 7 DEL PGOU (ART.5.14.2.1...)"
    - Enlazar referencias extraídas con el catálogo
    """
    
    def __init__(self, catalogo_path: Optional[str] = None):
        """
        Inicializa el gestor de normativa
        
        Args:
            catalogo_path: Ruta al archivo del catálogo (JSON o CSV)
        """
        self.normas: Dict[str, NormaUrbanistica] = {}
        self.catalogo_path = Path(catalogo_path) if catalogo_path else None
        
        if self.catalogo_path and self.catalogo_path.exists():
            self.cargar_catalogo(str(self.catalogo_path))
        else:
            logger.info("Iniciando con catálogo vacío")
    
    def cargar_catalogo(self, path: str):
        """
        Carga catálogo desde archivo JSON o CSV
        
        Args:
            path: Ruta al archivo
        """
        path = Path(path)
        
        try:
            if path.suffix.lower() == '.json':
                self._cargar_json(path)
            elif path.suffix.lower() == '.csv':
                self._cargar_csv(path)
            else:
                raise ValueError(f"Formato no soportado: {path.suffix}")
            
            logger.info(f"Catálogo cargado: {len(self.normas)} normas desde {path}")
        
        except Exception as e:
            logger.error(f"Error cargando catálogo desde {path}: {e}")
            raise
    
    def _cargar_json(self, path: Path):
        """Carga desde JSON"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            norma = NormaUrbanistica.from_dict(item)
            self.normas[norma.id_norma] = norma
    
    def _cargar_csv(self, path: Path):
        """Carga desde CSV"""
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convertir campos numéricos y booleanos
                if row.get('numero_modificacion'):
                    row['numero_modificacion'] = int(row['numero_modificacion'])
                else:
                    row['numero_modificacion'] = None
                
                row['vigente'] = row.get('vigente', 'True').lower() in ['true', '1', 'si', 'sí']
                
                norma = NormaUrbanistica(**row)
                self.normas[norma.id_norma] = norma
    
    def guardar_catalogo(self, path: str, formato: str = 'json'):
        """
        Guarda catálogo en archivo
        
        Args:
            path: Ruta de salida
            formato: 'json' o 'csv'
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if formato == 'json':
                self._guardar_json(path)
            elif formato == 'csv':
                self._guardar_csv(path)
            else:
                raise ValueError(f"Formato no soportado: {formato}")
            
            logger.info(f"Catálogo guardado: {len(self.normas)} normas en {path}")
        
        except Exception as e:
            logger.error(f"Error guardando catálogo: {e}")
            raise
    
    def _guardar_json(self, path: Path):
        """Guarda en JSON"""
        data = [norma.to_dict() for norma in self.normas.values()]
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _guardar_csv(self, path: Path):
        """Guarda en CSV"""
        if not self.normas:
            logger.warning("No hay normas para guardar")
            return
        
        fieldnames = list(asdict(list(self.normas.values())[0]).keys())
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for norma in self.normas.values():
                writer.writerow(norma.to_dict())
    
    def agregar_norma(self, norma: NormaUrbanistica):
        """Añade una norma al catálogo"""
        self.normas[norma.id_norma] = norma
        logger.debug(f"Norma agregada: {norma.id_norma}")
    
    def buscar_por_municipio(self, municipio: str) -> List[NormaUrbanistica]:
        """Busca normas de un municipio"""
        return [
            norma for norma in self.normas.values()
            if norma.municipio.lower() == municipio.lower()
        ]
    
    def buscar_por_codigo_ine(self, codigo_ine: str) -> List[NormaUrbanistica]:
        """Busca normas por código INE"""
        return [
            norma for norma in self.normas.values()
            if norma.codigo_ine == codigo_ine
        ]
    
    def buscar_por_id(self, id_norma: str) -> Optional[NormaUrbanistica]:
        """Busca norma por ID exacto"""
        return self.normas.get(id_norma)
    
    def buscar_por_tipo(self, tipo_norma: str, municipio: Optional[str] = None) -> List[NormaUrbanistica]:
        """Busca normas por tipo (opcionalmente filtradas por municipio)"""
        resultados = [
            norma for norma in self.normas.values()
            if norma.tipo_norma.lower() == tipo_norma.lower()
        ]
        
        if municipio:
            resultados = [n for n in resultados if n.municipio.lower() == municipio.lower()]
        
        return resultados
    
    def parsear_referencia_texto(self, texto_referencia: str, municipio: str = "") -> Dict:
        """
        Parsea una referencia textual del estilo extraído del PDF
        
        Ejemplos:
        - "N° 7 DEL PGOU (ART.5.14.2.1 DE LAS NORMAS)"
        - "Modificación nº 35, artículo 3.7.3, apdo c)"
        - "Revisión PGOU"
        
        Args:
            texto_referencia: Texto de la referencia
            municipio: Municipio para contexto de búsqueda
        
        Returns:
            Diccionario con componentes parseados
        """
        componentes = {
            'texto_original': texto_referencia,
            'numero_modificacion': None,
            'plan_base': 'PGOU',
            'articulo': None,
            'apartado': None,
            'tipo': 'Modificacion',
            'municipio': municipio
        }
        
        texto_lower = texto_referencia.lower()
        
        # Detectar tipo de norma
        if 'revisión' in texto_lower or 'revision' in texto_lower:
            componentes['tipo'] = 'Revision'
        elif 'adaptación' in texto_lower or 'adaptacion' in texto_lower:
            componentes['tipo'] = 'Adaptacion'
        elif 'modificación' in texto_lower or 'modificacion' in texto_lower or 'n°' in texto_lower or 'nº' in texto_lower:
            componentes['tipo'] = 'Modificacion'
        
        # Extraer número de modificación
        match_num = re.search(r'(?:n[º°]|modificación|modificacion)\s*(\d+)', texto_referencia, re.IGNORECASE)
        if match_num:
            componentes['numero_modificacion'] = int(match_num.group(1))
        
        # Extraer artículo
        match_art = re.search(r'art[ií]?[cn]?ulo?\s*([\d.]+)', texto_referencia, re.IGNORECASE)
        if match_art:
            componentes['articulo'] = match_art.group(1)
        
        # Extraer apartado
        match_apto = re.search(r'apdo?\.?\s*([a-z])', texto_referencia, re.IGNORECASE)
        if match_apto:
            componentes['apartado'] = match_apto.group(1)
        
        # Detectar plan base
        if 'nnss' in texto_lower or 'normas subsidiarias' in texto_lower:
            componentes['plan_base'] = 'NNSS'
        elif 'trlsrm' in texto_lower or 'texto refundido' in texto_lower:
            componentes['plan_base'] = 'TRLSRM'
        
        return componentes
    
    def enlazar_referencias(self, referencias_texto: List[str], municipio: str, codigo_ine: str = "") -> List[Dict]:
        """
        Enlaza referencias textuales con normas del catálogo
        
        Args:
            referencias_texto: Lista de textos de referencia
            municipio: Municipio para búsqueda
            codigo_ine: Código INE (opcional)
        
        Returns:
            Lista de diccionarios con referencia + norma encontrada (si existe)
        """
        resultados = []
        
        for ref_texto in referencias_texto:
            componentes = self.parsear_referencia_texto(ref_texto, municipio)
            
            # Construir ID esperado
            id_esperado = self._construir_id_norma(componentes, municipio)
            
            # Buscar en catálogo
            norma_encontrada = self.buscar_por_id(id_esperado)
            
            resultado = {
                'texto_original': ref_texto,
                'componentes': componentes,
                'id_esperado': id_esperado,
                'encontrada': norma_encontrada is not None,
                'norma': norma_encontrada.to_dict() if norma_encontrada else None
            }
            
            resultados.append(resultado)
        
        return resultados
    
    def _construir_id_norma(self, componentes: Dict, municipio: str) -> str:
        """Construye ID de norma a partir de componentes"""
        partes = [componentes['plan_base'], municipio.upper().replace(' ', '_')]
        
        if componentes.get('numero_modificacion'):
            partes.append(f"MOD_{componentes['numero_modificacion']}")
        
        if componentes.get('articulo'):
            art_limpio = componentes['articulo'].replace('.', '_')
            partes.append(f"ART_{art_limpio}")
        
        if componentes.get('apartado'):
            partes.append(f"APDO_{componentes['apartado'].upper()}")
        
        return "_".join(partes)
    
    def crear_catalogo_murcia_ejemplo(self):
        """Crea catálogo de ejemplo con normas de Murcia"""
        normas_murcia = [
            NormaUrbanistica(
                id_norma="PGOU_MURCIA_REVISION",
                municipio="Murcia",
                codigo_ine="30030",
                provincia="Murcia",
                ccaa="Región de Murcia",
                ambito="municipal",
                tipo_norma="Revision",
                plan_base="PGOU",
                titulo="Revisión del Plan General de Ordenación Urbana",
                descripcion="Revisión completa del PGOU de Murcia",
                url_oficial="https://sede.murcia.es/urbanismo/pgou",
                vigente=True
            ),
            NormaUrbanistica(
                id_norma="PGOU_MURCIA_MOD_7_ART_5_14_2_1",
                municipio="Murcia",
                codigo_ine="30030",
                provincia="Murcia",
                ccaa="Región de Murcia",
                ambito="municipal",
                tipo_norma="Modificacion",
                numero_modificacion=7,
                plan_base="PGOU",
                articulo="5.14.2.1",
                titulo="Modificación N° 7 - Consulta previa",
                descripcion="Modificación sobre procedimientos de consulta previa urbanística",
                vigente=True
            ),
            NormaUrbanistica(
                id_norma="PGOU_MURCIA_MOD_8_ART_9_4_1_1",
                municipio="Murcia",
                codigo_ine="30030",
                provincia="Murcia",
                ccaa="Región de Murcia",
                ambito="municipal",
                tipo_norma="Modificacion",
                numero_modificacion=8,
                plan_base="PGOU",
                articulo="9.4.1.1",
                titulo="Modificación N° 8 - Legalizaciones",
                descripcion="Normas sobre legalizaciones de construcciones existentes",
                vigente=True
            ),
            NormaUrbanistica(
                id_norma="PGOU_MURCIA_MOD_35_ART_3_7_3_APDO_C",
                municipio="Murcia",
                codigo_ine="30030",
                provincia="Murcia",
                ccaa="Región de Murcia",
                ambito="municipal",
                tipo_norma="Modificacion",
                numero_modificacion=35,
                plan_base="PGOU",
                articulo="3.7.3",
                apartado="c",
                titulo="Modificación N° 35 - Artículo 3.7.3 apartado c",
                descripcion="Modificación específica sobre clasificación de suelo",
                vigente=True
            ),
            NormaUrbanistica(
                id_norma="TRLSRM_MURCIA_ADAPTACION",
                municipio="Murcia",
                codigo_ine="30030",
                provincia="Murcia",
                ccaa="Región de Murcia",
                ambito="autonomico",
                tipo_norma="Adaptacion",
                plan_base="TRLSRM",
                titulo="Adaptación del PGOU al TRLSRM",
                descripcion="Adaptación del Plan General al Texto Refundido de la Ley del Suelo de la Región de Murcia",
                vigente=True
            ),
            NormaUrbanistica(
                id_norma="PGOU_MURCIA_MOD_95",
                municipio="Murcia",
                codigo_ine="30030",
                provincia="Murcia",
                ccaa="Región de Murcia",
                ambito="municipal",
                tipo_norma="Modificacion",
                numero_modificacion=95,
                plan_base="PGOU",
                titulo="Modificación N° 95 - Ampliación de plazos",
                descripcion="Ampliación del plazo contenido en la Norma Transitoria Única",
                vigente=True
            ),
            NormaUrbanistica(
                id_norma="PGOU_MURCIA_MOD_99_ART_3_7_2_3",
                municipio="Murcia",
                codigo_ine="30030",
                provincia="Murcia",
                ccaa="Región de Murcia",
                ambito="municipal",
                tipo_norma="Modificacion",
                numero_modificacion=99,
                plan_base="PGOU",
                articulo="3.7.2.3",
                titulo="Modificación N° 99 - Artículo 3.7.2.3",
                descripcion="Modificación de normas sobre clasificación del suelo",
                vigente=True
            ),
            NormaUrbanistica(
                id_norma="PGOU_MURCIA_MOD_108_ART_6_2_5",
                municipio="Murcia",
                codigo_ine="30030",
                provincia="Murcia",
                ccaa="Región de Murcia",
                ambito="municipal",
                tipo_norma="Modificacion",
                numero_modificacion=108,
                plan_base="PGOU",
                articulo="6.2.5",
                titulo="Modificación N° 108 - Normas urbanísticas",
                descripcion="Modificación de artículo 6.2.5 de las normas urbanísticas",
                vigente=True
            ),
        ]
        
        for norma in normas_murcia:
            self.agregar_norma(norma)
        
        logger.info(f"Catálogo de ejemplo creado con {len(normas_murcia)} normas de Murcia")
    
    def generar_informe_normativa(self, referencias_enlazadas: List[Dict], output_path: str):
        """
        Genera informe de normativa aplicable en formato legible
        
        Args:
            referencias_enlazadas: Resultado de enlazar_referencias()
            output_path: Ruta de salida del informe
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("INFORME DE NORMATIVA URBANÍSTICA APLICABLE\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                f.write(f"Total referencias: {len(referencias_enlazadas)}\n\n")
                
                for i, ref in enumerate(referencias_enlazadas, 1):
                    f.write(f"{i}. {ref['texto_original']}\n")
                    f.write("-" * 70 + "\n")
                    
                    if ref['encontrada']:
                        norma = ref['norma']
                        f.write(f"   ✓ Norma encontrada en catálogo\n")
                        f.write(f"   ID: {norma['id_norma']}\n")
                        f.write(f"   Título: {norma['titulo']}\n")
                        f.write(f"   Descripción: {norma['descripcion']}\n")
                        if norma.get('url_oficial'):
                            f.write(f"   URL: {norma['url_oficial']}\n")
                        f.write(f"   Vigente: {'Sí' if norma['vigente'] else 'No'}\n")
                    else:
                        f.write(f"   ✗ Norma NO encontrada en catálogo\n")
                        f.write(f"   ID esperado: {ref['id_esperado']}\n")
                        f.write(f"   Componentes: {ref['componentes']}\n")
                    
                    f.write("\n")
                
                f.write("=" * 80 + "\n")
                f.write("Fin del informe\n")
                f.write("=" * 80 + "\n")
            
            logger.info(f"Informe generado: {output_path}")
        
        except Exception as e:
            logger.error(f"Error generando informe: {e}")
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Crear gestor y catálogo de ejemplo
    gestor = GestorNormativaUrbanistica()
    
    # Crear catálogo de Murcia
    gestor.crear_catalogo_murcia_ejemplo()
    
    # Guardar en JSON
    gestor.guardar_catalogo("normativa_murcia.json", formato='json')
    
    # Guardar en CSV
    gestor.guardar_catalogo("normativa_murcia.csv", formato='csv')
    
    # Ejemplo de parseo de referencias (como las del PDF)
    referencias_ejemplo = [
        "N° 7 DEL PGOU (ART.5.14.2.1 DE LAS NORMAS)",
        "N°8 ART°S.9.4.1.1 Y 9.6.2 Y APDO.3 DE LA NORMA TRANSITORIA",
        "nº 35, artículo 3.7.3, apdo c)",
        "Modificación adaptación del PGOU al TRLSRM",
        "Nº 95, ampliación del plazo contenido en la Norma Transitoria Única",
        "nº 99 del PGOU, norma art. 3.7.2.3.",
        "nº 108, art. 6.2.5 de las normas urbanísticas"
    ]
    
    referencias_enlazadas = gestor.enlazar_referencias(referencias_ejemplo, "Murcia")
    
    # Generar informe
    gestor.generar_informe_normativa(referencias_enlazadas, "informe_normativa_murcia.txt")
    
    print(f"✅ Catálogo creado con {len(gestor.normas)} normas")
    print(f"✅ Referencias procesadas: {len(referencias_enlazadas)}")
    print(f"✅ Encontradas: {sum(1 for r in referencias_enlazadas if r['encontrada'])}/{len(referencias_enlazadas)}")
