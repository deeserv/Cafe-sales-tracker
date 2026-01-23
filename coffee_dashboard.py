import streamlit as st
import pandas as pd
import numpy as np
import os

# -----------------------------------------------------------------------------
# 1. 核心配置与 CSS 注入 (UI 灵魂)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="顿角咖啡智能数据看板",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入自定义 CSS 以实现“商务年轻”风格
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    /* 全局设置 */
    .stApp {
        background-color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }
    
    /* 图片圆角优化 */
    img {
        border-radius: 12px;
        transition: transform 0.3s ease;
    }
    
    /* 侧边栏优化 */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
        box-shadow: 2px 0 10px rgba(0,0,0,0.03);
    }
    
    /* 标题样式 */
    h1 {
        color: #0F172A;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 0px;
        padding-bottom: 0px;
    }
    h3 {
        color: #334155;
        font-weight: 600;
    }
    
    /* 卡片容器样式 (悬浮效果) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF;
        border-radius: 16px;
        border: 1px solid #F1F5F9;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        padding: 24px;
        transition: all 0.3s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 20px -5px rgba(0, 0, 0, 0.1);
        border-color: #E2E8F0;
    }

    /* KPI 指标数字增强 */
    [data-testid="stMetricValue"] {
        font-size: 36px !important;
        background: -webkit-linear-gradient(120deg, #2563EB, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
    }
    
    /* 调整 Tab 样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #FFFFFF;
        padding: 8px;
        border-radius: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        border-radius: 8px;
        border: none;
        color: #64748B;
        font-weight: 600;
        background-color: #F8FAFC;
    }
    .stTabs [aria-selected="true"] {
        background-color: #EFF6FF;
        color: #2563EB;
    }
    
    /* 多选框高亮 */
    div[data-testid="stMultiSelect"] label {
        font-weight: bold;
        color: #2563EB;
    }
</style>
""", unsafe_allow_html=True)

# 尝试导入 Plotly
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# 配色方案 (Vibrant Modern)
COLOR_PALETTE = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

# -----------------------------------------------------------------------------
# 2. 数据处理与清洗函数
# -----------------------------------------------------------------------------
def load_data_file(file):
    if file is None: return None
    filename = file.name.lower()
    
    if filename.endswith('.xlsx') or filename.endswith('.xls'):
        try:
            return pd.read_excel(file, engine='openpyxl')
        except ImportError:
            st.error("❌ 缺少 openpyxl 库。请在终端运行: pip3 install openpyxl")
            return None
        except Exception:
            pass

    encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb18030', 'mac_roman', 'big5']
    for enc in encodings:
        try:
            file.seek(0)
            df = pd.read_csv(file, encoding=enc)
            return df
        except:
            continue
    return None

def process_sales_files(uploaded_files):
    if not uploaded_files: return None
    all_dfs = []
    for file in uploaded_files:
        df = load_data_file(file)
        if df is not None: all_dfs.append(df)
    if not all_dfs:
        st.error("❌ 所有上传的销售文件都无法读取。")
        return None
    df_sales = pd.concat(all_dfs, ignore_index=True)
    
    if '统计周期' in df_sales.columns: df_sales['统计周期'] = df_sales['统计周期'].ffill()
    if '门店名称' in df_sales.columns: df_sales['门店名称'] = df_sales['门店名称'].ffill()

    # 映射列名
    column_mapping = {
        '商品实收': '销售金额',
        '商品销量': '销售数量'
    }
    df_sales = df_sales.rename(columns=column_mapping)

    numeric_cols = ['销售金额', '销售数量']
    for col in numeric_cols:
        if col in df_sales.columns:
            df_sales[col] = pd.to_numeric(
                df_sales[col].astype(str).str.replace(r'[¥$,￥]', '', regex=True), 
                errors='coerce'
            ).fillna(0)
    return df_sales

def merge_cost_data(df_sales, cost_file):
    if df_sales is None: return None
    if cost_file is not None:
        df_cost = load_data_file(cost_file)
        if df_cost is not None:
            if '产品' in df_cost.columns: df_cost = df_cost.rename(columns={'产品': '商品名称'})
            if '成本' in df_cost.columns:
                df_cost['成本'] = pd.to_numeric(df_cost['成本'], errors='coerce').fillna(0)
                if df_cost['商品名称'].duplicated().any():
                    df_cost = df_cost.groupby('商品名称', as_index=False)['成本'].mean()
                df_sales = pd.merge(df_sales, df_cost[['商品名称', '成本']], on='商品名称', how='left')
                df_sales['成本'] = df_sales['成本'].fillna(0)
                df_sales['商品毛利'] = df_sales['销售金额'] - (df_sales['销售数量'] * df_sales['成本'])
            else:
                st.warning("⚠️ 成本档案缺少 '成本' 列")
                df_sales['商品毛利'] = 0
        else:
            st.warning("⚠️ 成本档案读取失败")
            df_sales['商品毛利'] = 0
    else:
        df_sales['商品毛利'] = 0; df_sales['成本'] = 0
    return df_sales

def calculate_metrics(df, operate_days):
    if df.empty or operate_days <= 0: return 0, 0, 0, 0, 0, 0, 0
    
    qty = df['销售数量'].sum()
    amt = df['销售金额'].sum()
    profit = df['商品毛利'].sum()
    
    cup_price = (amt / qty) if qty > 0 else 0 
    margin = (profit / amt * 100) if amt > 0 else 0
    
    daily_qty = qty / operate_days
    daily_amt = amt / operate_days
    
    return qty, amt, profit, cup_price, margin, daily_qty, daily_amt

# -----------------------------------------------------------------------------
# 3. 侧边栏布局
# -----------------------------------------------------------------------------
logo_path = "logo.png"
if os.path.exists(logo_path):
    st.sidebar.image(logo_path, width=120)
else:
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/751/751621.png", width=100)

st.sidebar.markdown("## 顿角咖啡智能数据看板")
st.sidebar.caption("Dunjiao Coffee · Intelligent BI System")

with st.sidebar.expander("📂 数据源配置", expanded=True):
    uploaded_sales_files = st.file_uploader("1. 上传销售数据 (多选)", type=["csv", "xlsx"], accept_multiple_files=True)
    uploaded_cost = st.file_uploader("2. 上传成本档案", type=["csv", "xlsx"])

# -----------------------------------------------------------------------------
# 4. 数据加载
# -----------------------------------------------------------------------------
df_final = None
if uploaded_sales_files:
    df_sales_merged = process_sales_files(uploaded_sales_files)
    df_final = merge_cost_data(df_sales_merged, uploaded_cost)
    if df_final is not None:
        st.sidebar.success(f"✅ 数据加载完成")
else:
    st.markdown("""
    <div style="text-align: center; padding: 40px;">
        <h1 style="font-size: 42px; color: #1E293B;">👋 欢迎使用顿角咖啡智能数据看板</h1>
        <p style="color: #64748B; font-size: 18px;">专为顿角咖啡打造的智能经营分析平台</p>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    with c2:
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
        else:
            st.image("https://cdn-icons-png.flaticon.com/512/2935/2935413.png", use_container_width=True, caption="Dunjiao Coffee Analytics")
    
    st.stop()

# -----------------------------------------------------------------------------
# 5. 筛选与逻辑
# -----------------------------------------------------------------------------
if '统计周期' in df_final.columns:
    available_periods = sorted(list(df_final['统计周期'].dropna().unique()))
else:
    available_periods = []

df_current = pd.DataFrame(); df_previous = pd.DataFrame()
is_comparison_mode = False
days_current = 5; days_previous = 5

if '门店名称' in df_final.columns:
    all_stores = sorted(list(df_final['门店名称'].dropna().unique()))
else:
    all_stores = []

with st.sidebar.expander("🛠️ 筛选与参数", expanded=True):
    selected_stores = st.multiselect("门店筛选", all_stores, placeholder="默认全选")
    
    if len(available_periods) >= 2:
        st.markdown("---")
        enable_comparison = st.checkbox("开启环比分析", value=True)
        if enable_comparison:
            is_comparison_mode = True
            p_current = st.selectbox("本期", available_periods, index=len(available_periods)-1)
            remaining_periods = [p for p in available_periods if p != p_current]
            p_previous = st.selectbox("上期 (对比)", remaining_periods, index=len(remaining_periods)-1 if remaining_periods else 0)
            
            st.caption("⏱️ 营业天数设置")
            c1_day, c2_day = st.columns(2)
            days_current = c1_day.number_input("本期天数", 1, 31, 5)
            days_previous = c2_day.number_input("上期天数", 1, 31, 5)
            
            df_current = df_final[df_final['统计周期'] == p_current].copy()
            df_previous = df_final[df_final['统计周期'] == p_previous].copy()
        else:
            selected_periods = st.multiselect("统计周期", available_periods, default=available_periods)
            days_current = st.number_input("营业天数", 1, 31, 5)
            df_current = df_final[df_final['统计周期'].isin(selected_periods)].copy()
    else:
        days_current = st.number_input("营业天数", 1, 31, 5)
        df_current = df_final.copy()

if selected_stores:
    if not df_current.empty: df_current = df_current[df_current['门店名称'].isin(selected_stores)]
    if not df_previous.empty: df_previous = df_previous[df_previous['门店名称'].isin(selected_stores)]

# 计算 KPI
cur_qty, cur_amt, cur_profit, cur_cup_price, cur_margin, cur_daily_qty, cur_daily_amt = calculate_metrics(df_current, days_current)

if is_comparison_mode and not df_previous.empty:
    prev_qty, prev_amt, prev_profit, prev_cup_price, prev_margin, prev_daily_qty, prev_daily_amt = calculate_metrics(df_previous, days_previous)
    
    delta_qty = ((cur_qty - prev_qty) / prev_qty) if prev_qty != 0 else 0
    delta_amt = ((cur_amt - prev_amt) / prev_amt) if prev_amt != 0 else 0
    delta_price = ((cur_cup_price - prev_cup_price) / prev_cup_price) if prev_cup_price != 0 else 0
    delta_margin = cur_margin - prev_margin
    delta_daily_qty = ((cur_daily_qty - prev_daily_qty) / prev_daily_qty) if prev_daily_qty != 0 else 0
    delta_daily_amt = ((cur_daily_amt - prev_daily_amt) / prev_daily_amt) if prev_daily_amt != 0 else 0
else:
    delta_qty = delta_amt = delta_price = delta_margin = delta_daily_qty = delta_daily_amt = None

# === 🌟 核心升级：新品/组合多选搜索 ===
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 新品/组合搜索")
st.sidebar.caption("选择多个产品可查看组合表现及门店对比")

all_products_list = []
if not df_current.empty:
    all_products_list = sorted(df_current['商品名称'].unique().tolist())

search_products = st.sidebar.multiselect("选择商品名称", all_products_list, placeholder="可多选，例如：生椰拿铁、厚椰拿铁")

# -----------------------------------------------------------------------------
# 6. 主界面
# -----------------------------------------------------------------------------
st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf?auto=format&fit=crop&w=1200&h=250&q=80", use_container_width=True)

c_title, c_period = st.columns([2, 1])
with c_title: st.title("📊 顿角咖啡智能数据看板")
with c_period:
    if is_comparison_mode:
        st.markdown(f"<div style='text-align:right; padding-top:10px; color:#64748B;'><b>分析周期</b><br><span style='color:#3B82F6; font-size:1.1em'>{p_current}</span> vs <span style='color:#94A3B8'>{p_previous}</span></div>", unsafe_allow_html=True)

st.markdown("---")

if df_current.empty:
    st.warning("⚠️ 当前筛选结果为空。")
    st.stop()

def update_chart_layout(fig):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_family="Inter",
        font_color="#4B5563",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig

# -----------------------------------------------------------------------------
# 🎯 产品/组合透视卡片 (多选逻辑)
# -----------------------------------------------------------------------------
if search_products:
    if len(search_products) == 1:
        title_text = f"🎯 单品透视：<span style='color:#2563EB'>{search_products[0]}</span>"
    else:
        title_text = f"🎯 组合透视 ({len(search_products)}个商品)"
        
    st.markdown(f"### {title_text}", unsafe_allow_html=True)
    
    prod_curr = df_current[df_current['商品名称'].isin(search_products)]
    prod_prev = df_previous[df_previous['商品名称'].isin(search_products)] if not df_previous.empty else pd.DataFrame()
    
    p_qty, p_amt, p_profit, p_cup_price, p_margin, p_daily_qty, p_daily_amt = calculate_metrics(prod_curr, days_current)
    
    total_sales_all = df_current['销售金额'].sum()
    sales_contribution = (p_amt / total_sales_all) if total_sales_all > 0 else 0
    rank_str = f"贡献占比 {sales_contribution:.1%}"

    p_delta_qty = p_delta_amt = p_delta_margin = None
    if is_comparison_mode and not prod_prev.empty:
        pp_qty, pp_amt, _, _, pp_margin, _, _ = calculate_metrics(prod_prev, days_previous)
        p_delta_qty = ((p_qty - pp_qty) / pp_qty) if pp_qty != 0 else 0
        p_delta_amt = ((p_amt - pp_amt) / pp_amt) if pp_amt != 0 else 0
        p_delta_margin = p_margin - pp_margin

    with st.container(border=True):
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        
        def prod_card(col, label, val, delta=None, sub_text=""):
            d_str = f"{delta:+.1%}" if delta is not None else None
            if label == "综合毛利率" and delta is not None: d_str = f"{delta:+.1f} pts"
            col.metric(label, val, d_str, delta_color="inverse")
            if sub_text: col.caption(sub_text)

        prod_card(col_p1, "组合销量", f"{int(p_qty)} 杯", p_delta_qty, sub_text=f"📅 日均销量：{p_daily_qty:.1f} 杯")
        prod_card(col_p2, "组合营收", f"¥{p_amt:,.2f}", p_delta_amt, sub_text=rank_str)
        if uploaded_cost:
            prod_card(col_p3, "综合毛利率", f"{p_margin:.2f}%", p_delta_margin, sub_text="💰 组合盈利能力")
        else:
            col_p3.metric("毛利率", "--", help="请上传成本档案")
            
        avg_margin_all = (df_current['商品毛利'].sum() / df_current['销售金额'].sum()) if df_current['销售金额'].sum() > 0 else 0
        my_margin = p_margin / 100
        
        tag = "普通组合"; tag_color = "gray"
        if my_margin >= avg_margin_all: 
            tag = "💎 高利组合"; tag_color = "blue"
        else:
            tag = "📦 走量组合"; tag_color = "orange"
            
        col_p4.markdown(f"**🤖 组合诊断**")
        col_p4.markdown(f":{tag_color}[**{tag}**]")
        col_p4.caption(f"全店平均毛利: {avg_margin_all:.1%}")

    st.markdown("##### 🏠 组合各门店售卖表现 (合计销量)")
    prod_store_df = prod_curr.groupby('门店名称', as_index=False).agg({'销售数量':'sum', '销售金额':'sum', '商品毛利':'sum'})
    prod_store_df = prod_store_df.sort_values('销售数量', ascending=True) 
    
    if not prod_store_df.empty:
        with st.container(border=True):
            if PLOTLY_AVAILABLE:
                fig_store = px.bar(
                    prod_store_df, 
                    y='门店名称', 
                    x='销售数量', 
                    orientation='h',
                    text='销售数量',
                    color='销售数量',
                    color_continuous_scale='Blues',
                    hover_data={'销售数量':True, '销售金额':':.2f', '商品毛利':':.2f'},
                    title=f"各门店【{', '.join(search_products)[:20]}...】合计销量"
                )
                fig_store.update_traces(textposition='outside')
                fig_height = max(400, len(prod_store_df) * 40)
                fig_store.update_layout(coloraxis_showscale=False, height=fig_height)
                fig_store = update_chart_layout(fig_store)
                st.plotly_chart(fig_store, use_container_width=True)
            else:
                st.bar_chart(prod_store_df.set_index('门店名称')['销售数量'])
    else:
        st.info("所选商品在本期无销售记录。")

    st.markdown("---")

# -----------------------------------------------------------------------------
# 7. 全局 KPI 卡片区域
# -----------------------------------------------------------------------------
def metric_card(title, value, delta, prefix="", suffix="", is_percent=False, icon=""):
    delta_str = None
    if delta is not None:
        if is_percent: delta_str = f"{delta:+.2f} pts"
        else: delta_str = f"{delta:+.2%}"
    
    with st.container(border=True):
        label_text = f"{icon} {title}" if icon else title
        st.metric(label=label_text, value=f"{prefix}{value}{suffix}", delta=delta_str, delta_color="inverse")

st.subheader("📦 经营总量 (Volume & Revenue)")
r1c1, r1c2, r1c3 = st.columns(3)
with r1c1: metric_card("总销量", int(cur_qty), delta_qty, suffix=" 杯", icon="🛒")
with r1c2: metric_card("总销售额", f"{cur_amt:,.2f}", delta_amt, prefix="¥", icon="💰")
with r1c3: metric_card("平均杯单价", f"{cur_cup_price:.2f}", delta_price, prefix="¥", icon="🏷️")

st.subheader("🚀 日均效率 & 盈利 (Efficiency)")
r2c1, r2c2, r2c3 = st.columns(3)
with r2c1: metric_card("日均杯数", f"{cur_daily_qty:.1f}", delta_daily_qty, suffix=" 杯", icon="📅")
with r2c2: metric_card("日均营收", f"{cur_daily_amt:,.2f}", delta_daily_amt, prefix="¥", icon="💳")
with r2c3:
    if uploaded_cost:
        metric_card("平均毛利率", f"{cur_margin:.2f}", delta_margin, suffix="%", is_percent=True, icon="📈")
    else:
        with st.container(border=True): st.metric("📈 平均毛利率", "--")

st.markdown("---")

# -----------------------------------------------------------------------------
# 8. 图表区域
# -----------------------------------------------------------------------------
# 确保定义 df_display
df_display = df_current.copy()

# 聚合逻辑：确保去重，只按商品名称聚合
df_chart_data = df_display.groupby('商品名称', as_index=False).agg({'销售数量':'sum', '销售金额':'sum', '商品毛利':'sum'})

# 尝试合并回类别 (取众数) 用于染色
if '商品类别' in df_display.columns:
    cat_map = df_display.groupby('商品名称')['商品类别'].agg(lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0]).reset_index()
    df_chart_data = pd.merge(df_chart_data, cat_map, on='商品名称', how='left')

c1, c2 = st.columns(2)

with c1:
    with st.container(border=True):
        st.markdown("##### 🔥 本期销量排行 (Top 10)")
        top_sales = df_chart_data.sort_values('销售数量', ascending=True).tail(10)
        
        if PLOTLY_AVAILABLE:
            fig = px.bar(
                top_sales, y='商品名称', x='销售数量', orientation='h', text='销售数量',
                color_discrete_sequence=[COLOR_PALETTE[0]]
            )
            fig.update_traces(textposition='outside')
            fig = update_chart_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.bar_chart(top_sales.set_index('商品名称')['销售数量'])

with c2:
    with st.container(border=True):
        if uploaded_cost:
            st.markdown("##### 🏆 利润贡献排行")
            tab_cat, tab_prod = st.tabs(["📂 按类别", "☕️ 按单品"])
            total_profit = df_chart_data['商品毛利'].sum()
            
            with tab_cat:
                if '商品类别' in df_chart_data.columns:
                    df_cat = df_chart_data.groupby('商品类别', as_index=False)['商品毛利'].sum().sort_values('商品毛利', ascending=True)
                    df_cat['商品毛利'] = df_cat['商品毛利'].round(2)
                    df_cat['贡献率'] = np.where(total_profit>0, df_cat['商品毛利']/total_profit, 0)
                    
                    if PLOTLY_AVAILABLE:
                        fig_cat = px.bar(
                            df_cat, y='商品类别', x='商品毛利', orientation='h', 
                            text=df_cat['贡献率'].apply(lambda x: f"{x:.2%}"), 
                            color='商品毛利', color_continuous_scale='Mint', labels={'商品毛利':'毛利额'}
                        )
                        fig_cat.update_traces(textposition='outside')
                        fig_cat.update_layout(coloraxis_showscale=False)
                        fig_cat = update_chart_layout(fig_cat)
                        st.plotly_chart(fig_cat, use_container_width=True)
                else: st.info("暂无类别数据")

            with tab_prod:
                df_prod = df_chart_data.sort_values('商品毛利', ascending=True).tail(10)
                df_prod['商品毛利'] = df_prod['商品毛利'].round(2)
                df_prod['贡献率'] = np.where(total_profit>0, df_prod['商品毛利']/total_profit, 0)
                if PLOTLY_AVAILABLE:
                    fig_prod = px.bar(
                        df_prod, y='商品名称', x='商品毛利', orientation='h', 
                        text=df_prod['贡献率'].apply(lambda x: f"{x:.2%}"),
                        color='商品毛利', color_continuous_scale='Oranges', labels={'商品毛利':'毛利额'}
                    )
                    fig_prod.update_traces(textposition='outside')
                    fig_prod.update_layout(coloraxis_showscale=False)
                    fig_prod = update_chart_layout(fig_prod)
                    st.plotly_chart(fig_prod, use_container_width=True)
        else: st.info("请上传成本档案")

# -----------------------------------------------------------------------------
# 9. 品类涨跌 (日均杯数变动)
# -----------------------------------------------------------------------------
if is_comparison_mode and '商品类别' in df_current.columns:
    st.markdown("### 📈 品类涨跌风向标 (日均杯数变动)")
    cat_curr = df_current.groupby('商品类别')['销售数量'].sum().reset_index()
    cat_curr['日均杯数'] = cat_curr['销售数量'] / days_current
    
    if not df_previous.empty:
        cat_prev = df_previous.groupby('商品类别')['销售数量'].sum().reset_index()
        cat_prev['日均杯数'] = cat_prev['销售数量'] / days_previous
    else:
        cat_prev = pd.DataFrame(columns=['商品类别', '销售数量', '日均杯数'])
    
    cat_diff = pd.merge(cat_curr, cat_prev, on='商品类别', suffixes=('_curr', '_prev'), how='outer').fillna(0)
    cat_diff['日均杯数变动'] = cat_diff['日均杯数_curr'] - cat_diff['日均杯数_prev']
    cat_diff['日均杯数变动'] = cat_diff['日均杯数变动'].round(2)
    cat_diff = cat_diff.sort_values('日均杯数变动', ascending=True)
    cat_diff['颜色'] = np.where(cat_diff['日均杯数变动'] >= 0, '#EF4444', '#10B981')
    
    with st.container(border=True):
        if PLOTLY_AVAILABLE:
            fig_diff = px.bar(cat_diff, y='商品类别', x='日均杯数变动', text='日均杯数变动', orientation='h', title="品类日均杯数净增长/减少 (杯)")
            fig_diff.update_traces(marker_color=cat_diff['颜色'], texttemplate='%{text:+.2f}杯')
            fig_diff.update_layout(yaxis={'categoryorder':'total ascending'})
            fig_diff = update_chart_layout(fig_diff)
            st.plotly_chart(fig_diff, use_container_width=True)
        else: st.bar_chart(cat_diff.set_index('商品类别')['日均杯数变动'])

st.markdown("---")

# -----------------------------------------------------------------------------
# 9.5 [新增/修复] 门店品类涨跌雷达 (UI 优化版 + 分页)
# -----------------------------------------------------------------------------
if is_comparison_mode and '商品类别' in df_current.columns:
    st.markdown("### 🏪 门店品类涨跌雷达 (日均杯数变动)")
    st.caption("颜色越红增长越多，越绿下滑越严重（鼠标悬停查看数值）。")
    
    # Data Prep
    store_cat_curr = df_current.groupby(['门店名称', '商品类别'], as_index=False)['销售数量'].sum()
    store_cat_curr['日均'] = store_cat_curr['销售数量'] / days_current
    
    if not df_previous.empty:
        store_cat_prev = df_previous.groupby(['门店名称', '商品类别'], as_index=False)['销售数量'].sum()
        store_cat_prev['日均'] = store_cat_prev['销售数量'] / days_previous
    else:
        store_cat_prev = pd.DataFrame(columns=['门店名称', '商品类别', '日均'])
        
    merged_sc = pd.merge(store_cat_curr, store_cat_prev, on=['门店名称', '商品类别'], suffixes=('_curr', '_prev'), how='outer').fillna(0)
    merged_sc['变动'] = merged_sc['日均_curr'] - merged_sc['日均_prev']
    
    heatmap_data = merged_sc.pivot(index='门店名称', columns='商品类别', values='变动').fillna(0)
    
    # --- 分页控制 ---
    PAGE_SIZE = 15
    total_stores = len(heatmap_data)
    total_pages = max(1, -(-total_stores // PAGE_SIZE)) # Ceiling division
    
    col_pagination, _ = st.columns([1, 3])
    with col_pagination:
        page = st.number_input(f"选择页码 (共{total_pages}页)", min_value=1, max_value=total_pages, value=1)
        
    start_idx = (page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total_stores)
    
    heatmap_data_page = heatmap_data.iloc[start_idx:end_idx]
    
    # 动态高度计算
    n_stores_page = len(heatmap_data_page)
    fig_height = max(400, n_stores_page * 50) 
    
    with st.container(border=True):
        if PLOTLY_AVAILABLE:
            fig_hm = go.Figure(data=go.Heatmap(
                z=heatmap_data_page.values,
                x=heatmap_data_page.columns,
                y=heatmap_data_page.index,
                colorscale=[[0, '#10B981'], [0.5, '#FFFFFF'], [1, '#EF4444']], 
                zmid=0,
                hovertemplate="门店: %{y}<br>品类: %{x}<br>日均变化: %{z:+.2f}杯<extra></extra>", 
                xgap=1, ygap=1
            ))
            fig_hm.update_layout(
                xaxis_title="",
                yaxis_title="",
                height=fig_height,
                xaxis={'side': 'top'},
            )
            fig_hm = update_chart_layout(fig_hm)
            st.plotly_chart(fig_hm, use_container_width=True)
    
    # 涨跌榜单
    st.markdown("#### 🚀 涨跌榜单 Top 5")
    c_rise, c_fall = st.columns(2)
    
    merged_sc = merged_sc.sort_values('变动', ascending=False)
    top_risers = merged_sc.head(5)
    top_fallers = merged_sc.tail(5).sort_values('变动', ascending=True)
    
    with c_rise:
        with st.container(border=True):
            st.markdown("##### 🏆 增长最快")
            for _, row in top_risers.iterrows():
                if row['变动'] > 0: st.markdown(f"**{row['门店名称']} - {row['商品类别']}**: :red[+{row['变动']:.2f} 杯]")
    
    with c_fall:
        with st.container(border=True):
            st.markdown("##### ⚠️ 下滑最快")
            for _, row in top_fallers.iterrows():
                if row['变动'] < 0: st.markdown(f"**{row['门店名称']} - {row['商品类别']}**: :green[{row['变动']:.2f} 杯]")

st.markdown("---")

# -----------------------------------------------------------------------------
# 10. BCG 矩阵
# -----------------------------------------------------------------------------
if uploaded_cost:
    st.markdown("### 🧠 智能产品矩阵 (BCG)")
    
    # 使用聚合后的数据 (df_chart_data 已经按名称去重)
    matrix_df = df_chart_data.copy()
    matrix_df['毛利率'] = np.where(matrix_df['销售金额']>0, matrix_df['商品毛利']/matrix_df['销售金额'], 0)
    matrix_df['日均销量'] = matrix_df['销售数量'] / days_current
    
    avg_margin = matrix_df['毛利率'].mean()
    avg_volume = matrix_df['日均销量'].mean()
    
    def categorize_product(row):
        if row['日均销量'] >= avg_volume and row['毛利率'] >= avg_margin: return "🌟 明星"
        elif row['日均销量'] >= avg_volume and row['毛利率'] < avg_margin: return "🐮 现金牛"
        elif row['日均销量'] < avg_volume and row['毛利率'] >= avg_margin: return "❓ 潜力股"
        else: return "🐕 瘦狗"

    matrix_df['角色'] = matrix_df.apply(categorize_product, axis=1)
    
    c_matrix, c_list = st.columns([3, 2])
    with c_matrix:
        with st.container(border=True):
            if PLOTLY_AVAILABLE:
                matrix_df['毛利率(%)'] = (matrix_df['毛利率'] * 100).round(2)
                fig_bcg = px.scatter(
                    matrix_df, x="毛利率(%)", y="日均销量", color="角色", hover_name="商品名称", size="销售金额",
                    color_discrete_map={"🌟 明星":COLOR_PALETTE[0], "🐮 现金牛":COLOR_PALETTE[2], "❓ 潜力股":COLOR_PALETTE[4], "🐕 瘦狗":COLOR_PALETTE[3]}
                )
                fig_bcg.add_vline(x=avg_margin*100, line_dash="dash", line_color="#94A3B8", annotation_text="平均毛利率")
                fig_bcg.add_hline(y=avg_volume, line_dash="dash", line_color="#94A3B8", annotation_text="平均销量")
                fig_bcg = update_chart_layout(fig_bcg)
                st.plotly_chart(fig_bcg, use_container_width=True)
    with c_list:
        with st.container(border=True):
            st.markdown("#### 📋 诊断报告")
            cows = matrix_df[matrix_df['角色'].str.contains("现金牛")]['商品名称'].tolist()
            dogs = matrix_df[matrix_df['角色'].str.contains("瘦狗")]['商品名称'].tolist()
            st.markdown(f"**🐮 现金牛产品:** {len(cows)} 个")
            if cows: st.success("、".join(cows))
            else: st.caption("暂无")
            st.markdown(f"**🐕 瘦狗产品:** {len(dogs)} 个")
            if dogs: st.error("、".join(dogs))
            else: st.caption("暂无")

# -----------------------------------------------------------------------------
# 11. 明细表格 (去重，智能合并类别)
# -----------------------------------------------------------------------------
st.markdown("### 📄 商品明细透视")

# 聚合逻辑：按商品名称聚合 (强制去重)
df_view = df_display.groupby('商品名称', as_index=False).agg({
    '商品类别': lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0] if not x.empty else '未知',
    '销售数量': 'sum',
    '销售金额': 'sum',
    '商品毛利': 'sum'
})
df_view = df_view.rename(columns={'商品毛利': '商品毛利额'})

df_view['商品毛利率'] = np.where(df_view['销售金额']>0, (df_view['商品毛利额']/df_view['销售金额'] * 100), 0)
total_rev = df_view['销售金额'].sum()
df_view['商品销售占比'] = np.where(total_rev>0, (df_view['销售金额']/total_rev * 100), 0)

# 预警逻辑
conditions = [
    (df_view['商品毛利率'] >= 99.9), 
    (df_view['商品毛利率'] < 60),
    (df_view['商品毛利率'] >= 60) & (df_view['商品毛利率'] <= 65)
]
choices = ['⚠️ 缺成本', '🔴 低毛利', '🟡 毛利预警']
df_view['健康度'] = np.select(conditions, choices, default='🟢 健康')

df_view = df_view.sort_values('销售数量', ascending=False)
df_view['序号'] = range(1, len(df_view) + 1)
df_view = df_view.round(2)

cols = ['序号', '商品名称', '健康度', '商品类别', '销售数量', '销售金额', '商品毛利额', '商品毛利率', '商品销售占比']

with st.container(border=True):
    st.dataframe(
        df_view[cols],
        column_config={
            "序号": st.column_config.NumberColumn("排名", width="small"),
            "商品名称": st.column_config.TextColumn("商品名称", help="售卖的商品名称", width="medium"),
            "健康度": st.column_config.TextColumn("健康预警", width="small", help="基于毛利率的自动诊断"),
            "商品类别": st.column_config.TextColumn("类别", width="small"),
            "销售数量": st.column_config.ProgressColumn("销量 (杯)", format="%d", min_value=0, max_value=int(df_view['销售数量'].max())),
            "销售金额": st.column_config.NumberColumn("销售额", format="¥%.2f"),
            "商品毛利额": st.column_config.NumberColumn("毛利额", format="¥%.2f"),
            "商品毛利率": st.column_config.NumberColumn("毛利率", format="%.2f%%", help="<60%标红, 60-65%标黄"),
            "商品销售占比": st.column_config.NumberColumn("销售占比", format="%.2f%%", help="占总销售额的比例"),
        },
        use_container_width=True,
        hide_index=True,
        height=500
    )
