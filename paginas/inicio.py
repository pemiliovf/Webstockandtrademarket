"""Panel 1 — Mercado: franja de movimientos, rendimientos y noticias."""

import numpy as np
import pandas as pd
import streamlit as st

from nucleo import datos, graficos, noticias, ui, universo

ui.preparar_pagina()
ui.encabezado("Mercados hoy",
              f"Mayores alzas y caídas del día, rendimientos de 90 días, precios de más de 550 activos y noticias "
              f"económicas de Chile y el mundo. Actualizado {datos.hora_chile()} (hora de Chile).",
              "Panel de mercado")

N_FRANJA = 3          # alzas y caídas que se muestran arriba
DIVISA = "CLP=X"      # dólar / peso chileno


# --------------------------------------------------------------------------
# Rendimientos del universo completo
# --------------------------------------------------------------------------
@st.cache_data(ttl=60 * 30, show_spinner=False)
def calcular_rendimientos(precios: pd.DataFrame, univ: pd.DataFrame) -> pd.DataFrame:
    info = univ.set_index("Ticker")
    filas = []
    for t in precios.columns:
        s = precios[t].dropna()
        if len(s) < 3:
            continue
        ultimo = float(s.iloc[-1])
        corte_90 = s.index[-1] - pd.Timedelta(days=90)
        base = s[s.index <= corte_90]
        ultimos_90 = s[s.index >= corte_90]
        inicio_anio = s[s.index < pd.Timestamp(year=s.index[-1].year, month=1, day=1)]
        filas.append({
            "Ticker": t,
            "Nombre": info["Nombre"].get(t, t) if t in info.index else t,
            "Tipo": info["Tipo"].get(t, universo.tipo_de_activo(t)) if t in info.index else universo.tipo_de_activo(t),
            "Sector": info["Sector"].get(t, "—") if t in info.index else "—",
            "Precio (USD)": ultimo,
            "Var. día": ultimo / float(s.iloc[-2]) - 1,
            "Var. 90 días": ultimo / float(base.iloc[-1]) - 1 if len(base) else np.nan,
            "Var. en el año": ultimo / float(inicio_anio.iloc[-1]) - 1 if len(inicio_anio) else np.nan,
            "Últimos 90 días": ultimos_90.round(4).tolist(),
            "Fecha": s.index[-1].strftime("%d-%m-%Y"),
        })
    return pd.DataFrame(filas)


def armar_franja(sube: pd.DataFrame, baja: pd.DataFrame):
    """3 mayores alzas + 3 mayores caídas + dólar/peso, con minigráfico de 3 meses."""
    arriba, abajo = sube.head(N_FRANJA), baja.head(N_FRANJA)
    tickers = list(arriba["Ticker"]) + list(abajo["Ticker"]) + [DIVISA]
    historia, _ = datos.precios_cierre(tickers, "3mo")
    fichas = []
    for grupo, df, clase in (("Mayor alza", arriba, "sube"), ("Mayor caída", abajo, "baja")):
        for i, (_, r) in enumerate(df.iterrows(), start=1):
            t = r["Ticker"]
            serie = historia[t].dropna().iloc[-60:].tolist() if t in historia.columns else []
            fichas.append({"tag": f"{grupo} · {i}", "clase": clase, "ticker": t, "nombre": r["Nombre"],
                           "precio": r["Precio"], "var": r["Var. %"], "serie": serie, "url": ui.url_yahoo(t)})
    s = historia[DIVISA].dropna() if DIVISA in historia.columns else pd.Series(dtype=float)
    fichas.append({"tag": "Divisa · Chile", "clase": "neutro", "ticker": "USD/CLP", "nombre": "Dólar / Peso chileno",
                   "precio_txt": f"{ui.num(s.iloc[-1])} CLP" if len(s) else "—",
                   "var": float(s.iloc[-1] / s.iloc[-2] - 1) if len(s) >= 2 else np.nan,
                   "serie": s.iloc[-60:].tolist(), "url": ui.url_yahoo(DIVISA)})
    ui.franja(fichas)


def preparar_screener(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(**{"Var. %": df["Var. %"] / 100}).drop(columns="Volumen", errors="ignore")


# --------------------------------------------------------------------------
# Franja superior
# --------------------------------------------------------------------------
lugar_franja = st.container()
sube, baja, aviso_scr = datos.movimientos_del_dia(15)
fuente_mov = ("Fuente: screener de Yahoo Finance sobre todo el mercado accionario de EE.UU. (capitalización ≥ "
              "US$ 2.000 millones y precio ≥ US$ 5; alzas superiores a 3% y caídas superiores a 2,5% en el día).")
if sube is not None and baja is not None and not sube.empty and not baja.empty:
    sube, baja = preparar_screener(sube), preparar_screener(baja)
    with lugar_franja:
        armar_franja(sube, baja)
else:
    sube = baja = None

izquierda, derecha = st.columns([2.15, 1], gap="large")


# --------------------------------------------------------------------------
# Noticias (se renuevan solas cada 30 minutos)
# --------------------------------------------------------------------------
def destacadas(lista: list, n: int = 12) -> list:
    """La nota más relevante de cada medio y luego las más recientes, sin repetir."""
    elegidas, vistos = [], set()
    for n_ in lista:
        if n_["id_fuente"] not in vistos:
            vistos.add(n_["id_fuente"])
            elegidas.append(n_)
    for n_ in lista:
        if len(elegidas) >= n:
            break
        if n_ not in elegidas:
            elegidas.append(n_)
    minimo = pd.Timestamp("1970-01-01", tz="UTC")
    return sorted(elegidas[:n], key=lambda x: x["fecha"] if x["fecha"] is not None else minimo, reverse=True)


@st.fragment(run_every="30m")
def panel_noticias():
    datos_n, aviso = noticias.noticias()
    hora = datos_n["hora"].strftime("%H:%M") if datos_n else "—"
    ui.html(f"<div class='noticias-cab'><div class='t'>Últimas noticias</div>"
            f"<div class='n'>Economía y mercados<br>actualizado {hora} · se renueva cada 30 min</div></div>")
    ui.mostrar_aviso(aviso)
    if not datos_n:
        return
    todas = datos_n["noticias"]
    grupos = {"Destacadas": destacadas(todas),
              "Internacional": [n for n in todas if n["region"] == "Internacional"][:18],
              "Chile": [n for n in todas if n["region"] == "Chile"][:18]}
    for pestana, (nombre, lista) in zip(st.tabs(list(grupos)), grupos.items()):
        with pestana:
            with st.container(height=640, border=False):
                if lista:
                    ui.lista_noticias(lista, mostrar_region=nombre == "Destacadas")
                else:
                    st.caption(f"Sin notas recientes en las fuentes de {nombre.lower()} en este momento.")
    filas = []
    for f in noticias.FUENTES:
        estado = datos_n["estado"].get(f["id"], "sin respuesta")
        clase = "no" if estado in ("sin respuesta", "sin notas recientes") else "ok"
        filas.append(f"<a href='{ui.h(f['url_seccion'])}' target='_blank' rel='noopener'>{ui.h(f['nombre'])}</a> "
                     f"— {ui.h(f['seccion'])} <span class='{clase}'>● {ui.h(estado)}</span>")
    ui.html("<div class='fuentes-lista'><b>Fuentes consultadas</b> (solo secciones de economía, finanzas y "
            "mercados). Cada titular enlaza a la nota original:<br>" + "<br>".join(filas) + "</div>")


with derecha:
    panel_noticias()

# --------------------------------------------------------------------------
# Universo completo, tablas y buscador
# --------------------------------------------------------------------------
univ = universo.universo_inicio()
with izquierda:
    with st.spinner(f"Descargando precios de {len(univ)} activos desde Yahoo Finance… "
                    "(la primera visita tarda alrededor de un minuto; luego queda guardado 30 minutos)"):
        precios, aviso_precios = datos.precios_cierre(univ["Ticker"].tolist(), "6mo")
rend = calcular_rendimientos(precios, univ) if not precios.empty else pd.DataFrame()

if sube is None and not rend.empty:
    fuente_mov = ("Calculado sobre el universo de la página (S&P 500, ETFs, materias primas y criptomonedas), "
                  "porque el screener de Yahoo Finance no respondió.")
    base = rend[["Ticker", "Nombre", "Precio (USD)", "Var. día"]].rename(
        columns={"Precio (USD)": "Precio", "Var. día": "Var. %"})
    sube = base.nlargest(15, "Var. %").reset_index(drop=True)
    baja = base.nsmallest(15, "Var. %").reset_index(drop=True)
    with lugar_franja:
        armar_franja(sube, baja)

with lugar_franja:
    ui.html(f"<div class='nota-franja'>Arriba: las 3 mayores alzas y las 3 mayores caídas del día y el tipo de cambio "
            f"dólar/peso chileno. Minigráficos de los últimos 3 meses. {ui.h(fuente_mov)}</div>")

with izquierda:
    if rend.empty:
        st.error(aviso_precios or "No fue posible cargar los precios. Recarga la página en unos minutos.")
    else:
        ui.mostrar_aviso(aviso_precios if aviso_precios and "Sin datos" not in aviso_precios else None)
        tab_hoy, tab_90, tab_todos, tab_buscar = st.tabs(
            ["Hoy", "Últimos 90 días", f"Todos los precios ({len(rend)})", "Buscar cualquier activo"])

        # ---------------- Hoy ----------------
        with tab_hoy:
            c1, c2 = st.columns(2, gap="medium")
            with c1:
                ui.tabla_movimientos(sube, "Mayores alzas del día", 10)
            with c2:
                ui.tabla_movimientos(baja, "Mayores caídas del día", 10)
            ui.html(f"<div class='fuente-tabla'>{ui.h(fuente_mov)} Haz clic en un ticker para ver su ficha "
                    f"en Yahoo Finance.</div>")

        # ---------------- 90 días ----------------
        with tab_90:
            tipos = sorted(rend["Tipo"].unique())
            elegidos = st.pills("Tipos de activo", tipos, selection_mode="multi", default=tipos, key="tipos_90")
            base = rend[rend["Tipo"].isin(elegidos or tipos)].dropna(subset=["Var. 90 días"])
            n = st.slider("Cantidad a mostrar", 5, 25, 10, key="n_90")
            c1, c2 = st.columns(2)
            with c1:
                mejores = base.nlargest(n, "Var. 90 días")
                st.plotly_chart(graficos.barras_rendimiento(mejores, "Var. 90 días", titulo="Mayor crecimiento en 90 días"),
                                theme=None, config=graficos.CONFIG)
            with c2:
                peores = base.nsmallest(n, "Var. 90 días")
                st.plotly_chart(graficos.barras_rendimiento(peores, "Var. 90 días", titulo="Mayor caída en 90 días"),
                                theme=None, config=graficos.CONFIG)
            st.dataframe(
                pd.concat([mejores.assign(Grupo="Mejor"), peores.assign(Grupo="Peor")])[
                    ["Grupo", "Ticker", "Nombre", "Tipo", "Precio (USD)", "Var. 90 días", "Últimos 90 días"]],
                hide_index=True,
                column_config={
                    "Precio (USD)": st.column_config.NumberColumn(format="dollar"),
                    "Var. 90 días": st.column_config.NumberColumn(format="percent"),
                    "Últimos 90 días": st.column_config.LineChartColumn("Últimos 90 días", width="medium"),
                })

        # ---------------- Todos ----------------
        with tab_todos:
            c1, c2 = st.columns([2, 3])
            texto = c1.text_input("Filtrar por ticker o nombre", placeholder="Ej.: AAPL, Tesla, oro, bitcoin")
            tipos_sel = c2.multiselect("Tipo", sorted(rend["Tipo"].unique()), key="tipos_todos")
            vista = rend
            if texto:
                patron = texto.strip().lower()
                vista = vista[vista["Ticker"].str.lower().str.contains(patron, regex=False)
                              | vista["Nombre"].str.lower().str.contains(patron, regex=False)]
            if tipos_sel:
                vista = vista[vista["Tipo"].isin(tipos_sel)]
            st.dataframe(
                vista.sort_values("Ticker"), hide_index=True, height=620,
                column_config={
                    "Precio (USD)": st.column_config.NumberColumn(format="dollar"),
                    "Var. día": st.column_config.NumberColumn(format="percent"),
                    "Var. 90 días": st.column_config.NumberColumn(format="percent"),
                    "Var. en el año": st.column_config.NumberColumn(format="percent"),
                    "Últimos 90 días": st.column_config.LineChartColumn("Últimos 90 días"),
                })
            st.caption("Universo: S&P 500 completo, principales ETFs, materias primas y criptomonedas. "
                       "Cualquier otro activo de Yahoo Finance se consulta en la pestaña «Buscar cualquier activo».")

        # ---------------- Buscar ----------------
        with tab_buscar:
            consulta = st.text_input("Nombre o ticker", placeholder="Ej.: Falabella, Nvidia, plata, Solana, SQM")
            if consulta:
                resultados = datos.buscar_ticker(consulta.strip())
                if resultados.empty:
                    st.warning("Yahoo no encontró resultados para esa búsqueda.")
                else:
                    st.dataframe(resultados, hide_index=True)
                    elegido = st.selectbox("Ver gráfico de", resultados["Ticker"].tolist())
                    serie, aviso = datos.precios_cierre([elegido], "1y")
                    ui.mostrar_aviso(aviso)
                    if elegido in serie.columns:
                        s = serie[elegido].dropna()
                        k1, k2, k3 = st.columns(3)
                        k1.metric("Último precio", ui.num(s.iloc[-1]), ui.pct(s.iloc[-1] / s.iloc[-2] - 1, 2))
                        k2.metric("Variación 90 días", ui.pct(s.iloc[-1] / s[s.index <= s.index[-1] - pd.Timedelta(days=90)].iloc[-1] - 1)
                                  if (s.index <= s.index[-1] - pd.Timedelta(days=90)).any() else "—")
                        k3.metric("Variación 1 año", ui.pct(s.iloc[-1] / s.iloc[0] - 1))
                        st.plotly_chart(graficos.linea_precio(s.rename(elegido), f"{elegido} · último año"),
                                        theme=None, config=graficos.CONFIG)

ui.aviso_legal()
