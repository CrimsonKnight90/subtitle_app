import re

# Diccionario de correcciones personalizadas
CORRECCIONES = {
    "Llevan temprano": "Han llegado temprano",
    "código de liquidación": "código de acceso",
    "Luchador TIE": "TIE Fighter",
    "Capitán ...": "capitán..."
}

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

def postprocesar(texto: str) -> str:
    return limpiar_formato(aplicar_diccionario(texto))
