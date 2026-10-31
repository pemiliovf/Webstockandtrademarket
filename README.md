# webstockandtrademarket

Plataforma académica con cuatro paneles:

1. **Mercado**: franja con las 3 mayores alzas, las 3 mayores caídas del día y el dólar/peso chileno; precios del S&P 500 completo, ETFs, materias primas y criptomonedas desde Yahoo Finance; mejores y peores de los últimos 90 días; buscador de cualquier activo y noticias económicas (FT, WSJ, The Economist, NYT, BBC, Yahoo Finance, Diario Financiero, Banco Central de Chile y Ministerio de Economía) que se renuevan cada 30 minutos.
2. **Invertir**: perfil de riesgo + monto → preselección automática de activos según el perfil (volatilidad, caídas recientes y tendencia) → cartera óptima con el modelo híbrido Black-Litterman + Markowitz + CAPM dinámico (betas rodantes y regímenes ocultos de Markov) → proyección Monte Carlo → gráfico TradingView (con pantalla completa) y análisis técnico.
3. **Mi cartera**: el usuario ingresa activo, fecha y cantidad o monto invertido (y opcionalmente el precio por unidad) → rentabilidad real, comparación con el S&P 500, proyección Monte Carlo con recta de tendencia y estudio técnico.
4. **Acerca de**: propósito académico (no es corredor ni asesoría), fuentes de datos y metodología completa con fórmulas y referencias.

> **Importante al subir a GitHub:** la carpeta `.streamlit` (con `config.toml`) debe estar en el repositorio.
> Ahí están los colores, la tipografía y el tema claro. Si falta, la página se ve con el tema oscuro y los colores
> rojos por defecto de Streamlit.

Está hecha 100% en **Python** con **Streamlit** (la forma más rápida y estable de publicar un boceto con cálculos financieros pesados). Más adelante se puede rehacer la parte visual en TypeScript sin tocar los modelos.

---

## Parte A · Probarla en tu computador (15 minutos)

### 1. Abrir la carpeta en VS Code
Descomprime `webstockandtrademarket.zip`, abre VS Code y ve a **Archivo → Abrir carpeta…** → elige la carpeta `webstockandtrademarket`.

### 2. Crear un entorno virtual (una caja aislada para las librerías)
Abre la terminal de VS Code (**Terminal → Nueva terminal**) y escribe:

**Windows**
```
py -m venv .venv
.venv\Scripts\activate
```
> Si aparece un error de "ejecución de scripts deshabilitada", escribe una vez
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, responde **S** y repite la segunda línea.

**macOS / Linux**
```
python3 -m venv .venv
source .venv/bin/activate
```

Verás `(.venv)` al inicio de la línea. Si VS Code pregunta si quieres usar el nuevo entorno, responde **Sí**.

### 3. Instalar las librerías
```
pip install -r requirements.txt
```
(tarda 1-3 minutos)

### 4. Ejecutar la página
```
streamlit run app.py
```
Se abrirá el navegador en `http://localhost:8501`. La primera carga del panel Mercado tarda alrededor de un minuto porque descarga ~570 activos; después queda guardado 30 minutos.

Para detenerla: haz clic en la terminal y presiona `Ctrl + C`.

> **Modo demostración (sin internet):** `set WSTM_DEMO=1` (Windows) o `export WSTM_DEMO=1` (macOS) antes de `streamlit run app.py` usa datos sintéticos. Sirve solo para probar el diseño.

---

## Parte B · Publicarla para que tu amigo entre desde otra ciudad (20 minutos, gratis)

La dirección quedará así: **https://webstockandtrademarket.streamlit.app**

### 5. Subir el proyecto a GitHub
1. Crea una cuenta gratis en **github.com** (si no tienes).
2. En VS Code, abre el ícono de **Control de código fuente** (barra izquierda, tercer ícono).
3. Presiona **Publicar en GitHub** (Publish to GitHub), inicia sesión cuando lo pida y elige
   **repositorio privado** con el nombre `webstockandtrademarket`.
4. Si te pregunta qué archivos incluir, deja todos marcados **excepto `.venv`** (ya está excluido en `.gitignore`).

### 6. Desplegar en Streamlit Community Cloud
1. Entra a **share.streamlit.io** e inicia sesión con tu cuenta de GitHub (autoriza el acceso).
2. Presiona **Create app** → **Deploy a public app from GitHub** (o "Yup, I have an app").
3. Completa:
   - **Repository**: `tu-usuario/webstockandtrademarket`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL**: escribe `webstockandtrademarket`
4. En **Advanced settings** elige **Python 3.12** (o 3.13).
5. Presiona **Deploy**. La primera vez tarda 3-5 minutos en instalar todo.

### 7. Compartirla con tu amigo
- Si el repositorio es privado, la app también lo es: en la app presiona **Share** y agrega el correo de tu amigo (entrará con su cuenta de Google o GitHub).
- Si prefieres que cualquiera con el enlace pueda entrar, cambia la visibilidad a pública en el mismo menú **Share**.

### 8. Actualizarla
Cada vez que cambies algo en VS Code: **Control de código fuente → escribe un mensaje → Confirmar (Commit) → Sincronizar (Sync)**. La página se actualiza sola en uno o dos minutos.

---

## Estabilidad: qué hace la página para no caerse

| Riesgo | Cómo se maneja |
|---|---|
| Yahoo limita consultas | Los datos se guardan 30 min y los comparten todos los visitantes; reintentos automáticos con espera. |
| Yahoo no responde | Se muestra la última descarga exitosa con un aviso (no se rompe la página). |
| Un ticker no existe | Se omite y se avisa cuál fue. |
| La app se "duerme" | Streamlit Cloud duerme las apps gratuitas tras 12 horas sin visitas. Al entrar aparece un botón para despertarla (≈30 segundos). |
| Conexión lenta | Los cálculos pesados quedan en caché: cambiar de pestaña o de activo no recalcula todo. |

---

## Sobre el nombre "solo con webstockandtrademarket"

Un navegador siempre necesita una dirección completa; si escribes solo una palabra, Google la busca. Opciones:

- **Gratis (ahora):** `webstockandtrademarket.streamlit.app`. Tu amigo la guarda en favoritos una vez.
- **Dominio propio (después):** comprar `webstockandtrademarket.com` (≈US$ 10-15 al año) o `.cl` en NIC Chile y redirigirlo a la dirección de Streamlit, o alojar la app en un servicio que acepte dominio propio (Render, Railway, un servidor propio).

---

## Ajustar el modelo a tu investigación

Todos los parámetros están en `nucleo/modelo.py` y casi todos se pueden cambiar desde **Opciones avanzadas** en el panel Invertir:

| Parámetro | Valor por defecto | Dónde |
|---|---|---|
| Años de historia | 5 | `PARAMETROS_POR_DEFECTO["anios_historia"]` |
| Ventana de la regresión de betas (MCO sobre excesos de retorno) | 60 días | `["ventana_beta"]` |
| N.º de regímenes de Markov (EM + Viterbi) | 2 | `["n_regimenes"]` |
| Días que se promedian las vistas CAPM-HMM | 20 | `["ventana_vista"]` |
| Tope de las vistas | ±30% anual | `["tope_vista"]` |
| τ de Black-Litterman | 0,05 | `["tau"]` |
| Bandas sectoriales | ±10% sobre el S&P 500 | `["bandas_sectoriales"]`, `["banda_sectorial"]` |
| Pesos sectoriales del S&P 500 | ChartRow 29-10-2026 | `nucleo/universo.py → PESOS_SECTORES_SP500` |
| Aversión al riesgo (λ) por perfil | 1,5 / 4 / 10 | `PERFILES` |
| Máximo por activo, cripto y mínimo en bonos/oro | ver `PERFILES` | `PERFILES` |
| Matriz Ω (confianza en las vistas) | τ·σ²·(1+inestabilidad de la beta)/confianza del régimen | `construir_cartera()` |
| Universo del modo automático | ~60 activos | `nucleo/universo.py → POOL_AUTOMATICO` |
| Filtros y cupos por perfil | ver tabla | `nucleo/seleccion.py → REGLAS` |
| Autores (pie de página) | vacío | `nucleo/config.py → AUTORES` |

---

## Estructura

```
webstockandtrademarket/
├── app.py                 ← punto de entrada (menú con los 4 paneles)
├── paginas/
│   ├── inicio.py          ← Panel 1: Mercado
│   ├── inversion.py       ← Panel 2: Invertir
│   ├── mi_cartera.py      ← Panel 3: Mi cartera
│   └── acerca.py          ← Panel 4: Acerca de (metodología)
├── nucleo/
│   ├── datos.py           ← descarga desde Yahoo con caché y respaldo
│   ├── noticias.py        ← noticias RSS por medio (secciones de economía/finanzas)
│   ├── seleccion.py       ← preselección automática de activos por perfil
│   ├── modelo.py          ← HMM, betas rodantes, CAPM dinámico, Black-Litterman, Markowitz
│   ├── montecarlo.py      ← simulación con cambios de régimen
│   ├── tecnico.py         ← RSI, MACD, Bollinger, medias móviles, métricas de riesgo
│   ├── graficos.py        ← gráficos y widget de TradingView
│   ├── universo.py        ← listas de activos
│   └── ui.py              ← tarjetas, formatos y bloques compartidos
├── .streamlit/config.toml ← colores y tema
└── requirements.txt       ← librerías
```

---

## Notas legales (para la etapa comercial)

- **Yahoo Finance** permite uso personal; `yfinance` no es una API oficial. Para un producto comercial hay que contratar un proveedor de datos con licencia.
- **TradingView**: el gráfico incrustado es su widget gratuito oficial, con sus propios datos y su marca.
- Ofrecer recomendaciones de inversión al público en Chile puede requerir inscripción como asesor de inversión ante la **CMF** (Ley 21.521, Ley Fintec). Mientras sea una herramienta privada entre ustedes, es un ejercicio académico.
