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

CATEGORY_RULES = {
    "咖啡饮品": ["风味拿铁", "冰爽果咖", "SOE 冷萃", "SOE冷萃", "中式茶咖", "甄选咖啡", "优选咖啡", "常规咖啡", "拿铁系列", "美式家族", "拿铁家族", "果C美式", "经典意式"],
    "非咖啡饮品": ["清爽果茶", "手打柠", "新鲜果蔬汁", "原叶轻乳茶", "活力酸奶", "经典鲜果茶", "柠檬茶", "原叶鲜奶茶", "经典奶茶", "不喝咖啡", "经典果茶", "果茶系列", "乳茶系列"],
    "食品": ["多乐之日", "轻食甜品", "餐厅产品", "现烤烘焙", "烘焙甜品"]
}

# =============================================================================
# 2. 核心算法：数据处理引擎 (多维度对账)
# =============================================================================
def logic_clean_data(df):
    if df.empty: return df
    
    df = df.copy().reset_index(drop=True)
    # 暴力清理表头
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
    df['销售数量_raw'] = pd.to_numeric(df['销售数量_raw'], errors='coerce').fillna(0)
    df['销售金额_raw'] = pd.to_numeric(df['销售金额_raw'], errors='coerce').fillna(0)
    df['退款数量_raw'] = pd.to_numeric(df['退款数量_raw'], errors='coerce').fillna(0) if '退款数量_raw' in df.columns else 0
    
    # 核心计算逻辑
    df['销售杯数'] = df['销售数量_raw']
    df['净销售杯数'] = df['销售杯数'] - df['退款数量_raw']
    df['销售金额'] = df['销售金额_raw']
    
    # 字符串清理
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace('`', '').str.strip()
    
    # 🌟 核心修复：处理日期中的“合计”或空值
    # errors='coerce' 会把无法解析成日期的文字变成 NaT (空)
    df['日期_dt'] = pd.to_datetime(df['日期'], errors='coerce')
    
    # 自动剔除那些无法识别日期的行（即报表底部的合计行）
    df = df.dropna(subset=['日期_dt'])
    
    # 重新格式化日期字符串
    df['日期'] = df['日期_dt'].dt.strftime('%Y-%m-%d')
    
    # 项目映射
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(x, '其他项目')).values
    
    # 一级分类映射
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

    with st.sidebar.expander("📥 数据中心 (支持多文件上传)", expanded=True):
        files = st.file_uploader("点击上传企迈报表", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            all_dfs = []
            for f in files:
                try:
                    # 企迈导出的 CSV 有时是 GBK 编码
                    if f.name.endswith('.csv'):
                        try:
                            df = pd.read_csv(f, encoding='utf-8')
                        except:
                            df = pd.read_csv(f, encoding='gbk')
                    else:
                        df = pd.read_excel(f)
                    all_dfs.append(df)
                except Exception as e:
                    st.sidebar.error(f"文件 {f.name} 读取失败")
            
            if all_dfs:
                st.session_state.raw_data = pd.concat(all_dfs, ignore_index=True)
                st.success("数据已同步")

    if st.session_state.raw_data.empty:
        st.info("💡 请上传报表。支持多日期文件上传以开启环比功能。")
        return

    # 全量清洗
    df_full = logic_clean_data(st.session_state.raw_data)
    
    # --- 侧边栏：时间与维度中心 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 时间控制")
    
    # 获取可用日期列表
    available_dates = sorted(df_full['日期'].unique(), reverse=True)
    
    # 1. 选择当前查看日期
    curr_date = st.sidebar.selectbox("选择当前查看日期", available_dates)
    
    # 2. 环比设置
    enable_compare = st.sidebar.checkbox("开启环比对比分析")
    comp_date = None
    if enable_compare:
        remaining_dates = [d for d in available_dates if d != curr_date]
        if remaining_dates:
            comp_date = st.sidebar.selectbox("选择对比日期", remaining_dates)
        else:
            st.sidebar.warning("数据量不足，无法对比")

    st.sidebar.subheader("🔍 筛选器")
    sel_proj = st.sidebar.multiselect("所属项目", sorted(df_full['所属项目'].unique()))
    
    # 筛选逻辑
    def apply_filters(data, projects):
        if not projects: return data
        return data[data['所属项目'].isin(projects)]

    # 获取数据集
    df_curr = df_full[df_full['日期'] == curr_date]
    df_curr = apply_filters(df_curr, sel_proj)
    
    df_comp = pd.DataFrame()
    if enable_compare and comp_date:
        df_comp = df_full[df_full['日期'] == comp_date]
        df_comp = apply_filters(df_comp, sel_proj)

    # --- 数据汇总计算 ---
    def get_metrics(data):
        if data.empty: return 0, 0, 0, 0
        return data['销售杯数'].sum(), data['退款数量_raw'].sum(), data['净销售杯数'].sum(), data['销售金额'].sum()

    curr_gross, curr_refund, curr_net, curr_rev = get_metrics(df_curr)
    comp_gross, comp_refund, comp_net, comp_rev = get_metrics(df_comp)

    # 计算差值 (Delta)
    def calc_delta(curr, comp):
        if not enable_compare or comp == 0: return None
        return curr - comp

    # --- 顶层指标卡展示 ---
    st.subheader(f"📅 当前视图：{curr_date}" + (f" vs {comp_date}" if enable_compare else ""))
    
    c1, c2, c3 = st.columns(3)
    c1.metric("销售杯数 (总)", f"{curr_gross:,.0f} 杯", delta=calc_delta(curr_gross, comp_gross))
    c2.metric("退款杯数 (-)", f"{curr_refund:,.0f} 杯", delta=calc_delta(curr_refund, comp_refund), delta_color="inverse")
    c3.metric("净销售杯数 (=)", f"{curr_net:,.0f} 杯", delta=calc_delta(curr_net, comp_net))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    c4, c5 = st.columns(2)
    c4.metric("总营收金额 (实收)", f"¥{curr_rev:,.2f}", delta=calc_delta(curr_rev, comp_rev))
    avg_price = curr_rev / curr_net if curr_net != 0 else 0
    comp_avg = comp_rev / comp_net if comp_net != 0 else 0
    c5.metric("单杯均价 (净)", f"¥{avg_price:.2f}", delta=calc_delta(avg_price, comp_avg))

    # --- 商品对比表格 ---
    st.divider()
    st.subheader("📋 单品表现详情 (去规格汇总)")
    
    # 汇总当前单品
    rank_curr = df_curr.groupby(['商品名称', '二级分类']).agg({
        '销售杯数': 'sum',
        '退款数量_raw': 'sum',
        '净销售杯数': 'sum',
        '销售金额': 'sum'
    }).rename(columns={'销售金额': '营收金额', '退款数量_raw': '退款杯数'})

    if enable_compare and not df_comp.empty:
        rank_comp = df_comp.groupby(['商品名称', '二级分类']).agg({'净销售杯数': 'sum'}).rename(columns={'净销售杯数': '对比日期净销量'})
        display_df = rank_curr.merge(rank_comp, on=['商品名称', '二级分类'], how='left').fillna(0)
        display_df['销量变化'] = display_df['净销售杯数'] - display_df['对比日期净销量']
    else:
        display_df = rank_curr

    st.dataframe(display_df.sort_values('净销售杯数', ascending=False), use_container_width=True)

if __name__ == "__main__":
    init_ui()
    import plotly.express as px
    menu = st.sidebar.radio("系统导航", ["📊 经营看板", "⚙️ 配方中心"])
    if menu == "📊 经营看板":
        view_dashboard()
    else:
        st.title("⚙️ 成本配方中心")
        st.info("数据分析已就绪。")
