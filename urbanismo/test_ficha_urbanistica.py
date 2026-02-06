#!/usr/bin/env python3
"""
Script de prueba para procesar fichas urbanísticas
Ubicación: urbanismo/test_ficha_urbanistica.py
"""

import sys
from pathlib import Path

# Agregar el directorio padre al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from urbanismo.urbanismo_service import UrbanismoService

def main():
    print("\n" + "="*70)
    print("PROCESAMIENTO DE FICHA URBANÍSTICA")
    print("="*70 + "\n")
    
    # Rutas relativas desde urbanismo/
    catalogo_path = Path(__file__).parent.parent / "catalogo_espana_50_ciudades.json"
    output_dir = Path(__file__).parent.parent / "resultados_analisis"
    
    # Verificar que existe el catálogo
    if not catalogo_path.exists():
        print(f"❌ Error: No se encuentra el catálogo")
        print(f"   Esperado en: {catalogo_path}")
        print("\n💡 Asegúrate de que 'catalogo_espana_50_ciudades.json' está en:")
        print(f"   {catalogo_path.parent}")
        return
    
    # Inicializar servicio
    print(f"📚 Cargando catálogo desde: {catalogo_path.name}")
    servicio = UrbanismoService(
        output_base_dir=str(output_dir),
        catalogo_normativa_path=str(catalogo_path)
    )
    
    # Ruta al PDF (ajusta según tu archivo)
    # Buscar en el directorio raíz o en urbanismo/
    pdf_filename = "ficha-urb-SNUi.pdf"
    
    posibles_rutas = [
        Path(__file__).parent.parent / pdf_filename,  # Raíz del proyecto
        Path(__file__).parent / pdf_filename,          # Carpeta urbanismo/
        Path.cwd() / pdf_filename,                     # Directorio actual
    ]
    
    pdf_path = None
    for ruta in posibles_rutas:
        if ruta.exists():
            pdf_path = ruta
            break
    
    if not pdf_path:
        print(f"❌ Error: No se encuentra el archivo PDF '{pdf_filename}'")
        print("\n   Rutas buscadas:")
        for ruta in posibles_rutas:
            print(f"   - {ruta}")
        print(f"\n💡 Coloca tu PDF en alguna de estas ubicaciones o edita el script")
        return
    
    # Referencia catastral (ajusta según tu caso)
    referencia = "30030A000000001"
    
    # Procesar ficha
    print(f"📄 Procesando: {pdf_path.name}")
    print(f"🔖 Referencia: {referencia}\n")
    
    try:
        resultado = servicio.procesar_ficha_urbanistica_completa(
            pdf_path=str(pdf_path),
            referencia=referencia
        )
        
        # Mostrar resultados
        if 'error' in resultado:
            print(f"❌ Error: {resultado['error']}")
            return
        
        datos = resultado['datos_extraidos']
        normativa = resultado['normativa']
        
        print("✅ Procesamiento completado\n")
        print("="*70)
        print("DATOS EXTRAÍDOS")
        print("="*70)
        print(f"📍 Municipio: {datos['municipio']}")
        print(f"🏗️ Clasificación: {datos['clasificacion_suelo']}")
        print(f"🎯 Uso global: {datos['uso_global']}")
        print(f"📊 Uso dominante: {datos['uso_dominante']}")
        if datos['superficie']:
            print(f"📏 Superficie: {datos['superficie']} m²")
        
        print("\n" + "="*70)
        print("NORMATIVA APLICABLE")
        print("="*70)
        print(f"Total referencias detectadas: {normativa['total']}")
        print(f"Encontradas en catálogo: {normativa['encontradas']}")
        print(f"Porcentaje de match: {normativa['porcentaje_match']:.1f}%")
        
        if normativa['referencias']:
            print("\n📚 Detalle de referencias:")
            for i, ref in enumerate(normativa['referencias'], 1):
                estado = "✓" if ref['encontrada'] else "✗"
                print(f"\n  {i}. {estado} {ref['texto_original']}")
                if ref['encontrada'] and ref['norma']:
                    print(f"     → {ref['norma']['titulo']}")
                    if ref['norma'].get('url_oficial'):
                        print(f"     🔗 {ref['norma']['url_oficial']}")
        
        print("\n" + "="*70)
        print("ARCHIVOS GENERADOS")
        print("="*70)
        print(f"📄 CSV: {resultado['csv_path']}")
        print(f"📄 JSON: {resultado['json_path']}")
        if resultado.get('informe_normativa_path'):
            print(f"📄 Informe normativa: {resultado['informe_normativa_path']}")
        
        print("\n" + "="*70)
        print(f"✅ Resultados guardados en: {output_dir / referencia}")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"❌ Error durante el procesamiento: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
