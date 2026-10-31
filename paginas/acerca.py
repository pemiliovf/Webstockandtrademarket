"""Acerca de: propósito, fuentes de datos y metodología de los cálculos."""

import streamlit as st

from nucleo import modelo, noticias, seleccion, ui, universo
from nucleo.config import AUTORES

ui.preparar_pagina()
ui.encabezado("Acerca de esta plataforma",
              "Propósito, alcance, fuentes de datos y metodología de cada cálculo que realiza la página.",
              "Metodología")

# --------------------------------------------------------------------------
# Propósito y alcance
# --------------------------------------------------------------------------
ui.seccion("Propósito y alcance")
c1, c2 = st.columns([1.6, 1], gap="large")
with c1:
    st.markdown(f"""
**webstockandtrademarket** es un proyecto **académico y de estudio**. Su objetivo es mostrar, con datos reales de
mercado, cómo se comportan los activos financieros y cómo distintas estrategias y modelos cuantitativos de la teoría
financiera —selección de carteras, valoración por riesgo sistemático, detección de regímenes de mercado y simulación
estocástica— traducen esa información en métricas de rendimiento y riesgo.

La plataforma **no es un corredor de bolsa ni un medio para invertir**:

- no ejecuta órdenes de compra o venta, no custodia valores y no recibe ni administra dinero;
- no ofrece productos financieros ni cobra por sus resultados;
- sus resultados **no constituyen asesoría, recomendación ni oferta de inversión** en los términos de la
  Ley N.º 21.521 (Ley Fintec) y la normativa de la Comisión para el Mercado Financiero (CMF);
- toda cifra proyectada es una **estimación estadística** basada en información histórica; las rentabilidades
  pasadas no garantizan rentabilidades futuras.

Quien desee invertir debe hacerlo a través de intermediarios autorizados y, de preferencia, con asesoría profesional
registrada ante la CMF.{(" Desarrollado por " + AUTORES + ".") if AUTORES else ""}
""")
with c2:
    st.markdown("**Qué hace cada panel**")
    st.markdown("""
| Panel | Función |
|---|---|
| **Mercado** | Movimientos del día, rendimientos de 90 días, precios de ~570 activos y noticias económicas. |
| **Invertir** | Simula una cartera óptima según un perfil de riesgo y la proyecta con Monte Carlo. |
| **Mi cartera** | Mide la rentabilidad real de compras ya realizadas y proyecta escenarios. |
| **Acerca de** | Metodología, supuestos y referencias. |
""")

# --------------------------------------------------------------------------
# Fuentes de datos
# --------------------------------------------------------------------------
ui.seccion("Fuentes de datos y frecuencia de actualización")
st.markdown("""
- **Precios**: Yahoo Finance, mediante la librería de código abierto `yfinance`. Se usan cierres diarios
  **ajustados por dividendos y divisiones de acciones** (retorno total). Los datos pueden tener un retraso de
  15-20 minutos respecto del mercado y no son una fuente oficial.
- **Mayores alzas y caídas del día**: *screener* predefinido de Yahoo Finance (acciones de EE.UU. con
  capitalización ≥ US\\$ 2.000 millones, precio ≥ US\\$ 5 y volumen mínimo; alzas > 3 % y caídas > 2,5 %).
- **Universo del panel Mercado**: componentes vigentes del S&P 500 (lista pública de Wikipedia), más ETFs,
  materias primas y criptomonedas seleccionadas.
- **Tasa libre de riesgo**: rendimiento de la letra del Tesoro de EE.UU. a 13 semanas (`^IRX`).
- **Tipo de cambio**: USD/CLP de Yahoo Finance (`CLP=X`), referencial; no corresponde al dólar observado
  publicado por el Banco Central de Chile.
- **Gráficos interactivos**: widget oficial y gratuito de TradingView, con sus propios datos.
- **Actualización**: precios, movimientos y noticias se guardan en memoria **30 minutos** y luego se vuelven a
  consultar; el bloque de noticias se refresca solo cada 30 minutos aunque la página quede abierta.
""")
st.markdown("**Noticias** — solo secciones de economía, finanzas y mercados. Cada titular enlaza a la nota original:")
filas = "\n".join(f"| {f['nombre']} | {f['region']} | {f['seccion']} | [{f['url_seccion']}]({f['url_seccion']}) |"
                  for f in noticias.FUENTES)
st.markdown("| Medio | Ámbito | Sección | Dirección |\n|---|---|---|---|\n" + filas)
st.caption("Se leen los canales RSS oficiales de cada sección. El Banco Central de Chile no publica RSS, por lo que sus "
           "publicaciones (y las de cualquier medio cuyo canal no responda) se obtienen de Google News filtrando por el "
           "dominio oficial del emisor. Se priorizan las notas recientes que mencionan variables de mercado (tasas, "
           "inflación, bolsas, divisas, materias primas, bancos centrales) con un máximo de 4 por medio.")

# --------------------------------------------------------------------------
# Panel Mercado
# --------------------------------------------------------------------------
ui.seccion("Metodología · Panel Mercado")
st.markdown("Con $P_t$ el cierre ajustado del día $t$, las variaciones que se muestran son retornos simples:")
st.latex(r"r_{\text{día}} = \frac{P_t}{P_{t-1}} - 1,\qquad r_{90} = \frac{P_t}{P_{t-90\,\text{días}}} - 1,"
         r"\qquad r_{\text{año}} = \frac{P_t}{P_{\text{31-dic}}} - 1")
st.markdown("La franja superior muestra las tres mayores alzas y las tres mayores caídas del día según el screener "
            "de Yahoo Finance (si no responde, se calculan sobre el universo de la página) y el tipo de cambio USD/CLP, "
            "cada uno con un minigráfico de sus últimos tres meses.")

# --------------------------------------------------------------------------
# Panel Invertir
# --------------------------------------------------------------------------
ui.seccion("Metodología · Panel Invertir (cartera óptima)",
           "Proceso en dos etapas: preselección de activos y optimización de pesos")

st.markdown("#### Etapa 0 · Preselección de activos")
st.markdown("""
En el modo **automático** el usuario no elige activos. Se evalúan ~60 instrumentos líquidos de cinco clases
(bonos del Tesoro y corporativos de grado de inversión, oro y metales, ETFs de acciones, acciones líderes y
criptomonedas) con los precios del día. Para cada activo se calculan:
""")
st.latex(r"\sigma_{1a} = \sqrt{252}\;\operatorname{sd}\!\left(\ln\tfrac{P_t}{P_{t-1}}\right)_{\text{último año}},\qquad "
         r"r_{1m} = \frac{P_t}{P_{t-21}} - 1,\qquad "
         r"\text{MOM}_{12\text{-}1} = \frac{P_{t-21}}{P_{t-252}} - 1,\qquad"
         r"DD_{52} = \frac{P_t}{\max_{52\,\text{sem}} P} - 1")
st.markdown("""
(365 y 30 días para criptomonedas, que cotizan todos los días). Un activo queda **excluido** si incumple alguno de
estos filtros, cuyos umbrales dependen del perfil:
""")
filas_reglas = []
for perfil, r in seleccion.REGLAS.items():
    vols = ", ".join(f"{c}: {v:.0%}" for c, v in r["vol_max"].items() if v > 0)
    cupos = ", ".join(f"{c}: {n}" for c, n in r["cupos"].items() if n > 0)
    filas_reglas.append(f"| {perfil} | {r['caida_1m_min']:.0%} | {r['dist_max_52s_min']:.0%} | {vols} | {cupos} |")
st.markdown("| Perfil | Caída máx. último mes | Distancia máx. al máximo de 52 sem. | Volatilidad anual máxima | "
            "Activos por clase |\n|---|---|---|---|---|\n" + "\n".join(filas_reglas))
st.markdown("""
Además se excluye toda **tendencia bajista confirmada** (precio bajo su media móvil de 200 días *y* momentum 12-1
negativo), salvo en bonos, que se juzgan solo por riesgo. Entre los activos que pasan, se ordena cada clase con un
puntaje basado en rangos percentiles:
""")
st.latex(r"S_i = w_m \cdot \operatorname{rank}\!\left(\frac{\text{MOM}_{12\text{-}1}}{\sigma_{1a}}\right)"
         r"+ w_v \cdot \operatorname{rank}(-\sigma_{1a}) + w_d \cdot \operatorname{rank}(DD_{52})")
st.markdown("""
con $(w_m, w_v, w_d)$ = (0,30; 0,50; 0,20) defensivo, (0,45; 0,35; 0,20) moderado y (0,60; 0,15; 0,25)
arriesgado, y se toman los mejores de cada clase hasta su cupo. **Por qué esta etapa:** el CAPM explica el retorno
esperado solo con el riesgo sistemático (beta), por lo que un desplome idiosincrático reciente de una empresa casi no
cambia su vista de retorno; y Markowitz optimiza pesos, pero no decide qué activos son razonables para un perfil. La
preselección introduce reglas explícitas basadas en evidencia empírica —momentum (Jegadeesh y Titman, 1993), filtro de
tendencia de 200 días (Faber, 2007) y anomalía de baja volatilidad (Ang et al., 2006; Frazzini y Pedersen, 2014)—.
En el modo **manual** se aplican los mismos filtros a los activos que elige el usuario (puede desactivarlos).
""")

st.markdown("#### Etapa 1 · Retornos, excesos de retorno y covarianza")
st.markdown("Siguiendo la especificación del paper de referencia, se usan retornos logarítmicos diarios y excesos de "
            "retorno sobre la tasa libre de riesgo **de cada día**, tanto para los activos como para el S&P 500 "
            "(`^GSPC`):")
st.latex(r"r_{i,t} = \ln\frac{P_{i,t}}{P_{i,t-1}},\qquad Rf_t = \frac{IRX_t}{100\times 252},\qquad "
         r"r^{ex}_{i,t} = r_{i,t} - Rf_t")
st.markdown("La covarianza se estima con el **estimador de contracción de Ledoit y Wolf (2004)**, que reduce el error de "
            "estimación de la covarianza muestral (el paper usa la muestral):")
st.latex(r"\hat\Sigma = \delta^{*} F + (1-\delta^{*})\,S,\qquad \Sigma_{\text{anual}} = 252\,\hat\Sigma")

st.markdown("#### Etapa 2 · Regímenes ocultos de Markov")
st.markdown("Los excesos de retorno del S&P 500, **estandarizados**, se modelan con un **modelo oculto de Markov "
            "gaussiano** (Hamilton, 1989) estimado por máxima verosimilitud con el algoritmo EM (Baum-Welch); los "
            "regímenes se asignan con el **algoritmo de Viterbi**:")
st.latex(r"r^{ex}_{m,t} \mid s_t = k \sim \mathcal N(\mu_k, \sigma_k^2),\qquad \Pr(s_{t+1}=j \mid s_t=i) = p_{ij},"
         r"\qquad \hat s_{1:T} = \arg\max_{s_{1:T}} \Pr(s_{1:T}\mid r^{ex}_{m,1:T})")
st.markdown("Con 2 estados se etiquetan *Bajista / turbulento* y *Alcista / tranquilo* según su media. La matriz de "
            "transición también se usa para medir cuán incierto es el régimen de los próximos 3 meses (Etapa 4).")

st.markdown("#### Etapa 3 · CAPM rodante y vistas CAPM-HMM")
st.markdown("La beta de cada activo se estima por **mínimos cuadrados ordinarios en una ventana móvil** de 60 días "
            "(paper, sección 3.3):")
st.latex(r"r^{ex}_{i,t} = \alpha_{i,t} + \beta_{i,t}\, r^{ex}_{m,t} + \varepsilon_{i,t}")
st.markdown("Con el régimen de cada día y la beta dinámica se construye el retorno esperado condicional, que luego "
            "se promedia en los últimos 20 días, se anualiza y se acota a ±30 % (paper, sección 3.5):")
st.latex(r"\hat\mu_{i,t} = Rf_t + \beta_{i,t}\,\mu_m^{(s_t)},\qquad "
         r"\mu_m^{(k)} = E\big[r^{ex}_{m,t}\mid s_t = k\big],\qquad "
         r"Q_i = \operatorname{clip}\!\Big(252\cdot\tfrac{1}{20}\textstyle\sum_{t=T-19}^{T}\hat\mu_{i,t},\ -0{,}30,\ 0{,}30\Big)")

st.markdown("#### Etapa 4 · Black-Litterman")
st.markdown("Se combina el equilibrio de mercado implícito con las vistas (Black y Litterman, 1992; He y Litterman, "
            "1999), con vistas absolutas ($P = I$):")
st.latex(r"\Pi = \delta\,\Sigma\,w_{\text{mkt}},\qquad "
         r"\delta = \frac{252\;\overline{r^{ex}_m}}{252\;\operatorname{Var}(r^{ex}_m)} \in[1{,}5;\,4]")
st.latex(r"M = \big[(\tau\Sigma)^{-1} + P^\top\Omega^{-1}P\big]^{-1},\qquad "
         r"\mu_{BL} = M\big[(\tau\Sigma)^{-1}\Pi + P^\top\Omega^{-1}Q\big],\qquad \Sigma_{BL} = \Sigma + M")
st.latex(r"\Omega_{ii} = \frac{\tau\,\Sigma_{ii}\,\big(1 + \text{inestabilidad}(\beta_i)\big)}"
         r"{\max\!\big(\max_k \bar p_k,\ 0{,}34\big)}")
st.markdown("""
$w_{\\text{mkt}}$ son pesos por capitalización bursátil (o inverso de la volatilidad si falta ese dato) y $\\tau = 0{,}05$.
La inestabilidad de la beta es su coeficiente de variación en los últimos 63 días y $\\bar p_k$ la probabilidad media
de cada régimen en los próximos 3 meses: una beta inestable o un régimen futuro incierto reducen la confianza en la
vista.

**Nota sobre $\\Sigma_{BL}$.** $M$ mide la incertidumbre sobre el *retorno medio*; el riesgo de los *retornos* es
$\\Sigma + M$. Como $M \\preceq \\tau\\Sigma$, usar solo $M$ como matriz de riesgo daría una volatilidad de a lo más
$\\sqrt{\\tau}$ veces la verdadera y un Sharpe inflado; por eso se usa la covarianza predictiva $\\Sigma + M$.
""")

st.markdown("#### Etapa 5 · Optimización media-varianza de Markowitz con bandas sectoriales")
st.latex(r"\max_{w}\; w^\top\mu_{BL} - \frac{\lambda}{2}\,w^\top\Sigma_{BL}\,w\quad"
         r"\text{s.a.}\quad \textstyle\sum_i w_i = 1,\;\; 0 \le w_i \le w_{\max},\;\;"
         r"\sum_{i\in\text{cripto}} w_i \le c_{\max},\;\; \sum_{i\in\text{defensivos}} w_i \ge d_{\min}")
st.latex(r"\big|\,E_s(w) - b_s\,RV(w)\,\big| \le 0{,}10\cdot RV(w)\quad \forall s,\qquad "
         r"E_s(w) = \textstyle\sum_i A_{is}\,w_i,\qquad RV(w) = \sum_{i\in\text{renta variable}} w_i")
st.markdown(f"""
**Bandas sectoriales** (paper: `SECTOR_BAND = 0,10`): la exposición a cada sector GICS de la parte invertida en renta
variable debe quedar a ±10 puntos del peso de ese sector en el S&P 500 ($b_s$). $A_{{is}} = 1$ si el activo $i$
(acción o ETF sectorial) pertenece al sector $s$; los ETF diversificados (SPY, VTI, QQQ…) se cuentan con la composición
del índice, por lo que no alteran el balance sectorial. Bonos, oro y criptomonedas quedan fuera de la restricción.
Si en un sector no hay candidatos, su mínimo no se exige. Pesos sectoriales del S&P 500 estimados al
{universo.FECHA_PESOS_SECTORES} (ChartRow); se actualizan en `nucleo/universo.py`.
""")
filas_bandas = "\n".join(f"| {universo.SECTORES_ES[s_]} | {w_:.1%} | {max(w_ - 0.10, 0):.1%} – {w_ + 0.10:.1%} |"
                         for s_, w_ in universo.PESOS_SECTORES_SP500.items())
st.markdown("| Sector | Peso en el S&P 500 | Banda permitida |\n|---|---|---|\n" + filas_bandas)
filas_perf = "\n".join(
    f"| {p} | {str(c['aversion']).replace('.', ',')} | {c['peso_max']:.0%} | {c['cripto_max']:.0%} | {c['defensivo_min']:.0%} |"
    for p, c in modelo.PERFILES.items())
st.markdown("| Perfil | Aversión al riesgo λ | Máximo por activo | Máximo en cripto | Mínimo en bonos y oro |\n"
            "|---|---|---|---|---|\n" + filas_perf)
st.markdown("Se resuelve por programación cuadrática secuencial (SLSQP). Las posiciones menores a 1 % se eliminan y se "
            "vuelve a optimizar sin ellas, para que los pesos finales respeten todas las restricciones. Se reportan "
            "$\\mu_p = w^{*\\top}\\mu_{BL}$, $\\sigma_p = \\sqrt{w^{*\\top}\\Sigma_{BL}w^*}$, "
            "Sharpe $= (\\mu_p - Rf)/\\sigma_p$ y la diversificación efectiva $N_{\\text{eff}} = 1/\\sum_i w_i^2$.")

st.markdown("#### Etapa 6 · Proyección Monte Carlo con cambio de régimen")
st.latex(r"\ln V_{t+1} = \ln V_t + \mu_{s_t} + \sigma_{s_t}\,\varepsilon_t,\qquad"
         r"\varepsilon_t\sim\mathcal N(0,1),\qquad s_{t+1}\sim P(s_t,\cdot)")
st.markdown("""
Cada trayectoria parte del régimen actual y salta entre regímenes según la matriz de transición. La volatilidad de
cada régimen se estima con la historia de la cartera; la media se desplaza para que la deriva de largo plazo
(ponderada por la distribución estacionaria) coincida con $\\mu_{BL} - \\sigma^2/2$. Con 5.000 escenarios se reportan:
**peor escenario** = percentil 5; **mejor escenario** = percentil 95; **escenario más probable** = moda de la
distribución final (histograma en escala logarítmica) y la probabilidad de terminar a ±5 % de ella; además de la
mediana y las probabilidades de ganar o perder más de 10 % y 20 %.
""")

# --------------------------------------------------------------------------
# Panel Mi cartera
# --------------------------------------------------------------------------
ui.seccion("Metodología · Panel Mi cartera")
st.markdown("""
- **Datos de cada compra**: activo, fecha y al menos uno de *cantidad* o *monto invertido*. Se cumple
  monto = cantidad × precio por unidad; si falta el precio se usa el cierre de Yahoo Finance de esa fecha, y si se
  indican cantidad y monto sin precio, se calcula el precio implícito. Si el precio escrito es unas 1.000 veces menor que el de
  mercado de ese día (por ejemplo, 63.974 en lugar de 63974), se interpreta como separador de miles, se corrige y se informa.
- **Acciones chilenas (.SN)**: cotizan en pesos; se convierten a dólares con el tipo de cambio USD/CLP de cada día.
- **Rentabilidad**: valor actual = cantidad × último precio; rentabilidad = valor actual / monto invertido − 1.
- **Comparación con el S&P 500**: cada compra se replica, en la misma fecha y por el mismo monto, en SPY.
- **Proyección**: se estiman la deriva $\\hat\\mu = 252\\,\\overline{\\ln(V_t/V_{t-1})}$ y la volatilidad de la
  cartera actual desde la primera compra (mínimo un año de datos) y se simula con movimiento browniano geométrico o
  con 2 regímenes de Markov. La opción *moderar la tendencia* contrae la deriva hacia $\\ln(1{,}07)$:
""")
st.latex(r"\tilde\mu = \frac{n}{n+504}\,\hat\mu + \frac{504}{n+504}\,\ln(1{,}07)")
st.markdown("""
- **Recta de tendencia**: regresión lineal por mínimos cuadrados del valor de la cartera contra el tiempo.
- **Métricas de riesgo**: retorno anualizado (CAGR), volatilidad anual, índice de Sharpe, máxima caída
  ($\\min_t V_t/\\max_{s\\le t}V_s - 1$), VaR histórico diario al 95 % (percentil 5 de los retornos), beta y
  correlación con el S&P 500.
""")

ui.seccion("Metodología · Análisis técnico")
st.markdown("""
| Indicador | Definición |
|---|---|
| Medias móviles | Simples de 50 y 200 sesiones (SMA). |
| RSI 14 | Índice de fuerza relativa de Wilder (1978) con suavizado exponencial α = 1/14; sobrecompra ≥ 70, sobreventa ≤ 30. |
| MACD 12-26-9 | EMA(12) − EMA(26); señal = EMA(9) del MACD; histograma = MACD − señal (Appel). |
| Bandas de Bollinger | Media de 20 sesiones ± 2 desviaciones estándar; %B = (P − banda inferior)/(ancho). |
| Volatilidad 30 días | Desviación estándar de los retornos de 30 sesiones, anualizada. |
| Señal técnica | Suma de +1/−1 por: precio vs. SMA50, SMA50 vs. SMA200, signo del histograma MACD y RSI extremo. ≥ 2 alcista, ≤ −2 bajista. |

El gráfico de TradingView es un servicio externo: sus herramientas de dibujo e indicadores son de TradingView y no
forman parte de los cálculos de la página.
""")

# --------------------------------------------------------------------------
# Limitaciones
# --------------------------------------------------------------------------
ui.seccion("Supuestos y limitaciones")
st.markdown("""
- Los modelos suponen retornos condicionalmente normales dentro de cada régimen; los mercados presentan colas más
  pesadas, por lo que los escenarios extremos pueden estar subestimados.
- Los parámetros se estiman con historia reciente y pueden cambiar (riesgo de estimación y de modelo).
- No se consideran costos de transacción, comisiones, impuestos, diferencias de compra-venta ni el tipo de cambio
  para un inversionista que invierte desde pesos chilenos.
- El universo del S&P 500 corresponde a sus componentes actuales, lo que introduce sesgo de supervivencia en
  comparaciones históricas.
- Los datos de Yahoo Finance no son oficiales y pueden contener errores o retrasos.
""")

ui.seccion("Referencias")
st.markdown("""
- Ang, A., Hodrick, R., Xing, Y. y Zhang, X. (2006). The cross-section of volatility and expected returns. *Journal of Finance*, 61(1), 259-299.
- Black, F. y Litterman, R. (1992). Global portfolio optimization. *Financial Analysts Journal*, 48(5), 28-43.
- Faber, M. (2007). A quantitative approach to tactical asset allocation. *Journal of Wealth Management*, 9(4), 69-79.
- Frazzini, A. y Pedersen, L. H. (2014). Betting against beta. *Journal of Financial Economics*, 111(1), 1-25.
- Hamilton, J. D. (1989). A new approach to the economic analysis of nonstationary time series and the business cycle. *Econometrica*, 57(2), 357-384.
- He, G. y Litterman, R. (1999). *The intuition behind Black-Litterman model portfolios*. Goldman Sachs Investment Management Research.
- Jegadeesh, N. y Titman, S. (1993). Returns to buying winners and selling losers. *Journal of Finance*, 48(1), 65-91.
- Ledoit, O. y Wolf, M. (2004). A well-conditioned estimator for large-dimensional covariance matrices. *Journal of Multivariate Analysis*, 88(2), 365-411.
- Markowitz, H. (1952). Portfolio selection. *Journal of Finance*, 7(1), 77-91.
- Sharpe, W. F. (1964). Capital asset prices: a theory of market equilibrium under conditions of risk. *Journal of Finance*, 19(3), 425-442.
- Villarroel, P., Osorio, F. y Olivares, C. (2025). Métricas de los modelos de Markowitz y Black-Litterman con entradas de Machine Learning. Manuscrito.
- Wilder, J. W. (1978). *New concepts in technical trading systems*. Trend Research.
""")

ui.aviso_legal()
