import sys
from pathlib import Path

# Agregar el path
sys.path.insert(0, str(Path(__file__).parent))

# Importar la clase
from catastro.catastro_downloader import CatastroDownloader

# Crear instancia
downloader = CatastroDownloader(output_dir="outputs")

# Buscar archivos GML
outputs_dir = Path("outputs")
archivos_gml = list(outputs_dir.rglob("*.gml"))

print(f"Encontrados {len(archivos_gml)} archivos GML")

# Convertir cada uno
for gml_file in archivos_gml:
    print(f"\nConvirtiendo: {gml_file}")
    kml_file = gml_file.with_suffix('.kml')
    resultado = downloader.convertir_gml_a_kml(gml_file, kml_file)
    print(f"Resultado: {resultado}")

print("\nProceso completado")
