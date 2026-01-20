import streamlit as st
import pandas as pd
import numpy as np

# -----------------------------------------------------------------------------
# 1. 核心配置与 CSS 注入 (UI 灵魂)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="咖啡连锁智能数据看板",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入自定义 CSS 以实现“商务年轻”风格
st.markdown("""
<style>
    /* 引入 Inter 字体 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    /* 全局背景：极淡的蓝灰色，营造科技商务感 */
    .stApp {
        background-color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }
    
    /* 侧边栏优化 */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
        box-shadow: 2px 0 5px rgba(0,0,0,0.02);
    }
    
    /* 标题样式：深邃蓝，更有张力 */
    h1, h2, h3 {
        color: #0F172A;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    
    /* 关键：重塑 st.container(border=True) 为精致卡片 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF;
        border-radius: 16px;
        border: 1px solid #F1F5F9;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        padding: 20px;
        transition: all 0.3s ease;
    }
    
    /* 鼠标悬停卡片上浮效果 */
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        border-color: #E2E8F0;
    }

    /* 指标数值样式 */
    [data-testid="stMetricValue"] {
        font-size: 32px !important;
        background: -webkit-linear-gradient(45deg, #1E40AF, #3B82F6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 14px !important;
        color: #64748B !important;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Tab 样式优化 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #F1F5F9;
        padding: 4px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 8px;
        border: none;
        color: #64748B;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF;
        color: #0F172A;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* 表格样式微调 */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
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

# 定义一套“商务年轻”的配色方案
COLOR_PALETTE = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']
# 蓝色(主), 绿色(涨), 橙色(警告), 红色(跌), 紫色, 粉色

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

    column_mapping = {'商品实收': '销售金额', '商品销量': '销售数量'}
    df_sales = df_sales.rename(columns=column_mapping)

    for col in ['销售金额', '销售数量']:
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
    if df.empty or operate_days <= 0: return 0, 0, 0, 0, 0, 0
    qty = df['销售数量'].sum()
    amt = df['销售金额'].sum()
    profit = df['商品毛利'].sum()
    price = (amt / qty) if qty > 0 else 0
    margin = (profit / amt * 100) if amt > 0 else 0
    daily_qty = qty / operate_days
    daily_amt = amt / operate_days
    return qty, amt, price, margin, daily_qty, daily_amt

# -----------------------------------------------------------------------------
# 3. 侧边栏布局
# -----------------------------------------------------------------------------
st.sidebar.markdown("## ☕ Data Dashboard")
st.sidebar.caption("连锁咖啡 · 智能经营分析")

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
    # 欢迎页面
    st.markdown("""
    <div style="text-align: center; padding: 50px;">
        <h1>👋 欢迎使用智能数据看板</h1>
        <p style="color: #6B7280; font-size: 18px;">请在左侧侧边栏上传数据文件以开始分析。</p>
        <br>
        <div style="background-color: #FFFFFF; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); display: inline-block; text-align: left;">
            <p><strong>💡 快速上手指南：</strong></p>
            <ol style="color: #4B5563;">
                <li>支持同时上传多个周期的销售数据 (.csv/.xlsx)</li>
                <li>上传成本档案可自动计算毛利</li>
                <li>支持环比分析与日均效率追踪</li>
            </ol>
        </div>
    </div>
    """, unsafe_allow_html=True)
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
            
            st.caption("⏱️ 营业天数")
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
cur_qty, cur_amt, cur_price, cur_margin, cur_daily_qty, cur_daily_amt = calculate_metrics(df_current, days_current)
if is_comparison_mode and not df_previous.empty:
    prev_qty, prev_amt, prev_price, prev_margin, prev_daily_qty, prev_daily_amt = calculate_metrics(df_previous, days_previous)
    delta_qty = ((cur_qty - prev_qty) / prev_qty) if prev_qty != 0 else 0
    delta_amt = ((cur_amt - prev_amt) / prev_amt) if prev_amt != 0 else 0
    delta_price = ((cur_price - prev_price) / prev_price) if prev_price != 0 else 0
    delta_margin = cur_margin - prev_margin
    delta_daily_qty = ((cur_daily_qty - prev_daily_qty) / prev_daily_qty) if prev_daily_qty != 0 else 0
    delta_daily_amt = ((cur_daily_amt - prev_daily_amt) / prev_daily_amt) if prev_daily_amt != 0 else 0
else:
    delta_qty = delta_amt = delta_price = delta_margin = delta_daily_qty = delta_daily_amt = None

# -----------------------------------------------------------------------------
# 6. 主界面
# -----------------------------------------------------------------------------
st.title("📊 连锁门店经营概览")
if is_comparison_mode:
    st.markdown(f"**分析周期：** <span style='color:#3B82F6'>{p_current}</span> <span style='color:#9CA3AF'>vs</span> <span style='color:#6B7280'>{p_previous}</span>", unsafe_allow_html=True)
st.markdown("---")

if df_current.empty:
    st.warning("⚠️ 当前筛选结果为空。")
    st.stop()

# -----------------------------------------------------------------------------
# 7. KPI 卡片
# -----------------------------------------------------------------------------
def metric_card(title, value, delta, prefix="", suffix="", is_percent=False):
    delta_str = None
    if delta is not None:
        if is_percent: delta_str = f"{delta:+.2f} pts"
        else: delta_str = f"{delta:+.2%}"
    
    with st.container(border=True):
        st.metric(label=title, value=f"{prefix}{value}{suffix}", delta=delta_str, delta_color="inverse")

st.subheader("📦 经营总量")
r1c1, r1c2, r1c3 = st.columns(3)
with r1c1: metric_card("总销量", int(cur_qty), delta_qty, suffix=" 杯")
with r1c2: metric_card("总销售额", f"{cur_amt:,.2f}", delta_amt, prefix="¥")
with r1c3: metric_card("平均杯单价", f"{cur_price:.2f}", delta_price, prefix="¥")

st.subheader("🚀 日均效率 & 盈利")
r2c1, r2c2, r2c3 = st.columns(3)
with r2c1: metric_card("日均杯数", f"{cur_daily_qty:.1f}", delta_daily_qty, suffix=" 杯/天")
with r2c2: metric_card("日均营收", f"{cur_daily_amt:,.2f}", delta_daily_amt, prefix="¥")
with r2c3:
    if uploaded_cost:
        metric_card("平均毛利率", f"{cur_margin:.2f}", delta_margin, suffix="%", is_percent=True)
    else:
        with st.container(border=True): st.metric("平均毛利率", "--", help="请上传成本档案")

st.markdown("---")

# -----------------------------------------------------------------------------
# 8. 图表区域
# -----------------------------------------------------------------------------
df_display = df_current.copy()

def update_chart_layout(fig):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_family="Helvetica Neue",
        title_font_size=18,
        title_font_color="#1F2937",
        font_color="#4B5563",
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig

c1, c2 = st.columns(2)

with c1:
    with st.container(border=True):
        st.markdown("##### 🔥 本期销量排行 (Top 10)")
        # 修复：聚合时不带商品类别，确保重名产品合并
        top_sales = df_display.groupby('商品名称', as_index=False)['销售数量'].sum()
        top_sales = top_sales.sort_values('销售数量', ascending=True).tail(10)
        
        if PLOTLY_AVAILABLE:
            fig = px.bar(
                top_sales, 
                y='商品名称', x='销售数量', 
                orientation='h', 
                text='销售数量', 
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
            total_profit = df_display['商品毛利'].sum()
            
            with tab_cat:
                if '商品类别' in df_display.columns:
                    df_cat = df_display.groupby('商品类别', as_index=False)['商品毛利'].sum().sort_values('商品毛利', ascending=True)
                    df_cat['商品毛利'] = df_cat['商品毛利'].round(2)
                    df_cat['贡献率'] = np.where(total_profit>0, df_cat['商品毛利']/total_profit, 0)
                    
                    if PLOTLY_AVAILABLE:
                        fig_cat = px.bar(
                            df_cat, y='商品类别', x='商品毛利', 
                            orientation='h', 
                            text=df_cat['贡献率'].apply(lambda x: f"{x:.2%}"), 
                            color='商品毛利', 
                            color_continuous_scale='Mint', 
                            labels={'商品毛利':'毛利额'}
                        )
                        fig_cat.update_traces(textposition='outside')
                        fig_cat.update_layout(coloraxis_showscale=False)
                        fig_cat = update_chart_layout(fig_cat)
                        st.plotly_chart(fig_cat, use_container_width=True)
                else:
                    st.info("暂无类别数据")

            with tab_prod:
                # 修复：聚合时不带商品类别
                df_prod = df_display.groupby('商品名称', as_index=False)['商品毛利'].sum().sort_values('商品毛利', ascending=True).tail(10)
                df_prod['商品毛利'] = df_prod['商品毛利'].round(2)
                df_prod['贡献率'] = np.where(total_profit>0, df_prod['商品毛利']/total_profit, 0)
                
                if PLOTLY_AVAILABLE:
                    fig_prod = px.bar(
                        df_prod, y='商品名称', x='商品毛利', 
                        orientation='h', 
                        text=df_prod['贡献率'].apply(lambda x: f"{x:.2%}"), 
                        color='商品毛利', 
                        color_continuous_scale='Oranges', 
                        labels={'商品毛利':'毛利额'}
                    )
                    fig_prod.update_traces(textposition='outside')
                    fig_prod.update_layout(coloraxis_showscale=False)
                    fig_prod = update_chart_layout(fig_prod)
                    st.plotly_chart(fig_prod, use_container_width=True)
        else:
            st.info("请上传成本档案查看利润分析")

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
            fig_diff = px.bar(
                cat_diff, 
                y='商品类别', 
                x='日均杯数变动', 
                text='日均杯数变动', 
                orientation='h', 
                title="品类日均杯数净增长/减少 (杯)"
            )
            fig_diff.update_traces(marker_color=cat_diff['颜色'], texttemplate='%{text:+.2f}杯')
            fig_diff.update_layout(yaxis={'categoryorder':'total ascending'})
            fig_diff = update_chart_layout(fig_diff)
            st.plotly_chart(fig_diff, use_container_width=True)
        else:
            st.bar_chart(cat_diff.set_index('商品类别')['日均杯数变动'])

st.markdown("---")

# -----------------------------------------------------------------------------
# 10. 智能产品矩阵分析 (BCG)
# -----------------------------------------------------------------------------
if uploaded_cost:
    st.markdown("### 🧠 智能产品矩阵分析 (BCG)")
    st.caption("基于本期数据自动划分产品角色：横轴为毛利率，纵轴为日均销量。")

    # 修复：聚合时不带商品类别
    matrix_df = df_display.groupby('商品名称', as_index=False).agg({
        '销售数量': 'sum', 
        '销售金额': 'sum', 
        '商品毛利': 'sum'
    })
    
    matrix_df['毛利率'] = np.where(matrix_df['销售金额']>0, matrix_df['商品毛利']/matrix_df['销售金额'], 0)
    matrix_df['日均销量'] = matrix_df['销售数量'] / days_current
    
    avg_margin = matrix_df['毛利率'].mean()
    avg_volume = matrix_df['日均销量'].mean()
    
    def categorize_product(row):
        if row['日均销量'] >= avg_volume and row['毛利率'] >= avg_margin: return "🌟 明星 (Stars)"
        elif row['日均销量'] >= avg_volume and row['毛利率'] < avg_margin: return "🐮 现金牛 (Cash Cows)"
        elif row['日均销量'] < avg_volume and row['毛利率'] >= avg_margin: return "❓ 潜力股 (Question Marks)"
        else: return "🐕 瘦狗 (Dogs)"

    matrix_df['角色'] = matrix_df.apply(categorize_product, axis=1)
    
    c_matrix, c_list = st.columns([3, 2])
    
    with c_matrix:
        with st.container(border=True):
            if PLOTLY_AVAILABLE:
                matrix_df['毛利率(%)'] = (matrix_df['毛利率'] * 100).round(2)
                fig_bcg = px.scatter(
                    matrix_df, 
                    x="毛利率(%)", 
                    y="日均销量", 
                    color="角色",
                    hover_name="商品名称",
                    size="销售金额",
                    color_discrete_map={
                        "🌟 明星 (Stars)": COLOR_PALETTE[0],
                        "🐮 现金牛 (Cash Cows)": COLOR_PALETTE[2],
                        "❓ 潜力股 (Question Marks)": COLOR_PALETTE[4],
                        "🐕 瘦狗 (Dogs)": COLOR_PALETTE[3]
                    },
                )
                fig_bcg.add_vline(x=avg_margin*100, line_dash="dash", line_color="#94A3B8", annotation_text="平均毛利率")
                fig_bcg.add_hline(y=avg_volume, line_dash="dash", line_color="#94A3B8", annotation_text="平均销量")
                fig_bcg = update_chart_layout(fig_bcg)
                fig_bcg.update_layout(xaxis=dict(showgrid=True, gridcolor="#F1F5F9"), yaxis=dict(showgrid=True, gridcolor="#F1F5F9"))
                st.plotly_chart(fig_bcg, use_container_width=True)
    
    with c_list:
        with st.container(border=True):
            st.markdown("#### 📋 诊断报告")
            cows = matrix_df[matrix_df['角色'].str.contains("现金牛")]['商品名称'].tolist()
            dogs = matrix_df[matrix_df['角色'].str.contains("瘦狗")]['商品名称'].tolist()
            
            st.markdown(f"**🐮 现金牛产品 (薄利多销):** {len(cows)} 个")
            if cows: st.success("、".join(cows))
            else: st.caption("暂无")
                
            st.markdown(f"**🐕 瘦狗产品 (需优化):** {len(dogs)} 个")
            if dogs: st.error("、".join(dogs))
            else: st.caption("暂无")

# -----------------------------------------------------------------------------
# 11. 明细表格 (强制保留2位，移除类别列以实现完全合并)
# -----------------------------------------------------------------------------
st.markdown("### 📄 商品明细透视")

# 关键修复：Groupby 时不再包含 '商品类别'，只按 '商品名称' 聚合
group_cols = ['商品名称']
df_view = df_display.groupby(group_cols, as_index=False)[['销售数量', '销售金额', '商品毛利']].sum()
df_view = df_view.rename(columns={'商品毛利': '商品毛利额'})

df_view['商品毛利率'] = np.where(df_view['销售金额']>0, (df_view['商品毛利额']/df_view['销售金额'] * 100), 0)
total_rev = df_view['销售金额'].sum()
df_view['商品销售占比'] = np.where(total_rev>0, (df_view['销售金额']/total_rev * 100), 0)

df_view = df_view.sort_values('销售数量', ascending=False)
df_view['序号'] = range(1, len(df_view) + 1)
df_view = df_view.round(2)

# 选择列 (移除商品类别)
cols = ['序号', '商品名称', '销售数量', '销售金额', '商品毛利额', '商品毛利率', '商品销售占比']

with st.container(border=True):
    st.dataframe(
        df_view[cols],
        column_config={
            "序号": st.column_config.NumberColumn("排名", width="small"),
            "商品名称": st.column_config.TextColumn("商品名称", help="售卖的商品名称", width="medium"),
            "销售数量": st.column_config.ProgressColumn("销量 (杯)", format="%d", min_value=0, max_value=int(df_view['销售数量'].max())),
            "销售金额": st.column_config.NumberColumn("销售额", format="¥%.2f"),
            "商品毛利额": st.column_config.NumberColumn("毛利额", format="¥%.2f"),
            "商品毛利率": st.column_config.NumberColumn("毛利率", format="%.2f%%", help="越高越赚钱"),
            "商品销售占比": st.column_config.NumberColumn("销售占比", format="%.2f%%", help="占总销售额的比例"),
        },
        use_container_width=True,
        hide_index=True,
        height=500
    )
