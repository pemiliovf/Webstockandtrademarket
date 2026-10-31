"""Panel 1 — Mercado: precios, mejores y peores rendimientos y noticias."""

import html

import numpy as np
import pandas as pd
import streamlit as st

from nucleo import datos, graficos, ui, universo

ui.preparar_pagina()
ui.encabezado("Mercado hoy",
              f"Precios, rendimientos y noticias desde Yahoo Finance · actualizado {datos.hora_chile()} (hora de Chile)")

# --------------------------------------------------------------------------
# Franja de índices
# --------------------------------------------------------------------------
franja, aviso_franja = datos.precios_cierre(universo.FRANJA_INICIO, "3mo")
columnas = st.columns(len(universo.FRANJA_INICIO))
for col, t in zip(columnas, universo.FRANJA_INICIO):
    s = franja[t].dropna() if t in franja.columns else pd.Series(dtype=float)
    with col:
        if len(s) >= 2:
            color = "inverse" if t == "^VIX" else ("off" if t == "CLP=X" else "normal")
            st.metric(universo.INDICES.get(t, universo.nombre_de(t)), ui.num(s.iloc[-1]),
                      ui.pct(s.iloc[-1] / s.iloc[-2] - 1, 2), delta_color=color, border=True,
                      chart_data=s.iloc[-60:].round(4).tolist(), chart_type="area")
        else:
            st.metric(universo.INDICES.get(t, t), "—", border=True)


# --------------------------------------------------------------------------
# Universo completo y rendimientos
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


univ = universo.universo_inicio()
with st.spinner(f"Descargando precios de {len(univ)} activos desde Yahoo Finance… "
                "(la primera visita tarda alrededor de un minuto; luego queda guardado 30 minutos)"):
    precios, aviso_precios = datos.precios_cierre(univ["Ticker"].tolist(), "6mo")
rend = calcular_rendimientos(precios, univ) if not precios.empty else pd.DataFrame()

izquierda, derecha = st.columns([2.2, 1], gap="large")

with izquierda:
    if rend.empty:
        st.error(aviso_precios or "No fue posible cargar los precios. Recarga la página en unos minutos.")
    else:
        ui.mostrar_aviso(aviso_precios if aviso_precios and "Sin datos" not in aviso_precios else None)
        tab_hoy, tab_90, tab_todos, tab_buscar = st.tabs(
            ["Hoy", "Últimos 90 días", f"Todos los precios ({len(rend)})", "Buscar cualquier activo"])

        # ---------------- Hoy ----------------
        with tab_hoy:
            sube, baja, aviso_scr = datos.movimientos_del_dia(15)
            fuente = "Screener de Yahoo Finance: todo el mercado de EE.UU."
            if sube is None or baja is None:
                fuente = "Calculado sobre el universo de la página (el screener de Yahoo no respondió)."
                base = rend[["Ticker", "Nombre", "Precio (USD)", "Var. día"]].rename(
                    columns={"Precio (USD)": "Precio", "Var. día": "Var. %"})
                sube = base.nlargest(15, "Var. %")
                baja = base.nsmallest(15, "Var. %")
            else:
                sube = sube.assign(**{"Var. %": sube["Var. %"] / 100}).drop(columns="Volumen", errors="ignore")
                baja = baja.assign(**{"Var. %": baja["Var. %"] / 100}).drop(columns="Volumen", errors="ignore")
            cfg = {
                "Precio": st.column_config.NumberColumn("Precio", format="dollar"),
                "Var. %": st.column_config.NumberColumn("Variación", format="percent"),
                "Volumen": st.column_config.NumberColumn("Volumen", format="compact"),
            }
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Mayores alzas del día")
                st.dataframe(sube, hide_index=True, column_config=cfg, height=560)
            with c2:
                st.subheader("Mayores caídas del día")
                st.dataframe(baja, hide_index=True, column_config=cfg, height=560)
            st.caption(fuente)

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

with derecha:
    st.subheader("Últimas noticias")
    lista, aviso_not = datos.noticias(14)
    ui.mostrar_aviso(aviso_not)
    for n in lista:
        cuando = n["fecha"].strftime("%d-%m %H:%M") if n["fecha"] is not None else ""
        st.markdown(
            f"<div class='noticia'><a href='{html.escape(str(n['url'] or ''), quote=True)}' target='_blank' "
            f"rel='noopener'>{html.escape(n['titulo'])}</a>"
            f"<div class='meta'>{html.escape(str(n['fuente']))} · {cuando}</div></div>", unsafe_allow_html=True)
    st.caption("Fuente: Yahoo Finance. Los enlaces abren el artículo original.")

ui.aviso_legal()
