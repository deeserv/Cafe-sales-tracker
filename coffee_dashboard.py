# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta

# =============================================================================
# 1. 业务逻辑配置：映射关系表
# =============================================================================
PROJECT_STORE_MAPPING = {
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"],
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"]
}

CATEGORY_MAPPING = [
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "咖啡饮品", "二级分类": "拿铁家族"}, {"一级分类": "咖啡饮品", "二级分类": "奶咖家族"},
    {"一级分类": "咖啡饮品", "二级分类": "果C美式"}, {"一级分类": "咖啡饮品", "二级分类": "手冲咖啡"},
    {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"}, {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"},
    {"一级分类": "非咖啡饮品", "二级分类": "经典鲜果茶"}, {"一级分类": "非咖啡饮品", "二级分类": "新鲜果蔬汁"}
]

# =============================================================================
# 2. 核心算法：数据处理与清洗 (包含强力表头修复)
# =============================================================================
def logic_parse_days(date_series):
    if date_series.empty: return 1
    sample = str(date_series.iloc[0])
    match = re.search(r'(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})', sample)
    if match:
        try:
            d1, d2 = datetime.strptime(match.group(1), '%Y-%m-%d'), datetime.strptime(match.group(2), '%Y-%m-%d')
            return max(1, (d2 - d1).days + 1)
        except: pass
    return max(1, date_series.nunique())

def logic_clean_data(df):
    """
    本地数据清洗与层级映射
    🌟 增加强力容错，确保即便列名有空格也能识别
    """
    if df.empty: return df
    
    # --- 🌟 步骤 A: 暴力清洗表头 (核心修复) ---
    # 去除所有列名的空格、换行符、特殊符号
    df.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df.columns]
    
    # --- 🌟 步骤 B: 智能列名映射 (防止由于 Excel 导出导致的细微差异) ---
    rename_map = {}
    for col in df.columns:
        if '商品类别' in col or '分类' in col or '品类' in col:
            rename_map[col] = '商品类别'
        elif '门店' in col or '机构' in col:
            rename_map[col] = '门店名称'
        elif '统计周期' in col or '日期' in col or '时间' in col:
            rename_map[col] = '统计周期'
        elif '实收' in col or '金额' in col or '销售额' in col:
            rename_map[col] = '销售金额'
        elif '销量' in col or '数量' in col or '数量' in col:
            rename_map[col] = '销售数量'
    
    df = df.rename(columns=rename_map)

    # 验证关键列
    required_cols = ['门店名称', '统计周期', '商品类别', '销售金额', '销售数量']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"⚠️ 识别失败！报表中缺少列：{', '.join(missing)}")
        st.info(f"💡 当前读取到的列名为：{list(df.columns)}")
        st.stop()
    
    # 项目与门店映射
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(str(x).strip(), '其他项目'))
    
    # 品类层级映射
    df_cat = pd.DataFrame(CATEGORY_MAPPING)
    for col in ['一级分类', '二级分类']:
        if col in df.columns: df = df.drop(columns=[col])
    
    df['商品类别_clean'] = df['商品类别'].astype(str).str.strip()
    df = pd.merge(df, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('其他')
    df['二级分类'] = df['二级分类'].fillna('其他')
    return df

# =============================================================================
# 3. 前端 UI 样式
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡经营BI系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        section[data-testid="stSidebar"] div.stVerticalBlock { padding-top: 4rem !important; }
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            padding: 25px !important;
            border-radius: 20px !important;
            border: 1px solid #E2E8F0 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# 4. 视图：经营分析看板
# =============================================================================
def view_dashboard():
    st.title("📊 顿角咖啡·智能经营看板")
    
    if 'sales_data' not in st.session_state: st.session_state.sales_data = pd.DataFrame()

    with st.sidebar.expander("📥 数据上传 (本地上传)", expanded=True):
        files = st.file_uploader("支持多选 xlsx/csv", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            all_dfs = []
            for f in files:
                try:
                    df_u = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                    all_dfs.append(df_u)
                except Exception as e:
                    st.error(f"读取 {f.name} 出错: {e}")
            
            if all_dfs:
                # 暂时不在这里清洗，放到逻辑层统一处理
                st.session_state.sales_data = pd.concat(all_dfs, sort=False).drop_duplicates()
                st.success("数据已进入暂存区")

    if st.session_state.sales_data.empty:
        st.info("💡 请先在左侧上传企迈销售报表（包含商品类别、门店、销售额等）。")
        return

    # 执行强力清洗与维度处理
    df_base = logic_clean_data(st.session_state.sales_data)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 维度筛选")
    
    # 筛选联动
    all_projs = sorted(df_base['所属项目'].unique())
    sel_proj = st.sidebar.multiselect("所属项目", all_projs)
    df_f1 = df_base if not sel_proj else df_base[df_base['所属项目'].isin(sel_proj)]
    
    all_stores = sorted(df_f1['门店名称'].unique())
    sel_store = st.sidebar.multiselect("门店名称", all_stores)

    all_l1 = sorted(df_f1['一级分类'].unique())
    sel_l1 = st.sidebar.multiselect("一级分类", all_l1)
    df_f2 = df_f1 if not sel_l1 else df_f1[df_f1['一级分类'].isin(sel_l1)]
    
    all_l2 = sorted(df_f2['二级分类'].unique())
    sel_l2 = st.sidebar.multiselect("二级分类", all_l2)

    # 最终过滤
    df_view = df_base.copy()
    if sel_proj: df_view = df_view[df_view['所属项目'].isin(sel_proj)]
    if sel_store: df_view = df_view[df_view['门店名称'].isin(sel_store)]
    if sel_l1: df_view = df_view[df_view['一级分类'].isin(sel_l1)]
    if sel_l2: df_view = df_view[df_view['二级分类'].isin(sel_l2)]

    # 核心指标
    q, a = df_view['销售数量'].sum(), df_view['销售金额'].sum()
    days = logic_parse_days(df_view['统计周期'])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总销售杯数", f"{q:,.0f} 杯")
    c2.metric("总营收金额", f"¥{a:,.2f}")
    c3.metric("日均营收金额", f"¥{a/days:,.2f}")
    c4.metric("单杯成交均价", f"¥{a/q if q>0 else 0:.2f}")

    # 图表可视化
    import plotly.express as px
    st.divider()
    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.subheader("🏗️ 项目销售构成")
        p_sum = df_view.groupby('所属项目')['销售金额'].sum().reset_index()
        st.plotly_chart(px.bar(p_sum, x='所属项目', y='销售金额', color_discrete_sequence=['#3B82F6'], template="plotly_white"), use_container_width=True)
    with col_r:
        st.subheader("📈 品类贡献占比")
        c_sum = df_view.groupby('二级分类')['销售金额'].sum().reset_index()
        st.plotly_chart(px.pie(c_sum, values='销售金额', names='二级分类', hole=0.4), use_container_width=True)

    st.subheader("📋 单品销量明细")
    rank = df_view.groupby(['商品名称', '规格', '做法']).agg({'销售数量':'sum', '销售金额':'sum'}).sort_values('销售数量', ascending=False)
    st.dataframe(rank, use_container_width=True)

# =============================================================================
# 5. 视图：配方中心
# =============================================================================
def view_recipes():
    st.title("⚙️ 成本配方中心")
    st.info("本地旗舰版已就绪。在确保经营看板能正常读取您的报表后，我们将在此继续完善成本核算功能。")

# =============================================================================
# 6. 入口
# =============================================================================
if __name__ == "__main__":
    init_ui()
    menu = st.sidebar.radio("系统导航", ["📊 经营看板", "⚙️ 配方中心"])
    if menu == "📊 经营看板":
        view_dashboard()
    else:
        view_recipes()
