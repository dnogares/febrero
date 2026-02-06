#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para convertir archivos GML existentes a KML
"""
import sys
import os
from pathlib import Path

# Configurar el path
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

try:
    import geopandas as gpd
    import fiona
    
    # Habilitar el driver KML
    fiona.drvsupport.supported_drivers['KML'] = 'rw'
    
    print("=" * 70)
    print("CONVERSIÓN DE ARCHIVOS GML A KML")
    print("=" * 70)
    
    # Buscar archivos GML en outputs
    outputs_dir = Path("outputs")
    
    if not outputs_dir.exists():
        print(f"\n❌ El directorio 'outputs' no existe")
        sys.exit(1)
    
    # Buscar todos los archivos GML
    archivos_gml = list(outputs_dir.rglob("*.gml"))
    
    print(f"\n📁 Encontrados {len(archivos_gml)} archivos GML")
    
    if not archivos_gml:
        print("\n⚠️  No hay archivos GML para convertir")
        sys.exit(0)
    
    # Convertir cada archivo
    convertidos = 0
    errores = 0
    ya_existentes = 0
    
    for gml_file in archivos_gml:
        kml_file = gml_file.with_suffix('.kml')
        
        # Verificar si ya existe
        if kml_file.exists():
            ya_existentes += 1
            print(f"\n↩️  Ya existe: {kml_file.name}")
            continue
        
        try:
            print(f"\n🔄 Convirtiendo: {gml_file.relative_to(outputs_dir)}")
            
            # Leer GML
            gdf = gpd.read_file(gml_file)
            
            # Asegurar WGS84
            if gdf.crs and str(gdf.crs) != "EPSG:4326":
                print(f"   Reproyectando de {gdf.crs} a EPSG:4326")
                gdf = gdf.to_crs("EPSG:4326")
            
            # Guardar como KML
            gdf.to_file(kml_file, driver='KML')
            
            print(f"   ✅ KML creado: {kml_file.name}")
            convertidos += 1
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            errores += 1
    
    # Resumen
    print("\n" + "=" * 70)
    print("RESUMEN DE CONVERSIÓN")
    print("=" * 70)
    print(f"✅ Archivos convertidos: {convertidos}")
    print(f"↩️  Ya existían: {ya_existentes}")
    print(f"❌ Errores: {errores}")
    print(f"📊 Total procesados: {len(archivos_gml)}")
    print("=" * 70)
    
except ImportError as e:
    print(f"\n❌ Error de importación: {e}")
    print("   Asegúrate de tener instalados: geopandas, fiona")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error inesperado: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
