"""Panel 3 — Mi cartera: posiciones actuales, trayectoria, Monte Carlo y estudio técnico."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

from nucleo import datos, graficos, modelo, montecarlo, tecnico, ui, universo

ui.preparar_pagina()
ui.encabezado("Mi cartera",
              "Ingresa lo que ya tienes invertido: acciones, ETFs (por ejemplo del S&P 500), oro, criptomonedas y más. "
              "Analizamos su trayectoria desde tu compra, proyectamos escenarios y hacemos un estudio técnico.")

HORIZONTES = {"3 meses": 63, "6 meses": 126, "1 año": 252, "2 años": 504, "3 años": 756, "5 años": 1260}
COLUMNAS = ["Activo", "Cantidad", "Fecha de compra", "Precio de compra (USD)"]
EJEMPLO = pd.DataFrame({
    "Activo": ["VOO", "AAPL", "GLD", "BTC-USD"],
    "Cantidad": [10.0, 15.0, 8.0, 0.05],
    "Fecha de compra": [date.today() - timedelta(days=d) for d in (700, 420, 300, 180)],
    "Precio de compra (USD)": [np.nan, np.nan, np.nan, np.nan],
})


def tabla_vacia() -> pd.DataFrame:
    return pd.DataFrame({"Activo": pd.Series(dtype="str"), "Cantidad": pd.Series(dtype="float"),
                         "Fecha de compra": pd.Series(dtype="object"),
                         "Precio de compra (USD)": pd.Series(dtype="float")})


if "posiciones_base" not in st.session_state:
    st.session_state["posiciones_base"] = tabla_vacia()
    st.session_state["version_editor"] = 0

# --------------------------------------------------------------------------
# Ayuda con tickers
# --------------------------------------------------------------------------
with st.expander("¿Cómo escribo cada activo? (tickers de Yahoo Finance)"):
    st.markdown("""
| Si invertiste en… | Escribe | Si invertiste en… | Escribe |
|---|---|---|---|
| Fondo/ETF del S&P 500 | `VOO`, `SPY` o `IVV` | Bitcoin | `BTC-USD` |
| Nasdaq-100 | `QQQ` | Ethereum | `ETH-USD` |
| Oro (ETF) | `GLD` o `IAU` | Oro (futuro) | `GC=F` |
| Bonos del Tesoro de EE.UU. | `TLT`, `IEF`, `SHY` | Plata | `SLV` |
| Acción de EE.UU. | su ticker: `AAPL`, `MSFT`, `TSLA` | Acción chilena | ticker + `.SN`: `SQM-B.SN`, `FALABELLA.SN` |
""")
    buscar = st.text_input("¿No sabes el ticker? Búscalo por nombre", placeholder="Ej.: Tesla, oro, Banco de Chile")
    if buscar:
        st.dataframe(datos.buscar_ticker(buscar.strip()), hide_index=True)
    st.caption("Los precios de acciones chilenas (.SN) vienen en pesos chilenos; el resto, en dólares.")

# --------------------------------------------------------------------------
# Ingreso de posiciones
# --------------------------------------------------------------------------
b1, b2, b3 = st.columns([1, 1, 2])
if b1.button("Cargar ejemplo", width="stretch"):
    st.session_state["posiciones_base"] = EJEMPLO.copy()
    st.session_state["version_editor"] += 1
    st.session_state.pop("analisis_cartera", None)
if b2.button("Limpiar tabla", width="stretch"):
    st.session_state["posiciones_base"] = tabla_vacia()
    st.session_state["version_editor"] += 1
    st.session_state.pop("analisis_cartera", None)
archivo = b3.file_uploader("Cargar cartera guardada (CSV)", type="csv", label_visibility="collapsed")
if archivo is not None and st.session_state.get("ultimo_csv") != archivo.file_id:
    try:
        cargado = pd.read_csv(archivo)
        cargado = cargado[[c for c in COLUMNAS if c in cargado.columns]]
        cargado["Fecha de compra"] = pd.to_datetime(cargado["Fecha de compra"], dayfirst=False, errors="coerce").dt.date
        st.session_state["posiciones_base"] = cargado.reindex(columns=COLUMNAS)
        st.session_state["version_editor"] += 1
        st.session_state["ultimo_csv"] = archivo.file_id
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")

st.markdown("**Tus inversiones** · agrega una fila por cada compra (puedes repetir un activo si compraste en distintas fechas).")
editado = st.data_editor(
    st.session_state["posiciones_base"], num_rows="dynamic", hide_index=True, width="stretch",
    key=f"editor_{st.session_state['version_editor']}",
    column_config={
        "Activo": st.column_config.TextColumn("Activo (ticker)", required=True, help="Ej.: VOO, AAPL, BTC-USD, GLD"),
        "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, format="%.6f",
                                                  help="Número de acciones, cuotas o monedas (admite decimales)"),
        "Fecha de compra": st.column_config.DateColumn("Fecha de compra", min_value=date(1990, 1, 1),
                                                       max_value=date.today(), format="DD-MM-YYYY"),
        "Precio de compra (USD)": st.column_config.NumberColumn(
            "Precio de compra (opcional)", min_value=0.0, format="%.4f",
            help="Si lo dejas vacío se usa el precio de cierre de ese día según Yahoo Finance"),
    })

c1, c2, c3 = st.columns([1, 1, 1])
horizonte = c1.select_slider("Horizonte de la proyección", list(HORIZONTES), value="1 año")
modo_mc = c2.radio("Modelo de simulación", ["Regímenes de Markov", "Clásico (browniano)"], horizontal=True)
prudente = c3.toggle("Moderar la tendencia histórica", value=False,
                     help="Mezcla el rendimiento observado desde tu compra con un 7% anual de largo plazo. "
                          "Útil si compraste hace poco o en una racha excepcional.")
st.download_button("Guardar mi cartera (CSV)", editado.to_csv(index=False).encode("utf-8"), "mi_cartera.csv", "text/csv")
analizar = st.button("Analizar mi cartera", type="primary", width="stretch")


# --------------------------------------------------------------------------
# Validación
# --------------------------------------------------------------------------
def validar(df: pd.DataFrame):
    errores = []
    d = df.copy()
    d["Activo"] = d["Activo"].astype(str).str.strip().str.upper().replace({"NAN": "", "NONE": ""})
    d = d[d["Activo"] != ""]
    if d.empty:
        return None, ["Agrega al menos una inversión."]
    d["Cantidad"] = pd.to_numeric(d["Cantidad"], errors="coerce")
    d["Fecha de compra"] = pd.to_datetime(d["Fecha de compra"], errors="coerce")
    d["Precio de compra (USD)"] = pd.to_numeric(d["Precio de compra (USD)"], errors="coerce")
    malos = d[(d["Cantidad"].isna()) | (d["Cantidad"] <= 0)]
    if len(malos):
        errores.append("Revisa la cantidad de: " + ", ".join(malos["Activo"]))
    sin_fecha = d[d["Fecha de compra"].isna()]
    if len(sin_fecha):
        errores.append("Falta la fecha de compra de: " + ", ".join(sin_fecha["Activo"]))
    futuras = d[d["Fecha de compra"] > pd.Timestamp.today().normalize()]
    if len(futuras):
        errores.append("La fecha de compra no puede ser futura: " + ", ".join(futuras["Activo"]))
    if errores:
        return None, errores
    return d.reset_index(drop=True), []


if analizar:
    posiciones, errores = validar(editado)
    if errores:
        for e in errores:
            st.error(e)
        st.session_state.pop("analisis_cartera", None)
    else:
        st.session_state["analisis_cartera"] = {"posiciones": posiciones, "horizonte": horizonte,
                                                "modo": modo_mc, "prudente": prudente}

estado = st.session_state.get("analisis_cartera")
if not estado:
    st.info("Ingresa tus inversiones (o usa **Cargar ejemplo**) y presiona **Analizar mi cartera**.", icon="👆")
    ui.aviso_legal()
    st.stop()

pos: pd.DataFrame = estado["posiciones"]
tickers = list(dict.fromkeys(pos["Activo"]))
inicio = min(pos["Fecha de compra"].min(), pd.Timestamp.today() - pd.Timedelta(days=760)) - pd.Timedelta(days=10)

with st.spinner("Descargando la historia de tus activos desde Yahoo Finance…"):
    precios, aviso = datos.precios_cierre(tickers + [universo.PROXY_MERCADO], inicio=inicio.normalize())
if precios.empty:
    st.error(aviso or "No se pudieron descargar los precios. Intenta nuevamente en unos minutos.")
    st.stop()
faltan = [t for t in tickers if t not in precios.columns]
if faltan:
    st.warning("Yahoo Finance no tiene datos para: " + ", ".join(faltan) + ". Revisa el ticker; esas filas se omiten.")
    pos = pos[~pos["Activo"].isin(faltan)].reset_index(drop=True)
    tickers = [t for t in tickers if t not in faltan]
if pos.empty:
    st.stop()

precios = precios.sort_index().ffill()

# --------------------------------------------------------------------------
# Posiciones y rentabilidad
# --------------------------------------------------------------------------
filas = []
for _, f in pos.iterrows():
    s = precios[f["Activo"]].dropna()
    desde = s[s.index >= f["Fecha de compra"]]
    precio_fecha = float(desde.iloc[0]) if len(desde) else float(s.iloc[-1])
    precio_compra = float(f["Precio de compra (USD)"]) if pd.notna(f["Precio de compra (USD)"]) else precio_fecha
    actual = float(s.iloc[-1])
    filas.append({
        "Activo": f["Activo"], "Tipo": universo.tipo_de_activo(f["Activo"]),
        "Fecha de compra": f["Fecha de compra"], "Cantidad": float(f["Cantidad"]),
        "Precio de compra": precio_compra, "Precio actual": actual,
        "Invertido": precio_compra * f["Cantidad"], "Valor actual": actual * f["Cantidad"],
    })
lotes = pd.DataFrame(filas)
lotes["Ganancia (USD)"] = lotes["Valor actual"] - lotes["Invertido"]
lotes["Rentabilidad"] = lotes["Valor actual"] / lotes["Invertido"] - 1

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

st.header("Resumen")
k = st.columns(4)
k[0].metric("Monto invertido", ui.usd(invertido), border=True)
k[1].metric("Valor actual", ui.usd(valor), ui.pct(valor / invertido - 1), border=True)
k[2].metric("Ganancia / pérdida", ui.usd(valor - invertido), border=True)
k[3].metric("Si lo hubieras puesto en el S&P 500", ui.usd(float(referencia.iloc[-1])),
            ui.pct(float(referencia.iloc[-1]) / invertido - 1), border=True)

c1, c2 = st.columns([1.6, 1], gap="large")
with c1:
    st.plotly_chart(graficos.trayectoria_cartera(valor_real, costo, referencia), theme=None, config=graficos.CONFIG)
with c2:
    composicion = lotes.groupby("Activo")["Valor actual"].sum() / valor
    st.plotly_chart(graficos.barras_pesos(composicion, titulo="Composición actual"), theme=None, config=graficos.CONFIG)

st.dataframe(lotes, hide_index=True, column_config={
    "Fecha de compra": st.column_config.DateColumn(format="DD-MM-YYYY"),
    "Cantidad": st.column_config.NumberColumn(format="%.6f"),
    "Precio de compra": st.column_config.NumberColumn(format="dollar"),
    "Precio actual": st.column_config.NumberColumn(format="dollar"),
    "Invertido": st.column_config.NumberColumn(format="dollar"),
    "Valor actual": st.column_config.NumberColumn(format="dollar"),
    "Ganancia (USD)": st.column_config.NumberColumn(format="dollar"),
    "Rentabilidad": st.column_config.NumberColumn(format="percent"),
})

# --------------------------------------------------------------------------
# Proyección Monte Carlo desde la trayectoria desde la compra
# --------------------------------------------------------------------------
st.header("Proyección Monte Carlo")
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
st.header("Estudio técnico de tu cartera")
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

st.subheader("Gráfico por activo")
fechas_compra = lotes.groupby("Activo")["Fecha de compra"].min().to_dict()
ui.bloque_tradingview(tickers, "mi_cartera", fechas_compra)

ui.aviso_legal()
