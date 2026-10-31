"""Indicadores de análisis técnico (sin librerías externas)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    ganancia = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    perdida = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = ganancia / perdida.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0).where(perdida.notna())


def macd(s: pd.Series, rapida: int = 12, lenta: int = 26, senal: int = 9) -> pd.DataFrame:
    linea = ema(s, rapida) - ema(s, lenta)
    sen = ema(linea, senal)
    return pd.DataFrame({"MACD": linea, "Señal": sen, "Histograma": linea - sen})


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    media = sma(s, n)
    desv = s.rolling(n, min_periods=n).std()
    sup, inf = media + k * desv, media - k * desv
    return pd.DataFrame({"Media": media, "Superior": sup, "Inferior": inf,
                         "%B": (s - inf) / (sup - inf)})


def atr(ohlc: pd.DataFrame, n: int = 14) -> pd.Series:
    previo = ohlc["Close"].shift()
    rango = pd.concat([ohlc["High"] - ohlc["Low"], (ohlc["High"] - previo).abs(),
                       (ohlc["Low"] - previo).abs()], axis=1).max(axis=1)
    return rango.ewm(alpha=1 / n, adjust=False).mean()


def max_caida(s: pd.Series) -> float:
    s = s.dropna()
    return float((s / s.cummax() - 1).min()) if len(s) else np.nan


def dias_por_anio(ticker: str) -> int:
    return 365 if str(ticker).upper().endswith("-USD") else 252


def resumen_tecnico(cierre: pd.Series, ticker: str = "") -> dict:
    """Lectura técnica del último dato y una señal agregada (alcista/neutral/bajista)."""
    s = cierre.dropna()
    if len(s) < 30:
        return {"Señal": "Sin datos suficientes"}
    precio = float(s.iloc[-1])
    m50, m200 = sma(s, 50).iloc[-1], sma(s, 200).iloc[-1]
    r = float(rsi(s).iloc[-1])
    mc = macd(s)
    hist = mc["Histograma"]
    cruce = ""
    ultimos = np.sign(hist.iloc[-6:]).to_numpy()
    if len(ultimos) > 1 and ultimos[-1] > 0 and (ultimos[:-1] < 0).any():
        cruce = "cruce alcista reciente"
    elif len(ultimos) > 1 and ultimos[-1] < 0 and (ultimos[:-1] > 0).any():
        cruce = "cruce bajista reciente"
    bb = bollinger(s)["%B"].iloc[-1]
    vol30 = float(s.pct_change().iloc[-30:].std() * np.sqrt(dias_por_anio(ticker)))
    ventana_52 = s.iloc[-(dias_por_anio(ticker)):]
    dist_max = precio / float(ventana_52.max()) - 1

    puntaje = 0
    puntaje += 1 if pd.notna(m50) and precio > m50 else (-1 if pd.notna(m50) else 0)
    if pd.notna(m50) and pd.notna(m200):
        puntaje += 1 if m50 > m200 else -1
    puntaje += 1 if hist.iloc[-1] > 0 else -1
    if r >= 70:
        puntaje -= 1
    elif r <= 30:
        puntaje += 1

    if pd.notna(m50) and pd.notna(m200):
        tendencia = "Alcista" if precio > m50 > m200 else ("Bajista" if precio < m50 < m200 else "Mixta")
    else:
        tendencia = "Alcista" if pd.notna(m50) and precio > m50 else "Bajista" if pd.notna(m50) else "—"
    zona_rsi = "sobrecompra" if r >= 70 else "sobreventa" if r <= 30 else "neutral"
    senal = "Alcista" if puntaje >= 2 else "Bajista" if puntaje <= -2 else "Neutral"
    return {
        "Precio": precio, "Media 50": m50, "Media 200": m200, "Tendencia": tendencia,
        "RSI 14": r, "Zona RSI": zona_rsi,
        "MACD": "positivo" if hist.iloc[-1] > 0 else "negativo", "Cruce MACD": cruce or "—",
        "%B Bollinger": float(bb) if pd.notna(bb) else np.nan,
        "Volatilidad 30d": vol30, "Dist. máx. 52 sem.": dist_max,
        "Puntaje": puntaje, "Señal": senal,
    }


def metricas_riesgo(valor: pd.Series, referencia: pd.Series | None, rf: float, dias_anio: int = 252) -> dict:
    """Métricas de una serie de valor de cartera (sin aportes intermedios)."""
    v = valor.dropna()
    r = v.pct_change().dropna()
    if len(r) < 5:
        return {}
    anios = max(len(r) / dias_anio, 1 / dias_anio)
    ret_anual = (v.iloc[-1] / v.iloc[0]) ** (1 / anios) - 1 if anios >= 1 else r.mean() * dias_anio
    vol = r.std() * np.sqrt(dias_anio)
    salida = {
        "Retorno anualizado": float(ret_anual),
        "Volatilidad anual": float(vol),
        "Sharpe": float((ret_anual - rf) / vol) if vol > 0 else np.nan,
        "Máxima caída": max_caida(v),
        "VaR diario 95%": float(-np.percentile(r, 5)),
    }
    if referencia is not None:
        rr = referencia.pct_change().reindex(r.index).dropna()
        comun = r.reindex(rr.index)
        if len(rr) > 20 and rr.var() > 0:
            salida["Beta vs S&P 500"] = float(comun.cov(rr) / rr.var())
            salida["Correlación vs S&P 500"] = float(comun.corr(rr))
    return salida
