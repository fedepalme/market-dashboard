import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
from deep_translator import GoogleTranslator

st.set_page_config(
    page_title="Market Weekly Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Ticker universe ────────────────────────────────────────────────────────────

TICKERS = {
    # Mi Cartera
    "SPY":     {"name": "SPDR S&P 500 ETF Trust",              "group": "Mi Cartera"},
    "AAPL":    {"name": "Apple Inc.",                          "group": "Mi Cartera"},
    "KO":      {"name": "The Coca-Cola Company",               "group": "Mi Cartera"},
    "XLK":     {"name": "Technology Select Sector SPDR",       "group": "Mi Cartera"},
    "META":    {"name": "Meta Platforms Inc.",                 "group": "Mi Cartera"},
    "GOLD":    {"name": "Barrick Gold Corporation",            "group": "Mi Cartera"},
    # Tecnología
    "NVDA":    {"name": "NVIDIA Corporation",                  "group": "Tecnología"},
    "MSFT":    {"name": "Microsoft Corporation",               "group": "Tecnología"},
    "GOOGL":   {"name": "Alphabet Inc. (Google)",              "group": "Tecnología"},
    "AMZN":    {"name": "Amazon.com Inc.",                     "group": "Tecnología"},
    "TSLA":    {"name": "Tesla Inc.",                          "group": "Tecnología"},
    "AMD":     {"name": "Advanced Micro Devices Inc.",         "group": "Tecnología"},
    "AVGO":    {"name": "Broadcom Inc.",                       "group": "Tecnología"},
    "ASML":    {"name": "ASML Holding N.V.",                   "group": "Tecnología"},
    "QQQ":     {"name": "Invesco QQQ Trust (Nasdaq-100)",      "group": "Tecnología"},
    # Top 20
    "BRK.B":   {"name": "Berkshire Hathaway Inc.",             "group": "Top 20"},
    "JPM":     {"name": "JPMorgan Chase & Co.",                "group": "Top 20"},
    "V":       {"name": "Visa Inc.",                           "group": "Top 20"},
    "UNH":     {"name": "UnitedHealth Group Inc.",             "group": "Top 20"},
    "JNJ":     {"name": "Johnson & Johnson",                   "group": "Top 20"},
    "PG":      {"name": "Procter & Gamble Co.",                "group": "Top 20"},
    "WMT":     {"name": "Walmart Inc.",                        "group": "Top 20"},
    "XOM":     {"name": "ExxonMobil Corporation",              "group": "Top 20"},
    "DIS":     {"name": "The Walt Disney Company",             "group": "Top 20"},
    "NFLX":    {"name": "Netflix Inc.",                        "group": "Top 20"},
    "BAC":     {"name": "Bank of America Corp.",               "group": "Top 20"},
    "MA":      {"name": "Mastercard Inc.",                     "group": "Top 20"},
    "HD":      {"name": "The Home Depot Inc.",                 "group": "Top 20"},
    "LLY":     {"name": "Eli Lilly and Company",               "group": "Top 20"},
    "COST":    {"name": "Costco Wholesale Corp.",              "group": "Top 20"},
    "MCD":     {"name": "McDonald's Corporation",              "group": "Top 20"},
    "GLD":     {"name": "SPDR Gold Shares ETF",                "group": "Top 20"},
    "TLT":     {"name": "iShares 20+ Year Treasury Bond ETF",  "group": "Top 20"},
    # Macro
    "UUP":     {"name": "US Dollar Index ETF (≈DXY)",          "group": "Macro"},
    "USO":     {"name": "United States Oil Fund (≈WTI)",       "group": "Macro"},
    "BTC-USD": {"name": "Bitcoin",                             "group": "Macro"},
}

MY_PORTFOLIO = ["SPY", "AAPL", "KO", "XLK", "META", "GOLD"]

GROUP_ORDER = ["Mi Cartera", "Tecnología", "Top 20", "Macro"]

# ── Data fetching ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_data():
    end = datetime.now()
    start = end - timedelta(days=400)
    rows = []
    for ticker, meta in TICKERS.items():
        try:
            hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
            if hist.empty:
                continue
            price = hist["Close"].iloc[-1]

            def pct(n_days):
                if len(hist) > n_days:
                    return (price / hist["Close"].iloc[-n_days - 1] - 1) * 100
                return None

            year_start = f"{end.year}-01-01"
            ytd_hist = hist[hist.index >= year_start]
            ytd = (price / ytd_hist["Close"].iloc[0] - 1) * 100 if len(ytd_hist) > 1 else None

            rows.append({
                "Ticker":  ticker,
                "Empresa": meta["name"],
                "Grupo":   meta["group"],
                "Precio":  round(price, 2),
                "1S %":    round(pct(5), 2)   if pct(5)   is not None else None,
                "1M %":    round(pct(21), 2)  if pct(21)  is not None else None,
                "YTD %":   round(ytd, 2)      if ytd      is not None else None,
                "1A %":    round(pct(252), 2) if pct(252) is not None else None,
                "_hist":   hist,
            })
        except Exception:
            continue
    return rows


def _parse_article(article: dict) -> dict | None:
    """Normalize yfinance news article across different API versions."""
    content = article.get("content", {})

    title = (
        article.get("title")
        or content.get("title")
        or content.get("headline")
        or ""
    )
    link = (
        article.get("link")
        or article.get("url")
        or content.get("canonicalUrl", {}).get("url", "")
        or content.get("clickThroughUrl", {}).get("url", "")
        or ""
    )
    publisher = (
        article.get("publisher")
        or content.get("provider", {}).get("displayName", "")
        or ""
    )
    summary = (
        article.get("summary")
        or content.get("summary")
        or content.get("description")
        or content.get("body", "")[:300]
        or ""
    )
    ts = article.get("providerPublishTime") or article.get("pubDate") or None
    if isinstance(ts, str):
        try:
            ts = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
        except Exception:
            ts = None
    if not title or not link:
        return None
    return {"title": title, "summary": summary, "link": link, "publisher": publisher, "ts": ts}


@st.cache_data(ttl=86400, show_spinner=False)
def _translate(text: str) -> str:
    if not text or not text.strip():
        return text
    try:
        return GoogleTranslator(source="auto", target="es").translate(text[:4000])
    except Exception:
        return text


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_news(ticker: str) -> list[dict]:
    try:
        raw = yf.Ticker(ticker).news or []
        parsed = [_parse_article(a) for a in raw]
        return [a for a in parsed if a is not None][:6]
    except Exception:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_top_news(n: int = 20) -> list[dict]:
    """Aggregate global market news. Mix of portfolio, sector, macro and index tickers."""
    # Broader universe: our tickers + major indices + macro instruments
    extra = ["^GSPC", "^DJI", "^IXIC", "^VIX", "^TNX", "GC=F", "CL=F",
             "EURUSD=X", "^FTSE", "^N225", "^HSI", "EEM", "IWM", "XLE",
             "XLF", "XLV", "XLI", "XLB", "ARKK", "IBIT"]
    sources = list(TICKERS.keys()) + extra

    seen_titles: set[str] = set()
    per_ticker: dict[str, int] = {}
    all_articles: list[dict] = []

    for ticker in sources:
        try:
            raw = yf.Ticker(ticker).news or []
            for a in raw:
                parsed = _parse_article(a)
                if parsed is None:
                    continue
                key = parsed["title"].lower().strip()[:80]
                if key in seen_titles:
                    continue
                if per_ticker.get(ticker, 0) >= 2:
                    continue
                seen_titles.add(key)
                per_ticker[ticker] = per_ticker.get(ticker, 0) + 1
                label = TICKERS.get(ticker, {}).get("name", ticker)
                parsed["ticker"] = ticker
                parsed["company"] = label
                all_articles.append(parsed)
        except Exception:
            continue

    all_articles.sort(key=lambda x: x.get("ts") or 0, reverse=True)
    return all_articles[:n]


def color_pct(val):
    if val is None:
        return ""
    color = "#16a34a" if val >= 0 else "#dc2626"
    return f"color: {color}; font-weight: 600"


_MOVERS_COL_CFG = lambda pct_col: {
    "Ticker":  st.column_config.TextColumn("Ticker",  width=50),
    "Empresa": st.column_config.TextColumn("Empresa", width=130),
    "Precio":  st.column_config.TextColumn("Precio",  width=72),
    pct_col:   st.column_config.TextColumn(pct_col,   width=78),
}

def _movers_styled(dataframe: pd.DataFrame, pct_col: str):
    cols = [c for c in ["Ticker", "Empresa", "Precio", pct_col] if c in dataframe.columns]
    return (
        dataframe[cols].style
        .map(color_pct, subset=[pct_col])
        .format({"Precio": "${:,.2f}", pct_col: "{:+.2f}%"}, na_rep="—")
    )

def movers_table(dataframe: pd.DataFrame, pct_col: str):
    st.dataframe(
        _movers_styled(dataframe, pct_col),
        use_container_width=True,
        hide_index=True,
        column_config=_MOVERS_COL_CFG(pct_col),
    )

def movers_table_selectable(dataframe: pd.DataFrame, pct_col: str, key: str) -> str | None:
    event = st.dataframe(
        _movers_styled(dataframe, pct_col),
        use_container_width=True,
        hide_index=True,
        column_config=_MOVERS_COL_CFG(pct_col),
        on_select="rerun",
        selection_mode="single-row",
        key=key,
    )
    if event.selection.rows:
        return dataframe.iloc[event.selection.rows[0]]["Ticker"]
    return None


@st.dialog("📈 Performance — 6 meses", width="large")
def show_performance_chart(ticker: str, company: str):
    hist = hist_map.get(ticker)
    if hist is None:
        st.warning("Sin datos históricos para este ticker.")
        return

    cutoff = pd.Timestamp(datetime.now() - timedelta(days=182))
    if hist.index.tz is not None:
        cutoff = cutoff.tz_localize("UTC")
    hist_6m = hist[hist.index >= cutoff]

    if hist_6m.empty:
        st.warning("Sin datos en los últimos 6 meses.")
        return

    st.markdown(f"### {ticker} — {company}")

    price_now   = hist_6m["Close"].iloc[-1]
    price_start = hist_6m["Close"].iloc[0]
    pct_6m      = (price_now / price_start - 1) * 100
    col1, col2, col3 = st.columns(3)
    col1.metric("Precio actual",    f"${price_now:,.2f}")
    col2.metric("Hace 6 meses",     f"${price_start:,.2f}")
    col3.metric("Variación 6M",     f"{pct_6m:+.2f}%", delta=f"{pct_6m:+.2f}%")

    fig = go.Figure(go.Candlestick(
        x=hist_6m.index,
        open=hist_6m["Open"],
        high=hist_6m["High"],
        low=hist_6m["Low"],
        close=hist_6m["Close"],
        name=ticker,
        increasing_line_color="#16a34a",
        decreasing_line_color="#dc2626",
    ))
    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=380,
        margin=dict(t=20, b=20, l=10, r=10),
        plot_bgcolor="#1e293b",
        paper_bgcolor="#1e293b",
        font_color="#f1f5f9",
        xaxis=dict(gridcolor="#334155"),
        yaxis=dict(gridcolor="#334155", tickprefix="$"),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📈 Market Dashboard")
    ARG = timezone(timedelta(hours=-3))
    now_arg = datetime.now(ARG)
    st.caption(f"Actualizado: {now_arg.strftime('%d/%m/%Y %H:%M')} (ARG)")

    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("**Navegación**")
    page = st.radio(
        "",
        ["Mi Cartera", "Movers", "Mercado General", "Noticias", "Detalle de Ticker"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("**Filtrar por grupo**")
    selected_groups = st.multiselect(
        "",
        GROUP_ORDER,
        default=GROUP_ORDER,
        label_visibility="collapsed",
    )

# ── Load data ──────────────────────────────────────────────────────────────────

with st.spinner("Cargando datos de mercado..."):
    all_data = fetch_all_data()

df_full = pd.DataFrame([{k: v for k, v in r.items() if k != "_hist"} for r in all_data])
hist_map = {r["Ticker"]: r["_hist"] for r in all_data}

df = df_full[df_full["Grupo"].isin(selected_groups)].copy()

# ── Helper: styled table ───────────────────────────────────────────────────────

def styled_table(dataframe: pd.DataFrame):
    pct_cols = [c for c in ["1S %", "1M %", "YTD %", "1A %"] if c in dataframe.columns]
    styled = dataframe.style.map(color_pct, subset=pct_cols).format(
        {c: "{:+.2f}%" for c in pct_cols} | {"Precio": "${:,.2f}"},
        na_rep="—",
    )
    return styled


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MI CARTERA
# ══════════════════════════════════════════════════════════════════════════════

if page == "Mi Cartera":
    st.header("💼 Mi Cartera")

    df_port = df_full[df_full["Ticker"].isin(MY_PORTFOLIO)].copy()

    if df_port.empty:
        st.warning("No se pudieron cargar los datos de tu cartera.")
    else:
        # KPI cards
        cols = st.columns(len(df_port))
        for col, (_, row) in zip(cols, df_port.iterrows()):
            delta = row["1S %"]
            col.metric(
                label=f"{row['Ticker']}",
                value=f"${row['Precio']:,.2f}",
                delta=f"{delta:+.2f}% (1S)" if delta is not None else "—",
            )

        st.divider()

        # Table
        st.subheader("Performance")
        display_cols = ["Ticker", "Empresa", "Precio", "1S %", "1M %", "YTD %", "1A %"]
        st.dataframe(
            styled_table(df_port[display_cols].reset_index(drop=True)),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # Comparative chart (YTD normalized to 100)
        st.subheader("Evolución YTD (base 100)")
        year_start = f"{datetime.now().year}-01-01"
        fig = go.Figure()
        for ticker in MY_PORTFOLIO:
            hist = hist_map.get(ticker)
            if hist is None:
                continue
            ytd_hist = hist[hist.index >= year_start]["Close"]
            if ytd_hist.empty:
                continue
            normalized = (ytd_hist / ytd_hist.iloc[0]) * 100
            fig.add_trace(go.Scatter(
                x=normalized.index,
                y=normalized.values,
                name=f"{ticker} – {TICKERS[ticker]['name']}",
                mode="lines",
            ))
        fig.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.5)
        fig.update_layout(
            xaxis_title="Fecha",
            yaxis_title="Rendimiento (base 100)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            height=420,
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MOVERS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Movers":
    st.markdown("""
    <style>
    div[data-testid="stDataFrame"] div[class*="dvn-scroller"] * { font-size: 0.75rem !important; }
    div[data-testid="stDataFrame"] .ag-cell { font-size: 0.75rem !important; padding: 2px 6px !important; }
    div[data-testid="stDataFrame"] .ag-header-cell-label { font-size: 0.73rem !important; }
    div[data-testid="stDataFrame"] .ag-row { min-height: 28px !important; height: 28px !important; }
    </style>
    """, unsafe_allow_html=True)

    st.header("🚀 Movers")
    st.caption("Ranking de movimientos por período. No es recomendación de compra/venta.")

    if df.empty:
        st.warning("Sin datos disponibles.")
    else:
        MONTH_NAMES = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
        }

        def period_return(ticker: str, start, end) -> float | None:
            hist = hist_map.get(ticker)
            if hist is None or hist.empty:
                return None
            # Normalize index to date-only, stripping timezone
            idx_dates = hist.index.tz_localize(None) if hist.index.tz is not None else hist.index
            idx_dates = idx_dates.normalize()
            start_ts  = pd.Timestamp(start)
            end_ts    = pd.Timestamp(end)
            segment   = hist[(idx_dates >= start_ts) & (idx_dates <= end_ts)]
            if len(segment) < 2:
                return None
            return round((segment["Close"].iloc[-1] / segment["Close"].iloc[0] - 1) * 100, 2)

        def build_movers_df(start, end, pct_col: str) -> pd.DataFrame:
            rows = []
            for ticker, meta in TICKERS.items():
                if selected_groups and meta["group"] not in selected_groups:
                    continue
                pct = period_return(ticker, start, end)
                if pct is None:
                    continue
                price = hist_map[ticker]["Close"].iloc[-1] if ticker in hist_map else None
                rows.append({
                    "Ticker":  ticker,
                    "Empresa": meta["name"],
                    "Precio":  round(price, 2) if price else None,
                    pct_col:   pct,
                })
            return pd.DataFrame(rows)

        # ── Semanal ───────────────────────────────────────────────────────────
        st.subheader("📅 Semana")
        end_week = st.date_input(
            "Ver semana hasta:",
            value=datetime.now().date(),
            max_value=datetime.now().date(),
            key="week_end",
        )
        start_week = end_week - timedelta(days=7)
        st.caption(f"Período: {start_week.strftime('%d/%m/%Y')} → {end_week.strftime('%d/%m/%Y')}")

        df_sem = build_movers_df(start_week, end_week, "1S %")

        if df_sem.empty:
            st.info("Sin datos para el período seleccionado.")
        else:
            col_g, col_p = st.columns(2, gap="small")
            with col_g:
                ganadores = df_sem[df_sem["1S %"] > 0].nlargest(5, "1S %").reset_index(drop=True)
                st.markdown(f"##### 🟢 Top 5 Ganadoras ({len(ganadores)} con subida)")
                st.caption("Click en una fila para ver el gráfico")
                if not ganadores.empty:
                    sel = movers_table_selectable(ganadores, "1S %", key="sem_gan")
                    if sel:
                        show_performance_chart(sel, TICKERS.get(sel, {}).get("name", sel))
                else:
                    st.info("Sin ganadoras esta semana.")
            with col_p:
                perdedores = df_sem[df_sem["1S %"] < 0].nsmallest(5, "1S %").reset_index(drop=True)
                st.markdown(f"##### 🔴 Top 5 Perdedoras ({len(perdedores)} con baja)")
                st.caption("Click en una fila para ver el gráfico")
                if not perdedores.empty:
                    sel = movers_table_selectable(perdedores, "1S %", key="sem_per")
                    if sel:
                        show_performance_chart(sel, TICKERS.get(sel, {}).get("name", sel))
                else:
                    st.info("Sin perdedoras esta semana.")

        st.divider()

        # ── Mensual (mes cerrado) ─────────────────────────────────────────────
        st.subheader("📅 Mes cerrado")

        # Build list of closed months (up to 13 months back, excluding current month)
        today = datetime.now()
        closed_months = []
        for i in range(1, 14):
            d = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
            closed_months.append(d)
        closed_months = sorted(set(
            m.replace(day=1) for m in closed_months if m < today.replace(day=1)
        ), reverse=True)
        month_labels = [f"{MONTH_NAMES[m.month]} {m.year}" for m in closed_months]

        selected_month_label = st.selectbox("Seleccioná el mes:", month_labels, key="month_sel")
        selected_month = closed_months[month_labels.index(selected_month_label)]

        import calendar
        last_day = calendar.monthrange(selected_month.year, selected_month.month)[1]
        start_month = selected_month.date()
        end_month   = selected_month.replace(day=last_day).date()
        st.caption(f"Período: {start_month.strftime('%d/%m/%Y')} → {end_month.strftime('%d/%m/%Y')}")

        df_mes = build_movers_df(start_month, end_month, "1M %")

        if df_mes.empty:
            st.info("Sin datos para el mes seleccionado.")
        else:
            col_gm, col_pm = st.columns(2, gap="small")
            with col_gm:
                gan_mes = df_mes[df_mes["1M %"] > 0].nlargest(20, "1M %").reset_index(drop=True)
                st.markdown(f"##### 🟢 Top 20 Ganadoras ({len(gan_mes)} con subida)")
                st.caption("Click en una fila para ver el gráfico")
                if not gan_mes.empty:
                    sel = movers_table_selectable(gan_mes, "1M %", key="mes_gan")
                    if sel:
                        show_performance_chart(sel, TICKERS.get(sel, {}).get("name", sel))
                else:
                    st.info("Sin ganadoras este mes.")
            with col_pm:
                per_mes = df_mes[df_mes["1M %"] < 0].nsmallest(20, "1M %").reset_index(drop=True)
                st.markdown(f"##### 🔴 Top 20 Perdedoras ({len(per_mes)} con baja)")
                st.caption("Click en una fila para ver el gráfico")
                if not per_mes.empty:
                    sel = movers_table_selectable(per_mes, "1M %", key="mes_per")
                    if sel:
                        show_performance_chart(sel, TICKERS.get(sel, {}).get("name", sel))
                else:
                    st.info("Sin perdedoras este mes.")

        st.divider()

        # ── Emergentes ────────────────────────────────────────────────────────
        st.subheader("🌱 Emergentes — Under the radar")
        st.caption("Compañías de menor perfil con movimientos destacados esta semana y este mes.")

        EMERGENTES = {
            "PLTR":  "Palantir Technologies",
            "SNOW":  "Snowflake Inc.",
            "NET":   "Cloudflare Inc.",
            "DDOG":  "Datadog Inc.",
            "CRWD":  "CrowdStrike Holdings",
            "COIN":  "Coinbase Global Inc.",
            "APP":   "AppLovin Corporation",
            "HIMS":  "Hims & Hers Health",
            "RDDT":  "Reddit Inc.",
            "RKLB":  "Rocket Lab USA",
            "ASTS":  "AST SpaceMobile",
            "ACHR":  "Archer Aviation",
            "IONQ":  "IonQ Inc. (Quantum Computing)",
            "OKLO":  "Oklo Inc. (Nuclear Energy)",
            "SOUN":  "SoundHound AI Inc.",
            "RXRX":  "Recursion Pharmaceuticals",
            "CELH":  "Celsius Holdings",
            "BROS":  "Dutch Bros Inc.",
            "CAVA":  "CAVA Group Inc.",
            "AFRM":  "Affirm Holdings",
            "HOOD":  "Robinhood Markets",
            "RIVN":  "Rivian Automotive",
            "JOBY":  "Joby Aviation",
            "SMCI":  "Super Micro Computer",
            "MSTR":  "MicroStrategy Inc.",
            "ARKK":  "ARK Innovation ETF",
            "ARKG":  "ARK Genomic Revolution ETF",
        }

        @st.cache_data(ttl=3600, show_spinner=False)
        def fetch_emergentes_data():
            end = datetime.now()
            start = end - timedelta(days=400)
            result = {}
            for ticker in EMERGENTES:
                try:
                    hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
                    if not hist.empty:
                        result[ticker] = hist
                except Exception:
                    continue
            return result

        def build_emergentes_df(hist_data: dict, start, end, pct_col: str) -> pd.DataFrame:
            rows = []
            for ticker, name in EMERGENTES.items():
                hist = hist_data.get(ticker)
                if hist is None or hist.empty:
                    continue
                idx = hist.index.tz_localize(None) if hist.index.tz else hist.index
                idx = idx.normalize()
                seg = hist[(idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end))]
                if len(seg) < 2:
                    continue
                pct = round((seg["Close"].iloc[-1] / seg["Close"].iloc[0] - 1) * 100, 2)
                price = round(hist["Close"].iloc[-1], 2)
                rows.append({"Ticker": ticker, "Empresa": name, "Precio": price, pct_col: pct})
            return pd.DataFrame(rows)

        with st.spinner("Cargando emergentes..."):
            em_hist = fetch_emergentes_data()

        # Emergentes semanal
        st.markdown("**📅 Esta semana**")
        df_em_sem = build_emergentes_df(em_hist, start_week, end_week, "1S %")
        if not df_em_sem.empty:
            col_es, col_ep = st.columns(2, gap="small")
            with col_es:
                em_gan_sem = df_em_sem[df_em_sem["1S %"] > 0].nlargest(5, "1S %").reset_index(drop=True)
                st.markdown(f"##### 🟢 Top 5 Ganadoras ({len(em_gan_sem)} con subida)")
                if not em_gan_sem.empty:
                    movers_table(em_gan_sem, "1S %")
                else:
                    st.info("Sin ganadoras.")
            with col_ep:
                em_per_sem = df_em_sem[df_em_sem["1S %"] < 0].nsmallest(5, "1S %").reset_index(drop=True)
                st.markdown(f"##### 🔴 Top 5 Perdedoras ({len(em_per_sem)} con baja)")
                if not em_per_sem.empty:
                    movers_table(em_per_sem, "1S %")
                else:
                    st.info("Sin perdedoras.")

        st.markdown("**📅 Este mes**")
        df_em_mes = build_emergentes_df(em_hist, start_month, end_month, "1M %")
        if not df_em_mes.empty:
            col_ems, col_emp = st.columns(2, gap="small")
            with col_ems:
                em_gan_mes = df_em_mes[df_em_mes["1M %"] > 0].nlargest(10, "1M %").reset_index(drop=True)
                st.markdown(f"##### 🟢 Top 10 Ganadoras ({len(em_gan_mes)} con subida)")
                if not em_gan_mes.empty:
                    movers_table(em_gan_mes, "1M %")
                else:
                    st.info("Sin ganadoras.")
            with col_emp:
                em_per_mes = df_em_mes[df_em_mes["1M %"] < 0].nsmallest(10, "1M %").reset_index(drop=True)
                st.markdown(f"##### 🔴 Top 10 Perdedoras ({len(em_per_mes)} con baja)")
                if not em_per_mes.empty:
                    movers_table(em_per_mes, "1M %")
                else:
                    st.info("Sin perdedoras.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: MERCADO GENERAL
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Mercado General":
    st.header("🌎 Mercado General")

    if df.empty:
        st.warning("Sin datos para los grupos seleccionados.")
    else:
        # Full table grouped
        st.subheader("Tabla completa")
        display_cols = ["Ticker", "Empresa", "Grupo", "Precio", "1S %", "1M %", "YTD %", "1A %"]
        for group in GROUP_ORDER:
            if group not in selected_groups:
                continue
            grp_df = df[df["Grupo"] == group][display_cols].reset_index(drop=True)
            if grp_df.empty:
                continue
            with st.expander(f"**{group}** ({len(grp_df)} instrumentos)", expanded=True):
                st.dataframe(styled_table(grp_df), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: NOTICIAS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Noticias":
    month_map = {
        "January": "enero", "February": "febrero", "March": "marzo",
        "April": "abril", "May": "mayo", "June": "junio",
        "July": "julio", "August": "agosto", "September": "septiembre",
        "October": "octubre", "November": "noviembre", "December": "diciembre",
    }
    now = datetime.now()
    month_es = month_map[now.strftime("%B")]
    today_es = f"{now.day} de {month_es} de {now.year}"

    # Newspaper masthead
    st.markdown(
        f"""
        <div style='border-top:3px solid #f1f5f9; border-bottom:3px solid #f1f5f9;
                    padding:10px 0 8px; margin-bottom:4px; text-align:center'>
            <div style='font-size:2rem; font-weight:900; letter-spacing:0.05em;
                        color:#f1f5f9; font-family:Georgia,serif'>
                📰 DIARIO DE MERCADO
            </div>
            <div style='font-size:0.78rem; color:#94a3b8; margin-top:2px'>
                {today_es.upper()} &nbsp;·&nbsp; EDICIÓN GLOBAL &nbsp;·&nbsp; YAHOO FINANCE
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.spinner("Cargando noticias..."):
        top_news = fetch_top_news(20)

    if not top_news:
        st.info("No hay noticias disponibles en este momento.")
    else:
        # 2-column newspaper grid
        left_col, right_col = st.columns(2, gap="medium")
        columns = [left_col, right_col]

        for i, article in enumerate(top_news):
            raw_title   = article["title"]
            raw_summary = article.get("summary", "")
            link        = article["link"]
            pub         = article.get("publisher", "")
            ts          = article.get("ts")
            ticker      = article.get("ticker", "")
            date_str    = now.strftime("%H:%M") if not ts else datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")

            title   = _translate(raw_title)
            summary = _translate(raw_summary) if raw_summary else ""
            summary_short = (summary[:180] + "…") if len(summary) > 180 else summary

            col = columns[i % 2]
            with col:
                st.markdown(
                    f"""
                    <div style='border-left:3px solid #334155; padding-left:10px; margin-bottom:18px'>
                        <div style='font-size:0.7rem; color:#64748b; margin-bottom:3px'>
                            <span style='color:#4ade80; font-weight:700'>{ticker}</span>
                            &nbsp;·&nbsp; {pub} &nbsp;·&nbsp; {date_str}
                        </div>
                        <div style='font-size:0.92rem; font-weight:700; color:#f1f5f9;
                                    line-height:1.35; margin-bottom:5px'>
                            {title}
                        </div>
                        <div style='font-size:0.78rem; color:#94a3b8; line-height:1.5;
                                    margin-bottom:6px'>
                            {summary_short if summary_short else "<em>Sin resumen disponible.</em>"}
                        </div>
                        <a href='{link}' target='_blank'
                           style='font-size:0.75rem; color:#4ade80; font-weight:600;
                                  text-decoration:none'>
                            Leer más →
                        </a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: DETALLE DE TICKER
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Detalle de Ticker":
    st.header("🔍 Detalle de Ticker")

    available_tickers = df["Ticker"].tolist() if not df.empty else list(TICKERS.keys())
    ticker_options = [f"{t} – {TICKERS[t]['name']}" for t in available_tickers if t in TICKERS]
    selected_label = st.selectbox("Seleccioná un instrumento", ticker_options)
    selected_ticker = selected_label.split(" – ")[0] if selected_label else None

    period = st.radio("Período del gráfico", ["1M", "3M", "6M", "1A"], horizontal=True, index=3)
    period_days = {"1M": 21, "3M": 63, "6M": 126, "1A": 252}

    if selected_ticker and selected_ticker in hist_map:
        hist = hist_map[selected_ticker]
        n    = period_days[period]
        hist_slice = hist.tail(n)

        # Price chart with volume
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=hist_slice.index,
            open=hist_slice["Open"],
            high=hist_slice["High"],
            low=hist_slice["Low"],
            close=hist_slice["Close"],
            name="Precio",
        ))
        fig.update_layout(
            title=f"{selected_ticker} – {TICKERS[selected_ticker]['name']}",
            xaxis_title="Fecha",
            yaxis_title="Precio (USD)",
            xaxis_rangeslider_visible=False,
            height=450,
            margin=dict(t=50, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Fundamentals
        st.subheader("Datos fundamentales")
        try:
            info = yf.Ticker(selected_ticker).info
            fund_data = {
                "Sector":          info.get("sector", "—"),
                "Industria":       info.get("industry", "—"),
                "País":            info.get("country", "—"),
                "Market Cap":      f"${info.get('marketCap', 0):,.0f}" if info.get("marketCap") else "—",
                "P/E Ratio":       info.get("trailingPE", "—"),
                "52W Máximo":      f"${info.get('fiftyTwoWeekHigh', '—')}",
                "52W Mínimo":      f"${info.get('fiftyTwoWeekLow', '—')}",
                "Dividend Yield":  f"{info.get('dividendYield', 0)*100:.2f}%" if info.get("dividendYield") else "—",
                "Beta":            info.get("beta", "—"),
                "Descripción":     info.get("longBusinessSummary", "—"),
            }
            desc = fund_data.pop("Descripción")
            cols = st.columns(3)
            items = list(fund_data.items())
            for i, (k, v) in enumerate(items):
                cols[i % 3].metric(k, v)
            if desc and desc != "—":
                with st.expander("📄 Descripción de la empresa"):
                    st.write(desc[:800] + "..." if len(desc) > 800 else desc)
        except Exception:
            st.info("No se pudieron cargar los datos fundamentales.")

        # News
        st.subheader("📰 Últimas noticias")
        news = fetch_news(selected_ticker)
        if not news:
            st.info("Sin noticias disponibles.")
        else:
            for article in news:
                title    = article["title"]
                link     = article["link"]
                pub      = article.get("publisher", "")
                ts       = article.get("ts")
                date_str = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M") if ts else ""
                st.markdown(f"**[{title}]({link})**  \n_{pub} · {date_str}_")
                st.divider()
