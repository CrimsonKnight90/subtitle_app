# app\services\config.py
"""
Módulo de configuración global de la aplicación.
Define constantes y parámetros reutilizables.
"""

# Lista de idiomas permitidos para detección y traducción
# Usa códigos ISO 639-1 compatibles con tu traductor
ALLOWED_LANGS = ["en", "es", "fr"]

# Idioma por defecto si la detección falla o no está en la lista
DEFAULT_LANG = "en"
