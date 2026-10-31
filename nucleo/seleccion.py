"""Preselección automática de activos (etapa previa al modelo de cartera).

Problema que resuelve: el modelo Black-Litterman + Markowitz optimiza los
pesos de los activos que recibe, pero NO decide qué activos son razonables
para cada perfil. Además, las vistas del CAPM dinámico dependen de la beta
(riesgo sistemático), por lo que un desplome idiosincrático reciente de una
empresa casi no cambia su retorno esperado. Esta etapa agrega reglas
explícitas y auditables, como hacen los procesos de inversión profesionales
(screening → optimización):

1. Calidad de datos: historia suficiente.
2. Riesgo acorde al perfil: volatilidad anual máxima por clase de activo.
3. Filtro de shock: se excluye lo que cayó fuerte en el último mes.
4. Filtro de deterioro: distancia máxima al máximo de 52 semanas.
5. Filtro de tendencia: se excluye la tendencia bajista confirmada
   (precio bajo la media de 200 días Y momentum 12-1 negativo).
6. Ranking dentro de cada clase con un puntaje que combina momentum
   ajustado por riesgo, baja volatilidad y poca caída desde el máximo; se
   toma un número fijo de activos por clase para asegurar diversificación.

Referencias: Jegadeesh y Titman (1993) para el momentum 12-1; Faber (2007)
para el filtro de media de 200 días; Ang et al. (2006) y Frazzini y Pedersen
(2014) para la prima de baja volatilidad.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nucleo.universo import POOL_AUTOMATICO, clase_de, nombre_de

# Reglas por perfil. vol_max se expresa en volatilidad anual.
REGLAS = {
    "Defensivo": {
        "vol_max": {"Bonos": 0.20, "Oro y metales": 0.25, "ETF de acciones": 0.20, "Acciones": 0.24, "Cripto": 0.0},
        "caida_1m_min": -0.10, "dist_max_52s_min": -0.15,
        "cupos": {"Bonos": 6, "Oro y metales": 2, "ETF de acciones": 4, "Acciones": 4, "Cripto": 0},
        "pesos_puntaje": (0.30, 0.50, 0.20),   # momentum, baja volatilidad, cercanía al máximo
    },
    "Moderado": {
        "vol_max": {"Bonos": 0.25, "Oro y metales": 0.30, "ETF de acciones": 0.30, "Acciones": 0.40, "Cripto": 0.85},
        "caida_1m_min": -0.15, "dist_max_52s_min": -0.25,
        "cupos": {"Bonos": 4, "Oro y metales": 2, "ETF de acciones": 5, "Acciones": 7, "Cripto": 1},
        "pesos_puntaje": (0.45, 0.35, 0.20),
    },
    "Arriesgado": {
        "vol_max": {"Bonos": 0.30, "Oro y metales": 0.40, "ETF de acciones": 0.45, "Acciones": 0.65, "Cripto": 1.10},
        "caida_1m_min": -0.25, "dist_max_52s_min": -0.40,
        "cupos": {"Bonos": 2, "Oro y metales": 1, "ETF de acciones": 5, "Acciones": 10, "Cripto": 2},
        "pesos_puntaje": (0.60, 0.15, 0.25),
    },
}
CLASES_SIN_FILTRO_TENDENCIA = {"Bonos"}   # los bonos se juzgan por riesgo y shock, no por momentum
MIN_OBSERVACIONES = 260


def pool_automatico() -> list:
    return [t for lista in POOL_AUTOMATICO.values() for t in lista]


def metricas(precios: pd.DataFrame) -> pd.DataFrame:
    """Métricas de riesgo y tendencia de cada activo (con su propio calendario de cotización)."""
    filas = []
    for t in precios.columns:
        s = precios[t].dropna()
        if len(s) < 30:
            continue
        cripto = t.upper().endswith("-USD")
        anio, mes = (365, 30) if cripto else (252, 21)
        r = np.log(s).diff().dropna()
        p = float(s.iloc[-1])
        ventana = s.iloc[-anio:]
        filas.append({
            "Ticker": t, "Nombre": nombre_de(t), "Clase": clase_de(t), "Observaciones": len(s),
            "Volatilidad 1 año": float(r.iloc[-anio:].std() * np.sqrt(anio)),
            "Var. 1 mes": p / float(s.iloc[-mes - 1]) - 1 if len(s) > mes else np.nan,
            "Momentum 12-1": (float(s.iloc[-mes - 1]) / float(s.iloc[-anio - 1]) - 1) if len(s) > anio else np.nan,
            "Dist. máx. 52 sem.": p / float(ventana.max()) - 1,
            "Sobre media 200": bool(p > float(s.iloc[-200:].mean())) if len(s) >= 200 else np.nan,
        })
    return pd.DataFrame(filas)


def evaluar(met: pd.DataFrame, perfil: str) -> pd.DataFrame:
    """Agrega a cada activo el motivo de exclusión (vacío si pasa todos los filtros)."""
    reglas = REGLAS[perfil]
    d = met.copy()
    motivos = []
    for _, r in d.iterrows():
        m = []
        vol_max = reglas["vol_max"].get(r["Clase"], max(reglas["vol_max"].values()))
        if r["Observaciones"] < MIN_OBSERVACIONES:
            m.append("historia insuficiente")
        if vol_max <= 0:
            m.append("clase no permitida en este perfil")
        elif pd.notna(r["Volatilidad 1 año"]) and r["Volatilidad 1 año"] > vol_max:
            m.append(f"volatilidad {r['Volatilidad 1 año']:.0%} > máximo {vol_max:.0%}")
        if pd.notna(r["Var. 1 mes"]) and r["Var. 1 mes"] < reglas["caida_1m_min"]:
            m.append(f"caída de {r['Var. 1 mes']:.0%} en el último mes")
        if pd.notna(r["Dist. máx. 52 sem."]) and r["Dist. máx. 52 sem."] < reglas["dist_max_52s_min"]:
            m.append(f"{r['Dist. máx. 52 sem.']:.0%} bajo su máximo de 52 semanas")
        bajo_media = pd.notna(r["Sobre media 200"]) and not bool(r["Sobre media 200"])
        if (r["Clase"] not in CLASES_SIN_FILTRO_TENDENCIA and bajo_media
                and pd.notna(r["Momentum 12-1"]) and r["Momentum 12-1"] < 0):
            m.append("tendencia bajista (bajo la media de 200 días y momentum 12-1 negativo)")
        motivos.append("; ".join(m))
    d["Motivo de exclusión"] = motivos
    d["Pasa filtros"] = d["Motivo de exclusión"] == ""

    # Puntaje: rangos percentiles dentro de cada clase (0 = peor, 1 = mejor)
    w_mom, w_vol, w_dd = reglas["pesos_puntaje"]
    mom_aj = d["Momentum 12-1"].fillna(d["Var. 1 mes"]) / d["Volatilidad 1 año"].clip(lower=0.02)
    g = d.assign(_mom=mom_aj).groupby("Clase")
    d["Puntaje"] = (w_mom * g["_mom"].rank(pct=True)
                    + w_vol * g["Volatilidad 1 año"].rank(pct=True, ascending=False)
                    + w_dd * g["Dist. máx. 52 sem."].rank(pct=True)).fillna(0)
    return d


def seleccionar(met: pd.DataFrame, perfil: str) -> tuple[list, pd.DataFrame]:
    """Devuelve (tickers elegidos, tabla de evaluación con el estado de cada activo)."""
    reglas = REGLAS[perfil]
    d = evaluar(met, perfil)
    elegidos = []
    for clase, cupo in reglas["cupos"].items():
        if cupo <= 0:
            continue
        candidatos = d[(d["Clase"] == clase) & d["Pasa filtros"]].sort_values("Puntaje", ascending=False)
        elegidos += candidatos["Ticker"].head(cupo).tolist()
    # Red de seguridad: un perfil con mínimo defensivo siempre tiene bonos de corto plazo
    if not any(clase_de(t) == "Bonos" for t in elegidos):
        elegidos += [t for t in ("BIL", "SHY") if t in d["Ticker"].values]
    d["Estado"] = np.where(d["Ticker"].isin(elegidos), "Seleccionado",
                           np.where(d["Pasa filtros"], "Apto, fuera del cupo de su clase", "Excluido"))
    orden = {"Seleccionado": 0, "Apto, fuera del cupo de su clase": 1, "Excluido": 2}
    d = d.sort_values(["Estado", "Clase", "Puntaje"], key=lambda c: c.map(orden) if c.name == "Estado" else c,
                      ascending=[True, True, False]).reset_index(drop=True)
    return elegidos, d


def revisar_manual(met: pd.DataFrame, perfil: str) -> pd.DataFrame:
    """Evalúa activos elegidos por el usuario con las mismas reglas (sin cupos)."""
    d = evaluar(met, perfil)
    d["Estado"] = np.where(d["Pasa filtros"], "Seleccionado", "Excluido")
    return d.sort_values(["Estado", "Puntaje"], ascending=[False, False]).reset_index(drop=True)
