# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import math
import glob

# -----------------------------------------------------------------------------
# 1. 核心配置与 CSS 注入 (UI 灵魂)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="顿角咖啡智能数据看板",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入自定义 CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
    img { border-radius: 12px; transition: transform 0.3s ease; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E2E8F0; }
    h1 { color: #0F172A; font-weight: 800; letter-spacing: -0.03em; }
    h3 { color: #334155; font-weight: 600; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; border-radius: 16px; border: 1px solid #F1F5F9;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); padding: 24px; transition: all 0.3s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px); box-shadow: 0 12px 20px -5px rgba(0, 0, 0, 0.1); border-color: #E2E8F0;
    }
    [data-testid="stMetricValue"] {
        font-size: 36px !important;
        background: -webkit-linear-gradient(120deg, #2563EB, #06B6D4);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #FFFFFF; padding: 8px; border-radius: 12px; }
    .stTabs [data-baseweb="tab"] { height: 44px; border-radius: 8px; border: none; color: #64748B; font-weight: 600; background-color: #F8FAFC; }
    .stTabs [aria-selected="true"] { background-color: #EFF6FF; color: #2563EB; }
    div[data-testid="stMultiSelect"] label { font-weight: bold; color: #2563EB; }
</style>
""", unsafe_allow_html=True)

# 尝试导入 Plotly
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

COLOR_PALETTE = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

# -----------------------------------------------------------------------------
# 2. 内置分类映射字典 (核心业务规则)
# -----------------------------------------------------------------------------
CATEGORY_MAPPING_DATA = [
    # === 咖啡饮品 ===
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "咖啡饮品", "二级分类": "奶咖家族"},
    {"一级分类": "咖啡饮品", "二级分类": "果C美式"},
    {"一级分类": "咖啡饮品", "二级分类": "手冲咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "优选咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "经典意式"},
    {"一级分类": "咖啡饮品", "二级分类": "甄选咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "soe冷萃"},
    {"一级分类": "咖啡饮品", "二级分类": "SOE冷萃"}, 
    {"一级分类": "咖啡饮品", "二级分类": "风味拿铁"},
    {"一级分类": "咖啡饮品", "二级分类": "冰爽果咖"},
    {"一级分类": "咖啡饮品", "二级分类": "中式茶咖"},
    # === 非咖啡饮品 ===
    {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"},
    {"一级分类": "非咖啡饮品", "二级分类": "经典鲜果茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "手打柠"},
    {"一级分类": "非咖啡饮品", "二级分类": "清爽果茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "新鲜果蔬汁"},
    {"一级分类": "非咖啡饮品", "二级分类": "不喝咖啡"},
    {"一级分类": "非咖啡饮品", "二级分类": "果茶系列"},
    {"一级分类": "非咖啡饮品", "二级分类": "抹茶家族"},
]

# -----------------------------------------------------------------------------
# 3. 本地存储系统
# -----------------------------------------------------------------------------
DATA_DIR = "data_storage"
COST_FILE_NAME = "cost_data.xlsx"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def save_uploaded_file(uploaded_file, file_type="sales"):
    if uploaded_file is None: return None
    if file_type == "cost":
        file_path = os.path.join(DATA_DIR, COST_FILE_NAME)
    else:
        file_path = os.path.join(DATA_DIR, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def get_saved_sales_files():
    files = glob.glob(os.path.join(DATA_DIR, "*"))
    exclude_files = [COST_FILE_NAME]
    sales_files = [f for f in files if os.path.basename(f) not in exclude_files and (f.endswith('.csv') or f.endswith('.xlsx') or f.endswith('.xls'))]
    sales_files.sort()
    return sales_files

def get_saved_config_file(file_name):
    path = os.path.join(DATA_DIR, file_name)
    return path if os.path.exists(path) else None

# -----------------------------------------------------------------------------
# 4. 数据加载与清洗 (增强型)
# -----------------------------------------------------------------------------
def load_data_from_path(file_path):
    if not file_path: return None
    try:
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            return pd.read_excel(file_path, engine='openpyxl')
        else:
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb18030']
            for enc in encodings:
                try: return pd.read_csv(file_path, encoding=enc)
                except: continue
    except Exception as e:
        st.error(f"读取文件出错: {e}")
    return None

def process_sales_dataframe(df_sales):
    if df_sales is None: return None
    # 1. 统一列名
    column_mapping = {'商品实收': '销售金额', '商品销量': '销售数量'}
    df_sales = df_sales.rename(columns=column_mapping)
    
    # 2. 剔除含有“合计/总计”的行 (防止数据翻倍)
    if '商品名称' in df_sales.columns:
        df_sales = df_sales[~df_sales['商品名称'].astype(str).str.contains("合计|总计|Total", na=False)]
        # 剔除商品名称为空的行
        df_sales = df_sales.dropna(subset=['商品名称'])

    # 3. 向下填充
    if '统计周期' in df_sales.columns: df_sales['统计周期'] = df_sales['统计周期'].ffill()
    if '门店名称' in df_sales.columns: df_sales['门店名称'] = df_sales['门店名称'].ffill()
    
    # 4. 数值转换
    numeric_cols = ['销售金额', '销售数量']
    for col in numeric_cols:
        if col in df_sales.columns:
            df_sales[col] = pd.to_numeric(
                df_sales[col].astype(str).str.replace(r'[¥$,￥]', '', regex=True), 
                errors='coerce'
            ).fillna(0)
    return df_sales

def merge_category_map(df_sales):
    """
    将销售数据的 '商品类别' 匹配到内置的 一级/二级分类。
    """
    if df_sales is None: return None
    
    # 准备映射参考表
    df_ref = pd.DataFrame(CATEGORY_MAPPING_DATA)
    df_ref['二级分类_clean'] = df_ref['二级分类'].astype(str).str.strip()
    df_ref = df_ref.drop_duplicates(subset=['二级分类_clean'])

    if '商品类别' in df_sales.columns:
        # 清洗销售表中的类别名称
        df_sales['商品类别_clean'] = df_sales['商品类别'].astype(str).str.strip()
        
        # 合并
        df_sales = pd.merge(
            df_sales, 
            df_ref[['一级分类', '二级分类', '二级分类_clean']], 
            left_on='商品类别_clean', 
            right_on='二级分类_clean', 
            how='left',
            suffixes=('', '_ref')
        )
        
        # 结果处理
        df_sales['一级分类'] = df_sales['一级分类'].fillna('未分类')
        # 如果匹配成功，二级分类用标准名，否则用原始名
        df_sales['二级分类'] = np.where(df_sales['二级分类'].isna(), df_sales['商品类别'], df_sales['二级分类'])
        
        # 彻底清理临时列
        df_sales = df_sales.drop(columns=['商品类别_clean', '二级分类_clean', '二级分类_ref'], errors='ignore')
    else:
        df_sales['一级分类'] = '未分类'
        df_sales['二级分类'] = '未分类'
        
    return df_sales

def merge_cost_data(df_sales, df_cost):
    if df_sales is None: return None
    if df_cost is not None:
        if '产品' in df_cost.columns: df_cost = df_cost.rename(columns={'产品': '商品名称'})
        if '成本' in df_cost.columns:
            df_cost['成本'] = pd.to_numeric(df_cost['成本'], errors='coerce').fillna(0)
            if df_cost['商品名称'].duplicated().any():
                df_cost = df_cost.groupby('商品名称', as_index=False)['成本'].mean()
            df_sales = pd.merge(df_sales, df_cost[['商品名称', '成本']], on='商品名称', how='left')
            df_sales['成本'] = df_sales['成本'].fillna(0)
            df_sales['商品毛利'] = df_sales['销售金额'] - (df_sales['销售数量'] * df_sales['成本'])
        else: df_sales['商品毛利'] = 0
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
# 5. 侧边栏布局与数据加载
# -----------------------------------------------------------------------------
logo_path = "logo.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, width=120)
else: st.sidebar.image("https://cdn-icons-png.flaticon.com/512/751/751621.png", width=100)

st.sidebar.markdown("## 顿角咖啡智能数据看板")

with st.sidebar.expander("💾 数据仓库管理", expanded=True):
    st.markdown("**💰 成本档案**")
    saved_cost_path = get_saved_config_file(COST_FILE_NAME)
    if saved_cost_path:
        st.success("✅ 已有存档")
        if st.checkbox("更新成本表?"):
            new_cost = st.file_uploader("上传新成本表", type=["xlsx", "csv"])
            if new_cost:
                save_uploaded_file(new_cost, "cost")
                st.rerun()
    else:
        new_cost = st.file_uploader("请上传成本表", type=["xlsx", "csv"])
        if new_cost:
            save_uploaded_file(new_cost, "cost")
            st.rerun()
            
    st.divider()
    st.markdown("**📤 上传销售数据**")
    new_sales = st.file_uploader("支持多选上传", type=["xlsx", "csv"], accept_multiple_files=True)
    if new_sales:
        for f in new_sales: save_uploaded_file(f, "sales")
        st.success(f"已存入 {len(new_sales)} 个文件!")
        st.rerun()

st.sidebar.subheader("📂 选择分析数据")
saved_sales_files = get_saved_sales_files()

if not saved_sales_files:
    st.sidebar.warning("仓库为空，请先上传数据。")
    df_final = None
else:
    file_names = [os.path.basename(f) for f in saved_sales_files]
    selected_files = st.sidebar.multiselect("勾选历史文件", file_names, default=file_names)
    
    if selected_files:
        all_dfs = []
        for fname in selected_files:
            fpath = os.path.join(DATA_DIR, fname)
            df = load_data_from_path(fpath)
            if df is not None:
                df = process_sales_dataframe(df)
                all_dfs.append(df)
        
        if all_dfs:
            df_merged = pd.concat(all_dfs, ignore_index=True)
            # 加载成本
            df_cost = load_data_from_path(get_saved_config_file(COST_FILE_NAME))
            df_merged = merge_cost_data(df_merged, df_cost)
            # 匹配分类
            df_final = merge_category_map(df_merged)
            st.sidebar.success(f"✅ 加载成功")
        else: df_final = None
    else: df_final = None

if df_final is None:
    st.markdown("<div style='text-align:center;padding:100px;'><h1>👋 欢迎回来</h1><p>请在左侧上传或勾选数据。</p></div>", unsafe_allow_html=True)
    st.stop()

# -----------------------------------------------------------------------------
# 6. 核心筛选与联动逻辑
# -----------------------------------------------------------------------------
with st.sidebar.expander("🛠️ 筛选与参数", expanded=True):
    # 门店筛选
    all_stores = sorted(list(df_final['门店名称'].dropna().unique()))
    selected_stores = st.multiselect("门店筛选", all_stores, placeholder="默认全选")
    if selected_stores: st.success(f"✅ 选中{len(selected_stores)}家店")
    
    # 品类级联筛选
    st.markdown("##### 🏷️ 品类多级筛选")
    # 提取有效一级分类 (排除空值)
    all_l1 = sorted([str(x) for x in df_final['一级分类'].unique() if pd.notna(x)])
    selected_l1 = st.multiselect("一级分类", all_l1, placeholder="默认全选")
    if selected_l1: st.success(f"✅ 已勾选一级")
    
    if selected_l1:
        available_l2 = sorted([str(x) for x in df_final[df_final['一级分类'].isin(selected_l1)]['二级分类'].unique() if pd.notna(x)])
    else:
        available_l2 = sorted([str(x) for x in df_final['二级分类'].unique() if pd.notna(x)])
    
    selected_l2 = st.multiselect("二级分类", available_l2, placeholder="默认全选")
    if selected_l2: st.success(f"✅ 已勾选二级")
    
    st.divider()
    # 周期逻辑
    available_periods = sorted(list(df_final['统计周期'].dropna().unique()))
    is_comparison_mode = False
    days_current = 5; days_previous = 5
    df_current = df_final.copy()
    df_previous = pd.DataFrame()

    if len(available_periods) >= 2:
        enable_comparison = st.checkbox("开启环比分析", value=True)
        if enable_comparison:
            is_comparison_mode = True
            p_current = st.selectbox("本期", available_periods, index=len(available_periods)-1)
            p_previous = st.selectbox("上期 (对比)", [p for p in available_periods if p != p_current], index=0)
            c1_day, c2_day = st.columns(2)
            days_current = c1_day.number_input("本期天数", 1, 31, 5)
            days_previous = c2_day.number_input("上期天数", 1, 31, 5)
            df_current = df_final[df_final['统计周期'] == p_current].copy()
            df_previous = df_final[df_final['统计周期'] == p_previous].copy()
        else:
            selected_periods = st.multiselect("周期选择", available_periods, default=available_periods)
            days_current = st.number_input("营业天数", 1, 31, 5)
            df_current = df_final[df_final['统计周期'].isin(selected_periods)].copy()
    else:
        days_current = st.number_input("营业天数", 1, 31, 5)

# 应用筛选
if selected_stores:
    df_current = df_current[df_current['门店名称'].isin(selected_stores)]
    if not df_previous.empty: df_previous = df_previous[df_previous['门店名称'].isin(selected_stores)]
if selected_l1:
    df_current = df_current[df_current['一级分类'].isin(selected_l1)]
    if not df_previous.empty: df_previous = df_previous[df_previous['一级分类'].isin(selected_l1)]
if selected_l2:
    df_current = df_current[df_current['二级分类'].isin(selected_l2)]
    if not df_previous.empty: df_previous = df_previous[df_previous['二级分类'].isin(selected_l2)]

# -----------------------------------------------------------------------------
# 7. 搜索与主界面
# -----------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 商品/组合搜索")
# 修复 TypeError: 强制转字符串再排序
all_prods = sorted([str(x) for x in df_current['商品名称'].unique() if pd.notna(x)])
search_products = st.sidebar.multiselect("搜索商品", all_prods)

st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf?auto=format&fit=crop&w=1200&h=250&q=80", use_container_width=True)
st.title("📊 顿角咖啡智能数据看板")

if df_current.empty:
    st.warning("⚠️ 当前筛选结果为空，请调整侧边栏的分类或门店选项。")
    st.stop()

# 计算 KPI
cur_qty, cur_amt, cur_profit, cur_cup_price, cur_margin, cur_daily_qty, cur_daily_amt = calculate_metrics(df_current, days_current)
if is_comparison_mode and not df_previous.empty:
    prev_qty, prev_amt, _, prev_cup_price, prev_margin, prev_daily_qty, prev_daily_amt = calculate_metrics(df_previous, days_previous)
    delta_qty = ((cur_qty - prev_qty) / prev_qty) if prev_qty != 0 else 0
    delta_amt = ((cur_amt - prev_amt) / prev_amt) if prev_amt != 0 else 0
    delta_price = ((cur_cup_price - prev_cup_price) / prev_cup_price) if prev_cup_price != 0 else 0
    delta_margin = cur_margin - prev_margin
    delta_daily_qty = ((cur_daily_qty - prev_daily_qty) / prev_daily_qty) if prev_daily_qty != 0 else 0
    delta_daily_amt = ((cur_daily_amt - prev_daily_amt) / prev_daily_amt) if prev_daily_amt != 0 else 0
else: delta_qty = delta_amt = delta_price = delta_margin = delta_daily_qty = delta_daily_amt = None

# KPI 展示
def metric_card(title, value, delta, prefix="", suffix="", is_percent=False):
    d_str = f"{delta:+.2f} pts" if is_percent and delta is not None else (f"{delta:+.2%}" if delta is not None else None)
    with st.container(border=True):
        st.metric(title, f"{prefix}{value}{suffix}", d_str, delta_color="inverse")

st.subheader("📦 核心经营指标")
c1, c2, c3 = st.columns(3)
with c1: metric_card("总销量", int(cur_qty), delta_qty, suffix=" 杯")
with c2: metric_card("总营收", f"{cur_amt:,.2f}", delta_amt, prefix="¥")
with c3: metric_card("平均毛利率", f"{cur_margin:.2f}", delta_margin, suffix="%", is_percent=True)

st.subheader("🚀 日均效率指标")
c4, c5, c6 = st.columns(3)
with c4: metric_card("日均杯数", f"{cur_daily_qty:.1f}", delta_daily_qty, suffix=" 杯")
with c5: metric_card("日均营收", f"{cur_daily_amt:,.2f}", delta_daily_amt, prefix="¥")
with c6: metric_card("杯单价", f"{cur_cup_price:.2f}", delta_price, prefix="¥")

# --- 🎯 组合/单品深度透视 ---
if search_products:
    st.markdown("---")
    st.markdown(f"### 🎯 搜索透视: {', '.join(search_products)}")
    prod_curr = df_current[df_current['商品名称'].isin(search_products)]
    p_qty = prod_curr['销售数量'].sum()
    p_amt = prod_curr['销售金额'].sum()
    
    with st.container(border=True):
        cp1, cp2, cp3 = st.columns(3)
        cp1.metric("选中商品销量", f"{int(p_qty)} 杯")
        cp2.metric("选中商品营收", f"¥{p_amt:,.2f}")
        contribution = (p_amt / cur_amt) if cur_amt > 0 else 0
        cp3.metric("营收贡献占比", f"{contribution:.2%}")
    
    # 门店售卖排行
    store_rank = prod_curr.groupby('门店名称', as_index=False)['销售数量'].sum().sort_values('销售数量', ascending=True)
    if PLOTLY_AVAILABLE:
        fig_p = px.bar(store_rank, y='门店名称', x='销售数量', orientation='h', text='销售数量', title="各门店选中商品销量分布")
        fig_p.update_traces(texttemplate='%{text:.1f}', textposition='outside', marker_color='#3B82F6')
        st.plotly_chart(fig_p, use_container_width=True)

# -----------------------------------------------------------------------------
# 8. 图表展示区域 (去除了 BCG)
# -----------------------------------------------------------------------------
st.markdown("---")
c_left, c_right = st.columns(2)

df_chart = df_current.groupby('商品名称', as_index=False).agg({'销售数量':'sum', '销售金额':'sum', '商品毛利':'sum'})

with c_left:
    with st.container(border=True):
        st.markdown("##### 🔥 销量排行 (Top 10)")
        top10 = df_chart.sort_values('销售数量', ascending=True).tail(10)
        if PLOTLY_AVAILABLE:
            fig1 = px.bar(top10, y='商品名称', x='销售数量', orientation='h', text='销售数量')
            fig1.update_traces(texttemplate='%{text:.1f}', textposition='outside', marker_color='#10B981')
            st.plotly_chart(fig1, use_container_width=True)

with c_right:
    with st.container(border=True):
        st.markdown("##### 🏆 利润贡献排行")
        t1, t2 = st.tabs(["一级分类", "二级分类"])
        with t1:
            l1_profit = df_current.groupby('一级分类', as_index=False)['商品毛利'].sum().sort_values('商品毛利', ascending=True)
            if PLOTLY_AVAILABLE:
                fig2 = px.bar(l1_profit, y='一级分类', x='商品毛利', orientation='h', color='商品毛利', color_continuous_scale='Mint')
                st.plotly_chart(fig2, use_container_width=True)
        with t2:
            l2_profit = df_current.groupby('二级分类', as_index=False)['商品毛利'].sum().sort_values('商品毛利', ascending=True)
            if PLOTLY_AVAILABLE:
                fig3 = px.bar(l2_profit, y='二级分类', x='商品毛利', orientation='h', color='商品毛利', color_continuous_scale='Teal')
                st.plotly_chart(fig3, use_container_width=True)

# 品类涨跌 (日均变动)
if is_comparison_mode and not df_previous.empty:
    st.markdown("### 📈 二级分类日均销量涨跌")
    cat_curr = df_current.groupby('二级分类')['销售数量'].sum() / days_current
    cat_prev = df_previous.groupby('二级分类')['销售数量'].sum() / days_previous
    cat_diff = (cat_curr - cat_prev).fillna(0).reset_index()
    cat_diff.columns = ['二级分类', '变动值']
    cat_diff = cat_diff.sort_values('变动值')
    cat_diff['颜色'] = np.where(cat_diff['变动值']>=0, '#EF4444', '#10B981')
    
    with st.container(border=True):
        if PLOTLY_AVAILABLE:
            fig_diff = px.bar(cat_diff, y='二级分类', x='变动值', text='变动值')
            fig_diff.update_traces(marker_color=cat_diff['颜色'], texttemplate='%{text:+.2f}')
            st.plotly_chart(fig_diff, use_container_width=True)

# -----------------------------------------------------------------------------
# 9. 明细表格
# -----------------------------------------------------------------------------
st.markdown("### 📄 商品经营明细")
agg_dict = {'一级分类': 'first', '二级分类': 'first', '销售数量': 'sum', '销售金额': 'sum', '商品毛利': 'sum'}
df_view = df_current.groupby('商品名称', as_index=False).agg(agg_dict)
df_view['毛利率'] = (df_view['商品毛利'] / df_view['销售金额'] * 100).fillna(0)
df_view = df_view.sort_values('销售数量', ascending=False).round(2)

with st.container(border=True):
    st.dataframe(df_view, column_config={
        "销售数量": st.column_config.NumberColumn("总销量", format="%d"),
        "销售金额": st.column_config.NumberColumn("营收", format="¥%.2f"),
        "毛利率": st.column_config.NumberColumn("毛利率", format="%.2f%%"),
    }, use_container_width=True, hide_index=True)
    
