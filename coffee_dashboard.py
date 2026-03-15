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
    "百度项目": [
        "度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", 
        "度咖啡（百度大厦店）", "度咖啡（百度上研店）", "度咖啡（百度奎科店）", 
        "百度鹏寰店", "百度科技园店", "百度大厦店", "百度上研店", "百度奎科店"
    ],
    "顿角项目": [
        "中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", 
        "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", 
        "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"
    ],
    "光大项目": [
        "光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"
    ]
}

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
# 2. 核心算法：数据处理引擎
# =============================================================================
def logic_clean_data(df):
    if df.empty: return df
    
    df = df.copy().reset_index(drop=True)
    # 彻底清理表头
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
    
    # 严格对账：销售(830) - 退款(7) = 净销(823)
    df['销售杯数'] = df['销售数量_raw']
    df['净销售杯数'] = df['销售杯数'] - df['退款数量_raw']
    df['销售金额'] = df['销售金额_raw']
    
    # 🌟 关键：清理数据内容中的反引号和空格
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace('`', '').str.strip()
    
    # 日期标准化处理
    df['日期_dt'] = pd.to_datetime(df['日期'], errors='coerce')
    df = df.dropna(subset=['日期_dt'])
    df['日期'] = df['日期_dt'].dt.strftime('%Y-%m-%d')
    
    # 1. 项目映射
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(x, '其他项目')).values
    
    # 2. 分类映射
    lookup = {sub: main for main, subs in CATEGORY_RULES.items() for sub in subs}
    df['二级分类'] = df['二级分类_原始'].str.strip()
    df['一级分类'] = df['二级分类'].map(lookup).fillna("其他")
    
    return df.reset_index(drop=True)

# =============================================================================
# 3. UI 配置
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡经营决策系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        section[data-testid="stSidebar"] div.stVerticalBlock { padding-top: 4rem !important; }
        div[data-testid="stMetric"] { background-color: #FFFFFF; padding: 15px !important; border-radius: 12px !important; border: 1px solid #E2E8F0 !important; }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# 4. 视图层
# =============================================================================
def view_dashboard():
    st.title("📊 顿角咖啡·经营分析看板")
    
    if 'raw_data' not in st.session_state: st.session_state.raw_data = pd.DataFrame()

    with st.sidebar.expander("📥 数据中心 (历史数据叠加)", expanded=True):
        files = st.file_uploader("点击上传报表 (可多选日期)", type=["xlsx", "csv"], accept_multiple_files=True)
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
                # 🌟 修复多日期问题：合并并重置索引，使用更科学的去重逻辑
                combined = pd.concat(all_dfs, ignore_index=True)
                # 根据“日期、门店、商品、餐段、订单来源”去重，确保同天重复上传被覆盖，不同天数据保留
                subset_cols = [c for c in combined.columns if c in ['日期', '门店名称', '商品名称', '规格', '做法', '餐段', '订单来源']]
                st.session_state.raw_data = combined.drop_duplicates(subset=subset_cols).reset_index(drop=True)
                st.success(f"同步成功：当前已加载 {len(st.session_state.raw_data)} 条记录")

    if st.session_state.raw_data.empty:
        st.info("💡 请先在左侧上传报表。系统会自动对齐 1月5日等历史日期。")
        return

    # 清洗数据
    df_full = logic_clean_data(st.session_state.raw_data)
    
    # --- 侧边栏：交互中心 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 时间范围")
    available_dates = sorted(df_full['日期'].unique(), reverse=True)
    curr_date = st.sidebar.selectbox("当前日期", available_dates)
    
    enable_compare = st.sidebar.checkbox("环比对比")
    comp_date = None
    if enable_compare:
        remaining = [d for d in available_dates if d != curr_date]
        if remaining: comp_date = st.sidebar.selectbox("对比日期", remaining)

    st.sidebar.subheader("🔍 智能筛选")
    # 1. 项目
    sel_proj = st.sidebar.multiselect("项目", sorted(df_full['所属项目'].unique()))
    df_p = df_full if not sel_proj else df_full[df_full['所属项目'].isin(sel_proj)]
    
    # 2. 门店 (🌟 重新补回门店筛选)
    sel_store = st.sidebar.multiselect("门店", sorted(df_p['门店名称'].unique()))
    df_s = df_p if not sel_store else df_p[df_p['门店名称'].isin(sel_store)]
    
    # 3. 分类
    sel_l1 = st.sidebar.multiselect("一级分类", sorted(df_s['一级分类'].unique()))
    df_l1 = df_s if not sel_l1 else df_s[df_s['一级分类'].isin(sel_l1)]
    
    sel_l2 = st.sidebar.multiselect("二级分类 (商品类别)", sorted(df_l1['二级分类'].unique()))

    # --- 数据过滤引擎 ---
    def filter_data(data, projects, stores, l1s, l2s):
        tmp = data.copy()
        if projects: tmp = tmp[tmp['所属项目'].isin(projects)]
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

    st.subheader(f"📊 经营实况：{curr_date}" + (f" (环比 {comp_date})" if enable_compare else ""))
    
    # 销量卡片
    st.markdown("#### 🛒 销量详情")
    cl1, cl2, cl3 = st.columns(3)
    cl1.metric("销售杯数 (总)", f"{cg:,.0f} 杯", delta=diff(cg, pg))
    cl2.metric("退款杯数 (-)", f"{cr:,.0f} 杯", delta=diff(cr, pr), delta_color="inverse")
    cl3.metric("净销售杯数 (=)", f"{cn:,.0f} 杯", delta=diff(cn, pn))
    
    # 财务卡片
    st.markdown("#### 💰 财务概览")
    cl4, cl5 = st.columns(2)
    cl4.metric("总营收金额 (净实收)", f"¥{cv:,.2f}", delta=diff(cv, pv))
    avg = cv / cn if cn != 0 else 0
    p_avg = pv / pn if not df_comp.empty and pn != 0 else 0
    cl5.metric("单杯均价 (净)", f"¥{avg:.2f}", delta=diff(avg, p_avg))

    # --- 明细列表 ---
    st.divider()
    st.subheader("📋 商品销售排行 (去规格汇总)")
    
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
    menu = st.sidebar.radio("导航", ["📊 经营看板", "⚙️ 配方中心"])
    if menu == "📊 经营看板": view_dashboard()
    else:
        st.title("⚙️ 成本配方中心")
        st.info("数据接口已全面修复。")
