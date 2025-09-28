# SubtitlesUp 🎬

**SubtitlesUp** es una aplicación de escritorio para **extraer y traducir subtítulos** de vídeos, con una interfaz moderna construida en **PySide6**.  
Permite trabajar con múltiples motores de traducción (Google, MyMemory, LibreTranslate, etc.) y ofrece un flujo robusto para mantener la sincronización de los subtítulos.

---

## 🚀 Características principales
- Interfaz gráfica intuitiva con PySide6.
- Extracción de subtítulos desde vídeos.
- Traducción automática con varios motores.
- Soporte para múltiples idiomas.
- Manejo de errores y mensajes claros al usuario.
- Sistema de traducciones internas (UI multilenguaje).
- Configuración flexible de carpetas de salida.
- Logging avanzado con **loguru**.

---

## 📦 Requisitos

- **Python 3.10+**
- Dependencias listadas en `requirements.txt`:
  ```bash
  pip install -r requirements.txt
⚙️ Instalación
Clona el repositorio:

bash
git clone https://github.com/CrimsonKnight90/subtitle_app.git
cd subtitle_app
Crea un entorno virtual (recomendado):

bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows
Instala dependencias:

bash
pip install -r requirements.txt
🎥 FFmpeg
La aplicación requiere FFmpeg para la extracción de audio/vídeo. Debes descargarlo manualmente desde la página oficial:

👉 Descargar FFmpeg

Una vez descargado, coloca los binarios en la siguiente carpeta de tu proyecto:

Código
app/vendors/ffmpeg/
Ejemplo esperado en Windows:

Código
app/vendors/ffmpeg/ffmpeg.exe
app/vendors/ffmpeg/ffplay.exe
app/vendors/ffmpeg/ffprobe.exe
⚠️ Nota: estos binarios están excluidos del repositorio mediante .gitignore.

▶️ Uso
Ejecuta la aplicación con:

bash
python main.py

🛠️ Desarrollo
Código organizado y modular.

Traducciones centralizadas en app/services/translations.py.

.gitignore configurado para excluir entornos virtuales, logs y binarios grandes.

Uso de loguru para logging avanzado.

Dependencias externas gestionadas en requirements.txt.

📜 Licencia
Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo LICENSE para más detalles.