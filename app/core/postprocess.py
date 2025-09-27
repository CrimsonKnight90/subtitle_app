# app/core/postprocess.py
import re
import unicodedata
from app.core.correcciones import CORRECCIONES

def aplicar_diccionario(texto: str) -> str:
    for original, corregido in CORRECCIONES.items():
        texto = texto.replace(original, corregido)
    return texto

def limpiar_formato(texto: str) -> str:
    # Espacios antes de signos de puntuación
    texto = re.sub(r"\s+([.,;:!?])", r"\1", texto)
    # Espacios dentro de etiquetas <i>
    texto = re.sub(r"<i>\s+", "<i>", texto)
    texto = re.sub(r"\s+</i>", "</i>", texto)
    # Normalizar puntos suspensivos
    texto = texto.replace(" ...", "...")
    return texto

def normalizar_unicode(texto: str) -> str:
    # Asegura que todos los acentos y ñ estén en forma estándar NFC
    return unicodedata.normalize("NFC", texto)

def postprocesar(texto: str) -> str:
    if not texto:
        return texto

    # Normalizar Unicode y limpiar espacios extremos
    texto = normalizar_unicode(texto.strip())

    # Aplicar correcciones personalizadas
    texto = aplicar_diccionario(texto)

    # Limpiar formato (espacios, puntuación, etiquetas)
    texto = limpiar_formato(texto)

    # 🔹 Normalizar saltos de línea: eliminar dobles o más
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in texto.split("\n") if line.strip()]
    texto = "\n".join(lines)

    return texto

