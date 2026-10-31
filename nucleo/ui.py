"""Piezas visuales compartidas por todos los paneles."""

from __future__ import annotations

import html as _html
from datetime import datetime
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import streamlit as st

from nucleo import datos, graficos, montecarlo, tecnico, universo
from nucleo.config import AUTORES, MODO_DEMO, ZONA_CHILE

VERDE, ROJO, AZUL, TINTA = "#0a7f3f", "#c62828", "#0b57d0", "#111827"

CSS = """
<style>
/* ---------- Base ---------- */
.block-container {padding-top: 4.4rem; padding-bottom: 2.5rem; max-width: 1320px;}
[data-testid="stDecoration"] {display: none;}
header[data-testid="stHeader"] {border-bottom: 1px solid #e3e6eb;}
h1 {letter-spacing: -0.025em; line-height: 1.08 !important;}
h2, h3 {letter-spacing: -0.015em;}
[data-testid="stMetricValue"] {font-variant-numeric: tabular-nums; letter-spacing: -0.01em;}
.stTabs [data-baseweb="tab"] {font-weight: 600;}
.stTabs [data-baseweb="tab-list"] {gap: 1.4rem;}

/* ---------- Cabecera del sitio ---------- */
.cabecera {display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap;
  padding: 4px 0 12px; border-bottom: 4px solid #111827; margin-bottom: 18px;}
.marca {display: flex; align-items: center; gap: 12px;}
.marca .logo {width: 40px; height: 40px; border-radius: 6px; background: #0b1f3a; color: #fff; display: flex;
  align-items: center; justify-content: center; font-weight: 800; font-size: 20px; letter-spacing: -0.04em;}
.marca .nombre {font-weight: 800; font-size: 1.32rem; letter-spacing: -0.03em; color: #111827; line-height: 1.1;}
.marca .nombre span {font-weight: 500; color: #5b6472;}
.marca .lema {font-size: 0.8rem; color: #5b6472; margin-top: 2px;}
.cabecera .fecha {text-align: right; font-size: 0.8rem; color: #5b6472; line-height: 1.45;}
.cabecera .fecha b {color: #111827; font-weight: 600;}
@media (max-width: 640px) {.cabecera .fecha {text-align: left;}}

/* ---------- Títulos de página y secciones ---------- */
.antetitulo {font-size: 0.74rem; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase; color: #0b57d0;
  margin-bottom: -0.35rem;}
.subtitulo {color: #4b5563; font-size: 1.02rem; margin-top: -0.5rem; margin-bottom: 1.1rem; max-width: 900px;}
.seccion {border-top: 2px solid #111827; padding-top: 8px; margin: 1.8rem 0 0.8rem;}
.seccion .t {font-family: 'Inter Tight', Inter, sans-serif; font-weight: 800; font-size: 1.28rem; color: #111827;
  letter-spacing: -0.015em;}
.seccion .n {font-size: 0.84rem; color: #5b6472; margin-top: 2px;}

/* ---------- Franja de activos (panel Mercado) ---------- */
.franja {display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 12px; margin: 2px 0 8px;}
@media (max-width: 1150px) {.franja {grid-template-columns: repeat(4, minmax(0, 1fr));}}
@media (max-width: 640px) {.franja {grid-template-columns: repeat(2, minmax(0, 1fr));}}
.ficha {border: 1px solid #e3e6eb; border-radius: 8px; padding: 11px 13px 6px; background: #fff; min-width: 0;
  display: flex; flex-direction: column; text-decoration: none !important; color: inherit !important;
  transition: border-color .15s, box-shadow .15s;}
.ficha:hover {border-color: #0b57d0; box-shadow: 0 2px 12px rgba(17, 24, 39, .07);}
.ficha .tag {font-size: 0.64rem; font-weight: 700; letter-spacing: 0.07em; text-transform: uppercase; margin-bottom: 4px;}
.ficha .tag.sube {color: #0a7f3f;} .ficha .tag.baja {color: #c62828;} .ficha .tag.neutro {color: #0b1f3a;}
.ficha .tk {font-weight: 800; font-size: 0.98rem; color: #111827; line-height: 1.15;}
.ficha .nm {font-size: 0.76rem; color: #5b6472; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.ficha .px {font-size: 1.22rem; font-weight: 700; color: #111827; margin-top: 6px; font-variant-numeric: tabular-nums;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.ficha .var {font-size: 0.84rem; font-weight: 700; font-variant-numeric: tabular-nums;}
.sube {color: #0a7f3f;} .baja {color: #c62828;}
.ficha svg {width: 100%; height: 36px; margin-top: 4px; display: block;}
.nota-franja {font-size: 0.76rem; color: #5b6472; margin: 0 0 6px;}

/* ---------- Tablas editoriales ---------- */
.tabla {width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 0.9rem; border: none !important;
  margin: 0 !important;}
.tabla th, .tabla td {border: none !important;}
.tabla th {text-align: left; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  color: #5b6472; border-bottom: 2px solid #111827 !important; padding: 6px 8px !important; background: transparent !important;
  white-space: nowrap;}
.tabla td {padding: 7px 8px !important; border-bottom: 1px solid #eceff3 !important; vertical-align: middle;}
.tabla .activo {display: block; min-width: 0;}
.tabla .activo a {display: block;}
.tabla .activo .nm {display: block; font-size: 0.76rem; color: #5b6472; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis;}
.tabla tr:hover td {background: #f8fafc;}
.tabla td.num, .tabla th.num {text-align: right; font-variant-numeric: tabular-nums;}
.tabla td.cut {white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #374151;}
.tabla a {color: #111827; font-weight: 700; text-decoration: none;}
.tabla a:hover {color: #0b57d0; text-decoration: underline;}
.pill {display: inline-block; min-width: 64px; text-align: right; padding: 2px 7px; border-radius: 4px; font-weight: 700;
  font-variant-numeric: tabular-nums;}
.pill.sube {background: #e8f5ee; color: #0a7f3f;} .pill.baja {background: #fdeeee; color: #c62828;}
.tabla-titulo {font-weight: 800; font-size: 1.05rem; color: #111827; margin: 4px 0 6px;}
.fuente-tabla {font-size: 0.75rem; color: #5b6472; margin-top: 8px;}

/* ---------- Noticias ---------- */
.noticias-cab {border-top: 2px solid #111827; padding-top: 8px;}
.noticias-cab .t {font-family: 'Inter Tight', Inter, sans-serif; font-weight: 800; font-size: 1.28rem; color: #111827;}
.noticias-cab .n {font-size: 0.76rem; color: #5b6472; margin-top: 1px;}
.nota {padding: 11px 0 12px; border-bottom: 1px solid #eceff3;}
.nota .meta {display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 0.72rem; color: #5b6472;
  margin-bottom: 3px;}
.nota .fuente {font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; color: #0b1f3a;}
.nota .region {font-size: 0.64rem; font-weight: 700; padding: 1px 6px; border-radius: 3px; background: #eef2f7;
  color: #374151; text-transform: uppercase; letter-spacing: 0.05em;}
.nota .region.cl {background: #fdeeee; color: #9b1c1c;}
.nota a.titular {display: block; font-weight: 650; color: #111827 !important; font-size: 0.97rem; line-height: 1.35;
  text-decoration: none;}
.nota a.titular:hover {color: #0b57d0 !important; text-decoration: underline;}
.nota.destacada a.titular {font-size: 1.14rem; font-weight: 800; line-height: 1.28;}
.nota .resumen {font-size: 0.85rem; color: #4b5563; margin-top: 4px; line-height: 1.45;}
.nota .url {display: block; font-size: 0.72rem; color: #0b57d0 !important; margin-top: 4px; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; text-decoration: none;}
.fuentes-lista {font-size: 0.76rem; color: #5b6472; line-height: 1.55; margin-top: 10px;}
.fuentes-lista a {color: #0b57d0; text-decoration: none;}
.fuentes-lista .ok {color: #0a7f3f;} .fuentes-lista .no {color: #9ca3af;}

/* ---------- Tarjetas de escenarios ---------- */
.tarjeta {border: 1px solid #e3e6eb; border-radius: 8px; padding: 16px 18px; background: #ffffff; height: 100%;}
.tarjeta .etiqueta {color: #5b6472; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em; margin-bottom: 4px;}
.tarjeta .valor {color: #111827; font-size: 1.6rem; font-weight: 750; line-height: 1.2; font-variant-numeric: tabular-nums;}
.tarjeta .detalle {color: #4b5563; font-size: 0.86rem; margin-top: 6px;}
.tarjeta.peor {border-top: 4px solid #c62828;}
.tarjeta.probable {border-top: 4px solid #0b1f3a;}
.tarjeta.mejor {border-top: 4px solid #0a7f3f;}

/* ---------- Pie de página ---------- */
.pie {border-top: 3px solid #111827; margin-top: 3rem; padding-top: 14px; display: grid;
  grid-template-columns: 2fr 1fr; gap: 28px; font-size: 0.78rem; color: #5b6472; line-height: 1.55;}
@media (max-width: 760px) {.pie {grid-template-columns: 1fr;}}
.pie b {color: #111827;}
.pie a {color: #0b57d0; text-decoration: none;}
</style>
"""

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]


def fecha_larga(momento: datetime | None = None) -> str:
    m = momento or datetime.now(ZONA_CHILE)
    return f"{_DIAS[m.weekday()].capitalize()} {m.day} de {_MESES[m.month - 1]} de {m.year}"


def h(texto) -> str:
    """Escapa HTML y el signo $ (que Streamlit interpreta como fórmula)."""
    return _html.escape(str(texto if texto is not None else ""), quote=True).replace("$", "&#36;")


def html(contenido: str):
    """Inserta HTML sin que Markdown lo reinterprete (sin sangrías ni líneas vacías)."""
    limpio = " ".join(linea.strip() for linea in contenido.splitlines() if linea.strip())
    st.markdown(limpio, unsafe_allow_html=True)


def preparar_pagina():
    st.markdown(CSS, unsafe_allow_html=True)
    ahora = datetime.now(ZONA_CHILE)
    html(f"""
    <div class="cabecera">
      <div class="marca">
        <div class="logo">W</div>
        <div>
          <div class="nombre">webstock<span>and</span>trade<span>market</span></div>
          <div class="lema">Análisis de mercados financieros · Proyecto académico sin fines comerciales</div>
        </div>
      </div>
      <div class="fecha"><b>{fecha_larga(ahora)}</b><br>{ahora:%H:%M} hora de Chile · datos con retraso</div>
    </div>""")
    if MODO_DEMO:
        st.warning("Modo demostración: los datos son SINTÉTICOS (no vienen de Yahoo Finance).", icon="🧪")


def encabezado(titulo: str, subtitulo: str, antetitulo: str | None = None):
    if antetitulo:
        html(f"<div class='antetitulo'>{h(antetitulo)}</div>")
    st.title(titulo, anchor=False)
    html(f"<div class='subtitulo'>{h(subtitulo)}</div>")


def seccion(titulo: str, nota: str | None = None):
    html(f"<div class='seccion'><div class='t'>{h(titulo)}</div>"
         + (f"<div class='n'>{h(nota)}</div>" if nota else "") + "</div>")


def aviso_legal():
    autores = f" Desarrollado por {h(AUTORES)}." if AUTORES else ""
    html(f"""
    <div class="pie">
      <div><b>Aviso importante.</b> webstockandtrademarket es una plataforma <b>académica e informativa</b>. No es un
      corredor de bolsa, no ejecuta órdenes, no recibe dinero y no constituye asesoría ni recomendación de inversión
      (Ley N.º 21.521). Los resultados de los modelos son estimaciones estadísticas basadas en datos históricos y no
      garantizan rendimientos futuros.{autores} <a href="acerca" target="_self">Metodología y alcance →</a></div>
      <div><b>Datos.</b> Precios: Yahoo Finance (pueden tener retraso). Gráficos interactivos: TradingView.
      Noticias: BBC, The New York Times, Financial Times, The Economist, The Wall Street Journal, Yahoo Finance,
      Diario Financiero, Banco Central de Chile y Ministerio de Economía. Actualización cada 30 minutos.</div>
    </div>""")


# ----------------------------------------------------------------------------
# Formatos (estilo chileno: punto de miles, coma decimal)
# ----------------------------------------------------------------------------
def _cambiar_separadores(txt: str) -> str:
    return txt.replace(",", "§").replace(".", ",").replace("§", ".")


def _valido(x) -> bool:
    try:
        return x is not None and np.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def usd(x: float, decimales: int = 2) -> str:
    if not _valido(x):
        return "—"
    return "US$ " + _cambiar_separadores(f"{x:,.{decimales}f}")


def num(x: float, decimales: int = 2) -> str:
    if not _valido(x):
        return "—"
    return _cambiar_separadores(f"{x:,.{decimales}f}")


def precio(x: float) -> str:
    """Precio con decimales adaptados a su magnitud (0,00012 o 63.974,00)."""
    if not _valido(x):
        return "—"
    x = float(x)
    dec = 2 if abs(x) >= 1 else (4 if abs(x) >= 0.01 else 8)
    return num(x, dec)


def pct(x: float, decimales: int = 1, signo: bool = True) -> str:
    if not _valido(x):
        return "—"
    return _cambiar_separadores(f"{x:+.{decimales}%}" if signo else f"{x:.{decimales}%}")


def md(texto: str) -> str:
    """Evita que Streamlit interprete el signo $ como fórmula matemática."""
    return texto.replace("$", r"\$")


def tarjeta(etiqueta: str, valor: str, detalle: str = "", clase: str = ""):
    valor, detalle = valor.replace("$", "&#36;"), detalle.replace("$", "&#36;")
    html(f"<div class='tarjeta {clase}'><div class='etiqueta'>{etiqueta}</div>"
         f"<div class='valor'>{valor}</div><div class='detalle'>{detalle}</div></div>")


def mostrar_aviso(aviso: str | None):
    if aviso:
        st.info(aviso, icon=":material/info:")


# ----------------------------------------------------------------------------
# Franja superior y tablas del panel Mercado
# ----------------------------------------------------------------------------
def minigrafico(valores, color: str) -> str:
    v = np.asarray([x for x in (valores or []) if _valido(x)], dtype=float)
    if len(v) < 2:
        return "<svg viewBox='0 0 100 30'></svg>"
    lo, hi = float(v.min()), float(v.max())
    rango = (hi - lo) or 1.0
    xs = np.linspace(0, 100, len(v))
    ys = 28 - (v - lo) / rango * 26
    puntos = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"0,30 {puntos} 100,30"
    return (f"<svg viewBox='0 0 100 30' preserveAspectRatio='none'>"
            f"<polygon points='{area}' fill='{color}' fill-opacity='0.08'/>"
            f"<polyline points='{puntos}' fill='none' stroke='{color}' stroke-width='1.6' "
            f"vector-effect='non-scaling-stroke' stroke-linejoin='round'/></svg>")


def franja(fichas: list[dict]):
    """fichas: dict(tag, clase, ticker, nombre, precio, var, serie, url)."""
    partes = []
    for f in fichas:
        var = f.get("var")
        clase_var = "sube" if _valido(var) and var >= 0 else "baja"
        color = VERDE if clase_var == "sube" else ROJO
        flecha = "▲" if clase_var == "sube" else "▼"
        partes.append(
            f"<a class='ficha' href='{h(f.get('url') or '#')}' target='_blank' rel='noopener'>"
            f"<div class='tag {f.get('clase', 'neutro')}'>{h(f.get('tag', ''))}</div>"
            f"<div class='tk'>{h(f['ticker'])}</div><div class='nm'>{h(f.get('nombre', ''))}</div>"
            f"<div class='px'>{h(f.get('precio_txt') or precio(f.get('precio')))}</div>"
            f"<div class='var {clase_var}'>{flecha} {h(pct(var, 2))}</div>"
            f"{minigrafico(f.get('serie'), color)}</a>")
    html("<div class='franja'>" + "".join(partes) + "</div>")


def url_yahoo(ticker: str) -> str:
    return "https://finance.yahoo.com/quote/" + _html.escape(str(ticker), quote=True)


def tabla_movimientos(df: pd.DataFrame, titulo: str, filas: int = 10):
    """Tabla editorial de mayores alzas o caídas (columnas: Ticker, Nombre, Precio, Var. %)."""
    cuerpo = []
    for _, r in df.head(filas).iterrows():
        v = r.get("Var. %")
        clase = "sube" if _valido(v) and v >= 0 else "baja"
        cuerpo.append(
            f"<tr><td><span class='activo'><a href='{url_yahoo(r['Ticker'])}' target='_blank' rel='noopener'>"
            f"{h(r['Ticker'])}</a><span class='nm' title='{h(r.get('Nombre', ''))}'>{h(r.get('Nombre', ''))}</span>"
            f"</span></td>"
            f"<td class='num'>{h(precio(r.get('Precio')))}</td>"
            f"<td class='num'><span class='pill {clase}'>{h(pct(v, 2))}</span></td></tr>")
    html(f"<div class='tabla-titulo'>{h(titulo)}</div>"
         "<table class='tabla'><colgroup><col><col style='width:96px'><col style='width:96px'></colgroup>"
         "<thead><tr><th>Activo</th><th class='num'>Precio US&#36;</th>"
         "<th class='num'>Var. día</th></tr></thead><tbody>" + "".join(cuerpo) + "</tbody></table>")


# ----------------------------------------------------------------------------
# Noticias
# ----------------------------------------------------------------------------
def _hace(fecha) -> str:
    if fecha is None:
        return ""
    minutos = (pd.Timestamp.now(tz=ZONA_CHILE) - fecha).total_seconds() / 60
    if minutos < 1:
        return "recién"
    if minutos < 60:
        return f"hace {int(minutos)} min"
    if minutos < 60 * 24:
        return f"hace {int(minutos // 60)} h"
    return fecha.strftime("%d-%m-%Y")


def _url_visible(url: str) -> str:
    try:
        p = urlparse(url)
        ruta = p.path if len(p.path) < 46 else p.path[:44] + "…"
        return (p.netloc.replace("www.", "") + ruta).rstrip("/")
    except Exception:
        return url


def lista_noticias(items: list[dict], destacar_primera: bool = True, mostrar_region: bool = True):
    partes = []
    for i, n in enumerate(items):
        region = "cl" if n.get("region") == "Chile" else ""
        destacada = destacar_primera and i == 0
        resumen = f"<div class='resumen'>{h(n['resumen'])}</div>" if destacada and n.get("resumen") else ""
        partes.append(
            f"<article class='nota{' destacada' if destacada else ''}'>"
            f"<div class='meta'><span class='fuente'>{h(n['fuente'])}</span>"
            + (f"<span class='region {region}'>{h(n.get('region', ''))}</span>" if mostrar_region else "") +
            f"<span>· {h(_hace(n.get('fecha')))}</span></div>"
            f"<a class='titular' href='{h(n['url'])}' target='_blank' rel='noopener'>{h(n['titulo'])}</a>"
            f"{resumen}"
            f"<a class='url' href='{h(n['url'])}' target='_blank' rel='noopener'>"
            f"{h(n.get('url_visible') or _url_visible(n['url']))} ↗</a></article>")
    html("".join(partes))


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
# Análisis técnico: TradingView + gráfico propio (paneles 2 y 3)
# ----------------------------------------------------------------------------
ALTO_TRADINGVIEW = 720


def bloque_tradingview(tickers: list, clave: str, fechas_compra: dict | None = None):
    if not tickers:
        return
    c1, c2 = st.columns([1, 1])
    with c1:
        elegido = st.selectbox("Activo a analizar", tickers, key=f"tv_activo_{clave}",
                               format_func=lambda t: f"{t} · {universo.nombre_de(t)}")
    with c2:
        sugerido = graficos.simbolo_tradingview(elegido)
        simbolo = st.text_input("Símbolo en TradingView (cámbialo si el gráfico no lo encuentra)",
                                value=sugerido, key=f"tv_simbolo_{clave}_{elegido}",
                                help="Formato BOLSA:TICKER, por ejemplo NASDAQ:NVDA, BINANCE:BTCUSDT o BCS:SQMB.")

    pestana_tv, pestana_propia = st.tabs(["Gráfico TradingView (con herramientas de dibujo)",
                                          "Análisis técnico con datos de Yahoo"])
    with pestana_tv:
        o1, o2 = st.columns([1, 1.6])
        with o1:
            intervalo = st.segmented_control("Intervalo de las velas", list(graficos.INTERVALOS_TV),
                                             default="Diario", key=f"tv_intervalo_{clave}")
        with o2:
            indicadores = st.multiselect("Indicadores sobre el gráfico", list(graficos.INDICADORES_TV),
                                         key=f"tv_indicadores_{clave}",
                                         placeholder="Opcional: media móvil, Bollinger, RSI, MACD")
        st.iframe(graficos.html_tradingview(simbolo, intervalo or "Diario", indicadores), height=ALTO_TRADINGVIEW)
        st.caption("Gráfico y datos de TradingView. Usa la barra izquierda para trazar líneas de tendencia, "
                   "Fibonacci, soportes y resistencias; el botón «Pantalla completa» amplía el gráfico (Esc para salir) "
                   "y «Abrir en TradingView» lo abre en una pestaña nueva con todas las funciones.")
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
