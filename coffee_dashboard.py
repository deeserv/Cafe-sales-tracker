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

# 注入自定义 CSS 以实现精致的商务视觉效果
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
# 2. 内置分类字典 (Hardcoded Categories)
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
# 3. 本地数据仓库管理系统
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
    if os.path.exists(path): return path
    return None

# -----------------------------------------------------------------------------
# 4. 数据加载与清洗函数
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
        st.error(f"读取文件出错 {file_path}: {e}")
    return None

def process_sales_dataframe(df_sales):
    if df_sales is None: return None
    # 统一列名
    column_mapping = {'商品实收': '销售金额', '商品销量': '销售数量'}
    df_sales = df_sales.rename(columns=column_mapping)
    # 向下填充
    if '统计周期' in df_sales.columns: df_sales['统计周期'] = df_sales['统计周期'].ffill()
    if '门店名称' in df_sales.columns: df_sales['门店名称'] = df_sales['门店名称'].ffill()
    # 数值转换
    numeric_cols = ['销售金额', '销售数量']
    for col in numeric_cols:
        if col in df_sales.columns:
            df_sales[col] = pd.to_numeric(
                df_sales[col].astype(str).str.replace(r'[¥$,￥]', '', regex=True), 
                errors='coerce'
            ).fillna(0)
    return df_sales

def merge_category_map(df_sales):
    """使用内置字典合并分类，增强鲁棒性"""
    if df_sales is None: return None
    
    if '商品类别' in df_sales.columns:
        df_cat = pd.DataFrame(CATEGORY_MAPPING_DATA)
        df_cat['一级分类'] = df_cat['一级分类'].astype(str).str.strip()
        df_cat['二级分类'] = df_cat['二级分类'].astype(str).str.strip()
        df_sales['商品类别_match'] = df_sales['商品类别'].astype(str).str.strip()
        
        # 去重防止翻倍
        df_cat = df_cat.drop_duplicates(subset=['二级分类'])
        
        # 合并
        df_sales = pd.merge(df_sales, df_cat, left_on='商品类别_match', right_on='二级分类', how='left', suffixes=('', '_map'))
        
        # 填充一级分类，如果没匹配上显示为未分类
        df_sales['一级分类'] = df_sales['一级分类'].fillna('未分类')
        # 二级分类即原始商品类别
        df_sales['二级分类'] = df_sales['商品类别']
        
        # 清理中间列
        drop_list = ['商品类别_match', '二级分类_map']
        df_sales = df_sales.drop(columns=[c for c in drop_list if c in df_sales.columns], errors='ignore')
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
        else:
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
# 5. 侧边栏布局
# -----------------------------------------------------------------------------
logo_path = "logo.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, width=120)
else: st.sidebar.image("https://cdn-icons-png.flaticon.com/512/751/751621.png", width=100)

st.sidebar.markdown("## 顿角咖啡智能数据看板")
st.sidebar.caption("Dunjiao Coffee · Intelligent BI System")

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
        st.warning("⚠️ 暂无")
        new_cost = st.file_uploader("请上传成本表", type=["xlsx", "csv"])
        if new_cost:
            save_uploaded_file(new_cost, "cost")
            st.rerun()
            
    st.divider()
    st.markdown("**📤 上传销售数据**")
    new_sales = st.file_uploader("支持多选上传", type=["xlsx", "csv"], accept_multiple_files=True)
    if new_sales:
        for f in new_sales:
            save_uploaded_file(f, "sales")
        st.success(f"成功存入 {len(new_sales)} 个文件!")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📂 选择分析数据")
saved_sales_files = get_saved_sales_files()

if not saved_sales_files:
    st.sidebar.warning("仓库为空，请先在上方上传数据。")
    df_final = None
else:
    file_names = [os.path.basename(f) for f in saved_sales_files]
    selected_files = st.sidebar.multiselect("请勾选要分析的历史文件", file_names, default=file_names, placeholder="请选择")
    
    if selected_files:
        all_dfs = []
        for fname in selected_files:
            fpath = os.path.join(DATA_DIR, fname)
            df = load_data_from_path(fpath)
            if df is not None:
                df = process_sales_dataframe(df)
                all_dfs.append(df)
        
        if all_dfs:
            df_sales_merged = pd.concat(all_dfs, ignore_index=True)
            df_cost = None
            if saved_cost_path:
                df_cost = load_data_from_path(saved_cost_path)
            df_sales_merged = merge_cost_data(df_sales_merged, df_cost)
            df_final = merge_category_map(df_sales_merged)
            st.sidebar.success(f"已加载 {len(selected_files)} 个周期数据")
        else: df_final = None
    else: df_final = None

if df_final is None:
    st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf?auto=format&fit=crop&w=1200&h=250&q=80", use_container_width=True)
    st.markdown("<div style='text-align:center;padding:40px;'><h1>👋 欢迎回来</h1><p>请在左侧 <b>“数据仓库管理”</b> 中上传或勾选数据。</p></div>", unsafe_allow_html=True)
    st.stop()

# -----------------------------------------------------------------------------
# 6. 核心筛选逻辑
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
    if selected_stores: st.success(f"✅ 选中 {len(selected_stores)} 家门店")
    
    st.markdown("##### 🏷️ 品类筛选")
    all_l1_cats = sorted([str(x) for x in df_final['一级分类'].dropna().unique()])
    selected_l1 = st.multiselect("一级分类", all_l1_cats, placeholder="默认全选")
    
    if selected_l1:
        available_l2 = sorted([str(x) for x in df_final[df_final['一级分类'].isin(selected_l1)]['二级分类'].dropna().unique()])
    else:
        available_l2 = sorted([str(x) for x in df_final['二级分类'].dropna().unique()])
    selected_l2 = st.multiselect("二级分类", available_l2, placeholder="默认全选")
    
    st.divider()

    if len(available_periods) >= 2:
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

# 执行筛选
if selected_stores:
    if not df_current.empty: df_current = df_current[df_current['门店名称'].isin(selected_stores)]
    if not df_previous.empty: df_previous = df_previous[df_previous['门店名称'].isin(selected_stores)]
if selected_l1:
    if not df_current.empty: df_current = df_current[df_current['一级分类'].isin(selected_l1)]
    if not df_previous.empty: df_previous = df_previous[df_previous['一级分类'].isin(selected_l1)]
if selected_l2:
    if not df_current.empty: df_current = df_current[df_current['二级分类'].isin(selected_l2)]
    if not df_previous.empty: df_previous = df_previous[df_previous['二级分类'].isin(selected_l2)]

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

# 新品搜索 (修复 TypeError)
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 新品/组合搜索")
all_products_list = sorted([str(x) for x in df_current['商品名称'].unique().tolist()]) if not df_current.empty else []
search_products = st.sidebar.multiselect("选择商品名称", all_products_list, placeholder="可多选")

# -----------------------------------------------------------------------------
# 7. 主界面渲染
# -----------------------------------------------------------------------------
st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf?auto=format&fit=crop&w=1200&h=250&q=80", use_container_width=True)
c_title, c_period = st.columns([2, 1])
with c_title: st.title("📊 顿角咖啡智能数据看板")
with c_period:
    if is_comparison_mode:
        st.markdown(f"<div style='text-align:right; padding-top:10px; color:#64748B;'><b>分析周期</b><br><span style='color:#3B82F6; font-size:1.1em'>{p_current}</span> vs <span style='color:#94A3B8'>{p_previous}</span></div>", unsafe_allow_html=True)
st.markdown("---")

def update_chart_layout(fig):
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_family="Inter", font_color="#4B5563", margin=dict(l=20, r=20, t=40, b=20))
    return fig

if df_current.empty:
    st.warning("⚠️ 当前筛选结果为空。")
    st.stop()

# --- 🎯 组合透视 ---
if search_products:
    title_text = f"🎯 单品透视：<span style='color:#2563EB'>{search_products[0]}</span>" if len(search_products) == 1 else f"🎯 组合透视 ({len(search_products)}个商品)"
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
        if saved_cost_path:
            prod_card(col_p3, "综合毛利率", f"{p_margin:.2f}%", p_delta_margin, sub_text="💰 组合盈利能力")
        else: col_p3.metric("毛利率", "--")
        avg_margin_all = (df_current['商品毛利'].sum() / df_current['销售金额'].sum()) if df_current['销售金额'].sum() > 0 else 0
        my_margin = p_margin / 100
        tag = "💎 高利组合" if my_margin >= avg_margin_all else "📦 走量组合"
        tag_color = "blue" if my_margin >= avg_margin_all else "orange"
        col_p4.markdown(f"**🤖 组合诊断**")
        col_p4.markdown(f":{tag_color}[**{tag}**]")
        col_p4.caption(f"全店平均毛利: {avg_margin_all:.1%}")

    st.markdown("##### 🏠 组合各门店售卖表现 (合计销量)")
    prod_store_df = prod_curr.groupby('门店名称', as_index=False).agg({'销售数量':'sum', '销售金额':'sum', '商品毛利':'sum'})
    prod_store_df = prod_store_df.sort_values('销售数量', ascending=True) 
    prod_store_df['销售数量'] = prod_store_df['销售数量'].round(2)
    if not prod_store_df.empty:
        with st.container(border=True):
            if PLOTLY_AVAILABLE:
                fig_store = px.bar(prod_store_df, y='门店名称', x='销售数量', orientation='h', text='销售数量', color='销售数量', color_continuous_scale='Blues', hover_data={'销售数量':':.2f', '销售金额':':.2f', '商品毛利':':.2f'}, title=f"各门店合计销量")
                fig_store.update_traces(textposition='outside', texttemplate='%{text:,.2f}') 
                fig_height = max(400, len(prod_store_df) * 40)
                fig_store.update_layout(coloraxis_showscale=False, height=fig_height)
                fig_store = update_chart_layout(fig_store)
                st.plotly_chart(fig_store, use_container_width=True)
            else: st.bar_chart(prod_store_df.set_index('门店名称')['销售数量'])
    else: st.info("所选商品无销售记录。")
    st.markdown("---")

# --- 全局 KPI ---
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
    if saved_cost_path:
        metric_card("平均毛利率", f"{cur_margin:.2f}", delta_margin, suffix="%", is_percent=True, icon="📈")
    else:
        with st.container(border=True): st.metric("📈 平均毛利率", "--")

st.markdown("---")

# --- 图表区域 ---
df_chart_data = df_current.groupby('商品名称', as_index=False).agg({'销售数量':'sum', '销售金额':'sum', '商品毛利':'sum'})

c1, c2 = st.columns(2)
with c1:
    with st.container(border=True):
        st.markdown("##### 🔥 本期销量排行 (Top 10)")
        top_sales = df_chart_data.sort_values('销售数量', ascending=True).tail(10)
        top_sales['销售数量'] = top_sales['销售数量'].round(2)
        if PLOTLY_AVAILABLE:
            fig = px.bar(top_sales, y='商品名称', x='销售数量', orientation='h', text='销售数量', color_discrete_sequence=[COLOR_PALETTE[0]])
            fig.update_traces(textposition='outside', texttemplate='%{text:,.2f}')
            fig = update_chart_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
        else: st.bar_chart(top_sales.set_index('商品名称')['销售数量'])

with c2:
    with st.container(border=True):
        if saved_cost_path:
            st.markdown("##### 🏆 利润贡献排行")
            tab_cat, tab_prod = st.tabs(["📂 按分类", "☕️ 按单品"])
            total_profit = df_chart_data['商品毛利'].sum()
            with tab_cat:
                if '一级分类' in df_current.columns:
                    df_cat = df_current.groupby('一级分类', as_index=False)['商品毛利'].sum().sort_values('商品毛利', ascending=True)
                    df_cat['商品毛利'] = df_cat['商品毛利'].round(2)
                    df_cat['贡献率'] = np.where(total_profit>0, df_cat['商品毛利']/total_profit, 0)
                    if PLOTLY_AVAILABLE:
                        fig_cat = px.bar(df_cat, y='一级分类', x='商品毛利', orientation='h', text=df_cat['贡献率'].apply(lambda x: f"{x:.2%}"), color='商品毛利', color_continuous_scale='Mint', labels={'商品毛利':'毛利额'})
                        fig_cat.update_traces(textposition='outside')
                        fig_cat.update_layout(coloraxis_showscale=False)
                        fig_cat = update_chart_layout(fig_cat)
                        st.plotly_chart(fig_cat, use_container_width=True)
                else: st.info("分类映射未加载")
            with tab_prod:
                df_prod = df_chart_data.sort_values('商品毛利', ascending=True).tail(10)
                df_prod['商品毛利'] = df_prod['商品毛利'].round(2)
                df_prod['贡献率'] = np.where(total_profit>0, df_prod['商品毛利']/total_profit, 0)
                if PLOTLY_AVAILABLE:
                    fig_prod = px.bar(df_prod, y='商品名称', x='商品毛利', orientation='h', text=df_prod['贡献率'].apply(lambda x: f"{x:.2%}"), color='商品毛利', color_continuous_scale='Oranges', labels={'商品毛利':'毛利额'})
                    fig_prod.update_traces(textposition='outside')
                    fig_prod.update_layout(coloraxis_showscale=False)
                    fig_prod = update_chart_layout(fig_prod)
                    st.plotly_chart(fig_prod, use_container_width=True)
        else: st.info("请上传成本档案")

# --- 品类涨跌 (日均) ---
if is_comparison_mode and '二级分类' in df_current.columns:
    st.markdown("### 📈 品类涨跌风向标 (日均杯数变动)")
    cat_col = '二级分类'
    cat_curr = df_current.groupby(cat_col)['销售数量'].sum().reset_index()
    cat_curr['日均杯数'] = cat_curr['销售数量'] / days_current
    
    if not df_previous.empty:
        cat_prev = df_previous.groupby(cat_col)['销售数量'].sum().reset_index()
        cat_prev['日均杯数'] = cat_prev['销售数量'] / days_previous
    else:
        cat_prev = pd.DataFrame(columns=[cat_col, '销售数量', '日均杯数'])
    
    cat_diff = pd.merge(cat_curr, cat_prev, on=cat_col, suffixes=('_curr', '_prev'), how='outer').fillna(0)
    cat_diff['日均杯数变动'] = cat_diff['日均杯数_curr'] - cat_diff['日均杯数_prev']
    cat_diff['日均杯数变动'] = cat_diff['日均杯数变动'].round(2)
    cat_diff = cat_diff.sort_values('日均杯数变动', ascending=True)
    cat_diff['颜色'] = np.where(cat_diff['日均杯数变动'] >= 0, '#EF4444', '#10B981')
    
    with st.container(border=True):
        if PLOTLY_AVAILABLE:
            fig_diff = px.bar(cat_diff, y=cat_col, x='日均杯数变动', text='日均杯数变动', orientation='h', title=f"[{cat_col}] 日均变化 (杯)")
            fig_diff.update_traces(marker_color=cat_diff['颜色'], texttemplate='%{text:+.2f}杯')
            fig_diff.update_layout(yaxis={'categoryorder':'total ascending'})
            fig_diff = update_chart_layout(fig_diff)
            st.plotly_chart(fig_diff, use_container_width=True)
        else: st.bar_chart(cat_diff.set_index(cat_col)['日均杯数变动'])

st.markdown("---")

# --- 单店透视 (分页) ---
if is_comparison_mode and '二级分类' in df_current.columns:
    st.markdown("### 🏪 门店品类涨跌透视 (Store Deep Dive)")
    st.caption("分析选定门店的细分品类日均销量变化。")
    all_store_list_dd = sorted(df_current['门店名称'].unique().tolist())
    cat_col = '二级分类'
    
    if all_store_list_dd:
        c_sel, _ = st.columns([1, 2])
        with c_sel: selected_store_dd = st.selectbox("👉 请选择要分析的门店", all_store_list_dd)
        
        store_curr = df_current[df_current['门店名称'] == selected_store_dd]
        store_prev = df_previous[df_previous['门店名称'] == selected_store_dd] if not df_previous.empty else pd.DataFrame()
        
        s_day_c = store_curr['销售数量'].sum() / days_current
        s_day_p = (store_prev['销售数量'].sum() / days_previous) if not store_prev.empty else 0
        s_delta = (s_day_c - s_day_p)
        
        sc_curr = store_curr.groupby(cat_col, as_index=False)['销售数量'].sum()
        sc_curr['日均'] = sc_curr['销售数量'] / days_current
        sc_prev = store_prev.groupby(cat_col, as_index=False)['销售数量'].sum() if not store_prev.empty else pd.DataFrame(columns=[cat_col, '销售数量'])
        sc_prev['日均'] = sc_prev['销售数量'] / days_previous
            
        sc_merge = pd.merge(sc_curr, sc_prev, on=cat_col, suffixes=('_curr', '_prev'), how='outer').fillna(0)
        sc_merge['变动'] = sc_merge['日均_curr'] - sc_merge['日均_prev']
        sc_merge['变动'] = sc_merge['变动'].round(2)
        sc_merge = sc_merge.sort_values('变动', ascending=True) 
        
        with st.container(border=True):
            c_s_kpi, c_s_chart = st.columns([1, 2])
            with c_s_kpi:
                st.markdown(f"#### 🏠 {selected_store_dd}")
                st.metric("总日均杯数", f"{s_day_c:.1f}", f"{s_delta:+.1f} 杯", delta_color="inverse")
                st.divider()
                st.markdown(f"**📋 {cat_col}变动详情**")
                st.dataframe(sc_merge[[cat_col, '变动']].sort_values('变动', ascending=False), column_config={"变动": st.column_config.NumberColumn("变化", format="%+.2f 杯")}, hide_index=True, use_container_width=True, height=200)
            with c_s_chart:
                if PLOTLY_AVAILABLE:
                    sc_merge['颜色'] = np.where(sc_merge['变动'] >= 0, '#EF4444', '#10B981')
                    fig_s = px.bar(sc_merge, y=cat_col, x='变动', text='变动', orientation='h', title=f"{selected_store_dd} 品类日均变动")
                    fig_s.update_traces(marker_color=sc_merge['颜色'], texttemplate='%{text:+.2f}')
                    fig_s = update_chart_layout(fig_s)
                    st.plotly_chart(fig_s, use_container_width=True)
    else: st.info("当前无门店数据。")

# --- 明细表格 ---
st.markdown("### 📄 商品明细透视")
agg_dict = {'销售数量': 'sum', '销售金额': 'sum', '商品毛利': 'sum'}
if '一级分类' in df_current.columns: agg_dict['一级分类'] = lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0]
if '二级分类' in df_current.columns: agg_dict['二级分类'] = lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0]

df_view = df_current.groupby('商品名称', as_index=False).agg(agg_dict)
df_view = df_view.rename(columns={'商品毛利': '商品毛利额'})
df_view['商品毛利率'] = np.where(df_view['销售金额']>0, (df_view['商品毛利额']/df_view['销售金额'] * 100), 0)
total_rev = df_view['销售金额'].sum()
df_view['商品销售占比'] = np.where(total_rev>0, (df_view['销售金额']/total_rev * 100), 0)
conditions = [(df_view['商品毛利率'] >= 99.9), (df_view['商品毛利率'] < 60), (df_view['商品毛利率'] >= 60) & (df_view['商品毛利率'] <= 65)]
choices = ['⚠️ 缺成本', '🔴 低毛利', '🟡 毛利预警']
df_view['健康度'] = np.select(conditions, choices, default='🟢 健康')
df_view = df_view.sort_values('销售数量', ascending=False)
df_view['序号'] = range(1, len(df_view) + 1)
df_view = df_view.round(2)
cols = ['序号', '商品名称', '健康度', '一级分类', '二级分类', '销售数量', '销售金额', '商品毛利额', '商品毛利率', '商品销售占比']

with st.container(border=True):
    st.dataframe(df_view[cols], column_config={
        "序号": st.column_config.NumberColumn("排名", width="small"),
        "销售数量": st.column_config.ProgressColumn("杯数", format="%d", min_value=0, max_value=int(df_view['销售数量'].max())),
        "销售金额": st.column_config.NumberColumn("销售额", format="¥%.2f"),
        "商品毛利额": st.column_config.NumberColumn("毛利", format="¥%.2f"),
        "商品毛利率": st.column_config.NumberColumn("毛利率", format="%.2f%%"),
    }, use_container_width=True, hide_index=True, height=500)
