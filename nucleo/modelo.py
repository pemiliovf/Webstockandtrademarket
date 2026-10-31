"""Modelo híbrido de optimización de carteras.

Flujo (el mismo de la investigación):

    precios ──► retornos ──► covarianza (Ledoit-Wolf)
                    │
                    ├─► regímenes ocultos de Markov sobre el mercado (HMM)
                    ├─► betas rodantes de cada activo
                    │
                    ▼
        CAPM dinámico condicionado al régimen  ──►  VISTAS (Q, Ω)
                    │
    equilibrio de mercado (Π = δ Σ w_mkt) ──► BLACK-LITTERMAN ──► μ_BL, Σ_BL
                    │
                    ▼
        MARKOWITZ media-varianza con restricciones del perfil ──► pesos

Todos los parámetros están en PARAMETROS_POR_DEFECTO y se pueden ajustar
desde "Opciones avanzadas" del panel 2.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

from nucleo.universo import DEFENSIVOS, tipo_de_activo

DIAS_ANIO = 252

PARAMETROS_POR_DEFECTO = {
    "anios_historia": 5,        # años de datos diarios
    "ventana_beta": 126,        # días de la ventana rodante para las betas (~6 meses)
    "n_regimenes": 2,           # estados ocultos del HMM
    "horizonte_vista": 63,      # días hacia adelante de la vista CAPM (~3 meses)
    "mezcla_beta": 0.5,         # peso de la beta rodante vs. la beta por régimen
    "tau": 0.05,                # incertidumbre del equilibrio en Black-Litterman
    "min_observaciones": 500,   # días mínimos de historia para incluir un activo
}

# Perfil de riesgo -> parámetros de Markowitz
PERFILES = {
    "Arriesgado": {
        "aversion": 1.5, "peso_max": 0.30, "cripto_max": 0.15, "defensivo_min": 0.00,
        "descripcion": "Busca el mayor crecimiento y tolera caídas fuertes en el camino.",
    },
    "Moderado (más o menos)": {
        "aversion": 4.0, "peso_max": 0.20, "cripto_max": 0.05, "defensivo_min": 0.25,
        "descripcion": "Equilibrio entre crecimiento y estabilidad; acepta caídas moderadas.",
    },
    "Defensivo": {
        "aversion": 10.0, "peso_max": 0.15, "cripto_max": 0.00, "defensivo_min": 0.50,
        "descripcion": "Prioriza proteger el capital; al menos la mitad en bonos y oro.",
    },
}


# ----------------------------------------------------------------------------
# 1. Regímenes ocultos de Markov
# ----------------------------------------------------------------------------
@dataclass
class Regimenes:
    etiquetas: list
    estados: pd.Series          # régimen más probable de cada día (0 = el más bajista)
    probabilidades: pd.DataFrame  # probabilidad de cada régimen cada día
    transicion: np.ndarray      # matriz de transición diaria
    media_diaria: np.ndarray    # retorno medio diario del mercado en cada régimen
    vol_diaria: np.ndarray      # volatilidad diaria del mercado en cada régimen
    metodo: str

    @property
    def prob_actual(self) -> np.ndarray:
        return self.probabilidades.iloc[-1].to_numpy()

    @property
    def actual(self) -> int:
        return int(np.argmax(self.prob_actual))


def _etiquetas(k: int) -> list:
    if k == 2:
        return ["Turbulento", "Tranquilo"]
    if k == 3:
        return ["Bajista", "Lateral", "Alcista"]
    return [f"Régimen {i + 1}" for i in range(k)]


def _transiciones_por_conteo(estados: np.ndarray, k: int) -> np.ndarray:
    m = np.ones((k, k))  # suavizado de Laplace
    for a, b in zip(estados[:-1], estados[1:]):
        m[a, b] += 1
    return m / m.sum(axis=1, keepdims=True)


def detectar_regimenes(ret_mercado: pd.Series, n_regimenes: int = 2, semilla: int = 42) -> Regimenes:
    """Ajusta un HMM gaussiano a los retornos diarios del mercado."""
    x = ret_mercado.dropna()
    k = int(n_regimenes)
    X = (x.to_numpy() * 100).reshape(-1, 1)
    try:
        from hmmlearn.hmm import GaussianHMM

        mejor, mejor_puntaje = None, -np.inf
        for s in range(4):
            modelo = GaussianHMM(n_components=k, covariance_type="diag", n_iter=300,
                                 tol=1e-4, random_state=semilla + s)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                modelo.fit(X)
                puntaje = modelo.score(X)
            if np.isfinite(puntaje) and puntaje > mejor_puntaje:
                mejor, mejor_puntaje = modelo, puntaje
        if mejor is None:
            raise RuntimeError("HMM no convergió")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            post = mejor.predict_proba(X)
        medias = mejor.means_.ravel() / 100
        vols = np.sqrt(np.asarray(mejor.covars_).reshape(k, -1)[:, 0]) / 100
        trans = np.asarray(mejor.transmat_)
        metodo = "Modelo oculto de Markov gaussiano"
    except Exception:
        # Respaldo: regímenes por volatilidad rodante (si el HMM falla)
        vol21 = x.rolling(21, min_periods=5).std().bfill()
        cortes = np.quantile(vol21, np.linspace(0, 1, k + 1)[1:-1])
        est = np.digitize(vol21, cortes)  # 0 = baja volatilidad
        est = (k - 1) - est               # 0 = alta volatilidad (más bajista)
        post = np.eye(k)[est]
        medias = np.array([x[est == j].mean() if (est == j).any() else x.mean() for j in range(k)])
        vols = np.array([x[est == j].std() if (est == j).sum() > 2 else x.std() for j in range(k)])
        trans = _transiciones_por_conteo(est, k)
        metodo = "Regímenes por volatilidad (respaldo)"

    orden = np.argsort(medias)  # 0 = el más bajista
    post = post[:, orden]
    medias, vols = medias[orden], vols[orden]
    trans = trans[np.ix_(orden, orden)]
    etiquetas = _etiquetas(k)
    probs = pd.DataFrame(post, index=x.index, columns=etiquetas)
    estados = pd.Series(post.argmax(axis=1), index=x.index, name="regimen")
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
# 2. Betas rodantes y CAPM dinámico
# ----------------------------------------------------------------------------
def betas_rodantes(ret_activos: pd.DataFrame, ret_mercado: pd.Series, ventana: int) -> pd.DataFrame:
    minimo = max(20, ventana // 2)
    var_m = ret_mercado.rolling(ventana, min_periods=minimo).var()
    cov = pd.DataFrame({c: ret_activos[c].rolling(ventana, min_periods=minimo).cov(ret_mercado)
                        for c in ret_activos.columns})
    return cov.div(var_m, axis=0)


def betas_por_regimen(ret_activos: pd.DataFrame, ret_mercado: pd.Series, estados: pd.Series, k: int) -> pd.DataFrame:
    beta_total = ret_activos.apply(lambda c: c.cov(ret_mercado)) / ret_mercado.var()
    tabla = {}
    for j in range(k):
        mascara = (estados == j).reindex(ret_activos.index).fillna(False).astype(bool)
        if mascara.sum() < 30:
            tabla[j] = beta_total
            continue
        rm = ret_mercado[mascara]
        tabla[j] = ret_activos[mascara].apply(lambda c: c.cov(rm)) / rm.var()
    return pd.DataFrame(tabla).apply(lambda col: col.fillna(beta_total))


def vistas_capm_dinamico(ret_activos: pd.DataFrame, ret_mercado: pd.Series, reg: Regimenes,
                         rf: float, ventana: int, horizonte: int, mezcla_beta: float) -> dict:
    """Retorno esperado anual de cada activo según un CAPM con beta y prima de
    mercado que dependen del régimen esperado:

        E[R_i] = rf + β_i,t · E_t[R_m − rf]
        β_i,t      = m · β_rodante_i + (1 − m) · Σ_k p_k · β_i|k
        E_t[R_m−rf] = Σ_k p_k · prima_k        (p_k: prob. futura del régimen k)
    """
    k = len(reg.etiquetas)
    b_rod = betas_rodantes(ret_activos, ret_mercado, ventana)
    beta_actual = b_rod.iloc[-1].fillna(b_rod.mean())
    ultimos = b_rod.iloc[-63:]
    inestabilidad = (ultimos.std() / ultimos.mean().abs().clip(lower=0.1)).clip(0, 2).fillna(1)

    b_reg = betas_por_regimen(ret_activos, ret_mercado, reg.estados, k)
    p_futuro = probabilidad_futura(reg, horizonte)
    prima_regimen = (reg.media_diaria - rf / DIAS_ANIO) * DIAS_ANIO
    prima_esperada = float(p_futuro @ prima_regimen)
    beta_regimen = b_reg.to_numpy() @ p_futuro
    beta_dinamica = mezcla_beta * beta_actual + (1 - mezcla_beta) * pd.Series(beta_regimen, index=b_reg.index)
    q = (rf + beta_dinamica * prima_esperada).clip(-0.5, 0.6)
    return {
        "Q": q, "beta_dinamica": beta_dinamica, "beta_rodante": beta_actual, "betas_rodantes": b_rod,
        "betas_regimen": b_reg, "p_futuro": p_futuro, "prima_regimen": prima_regimen,
        "prima_esperada": prima_esperada, "inestabilidad_beta": inestabilidad,
        "confianza_regimen": float(p_futuro.max()),
    }


# ----------------------------------------------------------------------------
# 3. Black-Litterman
# ----------------------------------------------------------------------------
def aversion_mercado(ret_mercado: pd.Series, rf: float) -> float:
    exceso = ret_mercado.mean() * DIAS_ANIO - rf
    varianza = ret_mercado.var() * DIAS_ANIO
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
    """Vistas absolutas (P = I). Devuelve Π, μ_BL y Σ_BL (anuales)."""
    n = len(q)
    pi = delta * sigma @ w_mercado
    t_sigma = tau * sigma
    inv_t_sigma = np.linalg.pinv(t_sigma)
    inv_omega = np.diag(1 / np.maximum(omega_diag, 1e-12))
    p = np.eye(n)
    m = np.linalg.pinv(inv_t_sigma + p.T @ inv_omega @ p)
    mu_bl = m @ (inv_t_sigma @ pi + p.T @ inv_omega @ q)
    sigma_bl = sigma + m
    return pi, mu_bl, sigma_bl


# ----------------------------------------------------------------------------
# 4. Markowitz con restricciones del perfil
# ----------------------------------------------------------------------------
def optimizar_markowitz(mu: np.ndarray, sigma: np.ndarray, tickers: list, perfil: str) -> np.ndarray:
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

    restricciones = [{"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones(n)}]
    if es_cripto.any() and cfg["cripto_max"] > 0:
        restricciones.append({"type": "ineq", "fun": lambda w: cfg["cripto_max"] - w[es_cripto].sum()})
    def_min = min(cfg["defensivo_min"], techo[es_def].sum()) if es_def.any() else 0
    if def_min > 0:
        restricciones.append({"type": "ineq", "fun": lambda w: w[es_def].sum() - def_min})

    lam = cfg["aversion"]

    def objetivo(w):
        return -(w @ mu - lam / 2 * w @ sigma @ w)

    def gradiente(w):
        return -(mu - lam * sigma @ w)

    x0 = np.where(permitidos, 1.0, 0.0)
    x0 /= x0.sum()
    res = minimize(objetivo, x0, jac=gradiente, method="SLSQP",
                   bounds=[(0, techo[i]) for i in range(n)], constraints=restricciones,
                   options={"maxiter": 1000, "ftol": 1e-12})
    w = np.clip(res.x if res.success or np.isfinite(res.x).all() else x0, 0, None)
    w[w < 0.01] = 0  # limpia posiciones menores a 1%
    return w / w.sum()


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
    descartados: list = field(default_factory=list)
    parametros: dict = field(default_factory=dict)


def construir_cartera(precios: pd.DataFrame, proxy: str, perfil: str, rf: float, caps: dict,
                      parametros: dict | None = None, candidatos: list | None = None) -> ResultadoCartera:
    prm = {**PARAMETROS_POR_DEFECTO, **(parametros or {})}
    if proxy not in precios.columns:
        raise ValueError(f"No hay datos del índice de mercado ({proxy}).")

    # Alinea todo a los días hábiles de la bolsa de EE.UU.
    fechas = precios[proxy].dropna().index
    precios = precios.reindex(fechas).ffill(limit=5)
    candidatos = [c for c in (candidatos or list(precios.columns)) if c in precios.columns]
    validos = [c for c in candidatos if precios[c].notna().sum() >= prm["min_observaciones"]]
    descartados = [c for c in candidatos if c not in validos]
    if len(validos) < 3:
        raise ValueError("Se necesitan al menos 3 activos con historia suficiente.")

    columnas = list(dict.fromkeys(validos + [proxy]))
    ret = precios[columnas].pct_change().dropna(how="any")
    if len(ret) < 250:
        raise ValueError("No hay suficiente historia común entre los activos elegidos.")
    ret_m = ret[proxy]
    ret_a = ret[validos]

    sigma = LedoitWolf().fit(ret_a.to_numpy()).covariance_ * DIAS_ANIO
    reg = detectar_regimenes(ret_m, prm["n_regimenes"])
    vistas = vistas_capm_dinamico(ret_a, ret_m, reg, rf, prm["ventana_beta"],
                                  prm["horizonte_vista"], prm["mezcla_beta"])

    delta = aversion_mercado(ret_m, rf)
    w_mkt, metodo_pesos = pesos_equilibrio(validos, caps, sigma)
    tau = prm["tau"]
    # Ω: más incertidumbre si la beta es inestable o si el régimen futuro es incierto
    omega = tau * np.diag(sigma) * (1 + vistas["inestabilidad_beta"].to_numpy()) / max(vistas["confianza_regimen"], 0.34)
    q = vistas["Q"].reindex(validos).to_numpy()
    pi, mu_bl, sigma_bl = black_litterman(sigma, w_mkt, delta, q, omega, tau)

    w = optimizar_markowitz(mu_bl, sigma_bl, validos, perfil)
    ret_esp = float(w @ mu_bl)
    vol = float(np.sqrt(w @ sigma_bl @ w))
    sharpe = (ret_esp - rf) / vol if vol > 0 else np.nan

    tabla = pd.DataFrame({
        "Ticker": validos,
        "Tipo": [tipo_de_activo(t) for t in validos],
        "Peso": w,
        "Equilibrio (Π)": pi,
        "Vista CAPM dinámico (Q)": q,
        "Retorno Black-Litterman": mu_bl,
        "Beta rodante": vistas["beta_rodante"].reindex(validos).to_numpy(),
        "Beta dinámica": vistas["beta_dinamica"].reindex(validos).to_numpy(),
        "Volatilidad anual": np.sqrt(np.diag(sigma)),
        "Peso de mercado": w_mkt,
    })
    return ResultadoCartera(
        perfil=perfil, pesos=pd.Series(w, index=validos), tabla=tabla,
        retorno_esperado=ret_esp, volatilidad=vol, sharpe=sharpe, rf=rf, delta=delta,
        metodo_pesos=metodo_pesos, regimenes=reg, vistas=vistas, ret_diarios=ret_a,
        sigma_bl=pd.DataFrame(sigma_bl, index=validos, columns=validos),
        descartados=descartados, parametros=prm,
    )


def parametros_montecarlo_cartera(res: ResultadoCartera) -> dict:
    """Parámetros por régimen para simular la cartera óptima.

    La forma (volatilidad y persistencia de cada régimen) sale de la historia;
    la deriva de largo plazo se ancla al retorno esperado de Black-Litterman.
    """
    w = res.pesos.to_numpy()
    r_log = np.log1p(res.ret_diarios.to_numpy() @ w)
    estados = res.regimenes.estados.reindex(res.ret_diarios.index).ffill().bfill().to_numpy().astype(int)
    k = len(res.regimenes.etiquetas)
    medias = np.array([r_log[estados == j].mean() if (estados == j).sum() > 20 else r_log.mean() for j in range(k)])
    vols = np.array([r_log[estados == j].std() if (estados == j).sum() > 20 else r_log.std() for j in range(k)])
    pi_est = distribucion_estacionaria(res.regimenes.transicion)
    objetivo = (res.retorno_esperado - res.volatilidad ** 2 / 2) / DIAS_ANIO
    medias = medias + (objetivo - pi_est @ medias)
    return {"medias": medias, "vols": vols, "transicion": res.regimenes.transicion,
            "p0": res.regimenes.prob_actual}
