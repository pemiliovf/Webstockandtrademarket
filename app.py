"""webstockandtrademarket — plataforma académica de análisis de mercados.

Para ejecutar en tu computador:   streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="webstockandtrademarket · Análisis de mercados",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

paginas = [
    st.Page("paginas/inicio.py", title="Mercado", icon=":material/monitoring:", default=True),
    st.Page("paginas/inversion.py", title="Invertir", icon=":material/insights:", url_path="invertir"),
    st.Page("paginas/mi_cartera.py", title="Mi cartera", icon=":material/account_balance_wallet:", url_path="mi-cartera"),
    st.Page("paginas/acerca.py", title="Acerca de", icon=":material/info:", url_path="acerca"),
]

st.navigation(paginas, position="top").run()
