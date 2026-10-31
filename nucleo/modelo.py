"""Modelo híbrido de optimización de carteras.

Flujo (especificación del paper «Métricas de los modelos de Markowitz y
Black-Litterman con entradas de Machine Learning», con las correcciones
indicadas):

    precios ──► retornos logarítmicos ──► excesos de retorno  r_ex = r − Rf_t
                    │                       (Rf_t = IRX_t / (100·252))
                    ├─► covarianza (Ledoit-Wolf) ×252
                    ├─► HMM gaussiano sobre los excesos del S&P 500 (^GSPC), Viterbi
                    ├─► betas rodantes por MCO:  r_ex_i = α + β r_ex_m + ε
                    ▼
        vistas CAPM-HMM:  μ̂_i,t = Rf_t + β_i,t · μ_m^(s_t)
                          Q_i  = clip(252 · promedio últimos N días, ±tope)
                    │
    equilibrio Π = δ Σ w_mkt ──► BLACK-LITTERMAN ──► μ_BL, Σ_BL = Σ + M
                    │
                    ▼
        MARKOWITZ media-varianza con restricciones del perfil y
        BANDAS SECTORIALES (±10% alrededor del peso de cada sector en el S&P 500)

Todos los parámetros están en PARAMETROS_POR_DEFECTO y se pueden ajustar
desde «Opciones avanzadas» del panel Invertir.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

from nucleo.universo import (DEFENSIVOS, ETFS_DIVERSIFICADOS, PESOS_SECTORES_SP500, clase_de, sector_de,
                             tipo_de_activo)

DIAS_ANIO = 252

PARAMETROS_POR_DEFECTO = {
    "anios_historia": 5,        # años de datos diarios
    "ventana_beta": 60,         # días de la regresión rodante de las betas (paper, sección 3.3)
    "n_regimenes": 2,           # estados ocultos del HMM (paper: HMM_STATES = 2)
    "ventana_vista": 20,        # días que se promedian las vistas (paper, sección 3.5)
    "tope_vista": 0.30,         # |Q| máximo anual (paper, sección 3.5)
    "horizonte_confianza": 63,  # días para medir la incertidumbre del régimen futuro (Ω)
    "tau": 0.05,                # incertidumbre del equilibrio en Black-Litterman
    "bandas_sectoriales": True, # restricción sectorial del paper
    "banda_sectorial": 0.10,    # paper: SECTOR_BAND = 0.10
    "min_observaciones": 500,   # días mínimos de historia para incluir un activo
}

# Perfil de riesgo -> parámetros de Markowitz
PERFILES = {
    "Arriesgado": {
        "aversion": 1.5, "peso_max": 0.30, "cripto_max": 0.15, "defensivo_min": 0.00,
        "descripcion": "Busca el mayor crecimiento y tolera caídas fuertes en el camino. Cripto hasta 15%.",
    },
    "Moderado": {
        "aversion": 4.0, "peso_max": 0.20, "cripto_max": 0.05, "defensivo_min": 0.25,
        "descripcion": "Equilibrio entre crecimiento y estabilidad; acepta caídas moderadas. Al menos 25% en bonos y oro.",
    },
    "Defensivo": {
        "aversion": 10.0, "peso_max": 0.15, "cripto_max": 0.00, "defensivo_min": 0.50,
        "descripcion": "Prioriza proteger el capital; al menos la mitad en bonos y oro, sin criptomonedas.",
    },
}


# ----------------------------------------------------------------------------
# 0. Retornos y excesos de retorno
# ----------------------------------------------------------------------------
def tasa_diaria(serie_irx: pd.Series | None, fechas: pd.DatetimeIndex, rf_anual: float) -> pd.Series:
    """Rf_t = IRX_t / (100 · 252). Si no hay serie, se usa la tasa anual constante."""
    if serie_irx is not None and serie_irx.notna().sum() > 20:
        s = serie_irx.reindex(fechas).ffill().bfill()
        return (s / 100 / DIAS_ANIO).rename("Rf")
    return pd.Series(rf_anual / DIAS_ANIO, index=fechas, name="Rf")


# ----------------------------------------------------------------------------
# 1. Regímenes ocultos de Markov
# ----------------------------------------------------------------------------
@dataclass
class Regimenes:
    etiquetas: list
    estados: pd.Series          # régimen de cada día (Viterbi; 0 = el más bajista)
    probabilidades: pd.DataFrame  # probabilidad suavizada de cada régimen cada día
    transicion: np.ndarray      # matriz de transición diaria
    media_diaria: np.ndarray    # media diaria de la serie modelada en cada régimen
    vol_diaria: np.ndarray      # volatilidad diaria de la serie en cada régimen
    metodo: str

    @property
    def prob_actual(self) -> np.ndarray:
        return self.probabilidades.iloc[-1].to_numpy()

    @property
    def actual(self) -> int:
        return int(self.estados.iloc[-1])


def _etiquetas(k: int) -> list:
    if k == 2:
        return ["Bajista / turbulento", "Alcista / tranquilo"]
    if k == 3:
        return ["Bajista", "Lateral", "Alcista"]
    return [f"Régimen {i + 1}" for i in range(k)]


def _transiciones_por_conteo(estados: np.ndarray, k: int) -> np.ndarray:
    m = np.ones((k, k))  # suavizado de Laplace
    for a, b in zip(estados[:-1], estados[1:]):
        m[a, b] += 1
    return m / m.sum(axis=1, keepdims=True)


def detectar_regimenes(serie: pd.Series, n_regimenes: int = 2, semilla: int = 42) -> Regimenes:
    """HMM gaussiano estimado por EM sobre la serie ESTANDARIZADA (paper, 3.4);
    los estados se asignan por Viterbi."""
    x = serie.dropna()
    k = int(n_regimenes)
    media, desv = float(x.mean()), float(x.std()) or 1.0
    X = ((x.to_numpy() - media) / desv).reshape(-1, 1)
    try:
        from hmmlearn.hmm import GaussianHMM

        mejor, mejor_puntaje = None, -np.inf
        for s in range(4):  # varios inicios para no quedar en un óptimo local
            hmm = GaussianHMM(n_components=k, covariance_type="diag", n_iter=300, tol=1e-4,
                              random_state=semilla + s)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                hmm.fit(X)
                puntaje = hmm.score(X)
            if np.isfinite(puntaje) and puntaje > mejor_puntaje:
                mejor, mejor_puntaje = hmm, puntaje
        if mejor is None:
            raise RuntimeError("HMM no convergió")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            post = mejor.predict_proba(X)
            viterbi = mejor.predict(X)
        medias = mejor.means_.ravel() * desv + media
        vols = np.sqrt(np.asarray(mejor.covars_).reshape(k, -1)[:, 0]) * desv
        trans = np.asarray(mejor.transmat_)
        metodo = "Modelo oculto de Markov gaussiano (EM + Viterbi)"
    except Exception:
        # Respaldo: regímenes por volatilidad rodante (si el HMM falla)
        vol21 = x.rolling(21, min_periods=5).std().bfill()
        cortes = np.quantile(vol21, np.linspace(0, 1, k + 1)[1:-1])
        est = (k - 1) - np.digitize(vol21, cortes)  # 0 = alta volatilidad
        post = np.eye(k)[est]
        viterbi = est
        medias = np.array([x[est == j].mean() if (est == j).any() else x.mean() for j in range(k)])
        vols = np.array([x[est == j].std() if (est == j).sum() > 2 else x.std() for j in range(k)])
        trans = _transiciones_por_conteo(est, k)
        metodo = "Regímenes por volatilidad (respaldo)"

    orden = np.argsort(medias)  # 0 = el más bajista
    rango = np.empty(k, dtype=int)
    rango[orden] = np.arange(k)
    post = post[:, orden]
    medias, vols = medias[orden], vols[orden]
    trans = trans[np.ix_(orden, orden)]
    etiquetas = _etiquetas(k)
    probs = pd.DataFrame(post, index=x.index, columns=etiquetas)
    estados = pd.Series(rango[np.asarray(viterbi)], index=x.index, name="regimen")
    return Regimenes(etiquetas, estados, probs, trans, medias, vols, metodo)


def probabilidad_futura(reg: Regimenes, horizonte: int) -> np.ndarray:
    """Probabilidad promedio de cada régimen durante los próximos 'horizonte' días."""
    p = reg.prob_actual.copy()
    acumulado = np.zeros_like(p)
    for _ in range(max(1, int(horizonte))):
        p = p @ reg.transicion
        acumulado += p
    return acumulado / max(1, int(horizonte))


def distribucion_estacionaria(transicion: np.ndarray) -> np.ndarray:
    valores, vectores = np.linalg.eig(transicion.T)
    v = np.real(vectores[:, np.argmin(np.abs(valores - 1))])
    v = np.abs(v)
    return v / v.sum()


# ----------------------------------------------------------------------------
# 2. CAPM dinámico (betas rodantes por MCO) y vistas CAPM-HMM
# ----------------------------------------------------------------------------
def betas_rodantes(ex_activos: pd.DataFrame, ex_mercado: pd.Series, ventana: int) -> pd.DataFrame:
    """Pendiente MCO de r_ex_i = α + β·r_ex_m + ε en ventana rodante (= Cov/Var)."""
    minimo = max(20, int(ventana * 0.75))
    var_m = ex_mercado.rolling(ventana, min_periods=minimo).var()
    cov = pd.DataFrame({c: ex_activos[c].rolling(ventana, min_periods=minimo).cov(ex_mercado)
                        for c in ex_activos.columns})
    return cov.div(var_m, axis=0)


def vistas_capm_hmm(ex_activos: pd.DataFrame, ex_mercado: pd.Series, rf_d: pd.Series, reg: Regimenes,
                    prm: dict) -> dict:
    """Vistas condicionales (paper, sección 3.5):

        μ̂_i,t = Rf_t + β_i,t · μ_m^(s_t)
        Q_i   = clip(252 · promedio de los últimos N días de μ̂_i,t, −tope, +tope)

    donde μ_m^(s) es el exceso de retorno medio diario del mercado en el régimen s
    y s_t el régimen asignado por Viterbi.
    """
    k = len(reg.etiquetas)
    b_rod = betas_rodantes(ex_activos, ex_mercado, prm["ventana_beta"])
    estados = reg.estados.reindex(ex_mercado.index).ffill().bfill().astype(int)
    mu_reg = np.array([ex_mercado[estados == j].mean() if (estados == j).sum() > 5 else ex_mercado.mean()
                       for j in range(k)])
    mu_m_t = pd.Series(mu_reg[estados.to_numpy()], index=ex_mercado.index)
    mu_hat = b_rod.mul(mu_m_t, axis=0).add(rf_d.reindex(b_rod.index), axis=0)
    n = int(prm["ventana_vista"])
    ultimos = mu_hat.dropna(how="all").iloc[-n:]
    tope = float(prm["tope_vista"])
    q = (DIAS_ANIO * ultimos.mean()).clip(-tope, tope)

    beta_actual = b_rod.iloc[-1].fillna(b_rod.mean())
    beta_vista = b_rod.iloc[-n:].mean().fillna(beta_actual)
    recientes = b_rod.iloc[-63:]
    inestabilidad = (recientes.std() / recientes.mean().abs().clip(lower=0.1)).clip(0, 2).fillna(1)
    p_futuro = probabilidad_futura(reg, prm["horizonte_confianza"])
    return {
        "Q": q, "beta_rodante": beta_actual, "beta_vista": beta_vista, "betas_rodantes": b_rod,
        "mu_regimen": mu_reg, "prima_regimen": mu_reg * DIAS_ANIO,
        "prima_vista": float(DIAS_ANIO * mu_m_t.iloc[-n:].mean()), "p_futuro": p_futuro,
        "inestabilidad_beta": inestabilidad, "confianza_regimen": float(p_futuro.max()),
        "regimenes_ventana": estados.iloc[-n:].value_counts(normalize=True).reindex(range(k), fill_value=0).to_numpy(),
    }


# ----------------------------------------------------------------------------
# 3. Black-Litterman
# ----------------------------------------------------------------------------
def aversion_mercado(ex_mercado: pd.Series) -> float:
    """δ = E[r_ex_m] / Var(r_ex_m), ambos anualizados (252·media / 252·varianza)."""
    exceso = ex_mercado.mean() * DIAS_ANIO
    varianza = ex_mercado.var() * DIAS_ANIO
    delta = exceso / varianza if varianza > 0 else np.nan
    return float(np.clip(delta, 1.5, 4.0)) if np.isfinite(delta) else 2.5


def pesos_equilibrio(tickers: list, caps: dict, sigma: np.ndarray):
    con_cap = [t for t in tickers if t in caps]
    if len(con_cap) >= 0.8 * len(tickers):
        mediana = float(np.median([caps[t] for t in con_cap]))
        w = np.array([caps.get(t, mediana) for t in tickers], dtype=float)
        metodo = "capitalización de mercado"
    else:
        w = 1 / np.sqrt(np.diag(sigma))
        metodo = "inverso de la volatilidad (Yahoo no informó la capitalización de todos los activos)"
    return w / w.sum(), metodo


def black_litterman(sigma: np.ndarray, w_mercado: np.ndarray, delta: float, q: np.ndarray,
                    omega_diag: np.ndarray, tau: float):
    """Vistas absolutas (P = I). Devuelve Π, μ_BL y Σ_BL (anuales).

    Σ_BL = Σ + M, con M = [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹ (He y Litterman, 1999): M es la
    incertidumbre del retorno medio y Σ el riesgo de los retornos; usar solo M
    subestimaría la volatilidad del portafolio.
    """
    n = len(q)
    pi = delta * sigma @ w_mercado
    inv_t_sigma = np.linalg.pinv(tau * sigma)
    inv_omega = np.diag(1 / np.maximum(omega_diag, 1e-12))
    p = np.eye(n)
    m = np.linalg.pinv(inv_t_sigma + p.T @ inv_omega @ p)
    mu_bl = m @ (inv_t_sigma @ pi + p.T @ inv_omega @ q)
    return pi, mu_bl, sigma + m


# ----------------------------------------------------------------------------
# 4. Markowitz con restricciones del perfil y bandas sectoriales
# ----------------------------------------------------------------------------
def _pesos_sectores() -> tuple[list, np.ndarray]:
    sectores = list(PESOS_SECTORES_SP500)
    b = np.array([PESOS_SECTORES_SP500[s] for s in sectores])
    return sectores, b / b.sum()


def matriz_sectorial(tickers: list) -> tuple[np.ndarray, np.ndarray, list]:
    """A[i, s] = exposición del activo i al sector s; máscara de renta variable con sector.

    Acciones y ETFs sectoriales: 100% en su sector. ETFs diversificados: composición
    sectorial del índice (neutrales frente a la banda). Bonos, oro, cripto y acciones
    sin sector GICS: fuera de la restricción.
    """
    sectores, b = _pesos_sectores()
    A = np.zeros((len(tickers), len(sectores)))
    renta_variable = np.zeros(len(tickers), dtype=bool)
    for i, t in enumerate(tickers):
        s = sector_de(t)
        if s in sectores:
            A[i, sectores.index(s)] = 1.0
            renta_variable[i] = True
        elif t.upper() in ETFS_DIVERSIFICADOS:
            A[i] = b
            renta_variable[i] = True
    return A, renta_variable, sectores


def _restricciones_sectoriales(A, rv, b, banda, con_minimos: bool) -> list:
    """|exposición_s − b_s · RV| ≤ banda · RV, con RV = peso total en renta variable."""
    res = []
    directos = A == 1.0
    for s in range(A.shape[1]):
        a = A[:, s]
        res.append({"type": "ineq", "fun": lambda w, a=a, s=s: (b[s] + banda) * w[rv].sum() - a @ w})
        piso = b[s] - banda
        if con_minimos and piso > 0 and directos[:, s].any():
            res.append({"type": "ineq", "fun": lambda w, a=a, piso=piso: a @ w - piso * w[rv].sum()})
    return res


def optimizar_markowitz(mu: np.ndarray, sigma: np.ndarray, tickers: list, perfil: str,
                        banda: float | None = None) -> tuple[np.ndarray, str]:
    cfg = PERFILES[perfil]
    n = len(tickers)
    es_cripto = np.array([tipo_de_activo(t) == "Cripto" for t in tickers])
    es_def = np.array([t in DEFENSIVOS for t in tickers])

    techo = np.full(n, cfg["peso_max"])
    if cfg["cripto_max"] <= 0:
        techo[es_cripto] = 0.0
    permitidos = techo > 0
    if techo.sum() < 1:  # muy pocos activos: se relaja el máximo por activo
        techo[permitidos] = 1 / permitidos.sum() + 1e-6

    base = [{"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones(n)}]
    if es_cripto.any() and cfg["cripto_max"] > 0:
        base.append({"type": "ineq", "fun": lambda w: cfg["cripto_max"] - w[es_cripto].sum()})
    def_min = min(cfg["defensivo_min"], techo[es_def].sum()) if es_def.any() else 0
    if def_min > 0:
        base.append({"type": "ineq", "fun": lambda w: w[es_def].sum() - def_min})

    lam = cfg["aversion"]

    def objetivo(w):
        return -(w @ mu - lam / 2 * w @ sigma @ w)

    def gradiente(w):
        return -(mu - lam * sigma @ w)

    x0 = np.where(permitidos, 1.0, 0.0)
    x0 /= x0.sum()
    limites = [(0, techo[i]) for i in range(n)]

    intentos = [("sin bandas sectoriales", base)]
    if banda:
        A, rv, _ = matriz_sectorial(tickers)
        if rv.any():
            _, b = _pesos_sectores()
            intentos = [
                (f"bandas sectoriales de ±{banda:.0%} (máximos y mínimos)",
                 base + _restricciones_sectoriales(A, rv, b, banda, True)),
                (f"bandas sectoriales de ±{banda:.0%} (solo máximos; los mínimos eran infactibles)",
                 base + _restricciones_sectoriales(A, rv, b, banda, False)),
            ] + intentos
    w, nombre = None, ""
    for nombre, restricciones in intentos:
        res = minimize(objetivo, x0, jac=gradiente, method="SLSQP", bounds=limites,
                       constraints=restricciones, options={"maxiter": 1000, "ftol": 1e-12})
        candidato = np.clip(res.x, 0, None)
        factible = all((c["fun"](candidato) >= -1e-5) if c["type"] == "ineq" else abs(c["fun"](candidato)) < 1e-5
                       for c in restricciones)
        if res.success and factible:
            w = candidato
            break
    if w is None:
        w = np.clip(res.x if np.isfinite(res.x).all() else x0, 0, None)
        nombre, restricciones = "solución aproximada (el optimizador no convergió)", base
    # Limpia posiciones menores a 1% y vuelve a optimizar sin ellas, para que los
    # pesos finales sigan cumpliendo todas las restricciones (topes y bandas).
    activos = w >= 0.01
    if activos.sum() >= 2 and not activos.all():
        lim2 = [(0, techo[i]) if activos[i] else (0, 0) for i in range(n)]
        x1 = np.where(activos, w, 0) / w[activos].sum()
        res2 = minimize(objetivo, x1, jac=gradiente, method="SLSQP", bounds=lim2,
                        constraints=restricciones, options={"maxiter": 1000, "ftol": 1e-12})
        if res2.success:
            w = np.clip(res2.x, 0, None)
    w[w < 1e-4] = 0
    return w / w.sum(), nombre


def exposicion_sectorial(pesos: pd.Series, banda: float) -> pd.DataFrame:
    """Exposición sectorial de la parte de renta variable vs. el S&P 500 y su banda."""
    A, rv, sectores = matriz_sectorial(list(pesos.index))
    w = pesos.to_numpy()
    total_rv = float(w[rv].sum())
    _, b = _pesos_sectores()
    expo = (A.T @ w) / total_rv if total_rv > 0 else np.zeros(len(sectores))
    candidatos = (A == 1.0).sum(axis=0)
    minimo = np.where(candidatos > 0, np.clip(b - banda, 0, None), 0.0)  # sin candidatos no hay mínimo exigible
    return pd.DataFrame({"Sector": sectores, "Peso en el S&P 500": b, "Banda mínima": minimo,
                         "Banda máxima": b + banda, "Exposición de la cartera": expo,
                         "Candidatos directos": candidatos}), total_rv


# ----------------------------------------------------------------------------
# 5. Orquestador
# ----------------------------------------------------------------------------
@dataclass
class ResultadoCartera:
    perfil: str
    pesos: pd.Series
    tabla: pd.DataFrame
    retorno_esperado: float
    volatilidad: float
    sharpe: float
    rf: float
    delta: float
    metodo_pesos: str
    regimenes: Regimenes
    vistas: dict
    ret_diarios: pd.DataFrame
    sigma_bl: pd.DataFrame
    n_efectivo: float = np.nan
    restriccion_sectorial: str = ""
    descartados: list = field(default_factory=list)
    parametros: dict = field(default_factory=dict)


def construir_cartera(precios: pd.DataFrame, indice: str, perfil: str, rf: float, caps: dict,
                      parametros: dict | None = None, candidatos: list | None = None,
                      serie_irx: pd.Series | None = None) -> ResultadoCartera:
    prm = {**PARAMETROS_POR_DEFECTO, **(parametros or {})}
    if indice not in precios.columns:
        raise ValueError(f"No hay datos del índice de mercado ({indice}).")

    # Alinea todo a los días hábiles de la bolsa de EE.UU.
    fechas = precios[indice].dropna().index
    precios = precios.reindex(fechas).ffill(limit=5)
    candidatos = [c for c in (candidatos or list(precios.columns)) if c in precios.columns and c != indice]
    validos = [c for c in candidatos if precios[c].notna().sum() >= prm["min_observaciones"]]
    descartados = [c for c in candidatos if c not in validos]
    if len(validos) < 3:
        raise ValueError("Se necesitan al menos 3 activos con historia suficiente.")

    columnas = list(dict.fromkeys(validos + [indice]))
    log_ret = np.log(precios[columnas]).diff().dropna(how="any")
    if len(log_ret) < 250:
        raise ValueError("No hay suficiente historia común entre los activos elegidos.")
    rf_d = tasa_diaria(serie_irx, log_ret.index, rf)
    ex = log_ret.sub(rf_d, axis=0)                     # excesos de retorno (paper, 3.2.2)
    ex_m, ex_a = ex[indice], ex[validos]

    sigma = LedoitWolf().fit(log_ret[validos].to_numpy()).covariance_ * DIAS_ANIO
    reg = detectar_regimenes(ex_m, prm["n_regimenes"])
    vistas = vistas_capm_hmm(ex_a, ex_m, rf_d, reg, prm)

    delta = aversion_mercado(ex_m)
    w_mkt, metodo_pesos = pesos_equilibrio(validos, caps, sigma)
    tau = prm["tau"]
    # Ω: más incertidumbre si la beta es inestable o si el régimen futuro es incierto
    omega = tau * np.diag(sigma) * (1 + vistas["inestabilidad_beta"].reindex(validos).to_numpy()) \
        / max(vistas["confianza_regimen"], 0.34)
    q = vistas["Q"].reindex(validos).to_numpy()
    pi, mu_bl, sigma_bl = black_litterman(sigma, w_mkt, delta, q, omega, tau)

    banda = prm["banda_sectorial"] if prm.get("bandas_sectoriales") else None
    w, restriccion = optimizar_markowitz(mu_bl, sigma_bl, validos, perfil, banda)
    ret_esp = float(w @ mu_bl)
    vol = float(np.sqrt(w @ sigma_bl @ w))
    sharpe = (ret_esp - rf) / vol if vol > 0 else np.nan

    tabla = pd.DataFrame({
        "Ticker": validos,
        "Tipo": [clase_de(t) for t in validos],
        "Sector": [sector_de(t) or ("Diversificado" if t in ETFS_DIVERSIFICADOS else "—") for t in validos],
        "Peso": w,
        "Equilibrio (Π)": pi,
        "Vista CAPM-HMM (Q)": q,
        "Retorno Black-Litterman": mu_bl,
        "Beta rodante": vistas["beta_rodante"].reindex(validos).to_numpy(),
        "Beta media (ventana vista)": vistas["beta_vista"].reindex(validos).to_numpy(),
        "Volatilidad anual": np.sqrt(np.diag(sigma)),
        "Peso de mercado": w_mkt,
    })
    simples = precios[validos].pct_change().reindex(log_ret.index)
    return ResultadoCartera(
        perfil=perfil, pesos=pd.Series(w, index=validos), tabla=tabla,
        retorno_esperado=ret_esp, volatilidad=vol, sharpe=sharpe, rf=rf, delta=delta,
        metodo_pesos=metodo_pesos, regimenes=reg, vistas=vistas, ret_diarios=simples,
        sigma_bl=pd.DataFrame(sigma_bl, index=validos, columns=validos),
        n_efectivo=float(1 / np.sum(w ** 2)), restriccion_sectorial=restriccion,
        descartados=descartados, parametros=prm,
    )


def parametros_montecarlo_cartera(res: ResultadoCartera) -> dict:
    """Parámetros por régimen para simular la cartera óptima.

    La forma (volatilidad y persistencia de cada régimen) sale de la historia;
    la deriva de largo plazo se ancla al retorno esperado de Black-Litterman.
    """
    w = res.pesos.to_numpy()
    r_log = np.log1p(res.ret_diarios.fillna(0).to_numpy() @ w)
    estados = res.regimenes.estados.reindex(res.ret_diarios.index).ffill().bfill().to_numpy().astype(int)
    k = len(res.regimenes.etiquetas)
    medias = np.array([r_log[estados == j].mean() if (estados == j).sum() > 20 else r_log.mean() for j in range(k)])
    vols = np.array([r_log[estados == j].std() if (estados == j).sum() > 20 else r_log.std() for j in range(k)])
    pi_est = distribucion_estacionaria(res.regimenes.transicion)
    objetivo = (res.retorno_esperado - res.volatilidad ** 2 / 2) / DIAS_ANIO
    medias = medias + (objetivo - pi_est @ medias)
    return {"medias": medias, "vols": vols, "transicion": res.regimenes.transicion,
            "p0": res.regimenes.prob_actual}
