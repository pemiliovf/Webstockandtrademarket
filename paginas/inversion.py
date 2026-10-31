"""Panel 2 — Invertir: perfil de riesgo, cartera óptima, Monte Carlo y análisis técnico."""

import numpy as np
import pandas as pd
import streamlit as st

from nucleo import datos, graficos, modelo, montecarlo, seleccion, ui, universo

ui.preparar_pagina()
ui.encabezado("Invertir: tu cartera óptima",
              "Elige tu perfil de riesgo y un monto. El sistema preselecciona activos aptos para ese perfil y luego "
              "calcula los pesos con un modelo híbrido Black-Litterman + Markowitz, con vistas de un CAPM dinámico "
              "(betas rodantes y regímenes ocultos de Markov), y proyecta el resultado con Monte Carlo.",
              "Simulador de cartera · uso académico")

HORIZONTES = {"6 meses": 126, "1 año": 252, "2 años": 504, "3 años": 756, "5 años": 1260}
P = modelo.PARAMETROS_POR_DEFECTO
MODO_AUTO, MODO_MANUAL = "Automático (recomendado)", "Elijo mis activos"

# --------------------------------------------------------------------------
# Formulario del inversionista
# --------------------------------------------------------------------------
modo = st.segmented_control(
    "¿Cómo se eligen los activos de la cartera?", [MODO_AUTO, MODO_MANUAL], default=MODO_AUTO, key="modo_seleccion",
    help="Automático: el sistema evalúa ~60 activos (bonos, oro, ETFs, acciones líderes y cripto) y elige los aptos "
         "para tu perfil según volatilidad, caídas recientes y tendencia. Manual: tú eliges los activos.") or MODO_AUTO
if modo == MODO_AUTO:
    st.caption("No necesitas conocer ningún ticker: la preselección se recalcula con los precios del día, así que un "
               "activo que se desploma o entra en tendencia bajista queda fuera automáticamente.")

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

    candidatos, extra, filtrar = [], "", True
    if modo == MODO_MANUAL:
        candidatos = st.multiselect(
            "4. Activos candidatos (el modelo decide cuánto invertir en cada uno)",
            options=sorted(set(universo.CANDIDATOS_CARTERA) | set(seleccion.pool_automatico())
                           | set(universo.ETFS) | set(universo.CRIPTOS)),
            default=[], placeholder="Elige al menos 3 activos",
            format_func=lambda t: f"{t} · {universo.nombre_de(t)}")
        extra = st.text_input("Agregar otros tickers de Yahoo (separados por coma)", placeholder="Ej.: TSLA, AMD, SQM")
        filtrar = st.toggle("Excluir los activos que no pasen los filtros de riesgo de mi perfil", value=True,
                            help="Mismos filtros del modo automático: volatilidad máxima, caída del último mes, "
                                 "distancia al máximo de 52 semanas y tendencia.")

    with st.expander("Opciones avanzadas del modelo"):
        a1, a2, a3 = st.columns(3)
        anios = a1.slider("Años de historia", 3, 10, P["anios_historia"])
        ventana = a2.slider("Ventana de la regresión de betas (días)", 20, 252, P["ventana_beta"], step=10,
                            help="Paper: regresión MCO rodante de 60 días sobre excesos de retorno.")
        n_reg = a3.radio("Regímenes de Markov", [2, 3], index=0 if P["n_regimenes"] == 2 else 1, horizontal=True)
        b1, b2, b3 = st.columns(3)
        ventana_vista = b1.slider("Días que se promedian las vistas", 5, 60, P["ventana_vista"], step=1,
                                  help="Paper: VIEW_WINDOW = 20 días.")
        tope_vista = b2.slider("Tope de las vistas (± anual)", 0.10, 0.60, P["tope_vista"], step=0.05,
                               help="Paper: MU_CAP = 0,30.")
        tau = b3.number_input("τ (tau) de Black-Litterman", 0.01, 1.0, P["tau"], step=0.01, format="%.2f")
        s1, s2 = st.columns([1, 2])
        bandas = s1.toggle("Bandas sectoriales", value=P["bandas_sectoriales"],
                           help="Limita la exposición de la renta variable a cada sector a ± la banda alrededor de su "
                                "peso en el S&P 500 (paper: SECTOR_BAND = 0,10).")
        banda = s2.slider("Amplitud de la banda sectorial (±)", 0.05, 0.25, P["banda_sectorial"], step=0.01,
                          disabled=not bandas)

    enviado = st.form_submit_button("Construir mi cartera", type="primary", width="stretch")


@st.cache_data(ttl=60 * 30, show_spinner=False, max_entries=16)
def calcular_cartera(automatico: bool, candidatos: tuple, perfil: str, parametros: tuple, filtrar: bool):
    prm = dict(parametros)
    evaluados = tuple(seleccion.pool_automatico()) if automatico else candidatos
    tickers = tuple(dict.fromkeys(evaluados + (universo.INDICE_MERCADO, universo.TASA_LIBRE_RIESGO)))
    precios, aviso = datos.precios_cierre(tickers, f"{prm['anios_historia']}y")
    if precios.empty:
        raise RuntimeError(aviso or "No se pudieron descargar precios.")
    met = seleccion.metricas(precios[[t for t in evaluados if t in precios.columns]])
    if automatico:
        elegidos, evaluacion = seleccion.seleccionar(met, perfil)
    else:
        evaluacion = seleccion.revisar_manual(met, perfil)
        elegidos = (evaluacion.loc[evaluacion["Pasa filtros"], "Ticker"].tolist() if filtrar
                    else [t for t in candidatos if t in precios.columns])
    if len(elegidos) < 3:
        raise RuntimeError("Menos de 3 activos pasaron los filtros de riesgo de este perfil. Agrega más activos "
                           "candidatos, desactiva el filtro o usa el modo automático.")
    rf = datos.tasa_libre_riesgo()
    caps = datos.capitalizaciones(tuple(c for c in elegidos if c in precios.columns))
    irx = precios[universo.TASA_LIBRE_RIESGO] if universo.TASA_LIBRE_RIESGO in precios.columns else None
    res = modelo.construir_cartera(precios.drop(columns=[universo.TASA_LIBRE_RIESGO], errors="ignore"),
                                   universo.INDICE_MERCADO, perfil, rf, caps, prm, list(elegidos), serie_irx=irx)
    ultimos = precios.ffill().iloc[-1]
    mercado = precios[universo.INDICE_MERCADO].dropna()
    return res, ultimos, mercado, aviso, evaluacion


@st.cache_data(ttl=60 * 30, show_spinner=False, max_entries=8)
def simular_cartera(medias, vols, transicion, p0, v0: float, dias: int, n: int):
    return montecarlo.simular(v0, medias, vols, transicion, p0, dias, n)


if enviado:
    automatico = modo == MODO_AUTO
    extras = [universo.normalizar_ticker(t)[0] for t in extra.split(",") if t.strip()]
    lista = tuple(dict.fromkeys(list(candidatos) + extras))
    if not automatico and len(lista) < 3:
        st.error("Elige al menos 3 activos candidatos (o usa el modo automático).")
    else:
        parametros = (("anios_historia", anios), ("ventana_beta", ventana), ("n_regimenes", n_reg),
                      ("ventana_vista", ventana_vista), ("tope_vista", tope_vista), ("tau", tau),
                      ("bandas_sectoriales", bandas), ("banda_sectorial", banda),
                      ("horizonte_confianza", P["horizonte_confianza"]), ("min_observaciones", P["min_observaciones"]))
        with st.spinner("Descargando datos de Yahoo Finance, preseleccionando activos y optimizando la cartera… "
                        "(puede tardar 20-60 segundos)"):
            try:
                res, ultimos, mercado, aviso, evaluacion = calcular_cartera(automatico, lista, perfil, parametros,
                                                                            filtrar)
                st.session_state["cartera_optima"] = {
                    "res": res, "ultimos": ultimos, "mercado": mercado, "aviso": aviso, "evaluacion": evaluacion,
                    "automatico": automatico, "monto": monto, "horizonte": horizonte, "n_sim": n_sim}
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
ui.seccion(f"Cartera óptima · perfil {res.perfil.lower()}",
           "Preselección automática + Black-Litterman + Markowitz" if estado.get("automatico")
           else "Activos elegidos por ti + Black-Litterman + Markowitz")
reg = res.regimenes
prob = reg.prob_actual[reg.actual]
k = st.columns(3)
k[0].metric("Retorno esperado anual", ui.pct(res.retorno_esperado), border=True, help="μp = w*ᵀ μ_BL")
k[1].metric("Volatilidad anual", ui.pct(res.volatilidad, signo=False), border=True,
            help="σp = √(w*ᵀ Σ_BL w*), con Σ_BL = Σ + M (incluye el riesgo de los retornos)")
k[2].metric("Índice de Sharpe", ui.num(res.sharpe, 2), border=True, help="(μp − Rf) / σp")
k = st.columns(3)
k[0].metric("Diversificación efectiva (N_eff)", ui.num(res.n_efectivo, 1), border=True,
            help="N_eff = 1 / Σ wᵢ²: número equivalente de activos con igual peso.")
k[1].metric("Tasa libre de riesgo", ui.pct(res.rf, 2, signo=False), border=True,
            help="Letra del Tesoro de EE.UU. a 13 semanas (^IRX).")
k[2].metric("Régimen actual (Viterbi)", reg.etiquetas[reg.actual], f"{ui.pct(prob, 0, False)} de probabilidad",
            delta_color="off", border=True)

# --------------------------------------------------------------------------
# Cómo se eligieron los activos (etapa de preselección)
# --------------------------------------------------------------------------
evaluacion = estado.get("evaluacion")
if evaluacion is not None and not evaluacion.empty:
    n_sel = int((evaluacion["Estado"] == "Seleccionado").sum())
    n_exc = int((evaluacion["Estado"] == "Excluido").sum())
    reglas = seleccion.REGLAS[res.perfil]
    texto = (f"Se evaluaron **{len(evaluacion)} activos** con los precios de hoy: **{n_sel} pasaron** a la "
             f"optimización y **{n_exc} quedaron excluidos** por no cumplir los filtros del perfil "
             f"{res.perfil.lower()} (caída máxima en el último mes {ui.pct(reglas['caida_1m_min'], 0)}, distancia "
             f"máxima al máximo de 52 semanas {ui.pct(reglas['dist_max_52s_min'], 0)}, volatilidad tope por clase "
             f"y tendencia). Luego el modelo decide cuánto invertir en cada uno; puede asignar 0% a algunos.")
    with st.expander(f"Cómo se eligieron los activos · {n_sel} seleccionados, {n_exc} excluidos", expanded=False):
        st.markdown(texto)
        st.dataframe(
            evaluacion[["Estado", "Ticker", "Nombre", "Clase", "Volatilidad 1 año", "Var. 1 mes", "Momentum 12-1",
                        "Dist. máx. 52 sem.", "Sobre media 200", "Puntaje", "Motivo de exclusión"]],
            hide_index=True, height=min(560, 36 * len(evaluacion) + 40),
            column_config={
                "Volatilidad 1 año": st.column_config.NumberColumn(format="percent"),
                "Var. 1 mes": st.column_config.NumberColumn(format="percent"),
                "Momentum 12-1": st.column_config.NumberColumn(format="percent",
                                                              help="Retorno de los últimos 12 meses sin el último mes"),
                "Dist. máx. 52 sem.": st.column_config.NumberColumn(format="percent"),
                "Sobre media 200": st.column_config.CheckboxColumn("Sobre media 200 días"),
                "Puntaje": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1),
                "Motivo de exclusión": st.column_config.TextColumn(width="large"),
            })
        st.caption("Puntaje dentro de cada clase = combinación de momentum ajustado por riesgo, baja volatilidad y "
                   "cercanía al máximo de 52 semanas. El detalle está en la página «Acerca de».")

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

# --------------------------------------------------------------------------
# Bandas sectoriales
# --------------------------------------------------------------------------
expo, total_rv = modelo.exposicion_sectorial(res.pesos, res.parametros["banda_sectorial"])
if total_rv > 0:
    with st.expander(f"Exposición sectorial vs. S&P 500 · {res.restriccion_sectorial}", expanded=False):
        expo["Sector"] = expo["Sector"].map(universo.SECTORES_ES)
        st.markdown(f"Peso de la cartera en renta variable de EE.UU.: **{ui.pct(total_rv, 1, False)}**. Las "
                    f"exposiciones se miden sobre esa parte; los ETF diversificados (SPY, QQQ, VTI…) se cuentan con "
                    f"la composición sectorial del índice. Pesos del S&P 500 estimados al "
                    f"{universo.FECHA_PESOS_SECTORES} (ChartRow).")
        st.dataframe(expo, hide_index=True, column_config={
            c: st.column_config.NumberColumn(format="percent") for c in
            ["Peso en el S&P 500", "Banda mínima", "Banda máxima", "Exposición de la cartera"]})
        st.plotly_chart(graficos.bandas_sectoriales(expo), theme=None, config=graficos.CONFIG)

with st.expander("Cómo se construyó esta cartera (detalle del modelo)"):
    st.markdown(f"""
0. **Preselección.** {"Automática: se evaluaron ~60 activos y se tomaron los mejor puntuados de cada clase que pasaron los filtros de riesgo y tendencia del perfil." if estado.get("automatico") else "Activos elegidos por ti, revisados con las mismas reglas de riesgo del perfil."}
1. **Excesos de retorno.** Retornos logarítmicos diarios menos la tasa libre de riesgo de cada día
   (Rf_t = IRX_t / (100·252)), para los activos y para el S&P 500 (^GSPC).
2. **Regímenes ocultos de Markov.** Un {reg.metodo.lower()} con {len(reg.etiquetas)} estados se ajustó a los
   excesos de retorno estandarizados del S&P 500; los estados se asignan con el algoritmo de Viterbi. Hoy el
   régimen es **{reg.etiquetas[reg.actual]}**.
3. **CAPM rodante.** Beta de cada activo por regresión MCO de su exceso de retorno sobre el del mercado, en una
   ventana móvil de {res.parametros['ventana_beta']} días.
4. **Vistas CAPM-HMM.** μ̂ᵢ,ₜ = Rfₜ + βᵢ,ₜ · μₘ^(sₜ), donde μₘ^(s) es el exceso de retorno medio del mercado en el
   régimen s. Se promedian los últimos {res.parametros['ventana_vista']} días y se anualizan, acotadas a
   ±{ui.pct(res.parametros['tope_vista'], 0, False)}. Prima de mercado efectiva en esa ventana:
   **{ui.pct(res.vistas['prima_vista'])}** anual.
5. **Black-Litterman.** Combina el equilibrio de mercado (Π = δ·Σ·w, con δ = {ui.num(res.delta, 2)} y τ = {res.parametros['tau']})
   con esas vistas; la confianza en cada vista baja si la beta es inestable o si el régimen futuro es incierto.
   La covarianza posterior es Σ_BL = Σ + M.
6. **Markowitz.** Maximiza retorno − (λ/2)·riesgo con λ = {modelo.PERFILES[res.perfil]['aversion']},
   máximo {ui.pct(modelo.PERFILES[res.perfil]['peso_max'], 0, False)} por activo,
   cripto hasta {ui.pct(modelo.PERFILES[res.perfil]['cripto_max'], 0, False)}, bonos/oro al menos
   {ui.pct(modelo.PERFILES[res.perfil]['defensivo_min'], 0, False)} y {res.restriccion_sectorial}.
""")
    regs = pd.DataFrame({
        "Régimen": reg.etiquetas,
        "Prob. hoy": reg.prob_actual,
        "Prob. próximos 3 meses": res.vistas["p_futuro"],
        "Exceso de retorno anual del mercado": reg.media_diaria * 252,
        "Volatilidad anual": reg.vol_diaria * np.sqrt(252),
        "Permanencia diaria": np.diag(reg.transicion),
    })
    st.dataframe(regs, hide_index=True, column_config={c: st.column_config.NumberColumn(format="percent")
                                                        for c in regs.columns if c != "Régimen"})
    st.plotly_chart(graficos.regimenes_mercado(estado["mercado"].reindex(reg.probabilidades.index).ffill(), reg.probabilidades),
                    theme=None, config=graficos.CONFIG)
    detalle = res.tabla[["Ticker", "Tipo", "Sector", "Peso de mercado", "Equilibrio (Π)", "Beta rodante",
                         "Beta media (ventana vista)", "Vista CAPM-HMM (Q)", "Retorno Black-Litterman",
                         "Volatilidad anual", "Peso"]].copy()
    detalle["Sector"] = detalle["Sector"].map(lambda x: universo.SECTORES_ES.get(x, x))
    st.dataframe(detalle.sort_values("Peso", ascending=False), hide_index=True, column_config={
        c: st.column_config.NumberColumn(format="percent") for c in
        ["Peso de mercado", "Equilibrio (Π)", "Vista CAPM-HMM (Q)", "Retorno Black-Litterman", "Volatilidad anual", "Peso"]
    } | {"Beta rodante": st.column_config.NumberColumn(format="%.2f"),
         "Beta media (ventana vista)": st.column_config.NumberColumn(format="%.2f")})

# --------------------------------------------------------------------------
# Monte Carlo
# --------------------------------------------------------------------------
ui.seccion("Proyección Monte Carlo", "Simulación con cambios de régimen de Markov")
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
ui.seccion("Análisis técnico", "Gráfico interactivo de TradingView y estudio propio con datos de Yahoo Finance")
ui.bloque_tradingview(tabla["Ticker"].tolist(), "inversion")

ui.aviso_legal()
