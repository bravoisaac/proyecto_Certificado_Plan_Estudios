# Equivalencias para planes de estudio

Aplicación web local que lee una ficha curricular en PDF, identifica las equivalencias aprobadas y las agrega bajo la asignatura correspondiente en un plan de estudios de Word en formato RTF.

## Regla implementada

Para una celda como:

```text
1 2020/2 6.4 A
RTR20188
LENGUA DE SEÑAS
```

la aplicación descarta intento, periodo, nota y estado. En el RTF escribe:

```text
EQUIVALENTE: RTR20188 LENGUA DE SEÑAS
```

Las oportunidades con estado distinto de `A` no se agregan. Si una asignatura no tiene texto después de su línea de oportunidad, no se genera equivalencia.

## Ejecutar en Windows

La forma más simple es hacer doble clic en `iniciar_app.bat`. En el primer inicio se crea el entorno y se instala la dependencia; después se abre la aplicación en el navegador.

También puede iniciarla manualmente:

1. Abra PowerShell dentro de esta carpeta.
2. Cree y active un entorno virtual:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Instale la dependencia:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Inicie la aplicación:

   ```powershell
   python server.py
   ```

5. Abra [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Uso

1. Cargue la ficha curricular `.pdf`.
2. Cargue el plan de estudios vacío `.rtf`.
3. Pulse **Analizar equivalencias**.
4. Revise o corrija los nombres detectados.
5. Pulse **Generar Word completado**.

El navegador descargará una copia con el sufijo `_con_equivalencias.rtf`; el archivo original no se modifica.

Las equivalencias cuya asignatura no tenga una ficha editable en el RTF se
incluyen al final del Word, agrupadas bajo el título **Equivalencias sin ficha
editable**, para que ninguna selección se pierda.

## Privacidad y límites

- El servidor escucha solo en `127.0.0.1`.
- Los archivos se procesan en memoria y no se guardan en disco.
- Límites: 20 MB para PDF, 25 MB para RTF y 50 MB por solicitud.
- Algunos PDF no incluyen información Unicode completa para las letras acentuadas. La app repara vocabulario académico frecuente y marca los casos restantes para revisión manual.
- El editor busca las fichas de asignatura con la geometría del RTF de ejemplo (`posx1587` para el título y `posx732` para el código). Otros diseños de RTF pueden necesitar un adaptador.

## Despliegue en Render

El repositorio incluye `render.yaml` para publicarlo como un servicio web Python:

1. En Render, cree un **Blueprint** desde este repositorio de GitHub.
2. Render instalará `requirements.txt` y ejecutará `python server.py`.
3. La variable `HOST=0.0.0.0` y el puerto proporcionado por Render se configuran automáticamente.

El servicio no necesita base de datos ni disco persistente: los documentos se procesan únicamente en memoria.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

## Estructura

```text
core/pdf_extractor.py  extracción y filtrado de equivalencias
core/rtf_editor.py     inserción conservando el RTF original
server.py              servidor HTTP local y validación de archivos
static/                interfaz web responsive
tests/                 pruebas unitarias de reglas críticas
```
