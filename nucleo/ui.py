"""Piezas visuales compartidas por los tres paneles."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from nucleo import datos, graficos, montecarlo, tecnico
from nucleo.config import MODO_DEMO

CSS = """
<style>
  .block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1280px;}
  h1 {font-weight: 650; letter-spacing: -0.02em;}
  h2, h3 {font-weight: 600; letter-spacing: -0.01em;}
  .subtitulo {color: #52514e; font-size: 1.02rem; margin-top: -0.6rem; margin-bottom: 1.2rem;}
  .tarjeta {border: 1px solid #e6e5e1; border-radius: 14px; padding: 16px 18px; background: #ffffff; height: 100%;}
  .tarjeta .etiqueta {color: #52514e; font-size: 0.85rem; margin-bottom: 4px;}
  .tarjeta .valor {color: #0b0b0b; font-size: 1.55rem; font-weight: 650; line-height: 1.2;}
  .tarjeta .detalle {color: #52514e; font-size: 0.86rem; margin-top: 6px;}
  .tarjeta.peor {border-top: 4px solid #e34948;}
  .tarjeta.probable {border-top: 4px solid #1c5cab;}
  .tarjeta.mejor {border-top: 4px solid #2a78d6;}
  .noticia {padding: 10px 0; border-bottom: 1px solid #eeede9;}
  .noticia a {color: #0b0b0b; text-decoration: none; font-weight: 550;}
  .noticia a:hover {color: #2a78d6;}
  .noticia .meta {color: #6b6a66; font-size: 0.8rem; margin-top: 2px;}
  .aviso-legal {color: #6b6a66; font-size: 0.8rem; margin-top: 2rem;}
</style>
"""


def preparar_pagina():
    st.markdown(CSS, unsafe_allow_html=True)
    if MODO_DEMO:
        st.warning("Modo demostración: los datos son SINTÉTICOS (no vienen de Yahoo Finance).", icon="🧪")


def encabezado(titulo: str, subtitulo: str):
    st.title(titulo)
    st.markdown(f"<div class='subtitulo'>{subtitulo}</div>", unsafe_allow_html=True)


def aviso_legal():
    st.markdown(
        "<div class='aviso-legal'>Página informativa y educativa en etapa de boceto. Los datos provienen de "
        "Yahoo Finance (uso personal) y pueden tener retrasos. Los resultados de los modelos son estimaciones "
        "estadísticas y no constituyen asesoría de inversión ni garantizan rendimientos futuros.</div>",
        unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Formatos (estilo chileno: punto de miles, coma decimal)
# ----------------------------------------------------------------------------
def _cambiar_separadores(txt: str) -> str:
    return txt.replace(",", "§").replace(".", ",").replace("§", ".")


def usd(x: float, decimales: int = 2) -> str:
    if x is None or not np.isfinite(x):
        return "—"
    return "US$ " + _cambiar_separadores(f"{x:,.{decimales}f}")


def num(x: float, decimales: int = 2) -> str:
    if x is None or not np.isfinite(x):
        return "—"
    return _cambiar_separadores(f"{x:,.{decimales}f}")


def pct(x: float, decimales: int = 1, signo: bool = True) -> str:
    if x is None or not np.isfinite(x):
        return "—"
    return _cambiar_separadores(f"{x:+.{decimales}%}" if signo else f"{x:.{decimales}%}")


def md(texto: str) -> str:
    """Evita que Streamlit interprete el signo $ como fórmula matemática."""
    return texto.replace("$", r"\$")


def tarjeta(etiqueta: str, valor: str, detalle: str = "", clase: str = ""):
    valor, detalle = valor.replace("$", "&#36;"), detalle.replace("$", "&#36;")
    st.markdown(f"<div class='tarjeta {clase}'><div class='etiqueta'>{etiqueta}</div>"
                f"<div class='valor'>{valor}</div><div class='detalle'>{detalle}</div></div>",
                unsafe_allow_html=True)


def mostrar_aviso(aviso: str | None):
    if aviso:
        st.info(aviso, icon="ℹ️")


# ----------------------------------------------------------------------------
# Bloque de resultados de Monte Carlo (paneles 2 y 3)
# ----------------------------------------------------------------------------
def bloque_montecarlo(valores: np.ndarray, v0: float, fechas_fut, horizonte_txt: str,
                      historia: pd.Series | None = None, tendencia: pd.Series | None = None,
                      costo: pd.Series | None = None):
    esc = montecarlo.escenarios(valores[:, -1], v0)
    c1, c2, c3 = st.columns(3)
    with c1:
        tarjeta("Peor escenario (percentil 5)", usd(esc["peor"], 0),
                f"{pct(esc['peor_ret'])} · <b>5%</b> de probabilidad de terminar igual o peor", "peor")
    with c2:
        tarjeta("Escenario más probable", usd(esc["probable"], 0),
                f"{pct(esc['probable_ret'])} · <b>{pct(esc['prob_cerca_probable'], 0, False)}</b> de probabilidad de "
                f"terminar a ±5% de este valor", "probable")
    with c3:
        tarjeta("Mejor escenario (percentil 95)", usd(esc["mejor"], 0),
                f"{pct(esc['mejor_ret'])} · <b>5%</b> de probabilidad de terminar igual o mejor", "mejor")

    st.write("")
    b = montecarlo.bandas(valores)
    muestras = montecarlo.muestra_trayectorias(valores, 30)
    fig = graficos.abanico_montecarlo(fechas_fut, b, muestras, v0, historia=historia, tendencia=tendencia,
                                      costo=costo, titulo=f"Proyección a {horizonte_txt} · {valores.shape[0]:,} escenarios".replace(",", "."))
    st.plotly_chart(fig, theme=None, config=graficos.CONFIG)

    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(graficos.histograma_final(valores[:, -1], v0, esc), theme=None, config=graficos.CONFIG)
    with c2:
        st.markdown("**Probabilidades al final del horizonte**")
        tabla = pd.DataFrame({
            "Resultado": ["Terminar con ganancia", "Terminar con pérdida", "Ganar más de 10%", "Ganar más de 20%",
                          "Perder más de 10%", "Perder más de 20%"],
            "Probabilidad": [esc["prob_ganar"], esc["prob_perder"], esc["prob_ganar_10"], esc["prob_ganar_20"],
                             esc["prob_perder_10"], esc["prob_perder_20"]],
        })
        st.dataframe(tabla, hide_index=True, column_config={
            "Probabilidad": st.column_config.ProgressColumn("Probabilidad", format="percent", min_value=0, max_value=1)})
        st.caption(md(f"Escenario central (mediana): {usd(esc['mediana'], 0)} ({pct(esc['mediana_ret'])}). "
                   f"Promedio del 5% de escenarios más malos: {usd(esc['promedio_peor_5'], 0)}. "
                   f"Peor simulación absoluta: {usd(esc['minimo'], 0)}."))
    return esc


# ----------------------------------------------------------------------------
# Análisis técnico estilo TradingView (paneles 2 y 3)
# ----------------------------------------------------------------------------
def bloque_tradingview(tickers: list, clave: str, fechas_compra: dict | None = None):
    if not tickers:
        return
    c1, c2 = st.columns([2, 3])
    with c1:
        elegido = st.selectbox("Activo a analizar", tickers, key=f"tv_activo_{clave}")
    with c2:
        sugerido = graficos.simbolo_tradingview(elegido)
        simbolo = st.text_input("Símbolo en TradingView (cámbialo si el gráfico no lo encuentra)",
                                value=sugerido, key=f"tv_simbolo_{clave}_{elegido}")

    pestana_tv, pestana_propia = st.tabs(["Gráfico TradingView (con herramientas de dibujo)",
                                          "Análisis técnico con datos de Yahoo"])
    with pestana_tv:
        st.iframe(graficos.html_tradingview(simbolo, 600), height=620)
        st.caption("Gráfico y datos de TradingView. Usa la barra lateral del gráfico para trazar líneas de "
                   "tendencia, Fibonacci, soportes y resistencias, y el botón «Indicadores» para agregar más.")
    with pestana_propia:
        ohlc, aviso = datos.precios_ohlc(elegido, "2y")
        mostrar_aviso(aviso)
        if ohlc.empty:
            st.warning("No hay datos de velas para este activo.")
            return
        compra = (fechas_compra or {}).get(elegido)
        st.plotly_chart(graficos.grafico_tecnico(ohlc, elegido, compra), theme=None, config=graficos.CONFIG)
        r = tecnico.resumen_tecnico(ohlc["Close"], elegido)
        if "Precio" in r:
            k = st.columns(5)
            k[0].metric("Señal técnica", r["Señal"], help="Suma de: precio vs. media 50, media 50 vs. 200, MACD y RSI.")
            k[1].metric("Tendencia", r["Tendencia"])
            k[2].metric("RSI 14", num(r["RSI 14"], 1), r["Zona RSI"], delta_color="off")
            k[3].metric("MACD", r["MACD"], r["Cruce MACD"] if r["Cruce MACD"] != "—" else None, delta_color="off")
            k[4].metric("Distancia al máximo 52 sem.", pct(r["Dist. máx. 52 sem."]))
