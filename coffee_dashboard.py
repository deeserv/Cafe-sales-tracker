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
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度大厦店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
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
# 2. 核心算法：数据处理与清洗
# =============================================================================
def logic_parse_days(date_series):
    """解决日均计算问题的核心逻辑"""
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
    """本地数据清洗与层级映射"""
    if df.empty: return df
    
    # 门店与项目映射
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
# 3. 前端 UI 样式定义
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡经营BI系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        
        /* 🌟 UI 修复：增加侧边栏顶部边距，防止月份切换按钮被遮挡 */
        section[data-testid="stSidebar"] div.stVerticalBlock {
            padding-top: 4rem !important;
        }

        /* 统一指标卡设计 */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            padding: 25px !important;
            border-radius: 20px !important;
            border: 1px solid #E2E8F0 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        }
        
        .recipe-card {
            background: #FFFFFF;
            padding: 18px;
            border-radius: 15px;
            border-left: 6px solid #3B82F6;
            margin-bottom: 12px;
            border: 1px solid #F1F5F9;
        }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# 4. 视图：经营分析看板
# =============================================================================
def view_dashboard():
    st.title("📊 顿角咖啡·智能经营看板")
    
    # 本地数据内存
    if 'sales_data' not in st.session_state: st.session_state.sales_data = pd.DataFrame()

    # --- 侧边栏：数据上传 ---
    with st.sidebar.expander("📥 数据上传 (本地上传)", expanded=True):
        files = st.file_uploader("支持多选 xlsx/csv", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            all_dfs = []
            for f in files:
                df_u = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                df_u.columns = [str(c).strip() for c in df_u.columns]
                # 对齐关键列
                m = {'商品实收': '销售金额', '商品销量': '销售数量', '日期': '统计周期', '商品分类': '商品类别'}
                df_u = df_u.rename(columns={k: v for k, v in m.items() if k in df_u.columns})
                all_dfs.append(df_u)
            st.session_state.sales_data = pd.concat(all_dfs).drop_duplicates()
            st.success(f"成功加载 {len(st.session_state.sales_data)} 条销售流水")

    if st.session_state.sales_data.empty:
        st.info("💡 请先在左侧上传企迈销售报表以开启看板。")
        return

    # --- 侧边栏：核心筛选体系 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 维度筛选 (维度联动)")
    df_base = logic_clean_data(st.session_state.sales_data)
    
    # 1. 项目与门店联动
    all_projs = sorted(df_base['所属项目'].unique())
    sel_proj = st.sidebar.multiselect("所属项目", all_projs)
    df_f1 = df_base if not sel_proj else df_base[df_base['所属项目'].isin(sel_proj)]
    
    all_stores = sorted(df_f1['门店名称'].unique())
    sel_store = st.sidebar.multiselect("门店名称", all_stores)

    # 2. 类别层级联动
    all_l1 = sorted(df_f1['一级分类'].unique())
    sel_l1 = st.sidebar.multiselect("一级分类", all_l1)
    df_f2 = df_f1 if not sel_l1 else df_f1[df_f1['一级分类'].isin(sel_l1)]
    
    all_l2 = sorted(df_f2['二级分类'].unique())
    sel_l2 = st.sidebar.multiselect("二级分类", all_l2)

    # --- 智能过滤 (不选即全选) ---
    df_view = df_base.copy()
    if sel_proj: df_view = df_view[df_view['所属项目'].isin(sel_proj)]
    if sel_store: df_view = df_view[df_view['门店名称'].isin(sel_store)]
    if sel_l1: df_view = df_view[df_view['一级分类'].isin(sel_l1)]
    if sel_l2: df_view = df_view[df_view['二级分类'].isin(sel_l2)]

    # --- 核心指标显示 ---
    q, a = df_view['销售数量'].sum(), df_view['销售金额'].sum()
    days = logic_parse_days(df_view['统计周期'])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总杯数", f"{q:,.0f} 杯")
    c2.metric("总营收", f"¥{a:,.2f}")
    c3.metric("日均营收", f"¥{a/days:,.2f}")
    c4.metric("单杯均价", f"¥{a/q if q>0 else 0:.2f}")

    # --- 可视化图表 ---
    import plotly.express as px
    st.divider()
    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.subheader("🏗️ 销售额分布")
        p_sum = df_view.groupby('所属项目')['销售金额'].sum().reset_index()
        st.plotly_chart(px.bar(p_sum, x='所属项目', y='销售金额', color_discrete_sequence=['#3B82F6'], template="plotly_white"), use_container_width=True)
    with col_r:
        st.subheader("📈 品类占比 (按营收)")
        c_sum = df_view.groupby('二级分类')['销售金额'].sum().reset_index()
        st.plotly_chart(px.pie(c_sum, values='销售金额', names='二级分类', hole=0.4), use_container_width=True)

    st.subheader("📋 单品销售排行")
    rank = df_view.groupby(['商品名称', '规格', '做法']).agg({'销售数量':'sum', '销售金额':'sum'}).sort_values('销售数量', ascending=False)
    st.dataframe(rank, use_container_width=True)

# =============================================================================
# 5. 视图：成本配方中心
# =============================================================================
def view_recipes():
    st.title("⚙️ 成本配方中心")
    if 'mats' not in st.session_state: st.session_state.mats = pd.DataFrame()
    if 'recipes' not in st.session_state: st.session_state.recipes = []

    t1, t2 = st.tabs(["📦 原物料库", "📋 配方构建"])
    
    with t1:
        f = st.file_uploader("上传物料价格清单", type=["xlsx", "csv"])
        if f:
            st.session_state.mats = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            st.success("物料库同步成功")
        st.dataframe(st.session_state.mats, use_container_width=True, hide_index=True)

    with t2:
        m_df = st.session_state.mats
        if m_df.empty:
            st.warning("请先在第一步上传物料库。")
        else:
            rmats = sorted(m_df['物料名称'].tolist())
            p_name = st.text_input("饮品名称")
            if 'temp_rows' not in st.session_state: st.session_state.temp_rows = []
            
            if st.button("➕ 新增配料行"):
                st.session_state.temp_rows.append({'物料名称': rmats[0], '用量': 0.0})
                st.rerun()

            new_list = []
            for i, r in enumerate(st.session_state.temp_rows):
                c = st.columns([4, 3, 1])
                m = c[0].selectbox(f"物料{i}", rmats, index=rmats.index(r['物料名称']), key=f"m_{i}")
                q = c[1].number_input(f"克数{i}", value=float(r['用量']), key=f"q_{i}")
                new_list.append({'物料名称': m, '用量': q})
                if c[2].button("🗑️", key=f"d_{i}"):
                    st.session_state.temp_rows.pop(i)
                    st.rerun()
            st.session_state.temp_rows = new_list
            
            if st.button("💾 确认并保存在本地", type="primary"):
                st.session_state.recipes.append({"name": p_name, "items": new_list})
                st.success("配方已在本地生效")

# =============================================================================
# 6. 程序入口
# =============================================================================
if __name__ == "__main__":
    init_ui()
    menu = st.sidebar.radio("系统导航", ["📊 经营看板", "⚙️ 配方中心"])
    if menu == "📊 经营看板":
        view_dashboard()
    else:
        view_recipes()
