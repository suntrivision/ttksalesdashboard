import gzip
import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

#  Page config 
st.set_page_config(
    page_title="TTK Sales Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

#  Styling 
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    .metric-card {
        background: #1e2130;
        border-radius: 10px;
        padding: 20px 24px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.4);
        border-left: 4px solid #2196F3;
        margin-bottom: 8px;
    }
    .metric-card.green  { border-left-color: #4CAF50; }
    .metric-card.orange { border-left-color: #FF9800; }
    .metric-card.purple { border-left-color: #9C27B0; }
    .metric-label { font-size: 13px; color: #a0aec0; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { font-size: 28px; font-weight: 700; color: #f0f4f8; margin-top: 4px; }
    .metric-delta { font-size: 12px; color: #718096; margin-top: 2px; }
    .section-title { font-size: 16px; font-weight: 600; color: #e2e8f0; margin-bottom: 4px; padding-left: 2px; }
    div[data-testid="stSidebar"] { background-color: #1a1a2e; }
    div[data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    div[data-testid="stSidebar"] .stSelectbox label,
    div[data-testid="stSidebar"] .stMultiSelect label { color: #aaaaaa !important; font-size: 12px; }
    div[data-testid="stSidebar"] h1, div[data-testid="stSidebar"] h2,
    div[data-testid="stSidebar"] h3 { color: white !important; }
</style>
""", unsafe_allow_html=True)

#  Constants 
MONTH_NAMES = {1:"Jan",2:"Feb",3:"Mar",4:"Apr",5:"May",6:"Jun",
               7:"Jul",8:"Aug",9:"Sep",10:"Oct",11:"Nov",12:"Dec"}
ACCENT_COLORS = ["#FF5722", "#FF9800", "#FFC107"]
PRIMARY_COLOR = "#2196F3"
NEUTRAL_COLOR = "#90CAF9"
REGION_PALETTE = px.colors.qualitative.Set2
CATEGORY_PALETTE = px.colors.qualitative.Pastel

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATA_PATH = os.path.join(os.path.dirname(__file__), "combined_data.csv")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "sales-data")
SUPABASE_DATA_FILE = os.getenv("SUPABASE_DATA_FILE", "combined_data.csv.gz")

SALES_COLUMNS = [
    "date", "year", "month", "customer_id", "customer_name",
    "quantity", "net_amount", "distributor", "region", "area",
    "brand_group", "brand", "sub_brand", "category", "sub_category",
    "l_1_channel", "l_2_channel", "chain",
]


def _read_sales_csv(source: io.BytesIO | str) -> pd.DataFrame:
    return pd.read_csv(
        source,
        usecols=SALES_COLUMNS,
        parse_dates=["date"],
        low_memory=False,
    )


def _load_from_supabase() -> pd.DataFrame | None:
    if not (SUPABASE_URL and SUPABASE_KEY):
        return None

    from supabase import create_client

    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    raw = client.storage.from_(SUPABASE_BUCKET).download(SUPABASE_DATA_FILE)
    if SUPABASE_DATA_FILE.endswith(".gz"):
        raw = gzip.decompress(raw)
    return _read_sales_csv(io.BytesIO(raw))


def _load_from_local() -> pd.DataFrame:
    gz_path = DATA_PATH + ".gz"
    if os.path.isfile(gz_path):
        with gzip.open(gz_path, "rb") as gz:
            return _read_sales_csv(gz)
    return _read_sales_csv(DATA_PATH)


#  Data loading ─
@st.cache_data(show_spinner="Loading sales data…")
def load_data() -> pd.DataFrame:
    df = _load_from_supabase()
    if df is None:
        df = _load_from_local()
    df["net_amount"] = pd.to_numeric(df["net_amount"], errors="coerce").fillna(0)
    df["quantity"]   = pd.to_numeric(df["quantity"],   errors="coerce").fillna(0)
    df.dropna(subset=["date"], inplace=True)
    # Derive year/month from parsed date (CSV year column has Excel serial-number artifacts)
    df["year"]  = df["date"].dt.year.astype("Int64")
    df["month"] = df["date"].dt.month.astype("Int64")
    # Drop rows with clearly corrupted dates (Teanseng serial-number artifacts 2027+)
    df = df[df["year"].between(2020, 2026)]
    return df


df_all = load_data()

#  Derive defaults from data 
latest_date   = df_all["date"].max()
default_year  = int(latest_date.year)
default_month = int(latest_date.month)
years_avail   = sorted(df_all["year"].dropna().unique().tolist(), reverse=True)

#  Sidebar 
with st.sidebar:
    st.title("📊 TTK Dashboard")
    st.caption("Sell-Out Data Analytics")
    st.markdown("---")

    st.subheader("📅 Period")
    sel_year = st.selectbox("Year", years_avail, index=0)
    sel_month = st.selectbox(
        "Month (for MTD)",
        list(MONTH_NAMES.keys()),
        index=default_month - 1,
        format_func=lambda m: MONTH_NAMES[m],
    )

    st.markdown("---")
    st.subheader("🔍 Filters")

    all_regions = sorted(df_all["region"].dropna().unique().tolist())
    sel_regions = st.multiselect("Region", all_regions, default=[], placeholder="All regions")

    all_brands = sorted(df_all["brand_group"].dropna().unique().tolist())
    sel_brands = st.multiselect("Brand Group", all_brands, default=[], placeholder="All brand groups")

    all_channels = sorted(df_all["l_1_channel"].dropna().unique().tolist())
    sel_channels = st.multiselect("Channel (L1)", all_channels, default=[], placeholder="All channels")

    all_dists = sorted(df_all["distributor"].dropna().unique().tolist())
    sel_dists = st.multiselect("Distributor", all_dists, default=[], placeholder="All distributors")

    st.markdown("---")
    st.caption(f"Data last updated: {latest_date.strftime('%d %b %Y')}")
    st.caption(f"Total rows: {len(df_all):,}")

#  Apply global filters ─
df = df_all.copy()
if sel_regions:  df = df[df["region"].isin(sel_regions)]
if sel_brands:   df = df[df["brand_group"].isin(sel_brands)]
if sel_channels: df = df[df["l_1_channel"].isin(sel_channels)]
if sel_dists:    df = df[df["distributor"].isin(sel_dists)]

#  Chart theme helper ─
def apply_theme(fig, title: str = "", height: int = 380) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#e2e8f0", family="Arial"), x=0),
        height=height,
        plot_bgcolor="#1e2130",
        paper_bgcolor="#1e2130",
        font=dict(family="Arial", size=12, color="#cbd5e0"),
        margin=dict(l=10, r=20, t=45, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0, font=dict(color="#cbd5e0")),
        xaxis=dict(gridcolor="#2d3748", linecolor="#4a5568",
                   tickfont=dict(size=11, color="#a0aec0"),
                   title=dict(font=dict(color="#a0aec0"))),
        yaxis=dict(gridcolor="#2d3748", linecolor="#4a5568",
                   tickfont=dict(size=11, color="#a0aec0"),
                   title=dict(font=dict(color="#a0aec0"))),
    )
    return fig

def fmt_currency(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"RM {val/1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"RM {val/1_000:.1f}K"
    return f"RM {val:,.0f}"

#  Header ─
st.markdown("## TTK Sell-Out Sales Dashboard")
active_filter_tags = (
    ([f"Region: {', '.join(sel_regions)}"] if sel_regions else []) +
    ([f"Brand: {', '.join(sel_brands)}"] if sel_brands else []) +
    ([f"Channel: {', '.join(sel_channels)}"] if sel_channels else []) +
    ([f"Distributor: {', '.join(sel_dists)}"] if sel_dists else [])
)
if active_filter_tags:
    st.caption("Filters active: " + " | ".join(active_filter_tags))
else:
    st.caption("Showing all data — use sidebar to filter")

st.markdown("---")

#  KPI Cards 
total_sales    = df["net_amount"].sum()
total_qty      = df["quantity"].sum()
active_custs   = df["customer_id"].nunique()
ytd_df         = df[df["year"] == sel_year]
ytd_sales      = ytd_df["net_amount"].sum()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""<div class="metric-card">
        <div class="metric-label">Total Net Sales</div>
        <div class="metric-value">{fmt_currency(total_sales)}</div>
        <div class="metric-delta">All time (filtered)</div>
    </div>""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""<div class="metric-card green">
        <div class="metric-label">YTD Sales ({sel_year})</div>
        <div class="metric-value">{fmt_currency(ytd_sales)}</div>
        <div class="metric-delta">Jan – {MONTH_NAMES[sel_month]}</div>
    </div>""", unsafe_allow_html=True)

with col3:
    st.markdown(f"""<div class="metric-card orange">
        <div class="metric-label">Total Qty Sold</div>
        <div class="metric-value">{total_qty:,.0f}</div>
        <div class="metric-delta">Units (filtered)</div>
    </div>""", unsafe_allow_html=True)

with col4:
    st.markdown(f"""<div class="metric-card purple">
        <div class="metric-label">Active Customers</div>
        <div class="metric-value">{active_custs:,}</div>
        <div class="metric-delta">Unique customer IDs</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# Row 1: MTD Sales | YTD Cumulative
# 
col_mtd, col_ytd = st.columns(2)

#  MTD Sales Bar Chart 
with col_mtd:
    st.markdown('<div class="section-title">MTD Sales by Day</div>', unsafe_allow_html=True)
    mtd_df = df[(df["year"] == sel_year) & (df["month"] == sel_month)].copy()
    mtd_df["day"] = mtd_df["date"].dt.day
    mtd_daily = mtd_df.groupby("day", as_index=False)["net_amount"].sum()

    if mtd_daily.empty:
        st.info(f"No data for {MONTH_NAMES[sel_month]} {sel_year}.")
    else:
        mtd_cumulative = mtd_daily["net_amount"].sum()
        fig_mtd = px.bar(
            mtd_daily, x="day", y="net_amount",
            color_discrete_sequence=[PRIMARY_COLOR],
        )
        fig_mtd.update_traces(
            marker_line_width=0,
            hovertemplate="Day %{x}<br>Sales: RM %{y:,.0f}<extra></extra>",
        )
        fig_mtd.add_annotation(
            x=mtd_daily["day"].max(), y=mtd_daily["net_amount"].max(),
            text=f"MTD Total<br><b>{fmt_currency(mtd_cumulative)}</b>",
            showarrow=True, arrowhead=2, arrowcolor="#a0aec0",
            bgcolor="#2d3748", bordercolor="#4a5568", borderwidth=1,
            font=dict(size=11, color="#f0f4f8"), ax=40, ay=-40,
        )
        fig_mtd.update_xaxes(title="Day of Month", dtick=1)
        fig_mtd.update_yaxes(title="Net Sales (RM)", tickformat=",.0f")
        apply_theme(fig_mtd, height=370)
        st.plotly_chart(fig_mtd, use_container_width=True)

#  YTD Cumulative Line Chart 
with col_ytd:
    st.markdown('<div class="section-title">YTD Cumulative Sales</div>', unsafe_allow_html=True)
    ytd_monthly = ytd_df.groupby("month", as_index=False)["net_amount"].sum().sort_values("month")
    ytd_monthly["cumulative"] = ytd_monthly["net_amount"].cumsum()
    ytd_monthly["month_name"] = ytd_monthly["month"].map(MONTH_NAMES)

    if ytd_monthly.empty:
        st.info(f"No data for {sel_year}.")
    else:
        ytd_total = ytd_monthly["cumulative"].iloc[-1]
        fig_ytd = go.Figure()
        fig_ytd.add_trace(go.Scatter(
            x=ytd_monthly["month_name"], y=ytd_monthly["cumulative"],
            mode="lines+markers",
            line=dict(color="#4CAF50", width=3),
            marker=dict(size=7, color="#4CAF50"),
            fill="tozeroy", fillcolor="rgba(76,175,80,0.08)",
            hovertemplate="%{x}<br>Cumulative: RM %{y:,.0f}<extra></extra>",
            name="Cumulative Sales",
        ))
        last_month = ytd_monthly["month_name"].iloc[-1]
        last_val   = ytd_monthly["cumulative"].iloc[-1]
        fig_ytd.add_annotation(
            x=last_month, y=last_val,
            text=f"<b>{fmt_currency(ytd_total)}</b>",
            showarrow=True, arrowhead=2, arrowcolor="#a0aec0",
            bgcolor="#2d3748", bordercolor="#4a5568", borderwidth=1,
            font=dict(size=11, color="#68d391"), ax=40, ay=-30,
        )
        fig_ytd.update_xaxes(title="Month")
        fig_ytd.update_yaxes(title="Cumulative Sales (RM)", tickformat=",.0f", rangemode="tozero")
        apply_theme(fig_ytd, height=370)
        st.plotly_chart(fig_ytd, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# Row 1b: MTD Sales by Brand | MTD Sales by Chain

col_mtd_brand, col_mtd_chain = st.columns(2)

with col_mtd_brand:
    st.markdown('<div class="section-title">MTD Sales by Brand</div>', unsafe_allow_html=True)
    mtd_brand_df = (
        mtd_df.groupby("brand", as_index=False)["net_amount"].sum()
        .sort_values("net_amount", ascending=True).tail(15)
    )
    if mtd_brand_df.empty:
        st.info(f"No brand data for {MONTH_NAMES[sel_month]} {sel_year}.")
    else:
        colors_mb = [ACCENT_COLORS[0] if i == len(mtd_brand_df)-1 else NEUTRAL_COLOR
                     for i in range(len(mtd_brand_df))]
        fig_mtd_brand = go.Figure(go.Bar(
            x=mtd_brand_df["net_amount"], y=mtd_brand_df["brand"],
            orientation="h", marker_color=colors_mb, marker_line_width=0,
            text=[fmt_currency(v) for v in mtd_brand_df["net_amount"]],
            textposition="outside",
            hovertemplate="%{y}<br>MTD Sales: RM %{x:,.0f}<extra></extra>",
        ))
        fig_mtd_brand.update_xaxes(title="Net Sales (RM)", tickformat=",.0f")
        fig_mtd_brand.update_yaxes(title="", tickfont=dict(size=11))
        apply_theme(fig_mtd_brand, height=430)
        fig_mtd_brand.update_layout(margin=dict(r=90))
        st.plotly_chart(fig_mtd_brand, use_container_width=True)

with col_mtd_chain:
    st.markdown('<div class="section-title">MTD Sales by Chain</div>', unsafe_allow_html=True)
    mtd_chain_df = (
        mtd_df.groupby("chain", as_index=False)["net_amount"].sum()
        .sort_values("net_amount", ascending=True).tail(15)
    )
    if mtd_chain_df.empty:
        st.info(f"No chain data for {MONTH_NAMES[sel_month]} {sel_year}.")
    else:
        colors_mc = [ACCENT_COLORS[0] if i == len(mtd_chain_df)-1 else "#7986CB"
                     for i in range(len(mtd_chain_df))]
        fig_mtd_chain = go.Figure(go.Bar(
            x=mtd_chain_df["net_amount"], y=mtd_chain_df["chain"],
            orientation="h", marker_color=colors_mc, marker_line_width=0,
            text=[fmt_currency(v) for v in mtd_chain_df["net_amount"]],
            textposition="outside",
            hovertemplate="%{y}<br>MTD Sales: RM %{x:,.0f}<extra></extra>",
        ))
        fig_mtd_chain.update_xaxes(title="Net Sales (RM)", tickformat=",.0f")
        fig_mtd_chain.update_yaxes(title="", tickfont=dict(size=11))
        apply_theme(fig_mtd_chain, height=430)
        fig_mtd_chain.update_layout(margin=dict(r=90))
        st.plotly_chart(fig_mtd_chain, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# Row 2: 12-Month Sales Trend (full width)

st.markdown('<div class="section-title">12-Month Sales Trend</div>', unsafe_allow_html=True)

df["year_month"] = df["date"].dt.to_period("M")
period_counts = df["year_month"].value_counts()
if len(period_counts) > 0:
    all_periods = sorted(df["year_month"].dropna().unique())
    last_12 = all_periods[-12:] if len(all_periods) >= 12 else all_periods
    trend_df = (
        df[df["year_month"].isin(last_12)]
        .groupby("year_month", as_index=False)["net_amount"].sum()
        .sort_values("year_month")
    )
    trend_df["label"] = trend_df["year_month"].astype(str)
    trend_df["ma3"]   = trend_df["net_amount"].rolling(3, min_periods=1).mean()

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Bar(
        x=trend_df["label"], y=trend_df["net_amount"],
        name="Monthly Sales",
        marker_color=PRIMARY_COLOR, marker_line_width=0,
        hovertemplate="%{x}<br>Sales: RM %{y:,.0f}<extra></extra>",
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend_df["label"], y=trend_df["ma3"],
        name="3-Month Avg",
        mode="lines+markers",
        line=dict(color="#FF5722", width=2.5, dash="dot"),
        marker=dict(size=6, color="#FF5722", symbol="circle"),
        hovertemplate="%{x}<br>3-Mo Avg: RM %{y:,.0f}<extra></extra>",
    ))
    fig_trend.update_xaxes(title="Month", tickangle=-30)
    fig_trend.update_yaxes(title="Net Sales (RM)", tickformat=",.0f")
    apply_theme(fig_trend, height=360)
    fig_trend.update_layout(legend=dict(orientation="h", y=1.08, x=0))
    st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# Row 2b: YTD Sales by Brand | YTD Sales by Chain

col_ytd_brand, col_ytd_chain = st.columns(2)

with col_ytd_brand:
    st.markdown('<div class="section-title">YTD Sales by Brand</div>', unsafe_allow_html=True)
    ytd_brand_df = (
        ytd_df.groupby("brand", as_index=False)["net_amount"].sum()
        .sort_values("net_amount", ascending=True).tail(20)
    )
    if ytd_brand_df.empty:
        st.info(f"No brand data for {sel_year}.")
    else:
        colors_yb = [ACCENT_COLORS[0] if i == len(ytd_brand_df)-1 else NEUTRAL_COLOR
                     for i in range(len(ytd_brand_df))]
        fig_ytd_brand = go.Figure(go.Bar(
            x=ytd_brand_df["net_amount"], y=ytd_brand_df["brand"],
            orientation="h", marker_color=colors_yb, marker_line_width=0,
            text=[fmt_currency(v) for v in ytd_brand_df["net_amount"]],
            textposition="outside",
            hovertemplate="%{y}<br>YTD Sales: RM %{x:,.0f}<extra></extra>",
        ))
        fig_ytd_brand.update_xaxes(title="Net Sales (RM)", tickformat=",.0f")
        fig_ytd_brand.update_yaxes(title="", tickfont=dict(size=11))
        apply_theme(fig_ytd_brand, height=500)
        fig_ytd_brand.update_layout(margin=dict(r=90))
        st.plotly_chart(fig_ytd_brand, use_container_width=True)

with col_ytd_chain:
    st.markdown('<div class="section-title">YTD Sales by Chain</div>', unsafe_allow_html=True)
    ytd_chain_df = (
        ytd_df.groupby("chain", as_index=False)["net_amount"].sum()
        .sort_values("net_amount", ascending=True).tail(20)
    )
    if ytd_chain_df.empty:
        st.info(f"No chain data for {sel_year}.")
    else:
        colors_yc = [ACCENT_COLORS[0] if i == len(ytd_chain_df)-1 else "#7986CB"
                     for i in range(len(ytd_chain_df))]
        fig_ytd_chain = go.Figure(go.Bar(
            x=ytd_chain_df["net_amount"], y=ytd_chain_df["chain"],
            orientation="h", marker_color=colors_yc, marker_line_width=0,
            text=[fmt_currency(v) for v in ytd_chain_df["net_amount"]],
            textposition="outside",
            hovertemplate="%{y}<br>YTD Sales: RM %{x:,.0f}<extra></extra>",
        ))
        fig_ytd_chain.update_xaxes(title="Net Sales (RM)", tickformat=",.0f")
        fig_ytd_chain.update_yaxes(title="", tickfont=dict(size=11))
        apply_theme(fig_ytd_chain, height=500)
        fig_ytd_chain.update_layout(margin=dict(r=90))
        st.plotly_chart(fig_ytd_chain, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# Row 3: Most Selling Product | Most Selling Region

col_prod, col_region = st.columns(2)

#  Most Selling Product (Horizontal Bar) ─
with col_prod:
    st.markdown('<div class="section-title">Most Selling Product (by Brand)</div>', unsafe_allow_html=True)
    prod_df = (
        df.groupby("brand", as_index=False)["net_amount"].sum()
        .sort_values("net_amount", ascending=True)
        .tail(20)
    )
    if not prod_df.empty:
        colors = [ACCENT_COLORS[0] if i == len(prod_df) - 1 else NEUTRAL_COLOR
                  for i in range(len(prod_df))]
        fig_prod = go.Figure(go.Bar(
            x=prod_df["net_amount"], y=prod_df["brand"],
            orientation="h",
            marker_color=colors, marker_line_width=0,
            text=[fmt_currency(v) for v in prod_df["net_amount"]],
            textposition="outside",
            hovertemplate="%{y}<br>Sales: RM %{x:,.0f}<extra></extra>",
        ))
        fig_prod.update_xaxes(title="Net Sales (RM)", tickformat=",.0f")
        fig_prod.update_yaxes(title="", tickfont=dict(size=11))
        apply_theme(fig_prod, height=480)
        fig_prod.update_layout(margin=dict(r=80))
        st.plotly_chart(fig_prod, use_container_width=True)

#  Most Selling Region (Bar Chart) ─
with col_region:
    st.markdown('<div class="section-title">Most Selling Region</div>', unsafe_allow_html=True)
    reg_df = (
        df.groupby("region", as_index=False)["net_amount"].sum()
        .sort_values("net_amount", ascending=False)
    )
    if not reg_df.empty:
        max_val = reg_df["net_amount"].max()
        colors  = [ACCENT_COLORS[0] if v == max_val else c
                   for v, c in zip(reg_df["net_amount"],
                                   REGION_PALETTE[:len(reg_df)])]
        fig_reg = go.Figure(go.Bar(
            x=reg_df["region"], y=reg_df["net_amount"],
            marker_color=colors, marker_line_width=0,
            text=[fmt_currency(v) for v in reg_df["net_amount"]],
            textposition="outside",
            hovertemplate="%{x}<br>Sales: RM %{y:,.0f}<extra></extra>",
        ))
        fig_reg.update_xaxes(title="", tickangle=-20, tickfont=dict(size=11))
        fig_reg.update_yaxes(title="Net Sales (RM)", tickformat=",.0f")
        apply_theme(fig_reg, height=480)
        fig_reg.update_layout(margin=dict(t=55))
        st.plotly_chart(fig_reg, use_container_width=True)


# Row 4: Region Comparison Grouped Bar (full width)

st.markdown('<div class="section-title">Region Comparison (Last 6 Months)</div>', unsafe_allow_html=True)

if len(all_periods) > 0:
    last_6 = all_periods[-6:] if len(all_periods) >= 6 else all_periods
    comp_df = (
        df[df["year_month"].isin(last_6)]
        .groupby(["year_month", "region"], as_index=False)["net_amount"].sum()
    )
    comp_df["period"] = comp_df["year_month"].astype(str)
    comp_df = comp_df.sort_values("year_month")

    if not comp_df.empty:
        fig_comp = px.bar(
            comp_df, x="period", y="net_amount", color="region",
            barmode="group",
            color_discrete_sequence=REGION_PALETTE,
        )
        fig_comp.update_traces(
            marker_line_width=0,
            hovertemplate="%{x} | %{data.name}<br>Sales: RM %{y:,.0f}<extra></extra>",
        )
        fig_comp.update_xaxes(title="Month", tickangle=-20)
        fig_comp.update_yaxes(title="Net Sales (RM)", tickformat=",.0f")
        apply_theme(fig_comp, height=370)
        fig_comp.update_layout(legend=dict(orientation="h", y=1.1, x=0))
        st.plotly_chart(fig_comp, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# Row 4b: Distributor Sell Out Performance (full width)

st.markdown('<div class="section-title">Distributor Sell Out Performance</div>', unsafe_allow_html=True)

dist_df = (
    ytd_df.groupby(["distributor", "month"], as_index=False)["net_amount"].sum()
)
dist_df["month_name"] = dist_df["month"].map(MONTH_NAMES)
dist_df = dist_df.sort_values("month")

if not dist_df.empty:
    month_order = [MONTH_NAMES[m] for m in range(1, 13) if m in dist_df["month"].values]
    fig_dist = px.bar(
        dist_df, x="month_name", y="net_amount", color="distributor",
        barmode="group",
        color_discrete_sequence=px.colors.qualitative.Bold,
        category_orders={"month_name": month_order},
    )
    fig_dist.update_traces(
        marker_line_width=0,
        hovertemplate="%{x} — %{data.name}<br>Sales: RM %{y:,.0f}<extra></extra>",
    )
    fig_dist.update_xaxes(title="Month")
    fig_dist.update_yaxes(title="Net Sales (RM)", tickformat=",.0f")
    apply_theme(fig_dist, height=400)
    fig_dist.update_layout(legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)))
    st.plotly_chart(fig_dist, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)


# Row 5: Top 10 Customers | Sales by Category

col_cust, col_cat = st.columns(2)

#  Top 10 Customers (Horizontal Bar) 
with col_cust:
    st.markdown('<div class="section-title">Top 10 Customers</div>', unsafe_allow_html=True)
    cust_df = (
        df.groupby("customer_name", as_index=False)["net_amount"].sum()
        .sort_values("net_amount", ascending=True)
        .tail(10)
    )
    if not cust_df.empty:
        n = len(cust_df)
        colors = []
        for i in range(n):
            rank = n - 1 - i  # 0 = top, 1 = 2nd, 2 = 3rd
            if rank < len(ACCENT_COLORS):
                colors.append(ACCENT_COLORS[rank])
            else:
                colors.append(NEUTRAL_COLOR)

        fig_cust = go.Figure(go.Bar(
            x=cust_df["net_amount"], y=cust_df["customer_name"],
            orientation="h",
            marker_color=colors, marker_line_width=0,
            text=[fmt_currency(v) for v in cust_df["net_amount"]],
            textposition="outside",
            hovertemplate="%{y}<br>Sales: RM %{x:,.0f}<extra></extra>",
        ))
        fig_cust.update_xaxes(title="Net Sales (RM)", tickformat=",.0f")
        fig_cust.update_yaxes(title="", tickfont=dict(size=10))
        apply_theme(fig_cust, height=420)
        fig_cust.update_layout(margin=dict(r=90, l=200))
        st.plotly_chart(fig_cust, use_container_width=True)

#  Sales by Category (Pie Chart) 
with col_cat:
    st.markdown('<div class="section-title">Sales by Category</div>', unsafe_allow_html=True)
    cat_df = (
        df.groupby("category", as_index=False)["net_amount"].sum()
        .sort_values("net_amount", ascending=False)
    )
    cat_df = cat_df[cat_df["net_amount"] > 0]

    if not cat_df.empty:
        fig_pie = px.pie(
            cat_df, values="net_amount", names="category",
            color_discrete_sequence=CATEGORY_PALETTE,
            hole=0.35,
        )
        fig_pie.update_traces(
            textinfo="label+percent",
            textfont=dict(size=11, color="white"),
            hovertemplate="%{label}<br>Sales: RM %{value:,.0f}<br>%{percent}<extra></extra>",
            pull=[0.04 if i == 0 else 0 for i in range(len(cat_df))],
        )
        apply_theme(fig_pie, height=420)
        fig_pie.update_layout(
            showlegend=True,
            legend=dict(orientation="v", x=1.02, y=0.5),
            margin=dict(l=10, r=120, t=45, b=10),
        )
        st.plotly_chart(fig_pie, use_container_width=True)


# Data Explorer

st.markdown("---")
st.markdown('<div class="section-title">🔎 Data Explorer</div>', unsafe_allow_html=True)
st.caption("All tables reflect the sidebar filters. Click any column header to sort.")

tab_month, tab_brand, tab_chain, tab_region, tab_dist, tab_raw = st.tabs([
    "By Month", "By Brand", "By Chain", "By Region", "By Distributor", "Raw Data"
])

def _fmt_tbl(df_in: pd.DataFrame) -> pd.DataFrame:
    """Round net_amount and quantity for cleaner table display."""
    out = df_in.copy()
    if "net_amount" in out.columns:
        out["net_amount"] = out["net_amount"].round(0).astype(int)
    if "quantity" in out.columns:
        out["quantity"] = out["quantity"].round(0).astype(int)
    return out

_col_cfg_sales = st.column_config.NumberColumn("Net Sales (RM)", format="RM %d")
_col_cfg_qty   = st.column_config.NumberColumn("Qty", format="%d")
_col_cfg_pct   = st.column_config.NumberColumn("% of Total", format="%.1f %%")

def _add_pct(df_in: pd.DataFrame, col: str = "net_amount") -> pd.DataFrame:
    total = df_in[col].sum()
    df_in = df_in.copy()
    df_in["pct_of_total"] = (df_in[col] / total * 100).round(1) if total else 0.0
    return df_in

with tab_month:
    tbl = (
        df.groupby(["year", "month"], as_index=False)
        .agg(net_amount=("net_amount", "sum"), quantity=("quantity", "sum"),
             transactions=("net_amount", "count"), customers=("customer_id", "nunique"))
        .sort_values(["year", "month"])
    )
    tbl["month_name"] = tbl["month"].map(MONTH_NAMES)
    tbl = _add_pct(_fmt_tbl(tbl[["year","month_name","net_amount","quantity","transactions","customers"]]))
    st.dataframe(tbl, use_container_width=True, hide_index=True,
        column_config={
            "year":         st.column_config.NumberColumn("Year", format="%d"),
            "month_name":   st.column_config.TextColumn("Month"),
            "net_amount":   _col_cfg_sales,
            "quantity":     _col_cfg_qty,
            "transactions": st.column_config.NumberColumn("Transactions", format="%d"),
            "customers":    st.column_config.NumberColumn("Unique Customers", format="%d"),
            "pct_of_total": _col_cfg_pct,
        })

with tab_brand:
    tbl = (
        df.groupby(["brand_group", "brand"], as_index=False)
        .agg(net_amount=("net_amount","sum"), quantity=("quantity","sum"),
             customers=("customer_id","nunique"))
        .sort_values("net_amount", ascending=False)
    )
    tbl = _add_pct(_fmt_tbl(tbl))
    st.dataframe(tbl, use_container_width=True, hide_index=True,
        column_config={
            "brand_group":  st.column_config.TextColumn("Brand Group"),
            "brand":        st.column_config.TextColumn("Brand"),
            "net_amount":   _col_cfg_sales,
            "quantity":     _col_cfg_qty,
            "customers":    st.column_config.NumberColumn("Unique Customers", format="%d"),
            "pct_of_total": _col_cfg_pct,
        })

with tab_chain:
    tbl = (
        df.groupby(["l_1_channel", "l_2_channel", "chain"], as_index=False)
        .agg(net_amount=("net_amount","sum"), quantity=("quantity","sum"),
             customers=("customer_id","nunique"))
        .sort_values("net_amount", ascending=False)
    )
    tbl = _add_pct(_fmt_tbl(tbl))
    st.dataframe(tbl, use_container_width=True, hide_index=True,
        column_config={
            "l_1_channel":  st.column_config.TextColumn("Channel L1"),
            "l_2_channel":  st.column_config.TextColumn("Channel L2"),
            "chain":        st.column_config.TextColumn("Chain"),
            "net_amount":   _col_cfg_sales,
            "quantity":     _col_cfg_qty,
            "customers":    st.column_config.NumberColumn("Unique Customers", format="%d"),
            "pct_of_total": _col_cfg_pct,
        })

with tab_region:
    tbl = (
        df.groupby(["region", "area"], as_index=False)
        .agg(net_amount=("net_amount","sum"), quantity=("quantity","sum"),
             customers=("customer_id","nunique"))
        .sort_values("net_amount", ascending=False)
    )
    tbl = _add_pct(_fmt_tbl(tbl))
    st.dataframe(tbl, use_container_width=True, hide_index=True,
        column_config={
            "region":       st.column_config.TextColumn("Region"),
            "area":         st.column_config.TextColumn("Area"),
            "net_amount":   _col_cfg_sales,
            "quantity":     _col_cfg_qty,
            "customers":    st.column_config.NumberColumn("Unique Customers", format="%d"),
            "pct_of_total": _col_cfg_pct,
        })

with tab_dist:
    tbl = (
        df.groupby(["distributor", "month"], as_index=False)
        .agg(net_amount=("net_amount","sum"), quantity=("quantity","sum"))
        .sort_values(["distributor","month"])
    )
    tbl["month_name"] = tbl["month"].map(MONTH_NAMES)
    # Pivot: distributors as rows, months as columns
    pivot = tbl.pivot_table(index="distributor", columns="month_name",
                            values="net_amount", aggfunc="sum", fill_value=0)
    month_cols = [MONTH_NAMES[m] for m in range(1,13) if MONTH_NAMES[m] in pivot.columns]
    pivot = pivot[month_cols]
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("Total", ascending=False).reset_index()
    for c in pivot.columns[1:]:
        pivot[c] = pivot[c].round(0).astype(int)
    st.dataframe(pivot, use_container_width=True, hide_index=True,
        column_config={c: st.column_config.NumberColumn(c, format="RM %d")
                       for c in pivot.columns if c != "distributor"})

with tab_raw:
    RAW_LIMIT = 10_000
    raw_cols = ["date","distributor","region","area","customer_name","chain",
                "brand_group","brand","category","sub_category","quantity","net_amount"]
    raw_show = df[raw_cols].sort_values("date", ascending=False).head(RAW_LIMIT)
    raw_show = raw_show.copy()
    raw_show["net_amount"] = raw_show["net_amount"].round(2)
    raw_show["quantity"]   = raw_show["quantity"].round(0).astype(int)
    st.caption(f"Showing {len(raw_show):,} most recent rows of {len(df):,} total (filtered). Download via the ⬇ icon.")
    st.dataframe(raw_show, use_container_width=True, hide_index=True,
        column_config={
            "date":        st.column_config.DateColumn("Date", format="DD MMM YYYY"),
            "distributor": st.column_config.TextColumn("Distributor"),
            "region":      st.column_config.TextColumn("Region"),
            "area":        st.column_config.TextColumn("Area"),
            "customer_name": st.column_config.TextColumn("Customer"),
            "chain":       st.column_config.TextColumn("Chain"),
            "brand_group": st.column_config.TextColumn("Brand Group"),
            "brand":       st.column_config.TextColumn("Brand"),
            "category":    st.column_config.TextColumn("Category"),
            "sub_category":st.column_config.TextColumn("Sub-Category"),
            "quantity":    _col_cfg_qty,
            "net_amount":  st.column_config.NumberColumn("Net Sales (RM)", format="RM %.2f"),
        })

#  Footer ─
st.markdown("---")
st.caption(f"TTK Sales Dashboard  •  Data from `output/combined_data.csv`  •  {len(df):,} rows shown")
