"""Configuración general."""

import os
from zoneinfo import ZoneInfo

ZONA_CHILE = ZoneInfo("America/Santiago")

# Modo demostración: genera datos sintéticos en vez de consultar Yahoo.
# Solo sirve para probar la página sin internet: export WSTM_DEMO=1
MODO_DEMO = os.environ.get("WSTM_DEMO", "0") == "1"

# Minutos que se guardan en memoria los datos descargados (evita bloqueos de Yahoo)
MINUTOS_CACHE_PRECIOS = 30
MINUTOS_CACHE_NOTICIAS = 30   # las noticias se renuevan cada 30 minutos

# Nombre(s) de los autores que aparecen en el pie de página y en «Acerca de».
# Ejemplo: AUTORES = "Martina Anabalón y Pablo Emilio …"  (déjalo vacío para no mostrar)
AUTORES = ""
