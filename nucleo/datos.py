"""Descarga de datos desde Yahoo Finance.

Tres capas de protección para que la página no se caiga:
1. Caché: cada consulta se guarda unos minutos y la comparten todos los
   visitantes (tú y tu amigo no duplican descargas).
2. Reintentos con espera si Yahoo limita las consultas.
3. Último dato bueno: si Yahoo falla, se muestra la última descarga exitosa
   con un aviso, en vez de romper la página.
"""

from __future__ import annotations

import time
import zlib
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from nucleo.config import MINUTOS_CACHE_NOTICIAS, MINUTOS_CACHE_PRECIOS, MODO_DEMO, ZONA_CHILE

TTL_PRECIOS = MINUTOS_CACHE_PRECIOS * 60
TTL_NOTICIAS = MINUTOS_CACHE_NOTICIAS * 60
_ULTIMO_OK: dict = {}  # respaldo en memoria del proceso: clave -> resultado


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def _reintentar(funcion, intentos: int = 3, espera: float = 2.0):
    ultimo = None
    for i in range(intentos):
        try:
            return funcion()
        except Exception as e:  # incluye YFRateLimitError
            ultimo = e
            time.sleep(espera * (2 ** i))
    raise ultimo


def _con_respaldo(clave, funcion):
    """Ejecuta funcion(); si falla, devuelve el último resultado bueno."""
    try:
        resultado = funcion()
        _ULTIMO_OK[clave] = resultado
        return resultado, None
    except Exception as e:
        if clave in _ULTIMO_OK:
            return _ULTIMO_OK[clave], "Yahoo Finance no respondió; se muestran los últimos datos disponibles."
        return None, f"No se pudieron obtener datos de Yahoo Finance ({type(e).__name__}). Intenta de nuevo en unos minutos."


def _lotes(lista, n):
    for i in range(0, len(lista), n):
        yield lista[i:i + n]


def _limpiar(tickers) -> tuple:
    vistos = []
    for t in tickers:
        if t is None:
            continue
        t = str(t).strip().upper()
        if t and t not in vistos:
            vistos.append(t)
    return tuple(vistos)


def hora_chile() -> str:
    return datetime.now(ZONA_CHILE).strftime("%d-%m-%Y %H:%M")


# ----------------------------------------------------------------------------
# Datos sintéticos (solo modo demostración)
# ----------------------------------------------------------------------------
def _dias_periodo(periodo: str | None, inicio) -> int:
    if inicio is not None:
        return max(5, (pd.Timestamp.today().normalize() - pd.Timestamp(inicio)).days)
    tabla = {"5d": 7, "1mo": 31, "3mo": 92, "6mo": 183, "1y": 366, "2y": 731,
             "5y": 1827, "10y": 3653, "max": 3653}
    return tabla.get(periodo or "1y", 366)


def _serie_demo(ticker: str, dias: int) -> pd.DataFrame:
    rng = np.random.default_rng(zlib.crc32(ticker.encode()))
    if ticker == "^IRX":  # tasa en % anual, no un precio
        fechas = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=max(5, int(dias * 5 / 7)))
        tasa = np.clip(4 + np.cumsum(rng.normal(0, 0.02, len(fechas))), 0.5, 6)
        return pd.DataFrame({"Open": tasa, "High": tasa, "Low": tasa, "Close": tasa, "Volume": 0}, index=fechas)
    cripto = ticker.endswith("-USD")
    fechas = pd.date_range(end=pd.Timestamp.today().normalize(), periods=dias, freq="D")
    if not cripto:
        fechas = fechas[fechas.dayofweek < 5]
    n = len(fechas)
    vol = rng.uniform(0.55, 0.9) if cripto else rng.uniform(0.12, 0.45)
    mu = rng.uniform(-0.1, 0.35)
    if ticker in ("TLT", "IEF", "SHY", "LQD", "TIP", "BND"):
        vol, mu = rng.uniform(0.04, 0.15), rng.uniform(0.0, 0.05)
    paso = 1 / (365 if cripto else 252)
    # componente de mercado común para generar correlaciones realistas
    rng_m = np.random.default_rng(12345)
    mercado = rng_m.normal(0, 1, 6000)[-n:]
    beta = 0 if ticker in ("TLT", "IEF", "SHY", "TIP") else rng.uniform(0.4, 1.4)
    choque = 0.6 * beta * mercado + np.sqrt(max(1 - (0.6 * beta) ** 2, 0.2)) * rng.normal(0, 1, n)
    log_r = (mu - vol ** 2 / 2) * paso + vol * np.sqrt(paso) * choque
    precio = rng.uniform(20, 500) * np.exp(np.cumsum(log_r))
    alto = precio * (1 + np.abs(rng.normal(0, vol * np.sqrt(paso) / 2, n)))
    bajo = precio * (1 - np.abs(rng.normal(0, vol * np.sqrt(paso) / 2, n)))
    apertura = np.r_[precio[0], precio[:-1]]
    return pd.DataFrame({"Open": apertura, "High": np.maximum.reduce([alto, precio, apertura]),
                         "Low": np.minimum.reduce([bajo, precio, apertura]), "Close": precio,
                         "Volume": rng.integers(1e5, 1e7, n)}, index=fechas)


# ----------------------------------------------------------------------------
# Precios
# ----------------------------------------------------------------------------
def _extraer_cierres(df: pd.DataFrame, lote) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        nivel0 = df.columns.get_level_values(0)
        if "Close" in nivel0:
            cierres = df["Close"]
        else:  # agrupado por ticker
            cierres = df.xs("Close", axis=1, level=1)
    else:
        cierres = df[["Close"]].rename(columns={"Close": lote[0]})
    if isinstance(cierres, pd.Series):
        cierres = cierres.to_frame(lote[0])
    cierres.index = pd.to_datetime(cierres.index).tz_localize(None) if cierres.index.tz is not None else pd.to_datetime(cierres.index)
    return cierres.dropna(how="all", axis=1)


@st.cache_data(ttl=TTL_PRECIOS, show_spinner=False, max_entries=64)
def _descargar_cierres(tickers: tuple, periodo: str | None, inicio: str | None) -> pd.DataFrame:
    if MODO_DEMO:
        dias = _dias_periodo(periodo, inicio)
        return pd.DataFrame({t: _serie_demo(t, dias)["Close"] for t in tickers})
    partes = []
    for lote in _lotes(list(tickers), 100):
        kwargs = dict(interval="1d", auto_adjust=True, progress=False, threads=True)
        if inicio:
            kwargs["start"] = inicio
        else:
            kwargs["period"] = periodo or "1y"
        df = _reintentar(lambda: yf.download(lote, **kwargs))
        partes.append(_extraer_cierres(df, lote))
    resultado = pd.concat(partes, axis=1) if partes else pd.DataFrame()
    resultado = resultado.loc[:, ~resultado.columns.duplicated()].sort_index()
    if resultado.empty:
        raise ValueError("Yahoo devolvió una tabla vacía")
    return resultado


def precios_cierre(tickers, periodo: str | None = "1y", inicio=None):
    """Cierres ajustados (columnas = tickers). Devuelve (DataFrame, aviso)."""
    tickers = _limpiar(tickers)
    if not tickers:
        return pd.DataFrame(), "No hay tickers para consultar."
    inicio_txt = pd.Timestamp(inicio).strftime("%Y-%m-%d") if inicio is not None else None
    df, aviso = _con_respaldo(("cierres", tickers, periodo, inicio_txt),
                              lambda: _descargar_cierres(tickers, periodo, inicio_txt))
    if df is None:
        return pd.DataFrame(), aviso
    faltan = [t for t in tickers if t not in df.columns]
    if faltan and not aviso:
        aviso = "Sin datos en Yahoo para: " + ", ".join(faltan[:15]) + ("…" if len(faltan) > 15 else "")
    return df, aviso


@st.cache_data(ttl=TTL_PRECIOS, show_spinner=False, max_entries=64)
def _descargar_ohlc(ticker: str, periodo: str) -> pd.DataFrame:
    if MODO_DEMO:
        return _serie_demo(ticker, _dias_periodo(periodo, None))
    df = _reintentar(lambda: yf.download(ticker, period=periodo, interval="1d",
                                         auto_adjust=True, progress=False))
    if df is None or df.empty:
        raise ValueError("sin datos")
    if isinstance(df.columns, pd.MultiIndex):
        df = df.xs(ticker, axis=1, level=1) if ticker in df.columns.get_level_values(1) else df.droplevel(1, axis=1)
    df.index = pd.to_datetime(df.index).tz_localize(None) if df.index.tz is not None else pd.to_datetime(df.index)
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])


def precios_ohlc(ticker: str, periodo: str = "2y"):
    """Velas (apertura, máximo, mínimo, cierre, volumen). Devuelve (DataFrame, aviso)."""
    ticker = str(ticker).strip().upper()
    df, aviso = _con_respaldo(("ohlc", ticker, periodo), lambda: _descargar_ohlc(ticker, periodo))
    return (df if df is not None else pd.DataFrame()), aviso


# ----------------------------------------------------------------------------
# Ganadores y perdedores del día (screener oficial de Yahoo)
# ----------------------------------------------------------------------------
@st.cache_data(ttl=TTL_NOTICIAS, show_spinner=False)
def _screener(nombre: str, cantidad: int) -> pd.DataFrame:
    if MODO_DEMO:
        rng = np.random.default_rng(len(nombre))
        signo = 1 if "gainers" in nombre else -1
        return pd.DataFrame({
            "Ticker": [f"DEMO{i}" for i in range(cantidad)],
            "Nombre": [f"Empresa demo {i}" for i in range(cantidad)],
            "Precio": rng.uniform(5, 300, cantidad),
            "Var. %": signo * rng.uniform(2, 25, cantidad),
            "Volumen": rng.integers(1e5, 1e8, cantidad),
        }).sort_values("Var. %", ascending=signo < 0).reset_index(drop=True)
    datos = _reintentar(lambda: yf.screen(nombre, count=cantidad))
    filas = []
    for q in (datos or {}).get("quotes", []):
        filas.append({
            "Ticker": q.get("symbol"),
            "Nombre": q.get("shortName") or q.get("longName") or q.get("symbol"),
            "Precio": q.get("regularMarketPrice"),
            "Var. %": q.get("regularMarketChangePercent"),
            "Volumen": q.get("regularMarketVolume"),
        })
    df = pd.DataFrame(filas)
    if df.empty:
        raise ValueError("screener vacío")
    return df.sort_values("Var. %", ascending="losers" in nombre).reset_index(drop=True)


def movimientos_del_dia(cantidad: int = 15):
    """Mayores alzas y caídas del día en todo el mercado de EE.UU. según Yahoo."""
    sube, aviso1 = _con_respaldo(("scr", "day_gainers"), lambda: _screener("day_gainers", cantidad))
    baja, aviso2 = _con_respaldo(("scr", "day_losers"), lambda: _screener("day_losers", cantidad))
    return sube, baja, aviso1 or aviso2


# ----------------------------------------------------------------------------
# Búsqueda de tickers, capitalización y tasa libre de riesgo
# ----------------------------------------------------------------------------
@st.cache_data(ttl=60 * 60, show_spinner=False)
def buscar_ticker(texto: str) -> pd.DataFrame:
    """Busca tickers en Yahoo por nombre (p. ej. 'oro', 'tesla', 'bitcoin')."""
    if MODO_DEMO:
        return pd.DataFrame({"Ticker": [texto.upper()], "Nombre": [f"{texto} (demo)"],
                             "Tipo": ["EQUITY"], "Bolsa": ["DEMO"]})
    try:
        resultado = yf.Search(texto, max_results=10, news_count=0).quotes
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame([{
        "Ticker": q.get("symbol"), "Nombre": q.get("shortname") or q.get("longname"),
        "Tipo": q.get("quoteType"), "Bolsa": q.get("exchDisp") or q.get("exchange"),
    } for q in resultado if q.get("symbol")])


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def capitalizaciones(tickers: tuple) -> dict:
    """Capitalización de mercado (USD) de cada activo cuando Yahoo la informa."""
    caps = {}
    for t in tickers:
        if MODO_DEMO:
            caps[t] = float(np.random.default_rng(zlib.crc32(t.encode())).uniform(5e10, 3e12))
            continue
        try:
            valor = yf.Ticker(t).fast_info.get("marketCap")
            if valor and np.isfinite(valor) and valor > 0:
                caps[t] = float(valor)
        except Exception:
            continue
    return caps


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def tasa_libre_riesgo() -> float:
    """Rendimiento anual de la letra del Tesoro a 13 semanas (^IRX). Respaldo: 4%."""
    if MODO_DEMO:
        return 0.04
    try:
        df = yf.download("^IRX", period="1mo", progress=False, auto_adjust=False)
        valor = float(np.asarray(df["Close"]).ravel()[-1]) / 100
        if 0 <= valor < 0.2:
            return valor
    except Exception:
        pass
    return 0.04


def fecha_minima_compra() -> datetime:
    return datetime(1990, 1, 1)


def hoy() -> datetime:
    return datetime.now(ZONA_CHILE).replace(tzinfo=None)


def hace(dias: int) -> datetime:
    return hoy() - timedelta(days=dias)
