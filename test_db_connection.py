#!/usr/bin/env python3
import os
import sys
from sqlalchemy import create_engine, text

def test_connection():
    print("="*60)
    print("PRUEBA DE CONEXIÓN A POSTGIS")
    print("="*60)

    # 1. Obtener URL de conexión
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        print("⚠️  DATABASE_URL no encontrada en variables de entorno.")
        # Intentar construirla
        host = os.getenv("POSTGRES_HOST") or os.getenv("POSTGIS_HOST")
        db = os.getenv("POSTGRES_DB") or os.getenv("POSTGIS_DATABASE")
        user = os.getenv("POSTGRES_USER") or os.getenv("POSTGIS_USER")
        password = os.getenv("POSTGRES_PASSWORD") or os.getenv("POSTGIS_PASSWORD")
        port = os.getenv("POSTGRES_PORT") or os.getenv("POSTGIS_PORT") or "5432"
        
        if all([host, db, user, password]):
            print(f"ℹ️  Construyendo URL desde variables individuales...")
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        else:
            print("❌ No se encontraron suficientes variables para conectar.")
            return

    # Ocultar contraseña en el log
    safe_url = db_url.split('@')[-1] if '@' in db_url else '***'
    print(f"🔌 Intentando conectar a: ...@{safe_url}")

    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # Prueba básica
            version = conn.execute(text("SELECT version()")).fetchone()[0]
            print(f"✅ CONEXIÓN EXITOSA!")
            print(f"📊 Versión: {version}")
            
            # Listar tablas geométricas
            print("\n🌍 Capas espaciales disponibles (geometry_columns):")
            result = conn.execute(text("SELECT f_table_name, type FROM geometry_columns WHERE f_table_schema = 'public'"))
            for row in result:
                print(f"   - {row[0]} ({row[1]})")
                
    except Exception as e:
        print(f"\n❌ ERROR DE CONEXIÓN: {e}")

if __name__ == "__main__":
    test_connection()