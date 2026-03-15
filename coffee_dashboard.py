# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta

# =============================================================================
# 1. 业务逻辑配置：核心分类规则 (基于您的最新定义)
# =============================================================================
PROJECT_STORE_MAPPING = {
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"],
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"]
}

# 🌟 这里的字典对应您提供的一级分类规则
CATEGORY_RULES = {
    "咖啡饮品": ["风味拿铁", "冰爽果咖", "SOE 冷萃", "中式茶咖", "甄选咖啡", "优选咖啡", "常规咖啡"],
    "非咖啡饮品": ["清爽果茶", "手打柠", "新鲜果蔬汁", "原叶轻乳茶", "活力酸奶", "经典鲜果茶", "柠檬茶", "原叶鲜奶茶", "经典奶茶", "不喝咖啡", "经典果茶"],
    "食品": ["多乐之日", "轻食甜品"]
}

# =============================================================================
# 2. 核心算法：数据清洗与分类映射引擎
# =============================================================================
def logic_parse_days(date_series):
    """解析天数"""
    if date_series.empty: return 1
    s = date_series.iloc[:, 0] if isinstance(date_series, pd.DataFrame) else date_series
    return max(1, s.nunique())

def logic_clean_data(df):
    """
    针对企迈报表优化的清洗逻辑，并适配最新一级分类规则
    """
    if df.empty: return df
    
    # 🌟 核心修复：重置索引并清理列名
    df = df.copy().reset_index(drop=True)
    df.columns = [str(c).strip().replace('\n', '').replace('\r', '').replace('`', '') for c in df.columns]
    
    # 智能映射
    rename_map = {
        '日期': '统计周期',
        '门店名称': '门店名称',
        '商品类别': '二级分类',
        '商品实收': '销售金额',
        '商品销量': '销售数量'
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # 清理反引号 ` 并处理缺失值
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace('`', '').str.strip()
    
    # 1. 项目映射
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(str(x).strip(), '其他项目')).values
    
    # 2. 🌟 核心：执行一级分类规则映射
    # 将规则扁平化为： {二级分类: 一级分类}
    lookup = {sub: main for main, subs in CATEGORY_RULES.items() for sub in subs}
    
    # 获取商品类别列（二级分类）
    cat_series = df['二级分类'] if '二级分类' in df.columns else pd.Series(['其他']*len(df))
    
    # 应用映射逻辑：如果找不到，则归入“其他”
    df['一级分类'] = cat_series.map(lookup).fillna("其他")
    
    return df.reset_index(drop=True)

# =============================================================================
# 3. UI 界面
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡经营智能看板", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        
        /* 🌟 解决月份按钮遮挡 */
        section[data-testid="stSidebar"] div.stVerticalBlock { padding-top: 5rem !important; }

        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            padding: 25px !important;
            border-radius: 20px !important;
            border: 1px solid #E2E8F0 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        }
    </style>
    """, unsafe_allow_html=True)

def view_dashboard():
    st.title("📊 顿角咖啡·智能经营看板")
    
    if 'raw_data' not in st.session_state: st.session_state.raw_data = pd.DataFrame()

    with st.sidebar.expander("📥 数据上传", expanded=True):
        files = st.file_uploader("支持多选 CSV/XLSX", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            all_dfs = []
            for f in files:
                try:
                    df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                    all_dfs.append(df)
                except: pass
            if all_dfs:
                st.session_state.raw_data = pd.concat(all_dfs, ignore_index=True)
                st.success("数据加载成功！")

    if st.session_state.raw_data.empty:
        st.info("💡 请先在左侧上传报表以开启分析。")
        return

    # 数据处理
    df_clean = logic_clean_data(st.session_state.raw_data)
    
    # --- 侧边栏筛选器 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 维度筛选")
    
    sel_proj = st.sidebar.multiselect("所属项目", sorted(df_clean['所属项目'].unique()))
    df_f1 = df_clean if not sel_proj else df_clean[df_clean['所属项目'].isin(sel_proj)]
    
    sel_store = st.sidebar.multiselect("门店名称", sorted(df_f1['门店名称'].unique()))
    df_f2 = df_f1 if not sel_store else df_f1[df_f1['门店名称'].isin(sel_store)]
    
    sel_l1 = st.sidebar.multiselect("一级分类", sorted(df_f2['一级分类'].unique()))
    df_f3 = df_f2 if not sel_l1 else df_f2[df_f2['一级分类'].isin(sel_l1)]
    
    sel_l2 = st.sidebar.multiselect("商品类别 (二级)", sorted(df_f3['二级分类'].unique()))
    df_final = df_f3 if not sel_l2 else df_f3[df_f3['二级分类'].isin(sel_l2)]

    # --- 数据看板显示 ---
    q, a = df_final['销售数量'].sum(), df_final['销售金额'].sum()
    days = logic_parse_days(df_final['统计周期'])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总销售杯数", f"{q:,.0f} 杯")
    c2.metric("总营收金额", f"¥{a:,.2f}")
    c3.metric("日均营收金额", f"¥{a/days:,.2f}")
    c4.metric("单杯成交均价", f"¥{a/q if q>0 else 0:.2f}")

    # --- 可视化 ---
    import plotly.express as px
    st.divider()
    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.subheader("🏗️ 项目销售分布")
        p_sum = df_final.groupby('所属项目')['销售金额'].sum().reset_index()
        fig = px.bar(p_sum, x='所属项目', y='销售金额', color='所属项目', template="plotly_white", text_auto='.2s')
        st.plotly_chart(fig, use_container_width=True)
    with col_r:
        st.subheader("📈 营收分类占比")
        c_sum = df_final.groupby('一级分类')['销售金额'].sum().reset_index()
        st.plotly_chart(px.pie(c_sum, values='销售金额', names='一级分类', hole=0.4), use_container_width=True)

    st.subheader("📋 商品销售排行")
    # 汇总显示
    rank = df_final.groupby(['商品名称', '规格', '做法']).agg({'销售数量':'sum', '销售金额':'sum'}).sort_values('销售数量', ascending=False)
    st.dataframe(rank, use_container_width=True)

# =============================================================================
# 4. 入口
# =============================================================================
if __name__ == "__main__":
    init_ui()
    menu = st.sidebar.radio("系统导航", ["📊 经营看板", "⚙️ 配方中心"])
    if menu == "📊 经营看板":
        view_dashboard()
    else:
        st.title("⚙️ 成本配方中心")
        st.info("分类规则已全面适配。接下来我们将根据一级分类的细化，开始录入成本和核算利润。")
