# parser-rem

Utilidad para analizar datos REM (archivos HTML disfrazados como XLS), normalizarlos en un DataFrame en formato “tidy”, geocodificar establecimientos y exportar tanto un mapa en HTML (con marcadores agrupados) como un archivo CSV.

## Características
- Lectura de la primera tabla del archivo proporcionado (REM-YYYY.xls con contenido HTML).
- Segmentación por bloques utilizando filas separadoras “OTRAS”.
- Extracción de nombres de establecimientos y geocodificación opcional mediante Google Maps.
- Normalización de categorías a partir de `categories.py`, con sanitización de cadenas para mayor robustez.
- Exportación de un mapa Folium con MarkerCluster y de un archivo CSV con los datos normalizados.

## Requisitos
- Python 3.9+
- Paquetes:
  - pandas
  - numpy
  - folium
  - python-dotenv
  - googlemaps (opcional; si no hay API Key, la geocodificación se omite)

### Instalación sugerida
```bash
python -m venv .venv
source .venv/bin/activate
pip install pandas numpy folium python-dotenv googlemaps
```

## Configuración
Cree un archivo `.env` en la raíz del proyecto con el siguiente contenido si desea habilitar geocodificación:
```
GOOGLE_MAPS_API_KEY=su_clave_aqui
```
Si no se proporciona clave, la geocodificación se omite y las coordenadas quedarán en `None`.

Asegúrese de contar con un archivo `categories.py` que defina el diccionario `CATEGORIES` (mapeo de tuplas a categorías). Este proyecto ya lo incluye como referencia.

## Uso
### Desde el script proporcionado
Ejecute:
```bash
python test.py
```
Esto generará, a modo de ejemplo:
- `output_2020.csv` y `output_2020.html`
- `output_2019.csv` y `output_2019.html`

### Uso programático (API)
```python
from parser import RemParser

parser = RemParser("REM-2020.xls")
parser.export_csv("output_2020.csv")
parser.export_map("output_2020.html")

parser = RemParser("REM-2019.xls")
parser.export_csv("output_2019.csv")
parser.export_map("output_2019.html")
```

## API de RemParser
Constructor:
- `RemParser(file_path: str, country_suffix: str = ", Chile")`
  - Lee el archivo, separa bloques, intenta geocodificar establecimientos (si hay API Key) y construye el DataFrame final.

Atributos públicos:
- `df_formatted: pandas.DataFrame` con las columnas:
  - `[gender, age_group, location, latitude, longitude, category, subcategory, factor, subtype]`

Métodos públicos:
- `export_csv(output_csv: str = "data.csv")`
  - Exporta el DataFrame normalizado en formato CSV (UTF-8, sin índice).
- `export_map(output_html: str = "map.html", center=None, zoom_start: int = 13, max_zoom: int = 19, disable_clustering_at_zoom: int = 19)`
  - Genera un mapa HTML con Folium y marcadores agrupados (MarkerCluster).
  - Si `center` es `None` y existen coordenadas, centra el mapa en el promedio de latitud/longitud; de lo contrario, utiliza un centro por defecto.
  - Las filas sin coordenadas válidas no se incluyen en el mapa.

## Notas y consideraciones
- El archivo REM se procesa como HTML mediante `pandas.read_html`, aunque tenga extensión `.xls`.
- La separación en bloques usa filas donde las dos primeras columnas son “OTRAS”. Cada bloque representa un establecimiento u otro agrupador.
- La geocodificación con Google Maps es opcional; si no hay API Key, las coordenadas permanecerán `None`.
- El mapa utiliza `MarkerCluster` para mostrar correctamente puntos superpuestos; puede ajustar `disableClusteringAtZoom` y `max_zoom` según el proveedor de “tiles”.
- Los conteos en celdas se expanden a filas individuales para un formato “tidy”. Esto facilita análisis a costa de mayor tamaño en memoria; tenga en cuenta la posible implicación de rendimiento en conjuntos de datos grandes.
- El mapeo de categorías depende de `categories.py`. Existen rutinas de sanitización de cadenas para reducir inconsistencias (espacios no separables, paréntesis de ancho completo, etc.).

## Estructura de salida esperada
- CSV: columnas `[gender, age_group, location, latitude, longitude, category, subcategory, factor, subtype]`.
- HTML: archivo con mapa interactivo (Folium) centrado según datos o centro especificado, con marcadores agrupados.


