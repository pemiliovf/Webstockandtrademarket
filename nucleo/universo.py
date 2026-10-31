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
    "BIL": "SPDR Letras del Tesoro 1-3 meses", "IEI": "iShares Bonos Tesoro 3-7 años",
    "AGG": "iShares Bonos Agregado EE.UU.", "VCSH": "Vanguard Bonos Corporativos Corto Plazo",
    "USMV": "iShares Acciones EE.UU. Mínima Volatilidad", "VIG": "Vanguard Crecimiento de Dividendos",
    "SCHD": "Schwab Dividendos EE.UU.",
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

# Activos considerados "defensivos" (bonos de grado de inversión y oro) para los perfiles de riesgo
DEFENSIVOS = {"BIL", "SHY", "IEI", "IEF", "TLT", "BND", "AGG", "LQD", "VCSH", "TIP", "GLD", "IAU", "GC=F"}

# ---------------------------------------------------------------------------
# Universo del modo AUTOMÁTICO del panel Invertir (el modelo elige entre estos
# según el perfil, después de aplicar filtros de riesgo y tendencia).
# ---------------------------------------------------------------------------
POOL_AUTOMATICO = {
    "Bonos": ["BIL", "SHY", "IEI", "IEF", "TLT", "BND", "AGG", "LQD", "VCSH", "TIP"],
    "Oro y metales": ["GLD", "IAU", "SLV"],
    "ETF de acciones": ["SPY", "QQQ", "VTI", "IWM", "EFA", "EEM", "ECH", "USMV", "VIG", "SCHD", "VNQ",
                        "XLK", "XLF", "XLE", "XLV", "XLP", "XLU", "XLI"],
    "Acciones": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "BRK-B", "JPM", "V", "MA",
                 "UNH", "LLY", "JNJ", "PG", "KO", "PEP", "WMT", "COST", "HD", "MCD", "XOM", "CVX", "ABBV",
                 "MRK", "ORCL", "NFLX"],
    "Cripto": ["BTC-USD", "ETH-USD"],
}
CLASE_POR_TICKER = {t: c for c, lista in POOL_AUTOMATICO.items() for t in lista}

NOMBRES_ACCIONES = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon", "GOOGL": "Alphabet (Google)",
    "META": "Meta Platforms", "AVGO": "Broadcom", "TSLA": "Tesla", "BRK-B": "Berkshire Hathaway",
    "JPM": "JPMorgan Chase", "V": "Visa", "MA": "Mastercard", "UNH": "UnitedHealth", "LLY": "Eli Lilly",
    "JNJ": "Johnson & Johnson", "PG": "Procter & Gamble", "KO": "Coca-Cola", "PEP": "PepsiCo",
    "WMT": "Walmart", "COST": "Costco", "HD": "Home Depot", "MCD": "McDonald's", "XOM": "Exxon Mobil",
    "CVX": "Chevron", "ABBV": "AbbVie", "MRK": "Merck", "ORCL": "Oracle", "NFLX": "Netflix",
    "VOO": "Vanguard S&P 500",
}

# Escrituras frecuentes que en Yahoo Finance significan otra cosa (o nada)
ALIAS_TICKERS = {
    "BTC": "BTC-USD", "BITCOIN": "BTC-USD", "XBT": "BTC-USD", "ETH": "ETH-USD", "ETHEREUM": "ETH-USD",
    "SOLANA": "SOL-USD", "XRP": "XRP-USD", "CARDANO": "ADA-USD", "ADA": "ADA-USD", "DOGE": "DOGE-USD",
    "DOGECOIN": "DOGE-USD", "BNB": "BNB-USD", "ORO": "GLD", "GOLD": "GLD", "PLATA": "SLV", "SILVER": "SLV",
    "SP500": "VOO", "S&P500": "VOO", "S&P 500": "VOO", "NASDAQ": "QQQ", "BRK.B": "BRK-B", "BRKB": "BRK-B",
}

# Activos frecuentes para el formulario de «Mi cartera»: etiqueta -> ticker
POPULARES = {
    "Bitcoin · BTC-USD": "BTC-USD", "Ethereum · ETH-USD": "ETH-USD", "Solana · SOL-USD": "SOL-USD",
    "S&P 500 (Vanguard) · VOO": "VOO", "S&P 500 (SPDR) · SPY": "SPY", "S&P 500 (iShares) · IVV": "IVV",
    "Nasdaq-100 · QQQ": "QQQ", "Oro (ETF) · GLD": "GLD", "Plata (ETF) · SLV": "SLV",
    "Bonos del Tesoro 20+ años · TLT": "TLT", "Bonos del Tesoro 7-10 años · IEF": "IEF",
    "Bonos del Tesoro 1-3 años · SHY": "SHY", "Acciones chilenas (ETF) · ECH": "ECH",
    "Apple · AAPL": "AAPL", "Microsoft · MSFT": "MSFT", "NVIDIA · NVDA": "NVDA", "Amazon · AMZN": "AMZN",
    "Alphabet (Google) · GOOGL": "GOOGL", "Meta · META": "META", "Tesla · TSLA": "TSLA", "Netflix · NFLX": "NFLX",
    "Berkshire Hathaway · BRK-B": "BRK-B", "JPMorgan · JPM": "JPM", "Visa · V": "V", "Coca-Cola · KO": "KO",
    "SQM serie B (Chile) · SQM-B.SN": "SQM-B.SN", "Falabella (Chile) · FALABELLA.SN": "FALABELLA.SN",
    "Banco de Chile · CHILE.SN": "CHILE.SN", "Banco Santander Chile · BSANTANDER.SN": "BSANTANDER.SN",
    "Copec (Chile) · COPEC.SN": "COPEC.SN", "Cencosud (Chile) · CENCOSUD.SN": "CENCOSUD.SN",
}


def normalizar_ticker(texto: str) -> tuple[str, str | None]:
    """Devuelve (ticker de Yahoo, nota) corrigiendo escrituras frecuentes."""
    t = str(texto or "").strip()
    if t in POPULARES:
        return POPULARES[t], None
    if " · " in t:  # etiqueta tipo «Nombre · TICKER»
        t = t.rsplit(" · ", 1)[1]
    u = t.upper()
    if u in ALIAS_TICKERS:
        nuevo = ALIAS_TICKERS[u]
        return nuevo, f"«{t}» se interpretó como {nuevo} ({nombre_de(nuevo)})."
    return u, None


def clase_de(ticker: str) -> str:
    t = ticker.upper()
    if t in CLASE_POR_TICKER:
        return CLASE_POR_TICKER[t]
    tipo = tipo_de_activo(t)
    if tipo == "Cripto":
        return "Cripto"
    if t in DEFENSIVOS:
        return "Bonos" if t not in ("GLD", "IAU", "GC=F") else "Oro y metales"
    if tipo == "ETF":
        return "ETF de acciones"
    if tipo == "Materia prima":
        return "Materias primas"
    return "Acciones"

# Universo candidato por defecto para el modelo de cartera (panel 2):
# acciones líderes de distintos sectores + ETFs + bonos + oro + cripto.
CANDIDATOS_CARTERA = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "V", "JNJ", "PG",
    "KO", "XOM", "UNH", "HD", "COST", "LLY", "BRK-B", "WMT",
    "SPY", "QQQ", "IWM", "EFA", "EEM", "VNQ", "XLU",
    "TLT", "IEF", "SHY", "LQD", "TIP", "GLD",
    "BTC-USD", "ETH-USD",
]
PROXY_MERCADO = "SPY"          # activo invertible para comparar carteras (incluye dividendos)
INDICE_MERCADO = "^GSPC"       # índice S&P 500: mercado del CAPM y del HMM (como en el paper)
TASA_LIBRE_RIESGO = "^IRX"     # Letra del Tesoro de EE.UU. a 13 semanas (en % anual)

# ---------------------------------------------------------------------------
# Sectores GICS y bandas sectoriales
# ---------------------------------------------------------------------------
# Peso de cada sector en el S&P 500. Estimación de ChartRow al 29-10-2026
# (https://chartrow.com/sp500/sector-weights). Actualizar periódicamente.
FECHA_PESOS_SECTORES = "29-10-2026"
PESOS_SECTORES_SP500 = {
    "Information Technology": 0.385, "Financials": 0.121, "Health Care": 0.099,
    "Consumer Discretionary": 0.091, "Communication Services": 0.083, "Industrials": 0.081,
    "Consumer Staples": 0.047, "Energy": 0.038, "Utilities": 0.021, "Real Estate": 0.017, "Materials": 0.016,
}
SECTORES_ES = {
    "Information Technology": "Tecnología de la información", "Financials": "Financiero",
    "Health Care": "Salud", "Consumer Discretionary": "Consumo discrecional",
    "Communication Services": "Servicios de comunicación", "Industrials": "Industrial",
    "Consumer Staples": "Consumo básico", "Energy": "Energía", "Utilities": "Servicios públicos",
    "Real Estate": "Inmobiliario", "Materials": "Materiales",
}
SECTOR_POR_TICKER = {
    "AAPL": "Information Technology", "MSFT": "Information Technology", "NVDA": "Information Technology",
    "AVGO": "Information Technology", "ORCL": "Information Technology", "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary", "HD": "Consumer Discretionary", "MCD": "Consumer Discretionary",
    "GOOGL": "Communication Services", "GOOG": "Communication Services", "META": "Communication Services",
    "NFLX": "Communication Services", "BRK-B": "Financials", "JPM": "Financials", "V": "Financials",
    "MA": "Financials", "UNH": "Health Care", "LLY": "Health Care", "JNJ": "Health Care", "ABBV": "Health Care",
    "MRK": "Health Care", "PG": "Consumer Staples", "KO": "Consumer Staples", "PEP": "Consumer Staples",
    "WMT": "Consumer Staples", "COST": "Consumer Staples", "XOM": "Energy", "CVX": "Energy",
    # ETFs sectoriales
    "XLK": "Information Technology", "XLF": "Financials", "XLE": "Energy", "XLV": "Health Care",
    "XLP": "Consumer Staples", "XLU": "Utilities", "XLI": "Industrials", "XLY": "Consumer Discretionary",
    "VNQ": "Real Estate",
}
# ETFs de acciones diversificados: se tratan con la composición sectorial del índice (neutrales)
ETFS_DIVERSIFICADOS = {"SPY", "VOO", "IVV", "VTI", "QQQ", "DIA", "IWM", "EFA", "EEM", "ECH", "USMV", "VIG",
                       "SCHD", "ARKK"}


def sector_de(ticker: str) -> str | None:
    """Sector GICS del activo (None si no es renta variable de EE.UU. con sector)."""
    t = ticker.upper()
    if t in SECTOR_POR_TICKER:
        return SECTOR_POR_TICKER[t]
    if t in ETFS_DIVERSIFICADOS or tipo_de_activo(t) != "Acción" or "." in t or t.startswith("^"):
        return None
    try:
        sp = lista_sp500()
        fila = sp.loc[sp["Ticker"] == t, "Sector"]
        if len(fila) and fila.iloc[0] in PESOS_SECTORES_SP500:
            return str(fila.iloc[0])
    except Exception:
        pass
    return None

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
    for dic in (ETFS, MATERIAS_PRIMAS, CRIPTOS, INDICES, NOMBRES_ACCIONES):
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
