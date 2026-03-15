# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# =============================================================================
# 1. 业务逻辑配置：项目与分类规则
# =============================================================================
PROJECT_STORE_MAPPING = {
    "百度项目": ["百度", "度咖啡", "度小满", "鹏寰", "科技园", "百度大厦", "上研", "奎科"],
    "顿角项目": ["中信建投", "北京移动", "嘉铭中心", "天津联想", "小米", "快手", "悦读+", "新华三", "科大讯飞", "网易", "联想总部", "顿角咖啡"],
    "光大项目": ["光大咖啡", "光大银行"]
}

CATEGORY_RULES = {
    "咖啡饮品": ["风味拿铁", "冰爽果咖", "SOE 冷萃", "SOE冷萃", "中式茶咖", "甄选咖啡", "优选咖啡", "常规咖啡", "拿铁系列", "美式家族", "拿铁家族", "果C美式", "经典意式"],
    "非咖啡饮品": ["清爽果茶", "手打柠", "新鲜果蔬汁", "原叶轻乳茶", "活力酸奶", "经典鲜果茶", "柠檬茶", "原叶鲜奶茶", "经典奶茶", "不喝咖啡", "经典果茶", "果茶系列", "乳茶系列"],
    "食品": ["多乐之日", "轻食甜品", "餐厅产品", "现烤烘焙", "烘焙甜品"]
}

# =============================================================================
# 2. 核心算法：数据处理引擎 (多日多项目叠加)
# =============================================================================
def logic_clean_data(df):
    if df.empty: return df
    
    df = df.copy().reset_index(drop=True)
    # 清理表头
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

    # 数值转换
    for col in ['销售数量_raw', '销售金额_raw', '退款数量_raw']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 严格对账逻辑
    df['销售杯数'] = df['销售数量_raw']
    df['净销售杯数'] = df['销售杯数'] - df.get('退款数量_raw', 0)
    df['销售金额'] = df['销售金额_raw']
    
    # 字符串内容强力清洗
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace('`', '').str.strip()
    
    # 日期解析：保留能解析的行，剔除合计行
    df['日期_dt'] = pd.to_datetime(df['日期'], errors='coerce')
    df = df.dropna(subset=['日期_dt'])
    df['日期'] = df['日期_dt'].dt.strftime('%Y-%m-%d')
    
    # 1. 项目映射 (使用关键词包含逻辑，增强百度项目的识别)
    def map_project(store_name):
        store_name_str = str(store_name)
        for proj, keywords in PROJECT_STORE_MAPPING.items():
            if any(key in store_name_str for key in keywords):
                return proj
        return "其他项目"
    
    df['所属项目'] = df['门店名称'].apply(map_project)
    
    # 2. 分类映射
    lookup = {sub: main for main, subs in CATEGORY_RULES.items() for sub in subs}
    df['二级分类'] = df['二级分类_原始'].str.strip()
    df['一级分类'] = df['二级分类'].map(lookup).fillna("其他")
    
    return df.reset_index(drop=True)

# =============================================================================
# 3. UI 与 交互配置
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡经营决策系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        section[data-testid="stSidebar"] div.stVerticalBlock { padding-top: 4rem !important; }
        div[data-testid="stMetric"] { background-color: #FFFFFF; padding: 20px !important; border-radius: 12px !important; border: 1px solid #E2E8F0 !important; }
    </style>
    """, unsafe_allow_html=True)

def view_dashboard():
    st.title("📊 顿角咖啡·经营分析看板")
    
    # 初始化 session_state
    if 'raw_data' not in st.session_state:
        st.session_state.raw_data = pd.DataFrame()

    # --- 侧边栏：上传中心 ---
    with st.sidebar.expander("📥 数据上传 (支持多日期多项目叠加)", expanded=True):
        files = st.file_uploader("点击或拖拽上传报表", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            new_dfs = []
            for f in files:
                try:
                    df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f, encoding='utf-8', on_bad_lines='skip')
                except:
                    df = pd.read_csv(f, encoding='gbk', on_bad_lines='skip')
                new_dfs.append(df)
            
            if new_dfs:
                # 🌟 关键：将新上传的数据与旧数据合并
                combined = pd.concat([st.session_state.raw_data] + new_dfs, ignore_index=True)
                # 🌟 精准去重：防止重复上传同一份文件，但保留同一天不同店的数据
                # 我们根据日期、门店、商品名称、餐段、规格等特征来判断是否为重复行
                check_cols = [c for c in combined.columns if c in ['日期', '门店名称', '商品名称', '规格', '做法', '餐段', '订单来源', '商品实收', '商品销量']]
                st.session_state.raw_data = combined.drop_duplicates(subset=check_cols).reset_index(drop=True)
                st.success(f"✅ 同步成功！当前已加载 {len(st.session_state.raw_data)} 条销售记录")

        if st.button("🗑️ 清空所有缓存数据"):
            st.session_state.raw_data = pd.DataFrame()
            st.rerun()

    if st.session_state.raw_data.empty:
        st.info("💡 系统已就绪。请上传报表（如：1月5日顿角数据 + 1月5日百度数据）。")
        return

    # 清洗全量数据
    df_full = logic_clean_data(st.session_state.raw_data)
    
    # --- 侧边栏：分析控制 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 时间控制")
    available_dates = sorted(df_full['日期'].unique(), reverse=True)
    curr_date = st.sidebar.selectbox("查看日期", available_dates)
    
    enable_compare = st.sidebar.checkbox("开启环比分析")
    comp_date = None
    if enable_compare:
        remaining = [d for d in available_dates if d != curr_date]
        if remaining: comp_date = st.sidebar.selectbox("对比日期", remaining)

    st.sidebar.subheader("🔍 智能筛选")
    # 1. 项目联动
    all_projs = sorted(df_full['所属项目'].unique())
    sel_proj = st.sidebar.multiselect("所属项目", all_projs)
    df_p = df_full if not sel_proj else df_full[df_full['所属项目'].isin(sel_proj)]
    
    # 2. 门店联动 (🌟 补全门店筛选)
    all_stores = sorted(df_p['门店名称'].unique())
    sel_store = st.sidebar.multiselect("具体门店", all_stores)
    df_s = df_p if not sel_store else df_p[df_p['门店名称'].isin(sel_store)]
    
    # 3. 分类联动
    all_l1 = sorted(df_s['一级分类'].unique())
    sel_l1 = st.sidebar.multiselect("一级分类", all_l1)
    df_l1 = df_s if not sel_l1 else df_s[df_s['一级分类'].isin(sel_l1)]
    
    sel_l2 = st.sidebar.multiselect("二级分类 (类别)", sorted(df_l1['二级分类'].unique()))

    # --- 数据过滤引擎 ---
    def filter_data(data, projs, stores, l1s, l2s):
        tmp = data.copy()
        if projs: tmp = tmp[tmp['所属项目'].isin(projs)]
        if stores: tmp = tmp[tmp['门店名称'].isin(stores)]
        if l1s: tmp = tmp[tmp['一级分类'].isin(l1s)]
        if l2s: tmp = tmp[tmp['二级分类'].isin(l2s)]
        return tmp

    df_curr = df_full[df_full['日期'] == curr_date]
    df_curr = filter_data(df_curr, sel_proj, sel_store, sel_l1, sel_l2)
    
    df_comp = pd.DataFrame()
    if enable_compare and comp_date:
        df_comp = df_full[df_full['日期'] == comp_date]
        df_comp = filter_data(df_comp, sel_proj, sel_store, sel_l1, sel_l2)

    # --- 看板统计 ---
    def get_stats(data):
        if data.empty: return 0, 0, 0, 0
        return data['销售杯数'].sum(), data['退款数量_raw'].sum(), data['净销售杯数'].sum(), data['销售金额'].sum()

    cg, cr, cn, cv = get_stats(df_curr)
    pg, pr, pn, pv = get_stats(df_comp)

    def diff(c, p):
        return c - p if enable_compare and p != 0 else None

    st.subheader(f"📑 经营实况：{curr_date}" + (f" (环比 {comp_date})" if enable_compare else ""))
    
    # 核心指标卡
    st.markdown("##### 🛒 销售对账")
    c1, c2, c3 = st.columns(3)
    c1.metric("销售杯数 (总)", f"{cg:,.0f} 杯", delta=diff(cg, pg))
    c2.metric("退款杯数 (-)", f"{cr:,.0f} 杯", delta=diff(cr, pr), delta_color="inverse")
    c3.metric("净销售杯数 (=)", f"{cn:,.0f} 杯", delta=diff(cn, pn))
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### 💰 财务概览")
    c4, c5 = st.columns(2)
    c4.metric("总营收金额 (净实收)", f"¥{cv:,.2f}", delta=diff(cv, pv))
    avg = cv / cn if cn != 0 else 0
    p_avg = pv / pn if not df_comp.empty and pn != 0 else 0
    c5.metric("单杯成交均价", f"¥{avg:.2f}", delta=diff(avg, p_avg))

    # --- 商品排行表 ---
    st.divider()
    st.subheader("📋 单品销售排行 (去规格汇总)")
    
    rank_curr = df_curr.groupby(['商品名称', '二级分类']).agg({
        '销售杯数': 'sum',
        '退款数量_raw': 'sum',
        '净销售杯数': 'sum',
        '销售金额': 'sum'
    }).rename(columns={'退款数量_raw': '退款杯数', '销售金额': '营收金额'})

    if enable_compare and not df_comp.empty:
        rank_comp = df_comp.groupby(['商品名称', '二级分类']).agg({'净销售杯数': 'sum'}).rename(columns={'净销售杯数': '历史净销量'})
        display_df = rank_curr.merge(rank_comp, on=['商品名称', '二级分类'], how='left').fillna(0)
        display_df['销量变化'] = display_df['净销售杯数'] - display_df['历史净销量']
    else:
        display_df = rank_curr

    st.dataframe(display_df.sort_values('净销售杯数', ascending=False), use_container_width=True)

if __name__ == "__main__":
    init_ui()
    view_dashboard()
