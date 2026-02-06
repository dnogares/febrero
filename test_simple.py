import sys
from pathlib import Path

print("Inicio del script")
print(f"Python: {sys.version}")
print(f"Path actual: {Path.cwd()}")

output_dir = Path("outputs")
print(f"Directorio outputs existe: {output_dir.exists()}")

if output_dir.exists():
    items = list(output_dir.iterdir())
    print(f"Items en outputs: {len(items)}")
    for item in items[:5]:
        print(f"  - {item.name} ({'DIR' if item.is_dir() else 'FILE'})")

print("Fin del script")
