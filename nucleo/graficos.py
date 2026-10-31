"""Gráficos (Plotly) y el gráfico interactivo de TradingView."""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nucleo import tecnico

# Paleta (validada para daltonismo): azul = alza, rojo = baja
AZUL = "#2a78d6"
AZUL_OSCURO = "#1c5cab"
AZUL_CLARO = "#cde2fb"
AZUL_MEDIO = "#9ec5f4"
NARANJA = "#eb6834"
AQUA = "#1baf7a"
VIOLETA = "#6250d6"
ROJO = "#e34948"
TEXTO = "#0b0b0b"
TEXTO_2 = "#52514e"
GRILLA = "#ecebe7"
FONDO = "#fcfcfb"
GRIS = "#b9b8b2"
FUENTE = "Inter, 'Source Sans Pro', system-ui, sans-serif"

CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"], "locale": "es"}


def estilo(fig: go.Figure, alto: int = 380, titulo: str | None = None, leyenda: bool = True) -> go.Figure:
    fig.update_layout(
        height=alto, template="plotly_white", paper_bgcolor=FONDO, plot_bgcolor=FONDO,
        font=dict(family=FUENTE, size=13, color=TEXTO_2),
        title=dict(text=titulo, font=dict(size=15, color=TEXTO), x=0, xanchor="left") if titulo else None,
        margin=dict(l=8, r=8, t=48 if titulo else 16, b=8), hovermode="x unified",
        showlegend=leyenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, font=dict(size=12)),
        hoverlabel=dict(bgcolor="white", font=dict(family=FUENTE, color=TEXTO)),
        separators=",.",
    )
    fig.update_xaxes(showgrid=False, linecolor=GRILLA, tickfont=dict(color=TEXTO_2))
    fig.update_yaxes(gridcolor=GRILLA, zeroline=False, tickfont=dict(color=TEXTO_2))
    return fig


def _pct(x: float) -> str:
    return f"{x:+.1%}".replace(".", ",")


# ----------------------------------------------------------------------------
# Panel 1
# ----------------------------------------------------------------------------
def barras_rendimiento(df: pd.DataFrame, col_valor: str, col_etiqueta: str = "Ticker",
                       titulo: str | None = None) -> go.Figure:
    d = df.sort_values(col_valor)
    colores = [AZUL if v >= 0 else ROJO for v in d[col_valor]]
    fig = go.Figure(go.Bar(
        x=d[col_valor], y=d[col_etiqueta], orientation="h", marker=dict(color=colores, cornerradius=4),
        text=[_pct(v) for v in d[col_valor]], textposition="outside", cliponaxis=False,
        textfont=dict(color=TEXTO_2, size=12),
        hovertemplate="%{y}: %{x:+.2%}<extra></extra>",
    ))
    lo, hi = min(0.0, float(d[col_valor].min())), max(0.0, float(d[col_valor].max()))
    holgura = (hi - lo) * 0.22 or 0.05
    fig.update_xaxes(tickformat="+.0%", showgrid=True, gridcolor=GRILLA,
                     range=[lo - (holgura if lo < 0 else 0), hi + (holgura if hi > 0 else 0)])
    estilo(fig, alto=max(260, 28 * len(d) + 60), titulo=titulo, leyenda=False)
    fig.update_layout(hovermode="closest", bargap=0.35)
    return fig


def linea_precio(serie: pd.Series, titulo: str | None = None) -> go.Figure:
    fig = go.Figure(go.Scatter(x=serie.index, y=serie.values, mode="lines",
                               line=dict(color=AZUL, width=2), name=serie.name or "Precio",
                               hovertemplate="%{y:,.2f}<extra></extra>"))
    return estilo(fig, alto=320, titulo=titulo, leyenda=False)


# ----------------------------------------------------------------------------
# Monte Carlo
# ----------------------------------------------------------------------------
def abanico_montecarlo(fechas_fut, bandas: np.ndarray, muestras: np.ndarray, v0: float,
                       historia: pd.Series | None = None, tendencia: pd.Series | None = None,
                       costo: pd.Series | None = None, titulo: str | None = None) -> go.Figure:
    """bandas = percentiles 5, 25, 50, 75, 95 por día."""
    p5, p25, p50, p75, p95 = bandas
    fig = go.Figure()
    for tray in muestras:
        fig.add_trace(go.Scatter(x=fechas_fut, y=tray, mode="lines", line=dict(color=GRIS, width=0.7),
                                 opacity=0.45, hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=fechas_fut, y=p95, line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=fechas_fut, y=p5, fill="tonexty", fillcolor="rgba(42,120,214,0.14)",
                             line=dict(width=0), name="90% de los escenarios", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fechas_fut, y=p75, line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=fechas_fut, y=p25, fill="tonexty", fillcolor="rgba(42,120,214,0.28)",
                             line=dict(width=0), name="50% de los escenarios", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=fechas_fut, y=p95, mode="lines", line=dict(color=AZUL, width=1.5, dash="dot"),
                             name="Mejor escenario (P95)", hovertemplate="Mejor: %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=fechas_fut, y=p50, mode="lines", line=dict(color=AZUL_OSCURO, width=2.5),
                             name="Escenario central (mediana)", hovertemplate="Central: %{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=fechas_fut, y=p5, mode="lines", line=dict(color=ROJO, width=1.5, dash="dot"),
                             name="Peor escenario (P5)", hovertemplate="Peor: %{y:,.0f}<extra></extra>"))
    if historia is not None and len(historia):
        fig.add_trace(go.Scatter(x=historia.index, y=historia.values, mode="lines",
                                 line=dict(color=TEXTO, width=2), name="Valor real",
                                 hovertemplate="Real: %{y:,.0f}<extra></extra>"))
    if costo is not None and len(costo):
        fig.add_trace(go.Scatter(x=costo.index, y=costo.values, mode="lines", line=dict(color=TEXTO_2, width=1.2, shape="hv", dash="dash"),
                                 name="Monto invertido", hovertemplate="Invertido: %{y:,.0f}<extra></extra>"))
    if tendencia is not None and len(tendencia):
        fig.add_trace(go.Scatter(x=tendencia.index, y=tendencia.values, mode="lines",
                                 line=dict(color=NARANJA, width=1.8, dash="dash"), name="Recta de tendencia",
                                 hovertemplate="Tendencia: %{y:,.0f}<extra></extra>"))
    fig.add_hline(y=v0, line=dict(color=TEXTO_2, width=1, dash="dot"), opacity=0.6)
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    estilo(fig, alto=500, titulo=titulo)
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="left", x=0),
                      margin=dict(b=70))
    return fig


def histograma_final(finales: np.ndarray, v0: float, esc: dict) -> go.Figure:
    fig = go.Figure(go.Histogram(x=finales, nbinsx=70, marker=dict(color=AZUL_MEDIO, line=dict(color=FONDO, width=1)),
                                 hovertemplate="Entre %{x}<br>%{y} escenarios<extra></extra>", name="Escenarios"))
    for valor, nombre, color in ((esc["peor"], "Peor (P5)", ROJO), (esc["probable"], "Más probable", AZUL_OSCURO),
                                 (esc["mejor"], "Mejor (P95)", AZUL), (v0, "Inversión inicial", TEXTO_2)):
        fig.add_vline(x=valor, line=dict(color=color, width=2 if nombre != "Inversión inicial" else 1, dash="solid" if nombre == "Más probable" else "dot"),
                      annotation=dict(text=nombre, font=dict(size=11, color=TEXTO_2), textangle=-90, yanchor="top"),
                      annotation_position="top left" if nombre in ("Peor (P5)", "Inversión inicial") else "top right")
    fig.update_xaxes(tickprefix="$", tickformat=",.0f", title="Valor final de la cartera")
    fig.update_yaxes(title="N.º de escenarios")
    estilo(fig, alto=320, leyenda=False)
    fig.update_layout(hovermode="closest", bargap=0.02)
    return fig


# ----------------------------------------------------------------------------
# Cartera
# ----------------------------------------------------------------------------
def barras_pesos(pesos: pd.Series, titulo: str | None = None) -> go.Figure:
    p = pesos[pesos > 0].sort_values()
    fig = go.Figure(go.Bar(x=p.values, y=p.index, orientation="h", marker=dict(color=AZUL, cornerradius=4),
                           text=[f"{v:.1%}".replace(".", ",") for v in p.values], textposition="outside",
                           cliponaxis=False, textfont=dict(color=TEXTO_2, size=12),
                           hovertemplate="%{y}: %{x:.1%}<extra></extra>"))
    fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor=GRILLA, range=[0, float(p.max()) * 1.2])
    estilo(fig, alto=max(170, 30 * len(p) + 70), titulo=titulo, leyenda=False)
    fig.update_layout(hovermode="closest", bargap=0.35)
    return fig


def barras_por_tipo(tabla: pd.DataFrame) -> go.Figure:
    g = tabla.groupby("Tipo")["Peso"].sum().sort_values()
    g = g[g > 0]
    return barras_pesos(g, titulo="Por tipo de activo")


def regimenes_mercado(precio_mercado: pd.Series, probs: pd.DataFrame) -> go.Figure:
    """Precio del mercado y probabilidad del régimen más bajista."""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65, 0.35], vertical_spacing=0.06)
    fig.add_trace(go.Scatter(x=precio_mercado.index, y=precio_mercado.values, mode="lines",
                             line=dict(color=TEXTO, width=1.6), name="S&P 500 (SPY)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=probs.index, y=probs.iloc[:, 0], mode="lines", fill="tozeroy",
                             line=dict(color=ROJO, width=1), fillcolor="rgba(227,73,72,0.25)",
                             name=f"Prob. régimen «{probs.columns[0]}»"), row=2, col=1)
    fig.update_yaxes(tickformat=".0%", range=[0, 1], row=2, col=1)
    return estilo(fig, alto=420, titulo="Regímenes ocultos de Markov del mercado")


def trayectoria_cartera(valor: pd.Series, costo: pd.Series, referencia: pd.Series | None = None) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=valor.index, y=valor.values, mode="lines", line=dict(color=AZUL, width=2.2),
                             name="Valor de mi cartera", hovertemplate="Cartera: $%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=costo.index, y=costo.values, mode="lines", line=dict(color=TEXTO_2, width=1.4, shape="hv", dash="dash"),
                             name="Monto invertido", hovertemplate="Invertido: $%{y:,.0f}<extra></extra>"))
    if referencia is not None:
        fig.add_trace(go.Scatter(x=referencia.index, y=referencia.values, mode="lines", line=dict(color=NARANJA, width=1.6),
                                 name="Mismo dinero en el S&P 500", hovertemplate="S&P 500: $%{y:,.0f}<extra></extra>"))
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    return estilo(fig, alto=400, titulo="Trayectoria desde la primera compra")


def mapa_correlacion(corr: pd.DataFrame) -> go.Figure:
    escala = [[0, ROJO], [0.5, "#f0efec"], [1, AZUL]]
    fig = go.Figure(go.Heatmap(z=corr.values, x=corr.columns, y=corr.index, zmin=-1, zmax=1, zmid=0,
                               colorscale=escala, text=np.round(corr.values, 2), texttemplate="%{text}",
                               textfont=dict(size=11), hovertemplate="%{y} / %{x}: %{z:.2f}<extra></extra>",
                               colorbar=dict(thickness=10, len=0.8)))
    estilo(fig, alto=max(300, 38 * len(corr) + 80), titulo="Correlación entre tus activos", leyenda=False)
    fig.update_layout(hovermode="closest")
    fig.update_yaxes(autorange="reversed", showgrid=False)
    return fig


# ----------------------------------------------------------------------------
# Análisis técnico (velas + indicadores)
# ----------------------------------------------------------------------------
def grafico_tecnico(ohlc: pd.DataFrame, nombre: str, compra: pd.Timestamp | None = None) -> go.Figure:
    c = ohlc["Close"]
    bb = tecnico.bollinger(c)
    mc = tecnico.macd(c)
    r = tecnico.rsi(c)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.035)
    fig.add_trace(go.Candlestick(x=ohlc.index, open=ohlc["Open"], high=ohlc["High"], low=ohlc["Low"], close=c,
                                 increasing=dict(line=dict(color=AZUL, width=1), fillcolor=AZUL),
                                 decreasing=dict(line=dict(color=ROJO, width=1), fillcolor=ROJO),
                                 name="Precio", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=bb.index, y=bb["Superior"], line=dict(color=GRIS, width=1), name="Bollinger",
                             hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=bb.index, y=bb["Inferior"], line=dict(color=GRIS, width=1), fill="tonexty",
                             fillcolor="rgba(185,184,178,0.12)", showlegend=False, hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=c.index, y=tecnico.sma(c, 50), line=dict(color=NARANJA, width=1.5), name="Media 50"), row=1, col=1)
    fig.add_trace(go.Scatter(x=c.index, y=tecnico.sma(c, 200), line=dict(color=VIOLETA, width=1.5), name="Media 200"), row=1, col=1)
    fig.add_trace(go.Scatter(x=r.index, y=r, line=dict(color=AZUL_OSCURO, width=1.4), name="RSI 14"), row=2, col=1)
    for nivel in (30, 70):
        fig.add_hline(y=nivel, line=dict(color=TEXTO_2, width=0.8, dash="dot"), row=2, col=1)
    fig.add_trace(go.Bar(x=mc.index, y=mc["Histograma"], marker_color=[AZUL if v >= 0 else ROJO for v in mc["Histograma"].fillna(0)],
                         name="Histograma MACD", showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(x=mc.index, y=mc["MACD"], line=dict(color=TEXTO, width=1.2), name="MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=mc.index, y=mc["Señal"], line=dict(color=NARANJA, width=1.2), name="Señal MACD"), row=3, col=1)
    if compra is not None:
        fig.add_vline(x=pd.Timestamp(compra), line=dict(color=AQUA, width=1.5, dash="dash"))
    fig.update_layout(xaxis_rangeslider_visible=False)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    estilo(fig, alto=640, titulo=f"{nombre}: velas, medias móviles, Bollinger, RSI y MACD")
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])] if not nombre.upper().endswith("-USD") else [])
    return fig


# ----------------------------------------------------------------------------
# TradingView (widget oficial gratuito, con sus propias herramientas de dibujo)
# ----------------------------------------------------------------------------
_TV_ESPECIALES = {
    "GC=F": "COMEX:GC1!", "SI=F": "COMEX:SI1!", "HG=F": "COMEX:HG1!", "CL=F": "NYMEX:CL1!", "NG=F": "NYMEX:NG1!",
    "^GSPC": "SP:SPX", "^IXIC": "NASDAQ:IXIC", "^DJI": "DJ:DJI", "^RUT": "TVC:RUT", "^VIX": "TVC:VIX",
    "CLP=X": "FX_IDC:USDCLP", "SPY": "AMEX:SPY", "GLD": "AMEX:GLD",
}


def simbolo_tradingview(ticker: str) -> str:
    t = str(ticker).upper().strip()
    if t in _TV_ESPECIALES:
        return _TV_ESPECIALES[t]
    if t.endswith("-USD"):
        return f"BINANCE:{t[:-4]}USDT"
    if t.endswith(".SN"):
        return f"BCS:{t[:-3].replace('-', '')}"
    if t.endswith("=X"):
        return f"FX_IDC:USD{t[:-2]}" if len(t) == 5 else f"FX_IDC:{t[:-2]}"
    return t.replace("-", ".").lstrip("^")


def html_tradingview(simbolo: str, alto: int = 620) -> str:
    simbolo = re.sub(r"[^A-Za-z0-9:._!^=\-]", "", str(simbolo))[:40] or "SPY"
    config = {
        "autosize": True, "symbol": simbolo, "interval": "D", "timezone": "America/Santiago",
        "theme": "light", "style": "1", "locale": "es", "allow_symbol_change": True,
        "hide_side_toolbar": False, "withdateranges": True, "save_image": True,
        "studies": ["RSI@tv-basicstudies", "MACD@tv-basicstudies"],
        "support_host": "https://www.tradingview.com",
    }
    return f"""
<div class="tradingview-widget-container" style="height:{alto}px;width:100%">
  <div class="tradingview-widget-container__widget" style="height:{alto}px;width:100%"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
  {json.dumps(config)}
  </script>
</div>"""
