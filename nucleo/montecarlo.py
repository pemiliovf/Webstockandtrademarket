"""Simulación de Monte Carlo con cambios de régimen (Markov).

Cada trayectoria simulada salta entre regímenes según la matriz de
transición; dentro de cada régimen el retorno diario es normal con su propia
media y volatilidad. Con un solo régimen es el clásico movimiento browniano
geométrico.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DIAS_ANIO = 252
PERCENTILES = (5, 25, 50, 75, 95)


def simular(v0: float, medias: np.ndarray, vols: np.ndarray, transicion: np.ndarray,
            p0: np.ndarray, dias: int, n: int = 5000, semilla: int = 7) -> np.ndarray:
    """Devuelve una matriz (n trayectorias × dias+1) con el valor de la cartera."""
    rng = np.random.default_rng(semilla)
    medias, vols = np.asarray(medias, float), np.asarray(vols, float)
    k = len(medias)
    transicion = np.asarray(transicion, float).reshape(k, k)
    p0 = np.asarray(p0, float)
    p0 = p0 / p0.sum()
    acumulada = np.cumsum(transicion, axis=1)
    acumulada[:, -1] = 1.0
    estados = rng.choice(k, size=n, p=p0)
    log_v = np.empty((n, dias + 1), dtype=np.float32)
    actual = np.full(n, np.log(v0))
    log_v[:, 0] = actual
    for t in range(1, dias + 1):
        if k > 1:
            u = rng.random(n)
            estados = np.minimum((u[:, None] > acumulada[estados]).sum(axis=1), k - 1)
        actual = actual + medias[estados] + vols[estados] * rng.standard_normal(n)
        log_v[:, t] = actual
    return np.exp(log_v, dtype=np.float32)


def simular_gbm(v0: float, media_log_diaria: float, vol_diaria: float, dias: int,
                n: int = 5000, semilla: int = 7) -> np.ndarray:
    return simular(v0, [media_log_diaria], [vol_diaria], [[1.0]], [1.0], dias, n, semilla)


def bandas(valores: np.ndarray) -> np.ndarray:
    return np.percentile(valores, PERCENTILES, axis=0)


def escenarios(valores_finales: np.ndarray, v0: float) -> dict:
    """Peor escenario, más probable y mejor, con sus probabilidades."""
    x = np.asarray(valores_finales, float)
    p1, p5, p25, p50, p75, p95, p99 = np.percentile(x, [1, 5, 25, 50, 75, 95, 99])
    # valor más probable = moda de la distribución (histograma en escala log)
    lx = np.log(np.clip(x[(x >= p1) & (x <= p99)], 1e-9, None))
    conteo, bordes = np.histogram(lx, bins=60)
    i = int(np.argmax(conteo))
    moda = float(np.exp((bordes[i] + bordes[i + 1]) / 2))
    banda = 0.05
    return {
        "inicial": v0,
        "peor": float(p5), "peor_ret": p5 / v0 - 1,
        "probable": moda, "probable_ret": moda / v0 - 1,
        "prob_cerca_probable": float(np.mean(np.abs(x - moda) <= banda * moda)),
        "mediana": float(p50), "mediana_ret": p50 / v0 - 1,
        "mejor": float(p95), "mejor_ret": p95 / v0 - 1,
        "p25": float(p25), "p75": float(p75),
        "minimo": float(x.min()), "maximo": float(x.max()),
        "promedio_peor_5": float(x[x <= p5].mean()),
        "prob_ganar": float(np.mean(x > v0)),
        "prob_perder": float(np.mean(x < v0)),
        "prob_perder_10": float(np.mean(x < 0.9 * v0)),
        "prob_perder_20": float(np.mean(x < 0.8 * v0)),
        "prob_ganar_10": float(np.mean(x > 1.1 * v0)),
        "prob_ganar_20": float(np.mean(x > 1.2 * v0)),
        "banda": banda,
    }


def fechas_futuras(desde: pd.Timestamp, dias: int) -> pd.DatetimeIndex:
    return pd.bdate_range(start=pd.Timestamp(desde).normalize(), periods=dias + 1)


def muestra_trayectorias(valores: np.ndarray, cantidad: int = 30, semilla: int = 3) -> np.ndarray:
    rng = np.random.default_rng(semilla)
    idx = rng.choice(valores.shape[0], size=min(cantidad, valores.shape[0]), replace=False)
    return valores[idx]
