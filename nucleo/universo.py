"""Listas de activos que usa la página.

Yahoo Finance no ofrece una lista oficial de "todos los tickers", así que el
panel de inicio trabaja sobre un universo amplio: el S&P 500 completo (se
descarga de Wikipedia) más ETFs, materias primas, criptomonedas e índices.
Además, cualquier otro ticker de Yahoo se puede consultar con el buscador.
"""

from io import StringIO

import pandas as pd
import requests
import streamlit as st

# --- Activos adicionales al S&P 500 -------------------------------------------
ETFS = {
    "SPY": "SPDR S&P 500", "VOO": "Vanguard S&P 500", "IVV": "iShares Core S&P 500",
    "QQQ": "Invesco Nasdaq-100", "DIA": "SPDR Dow Jones", "IWM": "iShares Russell 2000",
    "VTI": "Vanguard Total Stock Market", "EFA": "iShares MSCI EAFE",
    "EEM": "iShares MSCI Emergentes", "ECH": "iShares MSCI Chile",
    "TLT": "iShares Bonos Tesoro 20+ años", "IEF": "iShares Bonos Tesoro 7-10 años",
    "SHY": "iShares Bonos Tesoro 1-3 años", "BND": "Vanguard Bonos Total",
    "LQD": "iShares Bonos Corporativos", "HYG": "iShares High Yield", "TIP": "iShares Bonos TIPS",
    "GLD": "SPDR Oro", "IAU": "iShares Oro", "SLV": "iShares Plata", "VNQ": "Vanguard Inmobiliario",
    "XLK": "Sector Tecnología", "XLF": "Sector Financiero", "XLE": "Sector Energía",
    "XLV": "Sector Salud", "XLY": "Sector Consumo Discrecional", "XLP": "Sector Consumo Básico",
    "XLI": "Sector Industrial", "XLU": "Sector Servicios Públicos", "ARKK": "ARK Innovation",
}
MATERIAS_PRIMAS = {
    "GC=F": "Oro (futuro)", "SI=F": "Plata (futuro)", "CL=F": "Petróleo WTI (futuro)",
    "NG=F": "Gas natural (futuro)", "HG=F": "Cobre (futuro)",
}
CRIPTOS = {
    "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana", "XRP-USD": "XRP",
    "BNB-USD": "BNB", "ADA-USD": "Cardano", "DOGE-USD": "Dogecoin",
}
INDICES = {
    "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^DJI": "Dow Jones", "^RUT": "Russell 2000",
    "^VIX": "VIX (volatilidad)", "^IPSA": "IPSA Chile", "CLP=X": "Dólar / Peso chileno",
}

# Franja superior del panel de inicio
FRANJA_INICIO = ["^GSPC", "^IXIC", "^DJI", "^VIX", "BTC-USD", "GC=F", "CLP=X"]

# Activos considerados "defensivos" (bonos y oro) para los perfiles de riesgo
DEFENSIVOS = {"TLT", "IEF", "SHY", "BND", "AGG", "LQD", "TIP", "GLD", "IAU", "GC=F"}

# Universo candidato por defecto para el modelo de cartera (panel 2):
# acciones líderes de distintos sectores + ETFs + bonos + oro + cripto.
CANDIDATOS_CARTERA = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "V", "JNJ", "PG",
    "KO", "XOM", "UNH", "HD", "COST", "LLY", "BRK-B", "WMT",
    "SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ", "XLU",
    "TLT", "IEF", "SHY", "LQD", "TIP", "GLD",
    "BTC-USD", "ETH-USD",
]
PROXY_MERCADO = "SPY"
TASA_LIBRE_RIESGO = "^IRX"  # Letra del Tesoro de EE.UU. a 13 semanas (en %)

# Respaldo por si Wikipedia no responde: 100 grandes empresas del S&P 500
SP500_RESPALDO = """AAPL MSFT NVDA AMZN GOOGL GOOG META BRK-B AVGO TSLA LLY JPM V UNH XOM MA JNJ PG
HD COST ABBV MRK WMT NFLX CVX KO PEP ADBE CRM BAC AMD TMO ORCL ACN MCD LIN CSCO ABT WFC
DHR DIS INTU TXN VZ PM QCOM CAT IBM AMGN GE NOW PFE AMAT CMCSA NEE UNP SPGI LOW ISRG RTX
GS HON UBER T BKNG PGR ELV SYK BLK MS COP TJX VRTX C LMT MDT ADP REGN SCHW BSX PLD CB MMC
ADI SBUX GILD MDLZ DE BMY ETN LRCX PANW AMT MU KLAC SO CI""".split()


def tipo_de_activo(ticker: str) -> str:
    t = ticker.upper()
    if t in CRIPTOS or t.endswith("-USD"):
        return "Cripto"
    if t in MATERIAS_PRIMAS or t.endswith("=F"):
        return "Materia prima"
    if t.startswith("^") or t.endswith("=X"):
        return "Índice / divisa"
    if t in ETFS:
        return "ETF"
    return "Acción"


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def lista_sp500() -> pd.DataFrame:
    """Componentes del S&P 500 (ticker, nombre, sector). Respaldo si falla."""
    from nucleo.config import MODO_DEMO
    if MODO_DEMO:
        return pd.DataFrame({"Ticker": SP500_RESPALDO, "Nombre": SP500_RESPALDO, "Sector": "—"})
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (webstockandtrademarket)"}, timeout=15)
        r.raise_for_status()
        tabla = pd.read_html(StringIO(r.text))[0]
        df = pd.DataFrame({
            "Ticker": tabla["Symbol"].astype(str).str.replace(".", "-", regex=False),
            "Nombre": tabla["Security"].astype(str),
            "Sector": tabla["GICS Sector"].astype(str),
        })
        if len(df) > 400:
            return df
    except Exception:
        pass
    return pd.DataFrame({"Ticker": SP500_RESPALDO, "Nombre": SP500_RESPALDO, "Sector": "—"})


def universo_inicio() -> pd.DataFrame:
    """Universo completo del panel de inicio con nombre y tipo de activo."""
    sp = lista_sp500().copy()
    sp["Tipo"] = "Acción"
    extras = []
    for dic, tipo in ((ETFS, "ETF"), (MATERIAS_PRIMAS, "Materia prima"), (CRIPTOS, "Cripto")):
        for t, n in dic.items():
            extras.append({"Ticker": t, "Nombre": n, "Sector": tipo, "Tipo": tipo})
    df = pd.concat([sp, pd.DataFrame(extras)], ignore_index=True)
    return df.drop_duplicates("Ticker").reset_index(drop=True)


def nombre_de(ticker: str) -> str:
    for dic in (ETFS, MATERIAS_PRIMAS, CRIPTOS, INDICES):
        if ticker in dic:
            return dic[ticker]
    try:
        sp = lista_sp500()
        fila = sp.loc[sp["Ticker"] == ticker, "Nombre"]
        if len(fila):
            return str(fila.iloc[0])
    except Exception:
        pass
    return ticker
