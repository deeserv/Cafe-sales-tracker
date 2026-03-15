# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# =============================================================================
# 1. 业务逻辑配置
# =============================================================================
PROJECT_STORE_MAPPING = {
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）", "度咖啡（百度奎科店）"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"],
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"]
}

# 您的核心分类规则
CATEGORY_RULES = {
    "咖啡饮品": [
        "风味拿铁", "冰爽果咖", "SOE 冷萃", "SOE冷萃", "中式茶咖", "甄选咖啡", "优选咖啡", 
        "常规咖啡", "拿铁系列", "美式家族", "拿铁家族", "果C美式", "经典意式"
    ],
    "非咖啡饮品": [
        "清爽果茶", "手打柠", "新鲜果蔬汁", "原叶轻乳茶", "活力酸奶", "经典鲜果茶", 
        "柠檬茶", "原叶鲜奶茶", "经典奶茶", "不喝咖啡", "经典果茶", "果茶系列", "乳茶系列"
    ],
    "食品": [
        "多乐之日", "轻食甜品", "餐厅产品", "现烤烘焙", "烘焙甜品"
    ]
}

# =============================================================================
# 2. 核心算法：数据处理引擎 (多维度对账)
# =============================================================================
def logic_clean_data(df):
    if df.empty: return df
    
    df = df.copy().reset_index(drop=True)
    # 清理表头特殊字符
    df.columns = [str(c).strip().replace('\n', '').replace('\r', '').replace('`', '') for c in df.columns]
    
    rename_map = {
        '日期': '日期',
        '门店名称': '门店名称',
        '商品类别': '二级分类_原始',
        '商品实收': '销售金额_raw',
        '商品销量': '销售数量_raw',
        '商品退款数': '退款数量_raw'
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # 数值强制转换
    df['销售数量_raw'] = pd.to_numeric(df['销售数量_raw'], errors='coerce').fillna(0)
    df['销售金额_raw'] = pd.to_numeric(df['销售金额_raw'], errors='coerce').fillna(0)
    df['退款数量_raw'] = pd.to_numeric(df['退款数量_raw'], errors='coerce').fillna(0) if '退款数量_raw' in df.columns else 0
    
    # 🌟 严格对账逻辑：销售(830) - 退款(7) = 净销(823)
    df['销售杯数'] = df['销售数量_raw']
    df['净销售杯数'] = df['销售杯数'] - df['退款数量_raw']
    df['销售金额'] = df['销售金额_raw']
    
    # 字符串清理
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace('`', '').str.strip()
    
    # 日期解析与脏数据剔除
    df['日期_dt'] = pd.to_datetime(df['日期'], errors='coerce')
    df = df.dropna(subset=['日期_dt'])
    df['日期'] = df['日期_dt'].dt.strftime('%Y-%m-%d')
    
    # 项目映射
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(x, '其他项目')).values
    
    # 分类映射
    lookup = {sub: main for main, subs in CATEGORY_RULES.items() for sub in subs}
    df['二级分类'] = df['二级分类_原始'].str.strip()
    df['一级分类'] = df['二级分类'].map(lookup).fillna("其他")
    
    return df.reset_index(drop=True)

# =============================================================================
# 3. UI 样式适配
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡经营智能看板", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        section[data-testid="stSidebar"] div.stVerticalBlock { padding-top: 4rem !important; }
        div[data-testid="stMetric"] {
            background-color: #FFFFFF; padding: 15px !important;
            border-radius: 12px !important; border: 1px solid #E2E8F0 !important;
        }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# 4. 视图：分析看板
# =============================================================================
def view_dashboard():
    st.title("📊 顿角咖啡·智能经营分析")
    
    if 'raw_data' not in st.session_state: st.session_state.raw_data = pd.DataFrame()

    with st.sidebar.expander("📥 数据上传", expanded=True):
        files = st.file_uploader("点击上传企迈报表", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            all_dfs = []
            for f in files:
                try:
                    if f.name.endswith('.csv'):
                        try: df = pd.read_csv(f, encoding='utf-8')
                        except: df = pd.read_csv(f, encoding='gbk')
                    else: df = pd.read_excel(f)
                    all_dfs.append(df)
                except: pass
            if all_dfs:
                st.session_state.raw_data = pd.concat(all_dfs, ignore_index=True)
                st.success("数据已同步")

    if st.session_state.raw_data.empty:
        st.info("💡 请上传报表开始分析。已恢复分类筛选功能。")
        return

    # 全量清洗
    df_full = logic_clean_data(st.session_state.raw_data)
    
    # --- 侧边栏：控制中心 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 时间控制")
    available_dates = sorted(df_full['日期'].unique(), reverse=True)
    curr_date = st.sidebar.selectbox("当前查看日期", available_dates)
    
    enable_compare = st.sidebar.checkbox("开启环比对比")
    comp_date = None
    if enable_compare:
        remaining = [d for d in available_dates if d != curr_date]
        if remaining: comp_date = st.sidebar.selectbox("对比日期", remaining)

    st.sidebar.subheader("🔍 智能筛选")
    # 1. 项目筛选
    sel_proj = st.sidebar.multiselect("所属项目", sorted(df_full['所属项目'].unique()))
    df_pool = df_full if not sel_proj else df_full[df_full['所属项目'].isin(sel_proj)]
    
    # 2. 一级分类筛选
    sel_l1 = st.sidebar.multiselect("一级分类", sorted(df_pool['一级分类'].unique()))
    df_pool = df_pool if not sel_l1 else df_pool[df_pool['一级分类'].isin(sel_l1)]
    
    # 3. 二级分类筛选
    sel_l2 = st.sidebar.multiselect("商品类别 (二级)", sorted(df_pool['二级分类'].unique()))

    # --- 数据过滤函数 (同时应用于当前和对比日期) ---
    def filter_final(data, projects, l1s, l2s):
        temp = data.copy()
        if projects: temp = temp[temp['所属项目'].isin(projects)]
        if l1s: temp = temp[temp['一级分类'].isin(l1s)]
        if l2s: temp = temp[temp['二级分类'].isin(l2s)]
        return temp

    df_curr = df_full[df_full['日期'] == curr_date]
    df_curr = filter_final(df_curr, sel_proj, sel_l1, sel_l2)
    
    df_comp = pd.DataFrame()
    if enable_compare and comp_date:
        df_comp = df_full[df_full['日期'] == comp_date]
        df_comp = filter_final(df_comp, sel_proj, sel_l1, sel_l2)

    # --- 统计与看板 ---
    def get_stats(data):
        if data.empty: return 0, 0, 0, 0
        return data['销售杯数'].sum(), data['退款数量_raw'].sum(), data['净销售杯数'].sum(), data['销售金额'].sum()

    curr_g, curr_r, curr_n, curr_rev = get_stats(df_curr)
    comp_g, comp_r, comp_n, comp_rev = get_stats(df_comp)

    def delta(c, cp):
        return c - cp if enable_compare and cp != 0 else None

    st.subheader(f"📊 业务概览：{curr_date}" + (f" (环比 {comp_date})" if enable_compare else ""))
    
    # 第一行：销量对账
    st.markdown("#### 🛒 销量对账")
    col1, col2, col3 = st.columns(3)
    col1.metric("销售杯数 (总)", f"{curr_g:,.0f} 杯", delta=delta(curr_g, comp_g))
    col2.metric("退款杯数 (-)", f"{curr_r:,.0f} 杯", delta=delta(curr_r, comp_r), delta_color="inverse")
    col3.metric("净销售杯数 (=)", f"{curr_n:,.0f} 杯", delta=delta(curr_n, comp_n))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 第二行：财务核心
    st.markdown("#### 💰 财务表现")
    col4, col5 = st.columns(2)
    col4.metric("总营收金额 (净实收)", f"¥{curr_rev:,.2f}", delta=delta(curr_rev, comp_rev))
    avg = curr_rev / curr_n if curr_n != 0 else 0
    cp_avg = comp_rev / comp_n if not df_comp.empty and comp_n != 0 else 0
    col5.metric("单杯成交均价 (净)", f"¥{avg:.2f}", delta=delta(avg, cp_avg))

    # --- 明细表格 ---
    st.divider()
    st.subheader("📋 单品销售对账排行 (去规格汇总)")
    
    rank_curr = df_curr.groupby(['商品名称', '二级分类']).agg({
        '销售杯数': 'sum',
        '退款数量_raw': 'sum',
        '净销售杯数': 'sum',
        '销售金额': 'sum'
    }).rename(columns={'退款数量_raw': '退款杯数', '销售金额': '营收金额'})

    if enable_compare and not df_comp.empty:
        rank_comp = df_comp.groupby(['商品名称', '二级分类']).agg({'净销售杯数': 'sum'}).rename(columns={'净销售杯数': '对比净销量'})
        display_df = rank_curr.merge(rank_comp, on=['商品名称', '二级分类'], how='left').fillna(0)
        display_df['净销量变化'] = display_df['净销售杯数'] - display_df['对比净销量']
    else:
        display_df = rank_curr

    st.dataframe(display_df.sort_values('净销售杯数', ascending=False), use_container_width=True)

if __name__ == "__main__":
    init_ui()
    import plotly.express as px
    menu = st.sidebar.radio("导航", ["📊 经营看板", "⚙️ 配方中心"])
    if menu == "📊 经营看板":
        view_dashboard()
    else:
        st.title("⚙️ 成本配方中心")
        st.info("分类筛选功能已完整回归。")
