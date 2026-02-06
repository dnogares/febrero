#!/usr/bin/env python3
"""
Script standalone para importar las 50 ciudades más grandes de España
No requiere estructura de paquetes
"""

import logging
import json
import csv
from pathlib import Path
from typing import Dict, List
from datetime import datetime
from dataclasses import dataclass, asdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class NormaUrbanistica:
    """Representa una norma urbanística individual"""
    id_norma: str
    municipio: str
    codigo_ine: str
    provincia: str
    ccaa: str
    ambito: str
    tipo_norma: str
    numero_modificacion: int = None
    plan_base: str = "PGOU"
    articulo: str = None
    apartado: str = None
    titulo: str = ""
    descripcion: str = ""
    url_oficial: str = None
    fecha_aprobacion: str = None
    vigente: bool = True
    observaciones: str = ""
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'NormaUrbanistica':
        """Crea instancia desde diccionario"""
        return cls(**data)


def importar_desde_csv(csv_path: str) -> Dict[str, NormaUrbanistica]:
    """
    Importa normas desde CSV
    
    Args:
        csv_path: Ruta al archivo CSV
        
    Returns:
        Diccionario de normas {id_norma: NormaUrbanistica}
    """
    csv_path = Path(csv_path)
    
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV no encontrado: {csv_path}")
    
    normas = {}
    normas_agregadas = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                # Construir ID
                partes = [row.get('plan_base', 'PGOU') or 'PGOU']
                
                if row['municipio']:
                    partes.append(row['municipio'].upper().replace(' ', '_'))
                
                if row.get('numero_modificacion'):
                    partes.append(f"MOD_{row['numero_modificacion']}")
                
                if row.get('articulo'):
                    partes.append(f"ART_{row['articulo'].replace('.', '_')}")
                
                id_norma = "_".join(partes)
                
                # Crear norma
                norma = NormaUrbanistica(
                    id_norma=id_norma,
                    municipio=row['municipio'],
                    codigo_ine=row['codigo_ine'],
                    provincia=row['provincia'],
                    ccaa=row['ccaa'],
                    ambito=row.get('ambito', 'municipal'),
                    tipo_norma=row['tipo_norma'],
                    numero_modificacion=int(row['numero_modificacion']) if row.get('numero_modificacion') and row['numero_modificacion'].strip() else None,
                    plan_base=row.get('plan_base', 'PGOU') or 'PGOU',
                    articulo=row.get('articulo') if row.get('articulo') else None,
                    apartado=row.get('apartado') if row.get('apartado') else None,
                    titulo=row['titulo'],
                    descripcion=row.get('descripcion', ''),
                    url_oficial=row.get('url_oficial') if row.get('url_oficial') else None,
                    vigente=row.get('vigente', 'True').lower() in ['true', '1', 'si']
                )
                
                normas[id_norma] = norma
                normas_agregadas += 1
                
            except Exception as e:
                logger.warning(f"Error procesando fila: {e}")
                logger.debug(f"Datos de la fila: {row}")
    
    logger.info(f"✓ {normas_agregadas} normas importadas desde CSV")
    return normas


def guardar_catalogo_json(normas: Dict[str, NormaUrbanistica], output_path: str):
    """Guarda catálogo en JSON"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = [norma.to_dict() for norma in normas.values()]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ Catálogo JSON guardado: {output_path}")


def guardar_catalogo_csv(normas: Dict[str, NormaUrbanistica], output_path: str):
    """Guarda catálogo en CSV"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not normas:
        logger.warning("No hay normas para guardar")
        return
    
    fieldnames = list(asdict(list(normas.values())[0]).keys())
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for norma in normas.values():
            writer.writerow(norma.to_dict())
    
    logger.info(f"✓ Catálogo CSV guardado: {output_path}")


def generar_resumen(normas: Dict[str, NormaUrbanistica]):
    """Genera resumen del catálogo"""
    print("\n" + "="*70)
    print("RESUMEN DEL CATÁLOGO DE NORMATIVA")
    print("="*70)
    
    # Por CCAA
    ccaas = {}
    for norma in normas.values():
        if norma.ccaa not in ccaas:
            ccaas[norma.ccaa] = []
        ccaas[norma.ccaa].append(norma)
    
    print(f"\nTotal normas: {len(normas)}")
    print(f"Comunidades Autónomas: {len(ccaas)}\n")
    
    for ccaa, normas_ccaa in sorted(ccaas.items()):
        municipios = set(n.municipio for n in normas_ccaa if n.municipio)
        print(f"  {ccaa}:")
        print(f"    - {len(normas_ccaa)} normas")
        print(f"    - {len(municipios)} municipios")
    
    print("\n" + "="*70)


def main():
    print("\n" + "="*70)
    print("IMPORTACIÓN DE LAS 50 CIUDADES MÁS GRANDES DE ESPAÑA")
    print("="*70 + "\n")
    
    # Rutas
    csv_input = "catalogo_50_ciudades_espana.csv"
    json_output = "catalogo_espana_50_ciudades.json"
    csv_output = "catalogo_espana_50_ciudades_export.csv"
    
    # Verificar que existe el CSV
    if not Path(csv_input).exists():
        print(f"❌ Error: No se encuentra el archivo {csv_input}")
        print(f"   Ruta esperada: {Path(csv_input).absolute()}")
        print("\n💡 Asegúrate de que el archivo CSV está en el mismo directorio")
        return
    
    try:
        # Importar desde CSV
        print(f"📥 Importando desde: {csv_input}")
        normas = importar_desde_csv(csv_input)
        
        # Guardar en JSON
        print(f"\n💾 Guardando catálogo JSON...")
        guardar_catalogo_json(normas, json_output)
        
        # Guardar en CSV (exportación)
        print(f"💾 Guardando catálogo CSV...")
        guardar_catalogo_csv(normas, csv_output)
        
        # Generar resumen
        print("\n📊 Generando resumen...")
        generar_resumen(normas)
        
        print("\n✅ Proceso completado exitosamente")
        print(f"\n📁 Archivos generados:")
        print(f"   - JSON: {Path(json_output).absolute()}")
        print(f"   - CSV:  {Path(csv_output).absolute()}")
        
        print("\n💡 Ahora puedes usar este catálogo con:")
        print("   servicio = UrbanismoService(")
        print("       output_base_dir='resultados',")
        print(f"       catalogo_normativa_path='{json_output}'")
        print("   )")
        
    except Exception as e:
        print(f"\n❌ Error durante el proceso: {e}")
        logger.exception("Detalles del error:")
        return


if __name__ == "__main__":
    main()
