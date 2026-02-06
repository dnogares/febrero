"""
Script de prueba para verificar la conversión de GML a KML
"""
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from catastro.catastro_downloader import CatastroDownloader

def probar_conversion_kml():
    """Prueba la conversión de archivos GML existentes a KML"""
    
    downloader = CatastroDownloader(output_dir="outputs")
    
    # Buscar directorios de referencias existentes
    output_dir = Path("outputs")
    
    if not output_dir.exists():
        print(f"❌ No existe el directorio de descargas: {output_dir.absolute()}")
        return
    
    print(f"✅ Directorio encontrado: {output_dir.absolute()}")
    
    # Buscar subdirectorios (referencias)
    referencias = [d for d in output_dir.iterdir() if d.is_dir() and not d.name.startswith('_')]
    
    print(f"📂 Total de directorios: {len(list(output_dir.iterdir()))}")
    print(f"📁 Referencias válidas: {len(referencias)}")
    
    if not referencias:
        print("❌ No se encontraron referencias procesadas")
        return
    
    print(f"📁 Encontradas {len(referencias)} referencias procesadas")
    
    # Probar con las primeras 3 referencias
    for ref_dir in referencias[:3]:
        ref = ref_dir.name
        print(f"\n{'='*60}")
        print(f"🔄 Procesando referencia: {ref}")
        print(f"{'='*60}")
        
        # Buscar archivos GML
        archivos_gml = list(ref_dir.glob("*.gml"))
        
        if not archivos_gml:
            print(f"  ⚠️  No se encontraron archivos GML en {ref_dir}")
            continue
        
        print(f"  📄 Encontrados {len(archivos_gml)} archivos GML")
        
        # Convertir cada GML a KML
        for gml_file in archivos_gml:
            print(f"\n  🔄 Convirtiendo: {gml_file.name}")
            kml_path = gml_file.with_suffix('.kml')
            
            if kml_path.exists():
                print(f"  ↩️  KML ya existe: {kml_path.name}")
            else:
                exito = downloader.convertir_gml_a_kml(gml_file, kml_path)
                if exito:
                    print(f"  ✅ Conversión exitosa")
                else:
                    print(f"  ❌ Error en la conversión")

if __name__ == "__main__":
    print("🚀 Iniciando prueba de conversión GML a KML\n")
    probar_conversion_kml()
    print("\n✅ Prueba completada")
