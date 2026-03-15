# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta

# =============================================================================
# 1. 业务逻辑配置：映射关系与分类规则
# =============================================================================
PROJECT_STORE_MAPPING = {
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度大厦店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"],
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"]
}

CATEGORY_RULES = {
    "咖啡饮品": ["风味拿铁", "冰爽果咖", "SOE 冷萃", "SOE冷萃", "中式茶咖", "甄选咖啡", "优选咖啡", "常规咖啡", "拿铁系列", "美式家族", "拿铁家族", "果C美式", "经典意式"],
    "非咖啡饮品": ["清爽果茶", "手打柠", "新鲜果蔬汁", "原叶轻乳茶", "活力酸奶", "经典鲜果茶", "柠檬茶", "原叶鲜奶茶", "经典奶茶", "不喝咖啡", "经典果茶", "果茶系列", "乳茶系列"],
    "食品": ["多乐之日", "轻食甜品", "餐厅产品", "现烤烘焙", "烘焙甜品"]
}

# =============================================================================
# 2. 核心算法：数据处理引擎 (精准对账逻辑)
# =============================================================================
def logic_parse_days(date_series):
    if date_series.empty: return 1
    s = date_series.iloc[:, 0] if isinstance(date_series, pd.DataFrame) else date_series
    return max(1, s.nunique())

def logic_clean_data(df):
    if df.empty: return df
    
    df = df.copy().reset_index(drop=True)
    df.columns = [str(c).strip().replace('\n', '').replace('\r', '').replace('`', '') for c in df.columns]
    
    rename_map = {
        '日期': '统计周期',
        '门店名称': '门店名称',
        '商品类别': '二级分类_原始',
        '商品实收': '销售金额_raw',
        '商品销量': '销售数量_raw',
        '商品退款数': '退款数量_raw'
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # 数值转换
    df['销售数量_raw'] = pd.to_numeric(df['销售数量_raw'], errors='coerce').fillna(0)
    df['销售金额_raw'] = pd.to_numeric(df['销售金额_raw'], errors='coerce').fillna(0)
    df['退款数量_raw'] = pd.to_numeric(df['退款数量_raw'], errors='coerce').fillna(0) if '退款数量_raw' in df.columns else 0
    
    # 核心对账逻辑：
    # 1. 销售杯数 = 报表原始销量
    df['销售杯数'] = df['销售数量_raw']
    # 2. 净销售杯数 = 销售杯数 - 退款数
    df['净销售杯数'] = df['销售杯数'] - df['退款数量_raw']
    
    # 金额保持原始实收
    df['销售金额'] = df['销售金额_raw']
    
    # 字符串清理
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace('`', '').str.strip()
    
    # 项目映射
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(x, '其他项目')).values
    
    # 一级分类映射
    lookup = {sub: main for main, subs in CATEGORY_RULES.items() for sub in subs}
    df['二级分类'] = df['二级分类_原始'].str.strip()
    df['一级分类'] = df['二级分类'].map(lookup).fillna("其他")
    
    return df.reset_index(drop=True)

# =============================================================================
# 3. UI 界面美化
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡经营智能看板", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        section[data-testid="stSidebar"] div.stVerticalBlock { padding-top: 5rem !important; }
        
        /* 响应式指标卡 */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF; padding: 20px !important;
            border-radius: 15px !important; border: 1px solid #E2E8F0 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        }
    </style>
    """, unsafe_allow_html=True)

def view_dashboard():
    st.title("📊 顿角咖啡·智能经营看板")
    
    if 'raw_data' not in st.session_state: st.session_state.raw_data = pd.DataFrame()

    with st.sidebar.expander("📥 数据上传", expanded=True):
        files = st.file_uploader("上传企迈报表 (CSV/XLSX)", type=["xlsx", "csv"], accept_multiple_files=True)
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
                st.success("报表已同步，请开始分析。")

    if st.session_state.raw_data.empty:
        st.info("💡 请上传报表。当前对账公式：[销售杯数] - [退款杯数] = [净销售杯数]")
        return

    # 数据处理
    df_clean = logic_clean_data(st.session_state.raw_data)
    
    # --- 筛选与设置 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 维度筛选")
    sel_proj = st.sidebar.multiselect("所属项目", sorted(df_clean['所属项目'].unique()))
    df_f = df_clean if not sel_proj else df_clean[df_clean['所属项目'].isin(sel_proj)]
    
    sel_store = st.sidebar.multiselect("门店名称", sorted(df_f['门店名称'].unique()))
    df_f = df_f if not sel_store else df_f[df_f['门店名称'].isin(sel_store)]
    
    sel_l1 = st.sidebar.multiselect("一级分类", sorted(df_f['一级分类'].unique()))
    df_f = df_f if not sel_l1 else df_f[df_f['一级分类'].isin(sel_l1)]
    
    sel_l2 = st.sidebar.multiselect("商品类别 (二级)", sorted(df_f['二级分类'].unique()))
    df_final = df_f if not sel_l2 else df_f[df_f['二级分类'].isin(sel_l2)]

    # --- 核心指标统计 ---
    gross_sales = df_final['销售杯数'].sum()
    refund_count = df_final['退款数量_raw'].sum()
    net_sales = df_final['净销售杯数'].sum()
    revenue = df_final['销售金额'].sum()
    days = logic_parse_days(df_final[['统计周期']])
    
    # 🌟 调整为 5 列显示，让对账一目了然
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("销售杯数", f"{gross_sales:,.0f} 杯", help="报表原始销量（含退款）")
    c2.metric("退款杯数", f"{refund_count:,.0f} 杯", help="报表记录的退款总数")
    c3.metric("净销售杯数", f"{net_sales:,.0f} 杯", help="计算逻辑：销售杯数 - 退款数")
    c4.metric("总营收金额", f"¥{revenue:,.2f}")
    c5.metric("单杯均价 (净)", f"¥{revenue/net_sales if net_sales!=0 else 0:.2f}")

    # --- 对账明细表 ---
    st.divider()
    st.subheader("📋 单品销售详细对账 (按名称汇总)")
    
    # 汇总显示
    rank = df_final.groupby(['商品名称', '二级分类']).agg({
        '销售杯数': 'sum',
        '退款数量_raw': 'sum',
        '净销售杯数': 'sum',
        '销售金额': 'sum'
    }).rename(columns={
        '退款数量_raw': '退款杯数',
        '销售金额': '营收金额'
    })
    
    # 过滤掉全 0 的行
    rank = rank[(rank['销售杯数'] != 0) | (rank['净销售杯数'] != 0)]
    
    st.dataframe(rank.sort_values('净销售杯数', ascending=False), use_container_width=True)

if __name__ == "__main__":
    init_ui()
    import plotly.express as px
    menu = st.sidebar.radio("系统导航", ["📊 经营看板", "⚙️ 配方中心"])
    if menu == "📊 经营看板":
        view_dashboard()
    else:
        st.title("⚙️ 成本配方中心")
        st.info("对账看板已升级。新增“退款杯数”独立指标。")
