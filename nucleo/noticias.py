"""Noticias del mercado financiero internacional y chileno.

Se consultan las secciones de economía / finanzas / mercados de cada medio
mediante sus canales RSS oficiales. Si un medio no publica RSS (Banco Central
de Chile) o su canal no responde, se usa como respaldo Google News filtrado
por el dominio del medio («site:»), que entrega los mismos artículos con el
enlace a la nota original.

Todo queda en caché 30 minutos y lo comparten todos los visitantes.
"""

from __future__ import annotations

import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import pandas as pd
import streamlit as st

from nucleo.config import MINUTOS_CACHE_NOTICIAS, MODO_DEMO, ZONA_CHILE

TTL = MINUTOS_CACHE_NOTICIAS * 60
CABECERAS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36 webstockandtrademarket/1.0"),
    "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
}

# ----------------------------------------------------------------------------
# Fuentes: solo secciones de economía, finanzas y mercados
# ----------------------------------------------------------------------------
FUENTES = [
    {
        "id": "ft", "nombre": "Financial Times", "region": "Internacional",
        "seccion": "Markets · Global Economy", "url_seccion": "https://www.ft.com/markets",
        "feeds": ["https://www.ft.com/markets?format=rss", "https://www.ft.com/global-economy?format=rss"],
        "google": "site:ft.com markets OR economy", "idioma": "en",
    },
    {
        "id": "wsj", "nombre": "The Wall Street Journal", "region": "Internacional",
        "seccion": "Markets · Economy", "url_seccion": "https://www.wsj.com/finance",
        "feeds": ["https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
                  "https://feeds.content.dowjones.io/public/rss/socialeconomyfeed"],
        "google": "site:wsj.com markets OR economy", "idioma": "en",
    },
    {
        "id": "economist", "nombre": "The Economist", "region": "Internacional",
        "seccion": "Finance & economics", "url_seccion": "https://www.economist.com/finance-and-economics",
        "feeds": ["https://www.economist.com/finance-and-economics/rss.xml"],
        "google": "site:economist.com finance-and-economics", "idioma": "en", "dias": 7,
    },
    {
        "id": "nyt", "nombre": "The New York Times", "region": "Internacional",
        "seccion": "Business · Economy", "url_seccion": "https://www.nytimes.com/section/business/economy",
        "feeds": ["https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
                  "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"],
        "google": "site:nytimes.com economy OR markets", "idioma": "en",
    },
    {
        "id": "bbc", "nombre": "BBC News", "region": "Internacional",
        "seccion": "Business", "url_seccion": "https://www.bbc.com/news/business",
        "feeds": ["https://feeds.bbci.co.uk/news/business/rss.xml"],
        "google": "site:bbc.com/news business", "idioma": "en",
    },
    {
        "id": "yahoo", "nombre": "Yahoo Finance", "region": "Internacional",
        "seccion": "Stock market news", "url_seccion": "https://finance.yahoo.com/topic/stock-market-news/",
        "feeds": ["https://finance.yahoo.com/news/rssindex"],
        "google": "site:finance.yahoo.com stock market", "idioma": "en",
    },
    {
        "id": "df", "nombre": "Diario Financiero", "region": "Chile",
        "seccion": "Mercados · Economía y Política · Empresas", "url_seccion": "https://www.df.cl/mercados",
        "feeds": ["https://www.df.cl/noticias/site/list/port/rss.xml"],
        "filtro_url": ["mercado", "economia", "empresas", "internacional", "finanzas", "banca", "bolsa", "monedas"],
        "google": "site:df.cl mercados OR economía", "idioma": "es",
    },
    {
        "id": "bcch", "nombre": "Banco Central de Chile", "region": "Chile",
        "seccion": "Prensa y publicaciones",
        "url_seccion": "https://www.bcentral.cl/web/banco-central/noticias-y-publicaciones/prensa",
        "feeds": [],  # no publica RSS: se usa Google News filtrado por su dominio
        "google": "site:bcentral.cl", "idioma": "es", "dias": 30,
    },
    {
        "id": "mineco", "nombre": "Ministerio de Economía", "region": "Chile",
        "seccion": "Noticias", "url_seccion": "https://www.economia.gob.cl/",
        "feeds": ["https://www.economia.gob.cl/feed"],
        "google": "site:economia.gob.cl", "idioma": "es", "dias": 30,
    },
]
FUENTES_POR_ID = {f["id"]: f for f in FUENTES}

# Palabras que vuelven más relevante una nota para un sitio de mercados
CLAVES = re.compile(
    r"\b(market|markets|stock|stocks|shares|bond|bonds|yield|yields|treasur|fed|federal reserve|rate|rates|"
    r"inflation|cpi|gdp|recession|tariff|trade|dollar|currency|oil|gold|copper|earnings|investor|central bank|"
    r"ecb|economy|economic|s&p|nasdaq|dow|wall street|bitcoin|crypto|"
    r"mercado|mercados|bolsa|acciones|bonos|tasa|tasas|inflaci[oó]n|ipc|imacec|pib|d[oó]lar|cobre|litio|"
    r"banco central|tpm|econom[ií]a|inversi[oó]n|inversionistas|ipsa|aranceles|crecimiento|empleo|fiscal|"
    r"hacienda|pensiones|afp|exportaciones|deuda)\b", re.IGNORECASE)

MAX_POR_FUENTE = 4
DIAS_POR_DEFECTO = 3


# ----------------------------------------------------------------------------
# Descarga y lectura
# ----------------------------------------------------------------------------
def _limpiar_texto(texto: str, largo: int = 240) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", str(texto or "")))
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:largo].rsplit(" ", 1)[0] + "…") if len(t) > largo else t


def _fecha(entrada) -> pd.Timestamp | None:
    for campo in ("published_parsed", "updated_parsed"):
        valor = entrada.get(campo)
        if valor:
            try:
                return pd.Timestamp(datetime(*valor[:6], tzinfo=timezone.utc)).tz_convert(ZONA_CHILE)
            except Exception:
                continue
    return None


def _leer_feed(url: str):
    import feedparser
    import requests

    r = requests.get(url, headers=CABECERAS, timeout=9)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    if not feed.entries:
        raise ValueError("canal vacío")
    return feed.entries


def _url_google(consulta: str, idioma: str, dias: int) -> str:
    q = quote(f"{consulta} when:{max(1, dias)}d")
    if idioma == "es":
        return f"https://news.google.com/rss/search?q={q}&hl=es-419&gl=CL&ceid=CL:es-419"
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def _a_noticia(e, fuente: dict, via_google: bool) -> dict | None:
    titulo = _limpiar_texto(e.get("title"), 220)
    enlace = e.get("link") or ""
    if not titulo or not enlace.startswith(("http://", "https://")):
        return None
    url_visible = None
    if via_google:
        # Google News agrega « - Medio» al final del titular y redirige a la nota original
        titulo = re.sub(r"\s+[-–|]\s+[^-–|]{2,60}$", "", titulo)
        origen = (e.get("source") or {}).get("href") or ""
        url_visible = (urlparse(origen).netloc.replace("www.", "") + " · vía Google News") if origen else None
    resumen = "" if via_google else _limpiar_texto(e.get("summary") or e.get("description"), 240)
    return {
        "titulo": titulo, "url": enlace, "url_visible": url_visible, "resumen": resumen,
        "fecha": _fecha(e), "fuente": fuente["nombre"], "id_fuente": fuente["id"], "region": fuente["region"],
    }


def _relevancia(n: dict) -> float:
    edad_h = ((pd.Timestamp.now(tz=ZONA_CHILE) - n["fecha"]).total_seconds() / 3600) if n["fecha"] is not None else 96
    aciertos = len(CLAVES.findall(f"{n['titulo']} {n['resumen']}"))
    return 2.0 * min(aciertos, 3) - edad_h / 12


def _consultar_fuente(fuente: dict) -> tuple[list, str]:
    """Devuelve (noticias, estado). Estado: 'RSS oficial', 'Google News' o 'sin respuesta'."""
    dias = fuente.get("dias", DIAS_POR_DEFECTO)
    limite = pd.Timestamp.now(tz=ZONA_CHILE) - pd.Timedelta(days=dias)
    notas, estado = [], "sin respuesta"
    for url in fuente.get("feeds", []):
        try:
            for e in _leer_feed(url):
                n = _a_noticia(e, fuente, via_google=False)
                if n:
                    notas.append(n)
            estado = "RSS oficial"
        except Exception:
            continue
    filtro = fuente.get("filtro_url")
    if filtro and notas:
        filtradas = [n for n in notas if any(p in urlparse(n["url"]).path.lower() for p in filtro)]
        notas = filtradas or notas
    recientes = [n for n in notas if n["fecha"] is None or n["fecha"] >= limite]
    if not recientes and fuente.get("google"):
        try:
            for e in _leer_feed(_url_google(fuente["google"], fuente.get("idioma", "en"), dias)):
                n = _a_noticia(e, fuente, via_google=True)
                if n and (n["fecha"] is None or n["fecha"] >= limite):
                    recientes.append(n)
            estado = "Google News" if recientes else estado
        except Exception:
            pass
    vistos, unicas = set(), []
    for n in sorted(recientes, key=_relevancia, reverse=True):
        clave = n["titulo"].lower()[:90]
        if clave not in vistos:
            vistos.add(clave)
            unicas.append(n)
    if not unicas and estado != "sin respuesta":
        estado = "sin notas recientes"
    return unicas[:MAX_POR_FUENTE], estado


def _demo() -> dict:
    ahora = pd.Timestamp.now(tz=ZONA_CHILE)
    temas = ["Las bolsas cierran mixtas a la espera de datos de inflación",
             "El dólar retrocede frente a las principales monedas",
             "Rendimiento de los bonos del Tesoro sube tras nuevas cifras de empleo",
             "El cobre avanza por mayor demanda desde China"]
    notas = []
    for i, f in enumerate(FUENTES):
        for j in range(2):
            notas.append({"titulo": f"[Demo] {temas[(i + j) % len(temas)]}", "url": f["url_seccion"],
                          "url_visible": None, "resumen": "Texto de demostración: el modo DEMO no consulta internet.",
                          "fecha": ahora - pd.Timedelta(minutes=23 * i + 70 * j), "fuente": f["nombre"],
                          "id_fuente": f["id"], "region": f["region"]})
    return {"noticias": sorted(notas, key=lambda n: n["fecha"], reverse=True),
            "estado": {f["id"]: "demo" for f in FUENTES}, "hora": ahora}


@st.cache_data(ttl=TTL, show_spinner=False)
def obtener_noticias() -> dict:
    """Noticias de todas las fuentes, ordenadas de la más reciente a la más antigua."""
    if MODO_DEMO:
        return _demo()
    with ThreadPoolExecutor(max_workers=len(FUENTES)) as ex:
        resultados = list(ex.map(_consultar_fuente, FUENTES))
    notas, estado = [], {}
    for fuente, (lista, est) in zip(FUENTES, resultados):
        notas.extend(lista)
        estado[fuente["id"]] = est
    minimo = pd.Timestamp("1970-01-01", tz=ZONA_CHILE)
    notas.sort(key=lambda n: n["fecha"] if n["fecha"] is not None else minimo, reverse=True)
    if not notas:
        raise RuntimeError("ninguna fuente respondió")
    return {"noticias": notas, "estado": estado, "hora": pd.Timestamp.now(tz=ZONA_CHILE)}


_ULTIMO_OK: dict = {}


def noticias() -> tuple[dict | None, str | None]:
    """(datos, aviso). Si todas las fuentes fallan se muestra la última lectura exitosa."""
    try:
        datos = obtener_noticias()
        _ULTIMO_OK["datos"] = datos
        return datos, None
    except Exception:
        if "datos" in _ULTIMO_OK:
            return _ULTIMO_OK["datos"], "Las fuentes de noticias no respondieron; se muestra la última lectura disponible."
        return None, "No fue posible conectar con las fuentes de noticias en este momento. Se reintentará automáticamente."
