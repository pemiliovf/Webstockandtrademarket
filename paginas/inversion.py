"""Panel 2 — Invertir: perfil de riesgo, cartera óptima, Monte Carlo y análisis técnico."""

import numpy as np
import pandas as pd
import streamlit as st

from nucleo import datos, graficos, modelo, montecarlo, ui, universo

ui.preparar_pagina()
ui.encabezado("Invertir: tu cartera óptima",
              "Modelo híbrido Black-Litterman + Markowitz, con vistas de un CAPM dinámico alimentado por betas "
              "rodantes y regímenes ocultos de Markov, proyectado con Monte Carlo.")

HORIZONTES = {"6 meses": 126, "1 año": 252, "2 años": 504, "3 años": 756, "5 años": 1260}
P = modelo.PARAMETROS_POR_DEFECTO

# --------------------------------------------------------------------------
# Formulario del inversionista
# --------------------------------------------------------------------------
with st.form("formulario_perfil", border=True):
    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        perfiles = list(modelo.PERFILES)
        perfil = st.radio("1. ¿Qué tan dispuesto estás a asumir riesgo?", perfiles, index=1,
                          captions=[modelo.PERFILES[p]["descripcion"] for p in perfiles])
    with c2:
        monto = st.number_input("2. ¿Cuánto quieres invertir? (USD, desde 1 hasta 9.999.999.999)",
                                min_value=1.0, max_value=9_999_999_999.0, value=10_000.0, step=500.0, format="%.2f")
        horizonte = st.select_slider("3. Horizonte de la proyección", options=list(HORIZONTES), value="1 año")
        n_sim = st.select_slider("Escenarios de Monte Carlo", options=[1000, 2000, 5000, 10000], value=5000)

    with st.expander("Opciones avanzadas del modelo"):
        candidatos = st.multiselect("Activos candidatos (el modelo elige entre estos)",
                                    options=sorted(set(universo.CANDIDATOS_CARTERA) | set(universo.ETFS) | set(universo.CRIPTOS)),
                                    default=universo.CANDIDATOS_CARTERA)
        extra = st.text_input("Agregar otros tickers de Yahoo (separados por coma)", placeholder="Ej.: TSLA, AMD, SQM")
        a1, a2, a3 = st.columns(3)
        anios = a1.slider("Años de historia", 3, 10, P["anios_historia"])
        ventana = a2.slider("Ventana de betas rodantes (días)", 60, 252, P["ventana_beta"], step=21)
        n_reg = a3.radio("Regímenes de Markov", [2, 3], index=0 if P["n_regimenes"] == 2 else 1, horizontal=True)
        b1, b2, b3 = st.columns(3)
        horizonte_vista = b1.slider("Horizonte de la vista CAPM (días)", 21, 252, P["horizonte_vista"], step=21)
        mezcla = b2.slider("Peso beta rodante vs. beta por régimen", 0.0, 1.0, P["mezcla_beta"], step=0.1)
        tau = b3.number_input("τ (tau) de Black-Litterman", 0.01, 1.0, P["tau"], step=0.01, format="%.2f")

    enviado = st.form_submit_button("Construir mi cartera", type="primary", width="stretch")


@st.cache_data(ttl=60 * 30, show_spinner=False, max_entries=16)
def calcular_cartera(candidatos: tuple, perfil: str, parametros: tuple):
    prm = dict(parametros)
    tickers = tuple(dict.fromkeys(candidatos + (universo.PROXY_MERCADO,)))
    precios, aviso = datos.precios_cierre(tickers, f"{prm['anios_historia']}y")
    if precios.empty:
        raise RuntimeError(aviso or "No se pudieron descargar precios.")
    rf = datos.tasa_libre_riesgo()
    caps = datos.capitalizaciones(tuple(c for c in candidatos if c in precios.columns))
    res = modelo.construir_cartera(precios, universo.PROXY_MERCADO, perfil, rf, caps, prm, list(candidatos))
    ultimos = precios.ffill().iloc[-1]
    mercado = precios[universo.PROXY_MERCADO].dropna()
    return res, ultimos, mercado, aviso


@st.cache_data(ttl=60 * 30, show_spinner=False, max_entries=8)
def simular_cartera(medias, vols, transicion, p0, v0: float, dias: int, n: int):
    return montecarlo.simular(v0, medias, vols, transicion, p0, dias, n)


if enviado:
    extras = [t.strip().upper() for t in extra.split(",") if t.strip()]
    lista = tuple(dict.fromkeys(candidatos + extras))
    if len(lista) < 3:
        st.error("Elige al menos 3 activos candidatos.")
    else:
        parametros = (("anios_historia", anios), ("ventana_beta", ventana), ("n_regimenes", n_reg),
                      ("horizonte_vista", horizonte_vista), ("mezcla_beta", mezcla), ("tau", tau),
                      ("min_observaciones", P["min_observaciones"]))
        with st.spinner("Descargando datos de Yahoo Finance y optimizando la cartera… (puede tardar 20-40 segundos)"):
            try:
                res, ultimos, mercado, aviso = calcular_cartera(lista, perfil, parametros)
                st.session_state["cartera_optima"] = {"res": res, "ultimos": ultimos, "mercado": mercado, "aviso": aviso,
                                                      "monto": monto, "horizonte": horizonte, "n_sim": n_sim}
            except Exception as e:
                st.session_state.pop("cartera_optima", None)
                st.error(f"No se pudo construir la cartera: {e}")

estado = st.session_state.get("cartera_optima")
if not estado:
    st.info("Completa el formulario y presiona **Construir mi cartera**.", icon="👆")
    ui.aviso_legal()
    st.stop()

res: modelo.ResultadoCartera = estado["res"]
monto, horizonte, ultimos = estado["monto"], estado["horizonte"], estado["ultimos"]
ui.mostrar_aviso(estado["aviso"] if estado["aviso"] and "Sin datos" not in (estado["aviso"] or "") else None)
if estado["aviso"] and "Sin datos" in estado["aviso"]:
    st.caption(estado["aviso"])
if res.descartados:
    st.caption("Excluidos por falta de historia suficiente: " + ", ".join(res.descartados))

# --------------------------------------------------------------------------
# Resultado: cartera óptima
# --------------------------------------------------------------------------
st.header(f"Cartera óptima · perfil {res.perfil.split(' (')[0].lower()}")
reg = res.regimenes
prob = reg.prob_actual[reg.actual]
k = st.columns(5)
k[0].metric("Retorno esperado anual", ui.pct(res.retorno_esperado), border=True)
k[1].metric("Volatilidad anual", ui.pct(res.volatilidad, signo=False), border=True)
k[2].metric("Índice de Sharpe", ui.num(res.sharpe, 2), border=True)
k[3].metric("Tasa libre de riesgo", ui.pct(res.rf, 2, signo=False), border=True, help="Letra del Tesoro de EE.UU. a 13 semanas (^IRX).")
k[4].metric("Régimen actual del mercado", reg.etiquetas[reg.actual], f"{ui.pct(prob, 0, False)} de probabilidad",
            delta_color="off", border=True)

tabla = res.tabla.copy()
tabla = tabla[tabla["Peso"] > 0].sort_values("Peso", ascending=False)
tabla["Nombre"] = [universo.nombre_de(t) for t in tabla["Ticker"]]
tabla["Monto (USD)"] = tabla["Peso"] * monto
tabla["Último precio"] = [float(ultimos.get(t, np.nan)) for t in tabla["Ticker"]]
tabla["Cantidad aprox."] = tabla["Monto (USD)"] / tabla["Último precio"]
tabla["Unidades enteras"] = np.where(tabla["Tipo"] == "Cripto", np.nan, np.floor(tabla["Cantidad aprox."]))
sobrante = monto - np.nansum(np.where(tabla["Tipo"] == "Cripto", tabla["Monto (USD)"],
                                      tabla["Unidades enteras"] * tabla["Último precio"]))

c1, c2 = st.columns([1, 1.5], gap="large")
with c1:
    st.plotly_chart(graficos.barras_pesos(res.pesos, titulo="Distribución por activo"), theme=None, config=graficos.CONFIG)
    st.plotly_chart(graficos.barras_por_tipo(res.tabla), theme=None, config=graficos.CONFIG)
with c2:
    st.markdown(ui.md(f"**Cómo repartir {ui.usd(monto)}**"))
    st.dataframe(
        tabla[["Ticker", "Nombre", "Tipo", "Peso", "Monto (USD)", "Último precio", "Cantidad aprox.", "Unidades enteras"]],
        hide_index=True, height=min(640, 38 * len(tabla) + 40),
        column_config={
            "Peso": st.column_config.ProgressColumn("Peso", format="percent", min_value=0, max_value=float(tabla["Peso"].max())),
            "Monto (USD)": st.column_config.NumberColumn(format="dollar"),
            "Último precio": st.column_config.NumberColumn(format="dollar"),
            "Cantidad aprox.": st.column_config.NumberColumn(format="%.4f", help="Con acciones fraccionadas"),
            "Unidades enteras": st.column_config.NumberColumn(format="%d", help="Si tu corredora no permite fracciones"),
        })
    st.caption(ui.md(f"Si compras solo unidades enteras (excepto cripto), te sobrarían aprox. {ui.usd(sobrante)}. "
                     f"Pesos de equilibrio calculados con {res.metodo_pesos}."))
    st.download_button("Descargar cartera (CSV)", tabla.to_csv(index=False).encode("utf-8"),
                       "cartera_optima.csv", "text/csv")

with st.expander("Cómo se construyó esta cartera (detalle del modelo)"):
    st.markdown(f"""
1. **Regímenes ocultos de Markov.** Un {reg.metodo.lower()} con {len(reg.etiquetas)} estados se ajustó a los
   retornos diarios del S&P 500 (SPY). Hoy el estado más probable es **{reg.etiquetas[reg.actual]}**.
2. **Betas rodantes.** Beta de cada activo contra el mercado en una ventana de {res.parametros['ventana_beta']} días,
   combinada ({ui.pct(res.parametros['mezcla_beta'], 0, False)} / {ui.pct(1 - res.parametros['mezcla_beta'], 0, False)})
   con la beta de cada activo dentro de cada régimen.
3. **CAPM dinámico (vistas).** Retorno esperado = tasa libre de riesgo + beta dinámica × prima de mercado esperada.
   La prima esperada para los próximos {res.parametros['horizonte_vista']} días es **{ui.pct(res.vistas['prima_esperada'])}**
   anual, ponderando la prima de cada régimen por su probabilidad futura.
4. **Black-Litterman.** Combina el equilibrio de mercado (Π = δ·Σ·w, con δ = {ui.num(res.delta, 2)} y τ = {res.parametros['tau']})
   con esas vistas; la confianza en cada vista baja si la beta es inestable o si el régimen futuro es incierto.
5. **Markowitz.** Maximiza retorno − (λ/2)·riesgo con λ = {modelo.PERFILES[res.perfil]['aversion']},
   máximo {ui.pct(modelo.PERFILES[res.perfil]['peso_max'], 0, False)} por activo,
   cripto hasta {ui.pct(modelo.PERFILES[res.perfil]['cripto_max'], 0, False)} y bonos/oro al menos
   {ui.pct(modelo.PERFILES[res.perfil]['defensivo_min'], 0, False)}.
""")
    regs = pd.DataFrame({
        "Régimen": reg.etiquetas,
        "Prob. hoy": reg.prob_actual,
        "Prob. próximos días": res.vistas["p_futuro"],
        "Retorno anual del mercado": reg.media_diaria * 252,
        "Volatilidad anual": reg.vol_diaria * np.sqrt(252),
        "Permanencia diaria": np.diag(reg.transicion),
    })
    st.dataframe(regs, hide_index=True, column_config={c: st.column_config.NumberColumn(format="percent")
                                                        for c in regs.columns if c != "Régimen"})
    st.plotly_chart(graficos.regimenes_mercado(estado["mercado"].reindex(reg.probabilidades.index).ffill(), reg.probabilidades),
                    theme=None, config=graficos.CONFIG)
    detalle = res.tabla[["Ticker", "Tipo", "Peso de mercado", "Equilibrio (Π)", "Beta rodante", "Beta dinámica",
                         "Vista CAPM dinámico (Q)", "Retorno Black-Litterman", "Volatilidad anual", "Peso"]]
    st.dataframe(detalle.sort_values("Peso", ascending=False), hide_index=True, column_config={
        c: st.column_config.NumberColumn(format="percent") for c in
        ["Peso de mercado", "Equilibrio (Π)", "Vista CAPM dinámico (Q)", "Retorno Black-Litterman", "Volatilidad anual", "Peso"]
    } | {"Beta rodante": st.column_config.NumberColumn(format="%.2f"),
         "Beta dinámica": st.column_config.NumberColumn(format="%.2f")})

# --------------------------------------------------------------------------
# Monte Carlo
# --------------------------------------------------------------------------
st.header("Proyección Monte Carlo")
st.caption("Cada escenario salta entre los regímenes de mercado según sus probabilidades de transición; "
           "la volatilidad de cada régimen sale de la historia y la tendencia de largo plazo se ancla al retorno "
           "esperado de Black-Litterman.")
pm = modelo.parametros_montecarlo_cartera(res)
dias = HORIZONTES[horizonte]
valores = simular_cartera(pm["medias"], pm["vols"], pm["transicion"], pm["p0"], float(monto), dias, int(estado["n_sim"]))
fechas = montecarlo.fechas_futuras(pd.Timestamp.today(), dias)
ui.bloque_montecarlo(valores, float(monto), fechas, horizonte)

# --------------------------------------------------------------------------
# Análisis técnico estilo TradingView
# --------------------------------------------------------------------------
st.header("Análisis técnico")
ui.bloque_tradingview(tabla["Ticker"].tolist(), "inversion")

ui.aviso_legal()
