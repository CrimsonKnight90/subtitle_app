# SubtitlesUp 🎬

**SubtitlesUp** es una aplicación de escritorio para **extraer y traducir subtítulos** de vídeos, con una interfaz moderna construida en **PySide6**.  
Permite trabajar con múltiples motores de traducción (Google, MyMemory, LibreTranslate, etc.) y ofrece un flujo robusto para mantener la sincronización de los subtítulos.

---

### 💖 Dedicado a mi tía Leyda

**SubtitlesUp** fue creado con mucho cariño para mi tía **Leyda Josefina Jaen Sánchez**, quien disfruta profundamente de las series, doramas y películas.  
Su pasión por el contenido internacional me inspiró a desarrollar esta herramienta, con el objetivo de facilitarle la traducción de subtítulos y permitirle disfrutar plenamente de sus historias favoritas sin barreras de idioma.  
Esta aplicación es, ante todo, un regalo para ella y para todos los que comparten ese amor por el cine y la televisión.

---

## 📑 Índice
- [🚀 Características principales](#-características-principales)
- [🌍 Idiomas soportados](#-idiomas-soportados)
- [📦 Requisitos](#-requisitos)
- [⚙️ Instalación](#️-instalación)
  - [🐍 Desde código Python](#-python)
  - [📥Desde ejecutable (.exe)](#-desde-ejecutable-exe)Desde ejecutable (.exe)
- [🎥 FFmpeg](#-ffmpeg)
- [▶️ Uso](#️-uso)
- [🛠️ Desarrollo](#️-desarrollo)
- [❗ Problemas comunes](#-problemas-comunes)
- [📜 Licencia](#-licencia)

---

## 🚀 Características principales
- Interfaz gráfica intuitiva con **PySide6**.
- Extracción de subtítulos desde vídeos `.mp4` y `.mkv`.
- Traducción automática con varios motores (Google V1, Google Free, MyMemory, LibreTranslate).
- Soporte para múltiples idiomas.
- Manejo robusto de errores y mensajes claros al usuario.
- Sistema de traducciones internas (UI multilenguaje).
- Configuración flexible de carpetas de salida.
- Logging avanzado con **loguru**.
- Distribución portable en `.exe` para Windows.

---

## 🌍 Idiomas soportados
Actualmente puedes traducir subtítulos a/desde:

- Inglés (`en`)
- Español (`es`)
- Francés (`fr`)
- Alemán (`de`)
- Coreano (`ko`)
- Chino Simplificado (`zh-CN`)
- Japonés (`ja`)
- Tailandés (`th`)
- Ruso (`ru`)
- Portugués (`pt`)
- Italiano (`it`)
- Turco (`tr`)

---

## 📦 Requisitos

- **Python 3.10+** (solo si ejecutas desde código).
- Dependencias listadas en `requirements.txt`:
  ```bash
  pip install -r requirements.txt.

---

## ⚙️ Instalación
### 🐍 Python
Clona el repositorio:

bash
git clone https://github.com/CrimsonKnight90/subtitle_app.git
cd subtitle_app
Crea un entorno virtual (recomendado):

bash
python -m venv venv

---

### 🐧 Linux /🍎 Mac
source venv/bin/activate
### 💻 Windows
venv\Scripts\activate
Instala dependencias:

bash
pip install -r requirements.txt
Ejecuta la aplicación:

bash
python main.py

## 📥 Desde ejecutable (.exe)
### Descarga

Puedes descargar la última versión ejecutable de **SubtitlesUp** aquí:

👉 [Descargar última versión](https://github.com/CrimsonKnight90/subtitle_app/releases/latest)

> El archivo `SubtitlesUp-vx.x.x.zip` contiene:
> - `SubtitlesUp.exe` → el ejecutable principal  
> - `_internal/` → carpeta con librerías necesarias  
>
> Solo necesitas descomprimir con [7-zip](https://www.7-zip.org/download.html) y hacer doble clic en `SubtitlesUp.exe`.

---

## 🎥 FFmpeg
La aplicación requiere FFmpeg para la extracción de subtítulos de vídeos. Debes descargarlo manualmente desde la página oficial:

👉 [Descargar FFmpeg](https://ffmpeg.org/download.html)

Una vez descargado, coloca los binarios en la siguiente carpeta de tu proyecto:

Código
app/vendors/ffmpeg/
Ejemplo esperado en Windows:

Código
app/vendors/ffmpeg/ffmpeg.exe
app/vendors/ffmpeg/ffplay.exe
app/vendors/ffmpeg/ffprobe.exe
⚠️ Nota: estos binarios están excluidos del repositorio mediante .gitignore.

---

## ▶️ Uso
- Abre la aplicación.

- Carga un archivo .srt o .vtt.

- Selecciona el idioma de destino.

- Haz clic en Traducir.

- Guarda el archivo traducido.

- Para extracción:

- Carga un archivo .mp4 o .mkv.

- Selecciona Extraer subtítulos.

- Obtendrás un .srt que luego puedes traducir.

## 🛠️ Desarrollo
Código organizado y modular.

Traducciones centralizadas en app/services/translations.py.

.gitignore configurado para excluir entornos virtuales, logs y binarios grandes.

Uso de loguru para logging avanzado.

Dependencias externas gestionadas en requirements.txt.

## ❗ Problemas comunes
No se encuentra FFmpeg → Instala FFmpeg y agrega la carpeta bin al PATH "app\vendors".

La traducción falla → Verifica tu conexión a internet. Ten en cuenta que los motores google_free y mymemory son más lentos que google_v1.

## 📜 Licencia
Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo [LICENSE](https://github.com/CrimsonKnight90/subtitle_app/blob/main/LICENSE) para más detalles.