#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para regenerar Planos Perfectos en referencias ya procesadas
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from catastro.catastro_downloader import CatastroDownloader

def regenerar_planos_perfectos():
    """Regenera los Planos Perfectos para todas las referencias existentes"""
    
    downloader = CatastroDownloader(output_dir="outputs")
    outputs_dir = Path("outputs")
    
    if not outputs_dir.exists():
        print("❌ El directorio 'outputs' no existe")
        return
    
    # Buscar subdirectorios (referencias)
    referencias = [d for d in outputs_dir.iterdir() if d.is_dir() and not d.name.startswith('_')]
    
    print(f"📁 Encontradas {len(referencias)} referencias procesadas")
    
    if not referencias:
        print("⚠️  No hay referencias para procesar")
        return
    
    generados = 0
    errores = 0
    ya_existentes = 0
    
    for ref_dir in referencias:
        ref = ref_dir.name
        print(f"\n{'='*60}")
        print(f"🔄 Procesando: {ref}")
        print(f"{'='*60}")
        
        # Buscar GML de parcela
        gml_file = ref_dir / f"{ref}_parcela.gml"
        
        if not gml_file.exists():
            print(f"  ⚠️  No se encontró GML de parcela")
            errores += 1
            continue
        
        # Crear directorio de imágenes
        images_dir = ref_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        # Ruta del plano perfecto
        plano_path = images_dir / f"{ref}_plano_perfecto.png"
        
        if plano_path.exists():
            print(f"  ↩️  Plano Perfecto ya existe: {plano_path.name}")
            ya_existentes += 1
            continue
        
        # Generar plano perfecto
        try:
            print(f"  🎨 Generando Plano Perfecto...")
            exito = downloader.generar_plano_perfecto(
                gml_path=gml_file,
                output_path=plano_path,
                ref=ref,
                info_afecciones=None
            )
            
            if exito:
                print(f"  ✅ Plano Perfecto generado exitosamente")
                generados += 1
            else:
                print(f"  ❌ Error generando Plano Perfecto")
                errores += 1
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            errores += 1
    
    # Resumen
    print("\n" + "="*60)
    print("RESUMEN DE GENERACIÓN")
    print("="*60)
    print(f"✅ Planos generados: {generados}")
    print(f"↩️  Ya existían: {ya_existentes}")
    print(f"❌ Errores: {errores}")
    print(f"📊 Total procesados: {len(referencias)}")
    print("="*60)

if __name__ == "__main__":
    print("🚀 Iniciando generación de Planos Perfectos\n")
    regenerar_planos_perfectos()
    print("\n✅ Proceso completado")
