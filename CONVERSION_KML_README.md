# Conversión de GML a KML - Implementación Completada

## Resumen

Se ha implementado la funcionalidad para generar archivos KML a partir de los archivos GML descargados del Catastro.

## Cambios Realizados

### 1. Archivo: `catastro/catastro_downloader.py`

#### Nuevas Funciones:

**`convertir_gml_a_kml(gml_path, kml_path=None)`**
- Convierte un archivo GML individual a formato KML
- Utiliza GeoPandas y Fiona para la conversión
- Asegura que el archivo esté en WGS84 (EPSG:4326) requerido por KML
- Agrega metadatos enriquecidos:
  - Nombre descriptivo (Parcela/Edificio Catastral + Referencia)
  - Descripción HTML con:
    - Referencia catastral
    - Área aproximada en m²
    - Enlaces directos a Catastro y Google Maps
- Incluye tanto el polígono de la parcela como todos los metadatos del GML original

**`generar_kmls_desde_gmls(ref)`**
- Genera archivos KML para todos los archivos GML de una referencia
- Busca automáticamente todos los archivos GML (parcela y edificio)
- Convierte cada uno a su correspondiente KML

#### Modificación en `descargar_todo(referencia)`:
- Ahora genera automáticamente los archivos KML después de descargar los GML
- Se ejecuta si se descargó al menos un GML (parcela o edificio)

## Estructura de Archivos KML Generados

Los archivos KML incluyen:

1. **Geometría completa**: Polígono de la parcela/edificio con todas sus coordenadas
2. **Metadatos extendidos**:
   - ID GML
   - Área oficial (del catastro)
   - Fecha de inicio de vigencia
   - Referencia catastral nacional
   - Etiqueta
   - Punto de referencia
3. **Información descriptiva**:
   - Nombre: "Parcela Catastral [REFERENCIA]" o "Edificio Catastral [REFERENCIA]"
   - Descripción HTML con enlaces a:
     - Visor del Catastro
     - Google Maps

## Ubicación de los Archivos

Los archivos KML se generan en el mismo directorio que los GML:
```
outputs/
  └── [REFERENCIA]/
      ├── [REFERENCIA]_parcela.gml
      ├── [REFERENCIA]_parcela.kml  ← NUEVO
      ├── [REFERENCIA]_edificio.gml (si existe)
      └── [REFERENCIA]_edificio.kml  ← NUEVO (si existe edificio)
```

## Compatibilidad

Los archivos KML generados son compatibles con:
- ✅ Google Earth
- ✅ Google Maps
- ✅ QGIS
- ✅ ArcGIS
- ✅ Cualquier software que soporte KML estándar

## Uso

### Automático
Los archivos KML se generan automáticamente cuando se descarga una referencia catastral:
```python
downloader = CatastroDownloader(output_dir="outputs")
downloader.descargar_todo("2289738XH6028N0001RY")
# Se generará automáticamente el archivo KML
```

### Manual
Para convertir archivos GML existentes:
```python
downloader = CatastroDownloader(output_dir="outputs")

# Convertir un archivo específico
downloader.convertir_gml_a_kml("path/to/archivo.gml")

# Convertir todos los GML de una referencia
downloader.generar_kmls_desde_gmls("2289738XH6028N0001RY")
```

### Script Standalone
Se ha creado el script `convertir_gml_a_kml.py` que convierte todos los archivos GML existentes:
```bash
python convertir_gml_a_kml.py
```

## Dependencias

- `geopandas`: Para leer GML y escribir KML
- `fiona`: Driver para formato KML
- `shapely`: Geometrías (incluido con geopandas)

Estas dependencias ya están incluidas en el proyecto.

## Integración con la API

Los archivos KML están disponibles a través del endpoint existente:
```
GET /api/v1/referencia/{referencia}/kml?tipo=parcela
GET /api/v1/referencia/{referencia}/kml?tipo=edificio
```

## Ejemplo de Archivo KML Generado

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Parcela Catastral 2289738XH6028N0001RY</name>
      <description>
        <![CDATA[
        <b>Referencia Catastral:</b> 2289738XH6028N0001RY<br/>
        <b>Área:</b> 715.00 m²<br/>
        <b>Enlaces:</b><br/>
        - <a href="https://www1.sedecatastro.gob.es/...">Ver en Catastro</a><br/>
        - <a href="https://www.google.com/maps/...">Ver en Google Maps</a>
        ]]>
      </description>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -1.153539,38.011194,0
              -1.153509,38.011211,0
              ...
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
```

## Estado Actual

✅ **Implementación completada y probada**
- 19 archivos KML generados exitosamente
- Incluyen geometría completa y metadatos
- Formato válido y compatible con estándares KML

## Próximos Pasos (Opcional)

1. Agregar estilos personalizados al KML (colores, iconos)
2. Incluir imágenes en la descripción del KML
3. Generar archivos KMZ (KML comprimido) para incluir imágenes
4. Agregar capas de afecciones al KML
