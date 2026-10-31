"""Panel 3 — Mi cartera: posiciones actuales, trayectoria, Monte Carlo y estudio técnico."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

from nucleo import datos, graficos, modelo, montecarlo, tecnico, ui, universo

ui.preparar_pagina()
ui.encabezado("Mi cartera",
              "Registra lo que ya compraste —acciones, ETFs, oro, bonos o criptomonedas— y analizamos su rentabilidad "
              "real desde la compra, la comparamos con el S&P 500, proyectamos escenarios y hacemos un estudio técnico.",
              "Seguimiento de inversiones · uso académico")

HORIZONTES = {"3 meses": 63, "6 meses": 126, "1 año": 252, "2 años": 504, "3 años": 756, "5 años": 1260}
COL_ACTIVO, COL_FECHA, COL_CANT, COL_MONTO, COL_PRECIO = (
    "Activo", "Fecha de compra", "Cantidad (unidades)", "Monto invertido (USD)", "Precio por unidad al comprar")
COLUMNAS = [COL_ACTIVO, COL_FECHA, COL_CANT, COL_MONTO, COL_PRECIO]
NOMBRES_ANTIGUOS = {"Cantidad": COL_CANT, "Precio de compra (USD)": COL_PRECIO, "Precio de compra": COL_PRECIO}
DIVISA = "CLP=X"
EJEMPLO = pd.DataFrame({
    COL_ACTIVO: ["VOO", "AAPL", "GLD", "BTC-USD"],
    COL_FECHA: [date.today() - timedelta(days=d) for d in (700, 420, 300, 220)],
    COL_CANT: [10.0, 15.0, np.nan, 0.003],
    COL_MONTO: [np.nan, np.nan, 2000.0, np.nan],
    COL_PRECIO: [np.nan, np.nan, np.nan, np.nan],
})


def tabla_vacia() -> pd.DataFrame:
    return pd.DataFrame({COL_ACTIVO: pd.Series(dtype="str"), COL_FECHA: pd.Series(dtype="object"),
                         COL_CANT: pd.Series(dtype="float"), COL_MONTO: pd.Series(dtype="float"),
                         COL_PRECIO: pd.Series(dtype="float")})


def reiniciar_editor(df: pd.DataFrame):
    st.session_state["posiciones_base"] = df.reindex(columns=COLUMNAS)
    st.session_state["version_editor"] += 1
    st.session_state.pop("analisis_cartera", None)


if "posiciones_base" not in st.session_state:
    st.session_state["posiciones_base"] = tabla_vacia()
    st.session_state["version_editor"] = 0

# --------------------------------------------------------------------------
# 1. Agregar una inversión (formulario guiado)
# --------------------------------------------------------------------------
ui.seccion("1. Agrega tus compras", "Una fila por cada compra. Si compraste el mismo activo en distintas fechas, "
                                    "agrégalo varias veces.")
with st.form("agregar_inversion", clear_on_submit=True, border=True):
    c1, c2 = st.columns([1.5, 1])
    activo_txt = c1.selectbox(
        "Activo", list(universo.POPULARES), index=None, accept_new_options=True,
        placeholder="Busca o escribe: Bitcoin, Apple, VOO, SQM-B.SN…",
        help="Elige de la lista o escribe el ticker de Yahoo Finance. Bitcoin es BTC-USD (no «BTC», que en Yahoo es "
             "un fondo cotizado); las acciones chilenas terminan en .SN.")
    fecha_txt = c2.date_input("Fecha de compra", value=None, min_value=date(1990, 1, 1), max_value=date.today(),
                              format="DD/MM/YYYY")
    d1, d2, d3 = st.columns(3)
    cantidad_in = d1.number_input(
        "Cantidad comprada (unidades del activo)", min_value=0.0, value=None, step=0.001, format="%.8f",
        placeholder="Ej.: 0.003  (BTC)  ·  10  (acciones)",
        help="Cuántas acciones, cuotas o monedas compraste. Ejemplo: si compraste 0,003 bitcoin escribe 0.003.")
    monto_in = d2.number_input(
        "Monto invertido (USD)", min_value=0.0, value=None, step=10.0, format="%.2f",
        placeholder="Ej.: 191.92",
        help="Total de dólares que pagaste en esa compra. Si lo indicas sin la cantidad, la calculamos con el precio.")
    precio_in = d3.number_input(
        "Precio por unidad al comprar (opcional)", min_value=0.0, value=None, step=1.0, format="%.4f",
        placeholder="Ej.: 63974  (precio de 1 BTC)",
        help="Precio de UNA unidad del activo en tu compra (en USD; en pesos chilenos para acciones .SN). "
             "Si lo dejas vacío usamos el cierre de ese día según Yahoo Finance.")
    st.caption("Completa la **cantidad o el monto** (o ambos). Escribe los números sin separador de miles y con "
               "**punto decimal**: 63974 y 0.003, no 63.974 ni 0,003. Ejemplo: 0.003 BTC-USD comprados el 24/03 a "
               "63974 por bitcoin = US$ 191,92 invertidos.")
    agregar = st.form_submit_button("Agregar a mi cartera", type="primary", icon=":material/add:")

if agregar:
    faltan = []
    if not activo_txt:
        faltan.append("el activo")
    if fecha_txt is None:
        faltan.append("la fecha de compra")
    if not (cantidad_in and cantidad_in > 0) and not (monto_in and monto_in > 0):
        faltan.append("la cantidad o el monto invertido")
    if faltan:
        st.error("Falta " + ", ".join(faltan) + ".")
    else:
        ticker, nota = universo.normalizar_ticker(activo_txt)
        fila = pd.DataFrame([{COL_ACTIVO: ticker, COL_FECHA: fecha_txt,
                              COL_CANT: cantidad_in if cantidad_in else np.nan,
                              COL_MONTO: monto_in if monto_in else np.nan,
                              COL_PRECIO: precio_in if precio_in else np.nan}])
        base = st.session_state["posiciones_base"]
        reiniciar_editor(pd.concat([base, fila], ignore_index=True) if len(base) else fila)
        st.toast(f"Agregado: {ticker}" + (f" · {nota}" if nota else ""), icon=":material/check:")

# --------------------------------------------------------------------------
# 2. Revisar / editar la tabla
# --------------------------------------------------------------------------
ui.seccion("2. Revisa tu cartera", "Puedes corregir cualquier celda, borrar filas (selecciónalas y presiona la "
                                   "papelera) o guardar la tabla en un archivo para cargarla otro día.")
b1, b2, b3 = st.columns([1, 1, 2])
if b1.button("Cargar ejemplo", width="stretch"):
    reiniciar_editor(EJEMPLO.copy())
if b2.button("Limpiar tabla", width="stretch"):
    reiniciar_editor(tabla_vacia())
archivo = b3.file_uploader("Cargar cartera guardada (CSV)", type="csv", label_visibility="collapsed")
if archivo is not None and st.session_state.get("ultimo_csv") != archivo.file_id:
    try:
        cargado = pd.read_csv(archivo).rename(columns=NOMBRES_ANTIGUOS)
        cargado = cargado[[c for c in COLUMNAS if c in cargado.columns]]
        cargado[COL_FECHA] = pd.to_datetime(cargado[COL_FECHA], errors="coerce").dt.date
        reiniciar_editor(cargado)
        st.session_state["ultimo_csv"] = archivo.file_id
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")

editado = st.data_editor(
    st.session_state["posiciones_base"], num_rows="dynamic", hide_index=True, width="stretch",
    key=f"editor_{st.session_state['version_editor']}",
    column_config={
        COL_ACTIVO: st.column_config.TextColumn("Activo (ticker)", required=True,
                                                help="Ticker de Yahoo Finance: VOO, AAPL, BTC-USD, GLD, SQM-B.SN"),
        COL_FECHA: st.column_config.DateColumn("Fecha de compra", min_value=date(1990, 1, 1),
                                               max_value=date.today(), format="DD-MM-YYYY"),
        COL_CANT: st.column_config.NumberColumn("Cantidad (unidades)", min_value=0.0, format="%.8f",
                                                help="Número de acciones, cuotas o monedas. Ej.: 0.003 bitcoin"),
        COL_MONTO: st.column_config.NumberColumn("Monto invertido (USD)", min_value=0.0, format="%.2f",
                                                 help="Dólares pagados en esa compra"),
        COL_PRECIO: st.column_config.NumberColumn(
            "Precio por unidad", min_value=0.0, format="%.4f",
            help="Precio de 1 unidad al comprar (USD; CLP para acciones .SN). Vacío = cierre de ese día en Yahoo"),
    })

c1, c2, c3 = st.columns([1, 1, 1])
horizonte = c1.select_slider("Horizonte de la proyección", list(HORIZONTES), value="1 año")
modo_mc = c2.radio("Modelo de simulación", ["Regímenes de Markov", "Clásico (browniano)"], horizontal=True)
prudente = c3.toggle("Moderar la tendencia histórica", value=False,
                     help="Mezcla el rendimiento observado desde tu compra con un 7% anual de largo plazo. "
                          "Útil si compraste hace poco o en una racha excepcional.")
g1, g2 = st.columns([1, 3])
g1.download_button("Guardar mi cartera (CSV)", editado.to_csv(index=False).encode("utf-8"), "mi_cartera.csv",
                   "text/csv", width="stretch")
analizar = g2.button("Analizar mi cartera", type="primary", width="stretch")


# --------------------------------------------------------------------------
# Validación
# --------------------------------------------------------------------------
def validar(df: pd.DataFrame):
    errores, notas = [], []
    d = df.copy()
    d[COL_ACTIVO] = d[COL_ACTIVO].astype(str).str.strip().replace({"nan": "", "None": "", "NaN": ""})
    d = d[d[COL_ACTIVO] != ""]
    if d.empty:
        return None, ["Agrega al menos una inversión."], []
    normalizados = [universo.normalizar_ticker(t) for t in d[COL_ACTIVO]]
    d[COL_ACTIVO] = [t for t, _ in normalizados]
    notas += [n for _, n in normalizados if n]
    for c in (COL_CANT, COL_MONTO, COL_PRECIO):
        d[c] = pd.to_numeric(d[c], errors="coerce").where(lambda x: x > 0)
    d[COL_FECHA] = pd.to_datetime(d[COL_FECHA], errors="coerce")
    sin_dato = d[d[COL_CANT].isna() & d[COL_MONTO].isna()]
    if len(sin_dato):
        errores.append("Indica la cantidad o el monto invertido de: " + ", ".join(sin_dato[COL_ACTIVO]))
    sin_fecha = d[d[COL_FECHA].isna()]
    if len(sin_fecha):
        errores.append("Falta la fecha de compra de: " + ", ".join(sin_fecha[COL_ACTIVO]))
    futuras = d[d[COL_FECHA] > pd.Timestamp.today().normalize()]
    if len(futuras):
        errores.append("La fecha de compra no puede ser futura: " + ", ".join(futuras[COL_ACTIVO]))
    if errores:
        return None, errores, notas
    return d.reset_index(drop=True), [], list(dict.fromkeys(notas))


if analizar:
    posiciones, errores, notas_val = validar(editado)
    if errores:
        for e in errores:
            st.error(e)
        st.session_state.pop("analisis_cartera", None)
    else:
        st.session_state["analisis_cartera"] = {"posiciones": posiciones, "horizonte": horizonte,
                                                "modo": modo_mc, "prudente": prudente, "notas": notas_val}

estado = st.session_state.get("analisis_cartera")
if not estado:
    st.info("Agrega tus compras (o usa **Cargar ejemplo**) y presiona **Analizar mi cartera**.",
            icon=":material/arrow_upward:")
    ui.aviso_legal()
    st.stop()

pos: pd.DataFrame = estado["posiciones"]
tickers = list(dict.fromkeys(pos[COL_ACTIVO]))
chilenos = [t for t in tickers if t.endswith(".SN")]
inicio = min(pos[COL_FECHA].min(), pd.Timestamp.today() - pd.Timedelta(days=760)) - pd.Timedelta(days=10)

with st.spinner("Descargando la historia de tus activos desde Yahoo Finance…"):
    extra = [universo.PROXY_MERCADO] + ([DIVISA] if chilenos else [])
    precios, aviso = datos.precios_cierre(tickers + extra, inicio=inicio.normalize())
if precios.empty:
    st.error(aviso or "No se pudieron descargar los precios. Intenta nuevamente en unos minutos.")
    st.stop()
faltan = [t for t in tickers if t not in precios.columns]
if faltan:
    st.warning("Yahoo Finance no tiene datos para: " + ", ".join(faltan) + ". Revisa el ticker (usa el buscador de "
               "la sección 1); esas filas se omiten.")
    pos = pos[~pos[COL_ACTIVO].isin(faltan)].reset_index(drop=True)
    tickers = [t for t in tickers if t not in faltan]
if pos.empty:
    st.stop()

precios = precios.sort_index().ffill()
nativos = precios.copy()  # precios en la moneda original de cada activo
clp = precios[DIVISA] if DIVISA in precios.columns else None
for t in chilenos:
    if clp is not None and t in precios.columns:
        precios[t] = nativos[t] / clp   # acciones chilenas convertidas a USD con el dólar de cada día


# --------------------------------------------------------------------------
# Interpretación de cada compra (cantidad, monto y precio)
# --------------------------------------------------------------------------
def revisar_precio(p: float, referencia: float, moneda: str) -> tuple[float, str]:
    """Detecta el error típico de escribir 63.974 (punto de miles) en vez de 63974."""
    if not (referencia and np.isfinite(referencia)) or not p:
        return p, ""
    r = p / referencia
    if 0.5 <= r <= 2:
        return p, ""
    for factor in (1000, 1_000_000):
        if 0.5 <= r * factor <= 2:
            return p * factor, (f"precio {ui.num(p, 3)} interpretado como {ui.num(p * factor, 2)} {moneda} "
                                f"(separador de miles)")
    return p, (f"el precio ingresado difiere {ui.pct(r - 1, 0)} del cierre de mercado de ese día "
               f"({ui.num(referencia, 2)} {moneda}); revísalo")


filas, observaciones = [], []
for _, f in pos.iterrows():
    t = f[COL_ACTIVO]
    moneda = "CLP" if t.endswith(".SN") else "USD"
    s_nat = nativos[t].dropna()
    desde = s_nat[s_nat.index >= f[COL_FECHA]]
    ref = float(desde.iloc[0]) if len(desde) else float(s_nat.iloc[-1])
    fecha_ref = (desde.index[0] if len(desde) else s_nat.index[-1]).strftime("%d-%m-%Y")
    a_usd = 1.0
    if moneda == "CLP" and clp is not None:
        tc = clp[clp.index >= f[COL_FECHA]]
        a_usd = 1 / float(tc.iloc[0] if len(tc) else clp.iloc[-1])
    cant, monto, p = f[COL_CANT], f[COL_MONTO], f[COL_PRECIO]
    obs = []
    if pd.notna(p):
        p, aviso_p = revisar_precio(float(p), ref, moneda)
        obs += [aviso_p] if aviso_p else []
        origen = "ingresado por ti" + (" (corregido)" if aviso_p and "interpretado" in aviso_p else "")
    elif pd.notna(cant) and pd.notna(monto):
        p = float(monto) / (float(cant) * a_usd)
        origen = "calculado: monto ÷ cantidad"
        _, aviso_p = revisar_precio(p, ref, moneda)
        obs += [aviso_p.replace("el precio ingresado", "el precio implícito (monto ÷ cantidad)")] if aviso_p else []
    else:
        p = ref
        origen = f"cierre de Yahoo Finance del {fecha_ref}"
    if pd.isna(cant):
        cant = float(monto) / (p * a_usd)
    cant = float(cant)
    invertido = cant * p * a_usd
    if pd.notna(monto) and pd.notna(f[COL_PRECIO]) and abs(invertido / float(monto) - 1) > 0.05:
        obs.append(f"cantidad × precio = {ui.usd(invertido)} no coincide con el monto indicado "
                   f"({ui.usd(float(monto))}); se usó cantidad × precio")
    actual = float(precios[t].dropna().iloc[-1])
    filas.append({
        "Activo": t, "Tipo": universo.clase_de(t), "Fecha de compra": f[COL_FECHA], "Cantidad": cant,
        "Precio de compra (moneda original)": p, "Moneda": moneda, "Origen del precio": origen,
        "Precio de compra": p * a_usd, "Precio actual": actual,
        "Invertido": invertido, "Valor actual": actual * cant, "Observación": "; ".join(obs) or "—",
    })
    observaciones += [f"**{t}**: {o}." for o in obs]
lotes = pd.DataFrame(filas)
lotes["Ganancia (USD)"] = lotes["Valor actual"] - lotes["Invertido"]
lotes["Rentabilidad"] = lotes["Valor actual"] / lotes["Invertido"] - 1

with st.expander("Así interpretamos tus datos", expanded=bool(observaciones or estado.get("notas"))):
    for n in (estado.get("notas") or []):
        st.markdown(f"- {ui.md(n)}")
    for o in observaciones:
        st.markdown(f"- {ui.md(o)}")
    st.dataframe(lotes[["Activo", "Fecha de compra", "Cantidad", "Precio de compra (moneda original)", "Moneda",
                        "Origen del precio", "Invertido", "Observación"]], hide_index=True, column_config={
        "Fecha de compra": st.column_config.DateColumn(format="DD-MM-YYYY"),
        "Cantidad": st.column_config.NumberColumn(format="%.8f"),
        "Precio de compra (moneda original)": st.column_config.NumberColumn("Precio por unidad", format="localized"),
        "Invertido": st.column_config.NumberColumn("Invertido (USD)", format="dollar"),
        "Observación": st.column_config.TextColumn(width="large"),
    })
    st.caption("Monto invertido = cantidad × precio por unidad. Las acciones chilenas (.SN) cotizan en pesos y se "
               "convierten a dólares con el tipo de cambio de cada día (USD/CLP de Yahoo Finance).")

invertido, valor = lotes["Invertido"].sum(), lotes["Valor actual"].sum()
primera = lotes["Fecha de compra"].min()

# Trayectoria real (cada compra cuenta desde su fecha) y comparación con el S&P 500
fechas = precios.index[precios.index >= primera]
valor_real = pd.Series(0.0, index=fechas)
costo = pd.Series(0.0, index=fechas)
referencia = pd.Series(0.0, index=fechas)
spy = precios[universo.PROXY_MERCADO].reindex(fechas)
for _, l in lotes.iterrows():
    activo = (fechas >= l["Fecha de compra"]).astype(float)
    valor_real += precios[l["Activo"]].reindex(fechas).fillna(0) * l["Cantidad"] * activo
    costo += l["Invertido"] * activo
    spy_compra = spy[spy.index >= l["Fecha de compra"]]
    if len(spy_compra):
        referencia += l["Invertido"] / spy_compra.iloc[0] * spy * activo

ui.seccion("3. Resultado", "Rentabilidad real desde cada compra, en dólares")
k = st.columns(4)
k[0].metric("Monto invertido", ui.usd(invertido), border=True)
k[1].metric("Valor actual", ui.usd(valor), ui.pct(valor / invertido - 1), border=True)
k[2].metric("Ganancia / pérdida", ui.usd(valor - invertido), ui.pct(valor / invertido - 1), border=True)
k[3].metric("Si lo hubieras puesto en el S&P 500", ui.usd(float(referencia.iloc[-1])),
            ui.pct(float(referencia.iloc[-1]) / invertido - 1), border=True)

c1, c2 = st.columns([1.6, 1], gap="large")
with c1:
    st.plotly_chart(graficos.trayectoria_cartera(valor_real, costo, referencia), theme=None, config=graficos.CONFIG)
with c2:
    composicion = lotes.groupby("Activo")["Valor actual"].sum() / valor
    st.plotly_chart(graficos.barras_pesos(composicion, titulo="Composición actual"), theme=None, config=graficos.CONFIG)

st.dataframe(lotes[["Activo", "Tipo", "Fecha de compra", "Cantidad", "Precio de compra", "Precio actual", "Invertido",
                    "Valor actual", "Ganancia (USD)", "Rentabilidad"]], hide_index=True, column_config={
    "Fecha de compra": st.column_config.DateColumn(format="DD-MM-YYYY"),
    "Cantidad": st.column_config.NumberColumn("Cantidad (unidades)", format="%.8f"),
    "Precio de compra": st.column_config.NumberColumn("Precio de compra (USD)", format="dollar"),
    "Precio actual": st.column_config.NumberColumn(format="dollar"),
    "Invertido": st.column_config.NumberColumn(format="dollar"),
    "Valor actual": st.column_config.NumberColumn(format="dollar"),
    "Ganancia (USD)": st.column_config.NumberColumn(format="dollar"),
    "Rentabilidad": st.column_config.NumberColumn(format="percent"),
})

# --------------------------------------------------------------------------
# Proyección Monte Carlo desde la trayectoria desde la compra
# --------------------------------------------------------------------------
ui.seccion("Proyección Monte Carlo", "Escenarios futuros estimados con la historia de tus propios activos")
cantidades = lotes.groupby("Activo")["Cantidad"].sum()
habiles = precios.index[precios.index.dayofweek < 5]
cartera_actual = (precios.loc[habiles, cantidades.index] * cantidades).sum(axis=1)  # tus cantidades de hoy
historia = cartera_actual[cartera_actual.index >= primera]
nota_historia = ""
if len(historia) < 120:
    historia = cartera_actual.iloc[-252:]
    nota_historia = (" Como tu compra es reciente (menos de ~6 meses de datos), la estimación usa el último año "
                     "de historia de tus activos.")
r_log = np.log(historia).diff().dropna()
deriva_anual = float(r_log.mean() * 252)
vol_anual = float(r_log.std() * np.sqrt(252))
if estado["prudente"]:
    peso = len(r_log) / (len(r_log) + 504)
    deriva_anual = peso * deriva_anual + (1 - peso) * np.log(1.07)

dias = HORIZONTES[estado["horizonte"]]
usar_regimenes = estado["modo"] == "Regímenes de Markov" and len(r_log) >= 250
if usar_regimenes:
    reg = modelo.detectar_regimenes(r_log.apply(np.expm1), 2)
    estados_hist = reg.estados.reindex(r_log.index).to_numpy()
    medias = np.array([r_log[estados_hist == j].mean() if (estados_hist == j).sum() > 20 else r_log.mean() for j in range(2)])
    vols = np.array([r_log[estados_hist == j].std() if (estados_hist == j).sum() > 20 else r_log.std() for j in range(2)])
    pi_est = modelo.distribucion_estacionaria(reg.transicion)
    medias = medias + (deriva_anual / 252 - pi_est @ medias)
    valores = montecarlo.simular(valor, medias, vols, reg.transicion, reg.prob_actual, dias, 5000)
    texto_modelo = (f"Simulación con 2 regímenes de Markov detectados en tu propia cartera "
                    f"(hoy: **{reg.etiquetas[reg.actual]}**, {ui.pct(reg.prob_actual[reg.actual], 0, False)}).")
else:
    valores = montecarlo.simular_gbm(valor, deriva_anual / 252, vol_anual / np.sqrt(252), dias, 5000)
    texto_modelo = "Simulación clásica (movimiento browniano geométrico)."
    if estado["modo"] == "Regímenes de Markov":
        texto_modelo += " Se usó el modelo clásico porque hay menos de un año de datos para detectar regímenes."

st.caption(f"{texto_modelo} Tendencia anual usada: {ui.pct(deriva_anual)} (logarítmica), volatilidad anual "
           f"{ui.pct(vol_anual, signo=False)}, estimadas con tu historia desde el "
           f"{historia.index[0].strftime('%d-%m-%Y')}.{nota_historia}")
if deriva_anual > 0.5 or deriva_anual < -0.3:
    st.warning("La tendencia histórica es extrema; los escenarios pueden verse exagerados. "
               "Prueba activando «Moderar la tendencia histórica».", icon="⚠️")

# Recta de tendencia: regresión lineal del valor contra el tiempo, proyectada
fechas_fut = montecarlo.fechas_futuras(historia.index[-1], dias)
x_hist = (historia.index - historia.index[0]).days.to_numpy()
pendiente, intercepto = np.polyfit(x_hist, historia.to_numpy(), 1)
eje = historia.index.append(fechas_fut[1:])
recta = pd.Series(intercepto + pendiente * (eje - historia.index[0]).days.to_numpy(), index=eje)
ui.bloque_montecarlo(valores, valor, fechas_fut, estado["horizonte"], historia=historia, tendencia=recta)

# --------------------------------------------------------------------------
# Estudio técnico
# --------------------------------------------------------------------------
ui.seccion("Estudio técnico de tu cartera")
resumenes = []
for t in tickers:
    r = tecnico.resumen_tecnico(precios[t].dropna(), t)
    if "Precio" in r:
        compra_t = lotes.loc[lotes["Activo"] == t, "Fecha de compra"].min()
        r["Máx. caída desde la compra"] = tecnico.max_caida(precios[t][precios.index >= compra_t])
        resumenes.append({"Activo": t, "Peso": float(composicion.get(t, 0)), **r})
tecn = pd.DataFrame(resumenes)

rf = datos.tasa_libre_riesgo()
met = tecnico.metricas_riesgo(historia, precios[universo.PROXY_MERCADO].reindex(historia.index), rf)
if met:
    k = st.columns(len(met))
    for col, (nombre, v) in zip(k, met.items()):
        es_pct = nombre not in ("Sharpe", "Beta vs S&P 500", "Correlación vs S&P 500")
        col.metric(nombre, ui.pct(v, signo=nombre == "Retorno anualizado") if es_pct else ui.num(v, 2), border=True)

if not tecn.empty:
    alcistas = (tecn["Señal"] == "Alcista").sum()
    bajistas = (tecn["Señal"] == "Bajista").sum()
    mas_vol = tecn.loc[tecn["Volatilidad 30d"].idxmax()]
    concentrado = composicion[composicion > 0.4]
    puntos = [f"**{alcistas}** de {len(tecn)} activos con señal técnica alcista y **{bajistas}** con señal bajista.",
              f"Activo más volátil: **{mas_vol['Activo']}** (volatilidad anualizada de 30 días: {ui.pct(mas_vol['Volatilidad 30d'], signo=False)})."]
    sobrecompra = tecn.loc[tecn["Zona RSI"] == "sobrecompra", "Activo"].tolist()
    sobreventa = tecn.loc[tecn["Zona RSI"] == "sobreventa", "Activo"].tolist()
    if sobrecompra:
        puntos.append("En zona de sobrecompra (RSI ≥ 70): " + ", ".join(sobrecompra) + ".")
    if sobreventa:
        puntos.append("En zona de sobreventa (RSI ≤ 30): " + ", ".join(sobreventa) + ".")
    if len(concentrado):
        puntos.append("Concentración alta: " + ", ".join(f"{a} ({ui.pct(p, 0, False)})" for a, p in concentrado.items())
                      + " pesa más del 40% de la cartera.")
    st.markdown("\n".join(f"- {p}" for p in puntos))

    st.dataframe(
        tecn[["Activo", "Peso", "Señal", "Tendencia", "Precio", "Media 50", "Media 200", "RSI 14", "Zona RSI", "MACD",
              "Cruce MACD", "%B Bollinger", "Volatilidad 30d", "Dist. máx. 52 sem.", "Máx. caída desde la compra"]],
        hide_index=True,
        column_config={
            "Peso": st.column_config.NumberColumn(format="percent"),
            "Precio": st.column_config.NumberColumn(format="dollar"),
            "Media 50": st.column_config.NumberColumn(format="dollar"),
            "Media 200": st.column_config.NumberColumn(format="dollar"),
            "RSI 14": st.column_config.NumberColumn(format="%.1f"),
            "%B Bollinger": st.column_config.NumberColumn(format="%.2f"),
            "Volatilidad 30d": st.column_config.NumberColumn(format="percent"),
            "Dist. máx. 52 sem.": st.column_config.NumberColumn(format="percent"),
            "Máx. caída desde la compra": st.column_config.NumberColumn(format="percent"),
        })
    st.caption("Señal técnica = suma de cuatro criterios: precio sobre/bajo la media de 50 días, media de 50 "
               "sobre/bajo la de 200, MACD positivo/negativo y RSI en sobreventa/sobrecompra.")

if len(tickers) >= 2:
    corr = np.log(precios.loc[habiles, tickers]).diff().iloc[-252:].corr()
    st.plotly_chart(graficos.mapa_correlacion(corr), theme=None, config=graficos.CONFIG)

ui.seccion("Gráfico por activo", "TradingView con herramientas de dibujo y gráfico propio con datos de Yahoo Finance")
fechas_compra = lotes.groupby("Activo")["Fecha de compra"].min().to_dict()
ui.bloque_tradingview(tickers, "mi_cartera", fechas_compra)

ui.aviso_legal()
