<div align="center">

<h1>Equivalencias para planes de estudio</h1>

<p>Completa automáticamente un plan de estudios RTF con las equivalencias aprobadas encontradas en una ficha curricular PDF.</p>

<a href="https://bravoisaac.github.io/proyecto_Certificado_Plan_Estudios/">
  <img src="https://img.shields.io/badge/ABRIR_LA_APLICACIÓN-047857?style=for-the-badge&logo=googlechrome&logoColor=white" height="56" alt="Abrir la aplicación" />
</a>

<br /><br />

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-activo-2ea44f?logo=github)](https://bravoisaac.github.io/proyecto_Certificado_Plan_Estudios/)
[![Backend](https://img.shields.io/badge/Backend-Render-46E3B7?logo=render&logoColor=000)](https://equivalencias-plan-estudios.onrender.com/)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)

</div>

![Pantalla principal de Equivalencias para planes de estudio](./output/playwright/readme/app-inicio.png)

## ¿Qué hace la aplicación?

La herramienta recibe dos documentos:

- Una ficha curricular en formato `.pdf`.
- Un plan de estudios de Word en formato `.rtf`.

Lee las asignaturas del PDF, conserva únicamente las equivalencias aprobadas y agrega cada una dentro de la ficha correspondiente del RTF. El documento original no se modifica: el navegador descarga una copia nueva con el sufijo `_con_equivalencias.rtf`.

## Flujo de trabajo

1. Carga la ficha curricular PDF.
2. Carga el plan de estudios RTF vacío.
3. Presiona **Analizar equivalencias**.
4. Revisa, corrige o desmarca los resultados.
5. Presiona **Generar Word completado**.

![Panel de revisión de equivalencias detectadas](./output/playwright/readme/app-equivalencias.png)

## Reglas de procesamiento

Para una oportunidad como:

```text
1 2020/2 6.4 A
RTR20188
LENGUA DE SEÑAS
```

la aplicación descarta intento, periodo, nota y estado, y escribe en el RTF:

```text
EQUIVALENTE: RTR20188 LENGUA DE SEÑAS
```

- Solo se incluyen oportunidades con estado aprobado `A`.
- Primero se busca la asignatura por código exacto.
- Si el plan utiliza otro código, se busca de forma segura por el nombre normalizado.
- Las coincidencias ambiguas no se insertan automáticamente.
- Las asignaturas sin ficha editable se agrupan al final para evitar pérdidas.

## Privacidad y límites

- Los documentos se procesan en memoria y no se guardan en una base de datos.
- En GitHub Pages, los archivos se envían al backend de Render únicamente para procesar la solicitud.
- PDF máximo: 20 MB.
- RTF máximo: 25 MB.
- Solicitud completa máxima: 50 MB.
- Algunos PDF pueden contener caracteres Unicode incompletos; la interfaz permite corregir los nombres antes de generar el documento.

## Ejecutar la aplicación de escritorio en Windows

### Opción recomendada: usar el ejecutable

La aplicación es portable: no requiere instalación ni necesita que Python esté instalado.

1. Abre la carpeta `dist`.
2. Haz doble clic en `EquivalenciasPlanEstudios.exe`.
3. Selecciona el PDF y el archivo RTF desde la ventana de la aplicación.
4. Cierra la ventana cuando termines.

```text
dist\EquivalenciasPlanEstudios.exe
```

Puedes copiar ese único archivo `.exe` al escritorio, a otra carpeta, a un pendrive o a otro computador con Windows 10/11.

> [!NOTE]
> Los documentos se procesan localmente. La aplicación abre un servicio privado en `127.0.0.1`, elige automáticamente un puerto libre y lo cierra junto con la ventana.

### Advertencia de Windows SmartScreen

Como el ejecutable no tiene una firma digital comercial, Windows puede mostrar el mensaje **Windows protegió su PC** la primera vez que se abre.

1. Selecciona **Más información**.
2. Verifica que el archivo se llame `EquivalenciasPlanEstudios.exe`.
3. Selecciona **Ejecutar de todas formas**.

La ventana utiliza Microsoft Edge WebView2, incluido normalmente en Windows 10 y Windows 11. Si la ventana no abre, instala o repara [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/).

## Compilar el ejecutable en Windows

Esta sección es solamente para desarrolladores que hayan modificado el proyecto y necesiten generar un `.exe` nuevo.

### Requisitos de compilación

- Windows 10 u 11.
- Python 3.10 o superior.
- Conexión a Internet durante la primera compilación.

Desde PowerShell, en la carpeta raíz del proyecto, ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

El script crea un entorno aislado en `.venv-build`, instala las dependencias y genera:

```text
dist\EquivalenciasPlanEstudios.exe
```

## Ejecutar desde el código fuente

Si no quieres usar el ejecutable, puedes iniciar la versión local con `iniciar_app.bat`. En el primer inicio se crea el entorno virtual y se instalan las dependencias.

También puedes iniciarla manualmente:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python server.py
```

Después abre [http://127.0.0.1:8000](http://127.0.0.1:8000). No cierres la terminal mientras estés utilizando la aplicación.

## Arquitectura y despliegue

```text
GitHub Pages (interfaz estática)
              │
              ▼
Render (API Python en memoria)
              │
              ▼
RTF completado descargado por el navegador
```

- `index.html` y `static/` forman la interfaz publicada por GitHub Pages.
- `server.py` expone los endpoints de análisis y generación.
- `desktop.py` abre la aplicación local dentro de una ventana de escritorio.
- `build_desktop.ps1` genera el ejecutable autónomo para Windows.
- `core/pdf_extractor.py` extrae las equivalencias del PDF.
- `core/rtf_editor.py` inserta las equivalencias conservando el formato RTF.
- `render.yaml` configura el backend desplegado en Render.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

Las pruebas cubren la extracción de equivalencias aprobadas, la reparación de texto, la búsqueda por código o nombre y la inserción dentro de las fichas del RTF.

## Estructura

```text
core/
  pdf_extractor.py       Extracción y filtrado desde PDF
  rtf_editor.py          Edición del RTF
static/
  app.js                 Interacción y consumo de la API
  styles.css             Diseño responsive
tests/                   Pruebas unitarias
index.html               Entrada web y GitHub Pages
server.py                Servidor HTTP y validaciones
desktop.py               Entrada de la aplicación de escritorio
build_desktop.ps1        Empaquetado del ejecutable de Windows
render.yaml              Configuración del backend
```

---

<div align="center">
  <a href="https://bravoisaac.github.io/proyecto_Certificado_Plan_Estudios/"><strong>Abrir Equivalencias para planes de estudio</strong></a>
</div>
