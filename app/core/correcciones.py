# app/core/correcciones.py

# Diccionario de reemplazos comunes (reemplazo literal)
CORRECCIONES = {
    " ,": ",",
    " .": ".",
    " !": "!",
    " ?": "?",
    " :": ":",
    " ;": ";",
    "¿ ": "¿",
    "¡ ": "¡",
    "  ": " ",  # espacios dobles
    "senor": "señor",
    "pateticos": "patéticos",
    "Llevan temprano": "Han llegado temprano",
    "código de liquidación": "código de acceso",
    "Luchador TIE": "TIE Fighter",
    "Capitán ...": "capitán...",
}

# Opcional: reglas basadas en regex (más flexibles)
REGEX_CORRECCIONES = [
    (r"\bSenor\b", "Señor"),  # solo corrige "Senor" como palabra completa
    (r"\bPateticos\b", "Patéticos"),
]
