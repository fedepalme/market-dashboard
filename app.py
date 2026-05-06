import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

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
    # New yfinance structure: article may have nested 'content'
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
    ts = article.get("providerPublishTime") or article.get("pubDate") or None
    if isinstance(ts, str):
        try:
            ts = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
        except Exception:
            ts = None
    if not title or not link:
        return None
    return {"title": title, "link": link, "publisher": publisher, "ts": ts}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_news(ticker: str) -> list[dict]:
    try:
        raw = yf.Ticker(ticker).news or []
        parsed = [_parse_article(a) for a in raw]
        return [a for a in parsed if a is not None][:6]
    except Exception:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_top_news(n: int = 10) -> list[dict]:
    """Aggregate news from key tickers, deduplicate, return top-n by date."""
    key_tickers = MY_PORTFOLIO + ["NVDA", "MSFT", "GOOGL", "AMZN", "TSLA",
                                   "JPM", "BRK.B", "NFLX", "DIS", "QQQ", "SPY"]
    seen_titles: set[str] = set()
    all_articles: list[dict] = []
    for ticker in key_tickers:
        try:
            raw = yf.Ticker(ticker).news or []
            for a in raw:
                parsed = _parse_article(a)
                if parsed is None:
                    continue
                key = parsed["title"].lower().strip()[:80]
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                parsed["ticker"] = ticker
                parsed["company"] = TICKERS.get(ticker, {}).get("name", ticker)
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


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📈 Market Dashboard")
    st.caption(f"Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    if st.button("🔄 Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.markdown("**Navegación**")
    page = st.radio(
        "",
        ["Mi Cartera", "Mercado General", "Noticias", "Detalle de Ticker"],
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
# PAGE: MERCADO GENERAL
# ══════════════════════════════════════════════════════════════════════════════

elif page == "Mercado General":
    st.header("🌎 Mercado General")

    if df.empty:
        st.warning("Sin datos para los grupos seleccionados.")
    else:
        # Heatmap (1S %)
        st.subheader("Heatmap semanal (1S %)")
        hm_df = df.dropna(subset=["1S %"]).copy()
        hm_df["Label"] = hm_df["Ticker"] + "<br>" + hm_df["1S %"].map(lambda x: f"{x:+.2f}%")

        fig_hm = px.treemap(
            hm_df,
            path=["Grupo", "Ticker"],
            values=hm_df["Precio"],
            color="1S %",
            color_continuous_scale=["#dc2626", "#f97316", "#e5e7eb", "#4ade80", "#16a34a"],
            color_continuous_midpoint=0,
            custom_data=["Empresa", "1S %", "Precio"],
        )
        fig_hm.update_traces(
            hovertemplate="<b>%{label}</b><br>%{customdata[0]}<br>Precio: $%{customdata[2]:,.2f}<br>1S: %{customdata[1]:+.2f}%<extra></extra>"
        )
        fig_hm.update_layout(height=500, margin=dict(t=30, b=10))
        st.plotly_chart(fig_hm, use_container_width=True)

        st.divider()

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
    st.header("📰 Top 10 Noticias de la Semana")
    st.caption("Fuentes: Yahoo Finance — tickers del universo de seguimiento")

    with st.spinner("Cargando noticias..."):
        top_news = fetch_top_news(10)

    if not top_news:
        st.info("No hay noticias disponibles en este momento.")
    else:
        for i, article in enumerate(top_news, 1):
            title    = article["title"]
            link     = article["link"]
            pub      = article["publisher"]
            ts       = article.get("ts")
            ticker   = article.get("ticker", "")
            company  = article.get("company", "")
            date_str = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M") if ts else ""

            with st.container():
                col_num, col_body = st.columns([0.5, 9.5])
                col_num.markdown(f"### {i}")
                with col_body:
                    st.markdown(f"### [{title}]({link})")
                    meta_parts = []
                    if ticker:
                        meta_parts.append(f"🏷️ **{ticker}** — {company}")
                    if pub:
                        meta_parts.append(f"📡 {pub}")
                    if date_str:
                        meta_parts.append(f"🕐 {date_str}")
                    st.caption("  ·  ".join(meta_parts))
                st.divider()


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
