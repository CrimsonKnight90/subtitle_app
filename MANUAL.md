Manual de Usuario – SubtitlesUp
🎯 Público objetivo
Este manual está pensado para cualquier persona, tanto usuarios sin conocimientos técnicos que solo quieren traducir subtítulos, como desarrolladores que deseen ejecutar el proyecto desde código Python.

🚀 Funcionalidades principales
Traducción de subtítulos en formatos .srt y .vtt.

Idiomas soportados actualmente:

Inglés (en)

Español (es)

Francés (fr)

Alemán (de)

Coreano (ko)

Chino Simplificado (zh-CN)

Japonés (ja)

Tailandés (th)

Ruso (ru)

Portugués (pt)

Italiano (it)

Turco (tr)

Extracción de subtítulos desde archivos de video .mp4 y .mkv.

Interfaz gráfica moderna con temas claro/oscuro.

Empaquetado en .exe portable para Windows.

📥 Instalación y ejecución
Opción 1: Ejecutar desde código Python
Clonar el repositorio:

bash
git clone https://github.com/CrimsonKnight90/subtitle_app.git
cd subtitle_app
Crear entorno virtual e instalar dependencias:

bash
python -m venv venv
venv\Scripts\activate   # en Windows
pip install -r requirements.txt
Ejecutar la aplicación:

bash
python main.py
Opción 2: Ejecutar desde el .exe
Descarga el ejecutable desde la sección Releases en GitHub.

Haz doble clic en SubtitlesUp.exe para abrir la aplicación.

No requiere instalación adicional.

⚙️ Requisitos previos
Python 3.10+ (solo si corres desde código).

Windows 10/11 para el ejecutable.

FFmpeg:

No se incluye en el proyecto.

Si deseas usar la función de extracción de subtítulos de videos, debes instalar FFmpeg y asegurarte de que esté en el PATH "app\vendors".

🛠️ Uso básico
Abre la aplicación.

Carga un archivo .srt o .vtt desde el menú.

Selecciona el idioma de destino.

Haz clic en Traducir.

Guarda el archivo traducido.

Para extracción:

Carga un archivo .mp4 o .mkv.

Selecciona Extraer subtítulos.

El programa generará un .srt que luego puedes traducir.

❗ Resolución de problemas comunes
No se encuentra FFmpeg → Instala FFmpeg desde https://ffmpeg.org/download.html y agrega la carpeta bin al PATH "app\vendors".

La traducción falla → Verifica tu conexión a internet. → Ten en cuenta que los motores google_free y mymemory son más lentos que google_v1.

📜 Licencia
Este proyecto está bajo licencia MIT. Consulta el archivo LICENSE para más detalles.

👨‍💻 Créditos
Desarrollado por CrimsonKnight90. Contribuciones y mejoras son bienvenidas en el repositorio oficial.