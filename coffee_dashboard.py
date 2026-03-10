# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import sqlite3
import re
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 1. 核心配置与 CSS 注入 (精装全功能版)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="顿角咖啡智能经营系统",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

def check_password():
    CORRECT_PASSWORD = "888" 
    def password_entered():
        if st.session_state.get("password") == CORRECT_PASSWORD:
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    if not st.session_state["password_correct"]:
        st.markdown("""<style>.stTextInput > label {display:none;}</style><div style='text-align: center; margin-top: 100px;'><h1>🔒 请登录</h1><p>顿角咖啡内部数据系统</p></div>""", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.text_input("密码", type="password", on_change=password_entered, key="password", placeholder="请输入访问密码")
            if "password" in st.session_state and st.session_state["password"] and not st.session_state["password_correct"]:
                 st.error("❌ 密码错误，请重试")
        return False
    return True

if not check_password(): st.stop()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
    
    /* 指标卡片美化 */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF; padding: 22px; border-radius: 18px;
        box-shadow: 0 4px 10px -2px rgba(0, 0, 0, 0.05); border: 1px solid #E2E8F0;
    }
    [data-testid="stMetricValue"] {
        font-size: 32px !important; font-weight: 800 !important;
        background: -webkit-linear-gradient(120deg, #1E40AF, #3B82F6);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    
    /* 容器间距 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; border-radius: 15px; border: 1px solid #E2E8F0; padding: 25px;
        margin-bottom: 25px;
    }
    
    /* 配方卡片页眉 */
    .recipe-card-header { background: #F8FAFC; padding: 15px; border-radius: 12px; border-left: 8px solid #3B82F6; margin-bottom: 12px; box-shadow: inset 0 0 0 1px #E2E8F0; }
    .cost-tag { background: #EFF6FF; color: #1E40AF; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 700; border: 1px solid #DBEAFE; margin-right: 8px; }
</style>
""", unsafe_allow_html=True)

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# -----------------------------------------------------------------------------
# 2. 映射与数据库引擎
# -----------------------------------------------------------------------------
RAW_COLUMN_MAPPING = { '商品实收': '销售金额', '商品销量': '销售数量', '日期': '统计周期', '商品分类': '商品类别' }

CATEGORY_MAPPING_DATA = [
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "咖啡饮品", "二级分类": "奶咖家族"}, {"一级分类": "咖啡饮品", "二级分类": "果C美式"},
    {"一级分类": "咖啡饮品", "二级分类": "手冲咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "优选咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "经典意式"}, {"一级分类": "咖啡饮品", "二级分类": "甄选咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "soe冷萃"}, {"一级分类": "咖啡饮品", "二级分类": "SOE冷萃"}, 
    {"一级分类": "咖啡饮品", "二级分类": "风味拿铁"}, {"一级分类": "咖啡饮品", "二级分类": "冰爽果咖"},
    {"一级分类": "咖啡饮品", "二级分类": "中式茶咖"}, {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"}, {"一级分类": "非咖啡饮品", "二级分类": "经典鲜果茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "手打柠"}, {"一级分类": "非咖啡饮品", "二级分类": "清爽果茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "新鲜果蔬汁"}, {"一级分类": "非咖啡饮品", "二级分类": "不喝咖啡"},
    {"一级分类": "非咖啡饮品", "二级分类": "果茶系列"}, {"一级分类": "非咖啡饮品", "二级分类": "抹茶家族"},
    {"一级分类": "非咖啡饮品", "二级分类": "柠檬茶"}, {"一级分类": "非咖啡饮品", "二级分类": "原叶鲜奶茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "经典果茶"}, {"一级分类": "非咖啡饮品", "二级分类": "经典奶茶"}
]

PROJECT_STORE_MAPPING = {
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"],
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "腾讯项目": ["北京总部image"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"]
}

DATA_DIR = "data_storage"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "coffee_master.db")

def get_db_conn(): return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales_raw (门店名称 TEXT, 商品名称 TEXT, 商品类别 TEXT, 规格 TEXT, 做法 TEXT, 统计周期 TEXT, 销售金额 REAL, 销售数量 REAL, source_file TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS raw_materials (物料名称 TEXT PRIMARY KEY, 品项类别 TEXT, 单位 TEXT, 物流单价 REAL, 顿角单价 REAL, 百度单价 REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS bom_recipes (配方类型 TEXT, 适用范围 TEXT, 商品名称 TEXT, 规格 TEXT, 做法 TEXT, 物料名称 TEXT, 用量 REAL, UNIQUE(配方类型, 适用范围, 商品名称, 规格, 做法, 物料名称))''')
    # 脏数据自动清理
    cursor.execute("UPDATE sales_raw SET 规格 = '常规' WHERE 规格 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE sales_raw SET 做法 = '常规' WHERE 做法 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE bom_recipes SET 规格 = '常规' WHERE 规格 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE bom_recipes SET 做法 = '常规' WHERE 做法 IN ('0', 'nan', 'None', '', 'NaN')")
    conn.commit(); conn.close()

init_db()

# -----------------------------------------------------------------------------
# 3. 优先匹配逻辑引擎 (核账之魂)
# -----------------------------------------------------------------------------
def clean_store_name(n): return str(n).strip().replace(" ", "").replace("(", "（").replace(")", "）")

def merge_category_map(df):
    if df.empty: return df
    df_cat = pd.DataFrame(CATEGORY_MAPPING_DATA)
    if '一级分类' in df.columns: df = df.drop(columns=['一级分类'], errors='ignore')
    if '二级分类' in df.columns: df = df.drop(columns=['二级分类'], errors='ignore')
    df['商品类别_clean'] = df['商品类别'].astype(str).str.strip()
    df = pd.merge(df, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('未分类')
    df['二级分类'] = df['二级分类'].fillna('未分类')
    s2p = {clean_store_name(s): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(clean_store_name(x), '其他项目'))
    return df

def get_cost_mapping(df_sales, df_bom, df_raw, track_name):
    """
    track_name: '物流' 或 '门店'
    实现核心：店 > 项目 > 全局 优先覆盖逻辑
    """
    if df_bom.empty or df_raw.empty: return pd.Series(0.0, index=df_sales.index)
    
    # 1. 预计算物料单价
    m_bom = df_bom[df_bom['配方类型'] == track_name].merge(df_raw, on='物料名称', how='left').fillna(0)
    m_bom['c_log'] = m_bom['用量'] * m_bom['物流单价']
    m_bom['c_dj'] = m_bom['用量'] * m_bom['顿角单价']
    m_bom['c_bd'] = m_bom['用量'] * m_bom['百度单价']
    
    # 2. 按配方卡聚合
    grp = m_bom.groupby(['适用范围', '商品名称', '规格', '做法'], as_index=False)[['c_log', 'c_dj', 'c_bd']].sum()
    
    # 3. 逐级匹配逻辑
    def match_row_cost(row):
        store = clean_store_name(row['门店名称'])
        proj = row['所属项目']
        prod = row['商品名称']
        spec = row['规格']
        meth = row['做法']
        
        # 寻找匹配的物料清单结果
        def find_in_grp(scope):
            res = grp[(grp['适用范围'] == scope) & (grp['商品名称'] == prod) & (grp['规格'] == spec) & (grp['做法'] == meth)]
            if res.empty: return None
            # 根据所属项目决定取哪一列单价
            if track_name == '物流': return res.iloc[0]['c_log']
            else: return res.iloc[0]['c_bd'] if proj == '百度项目' else res.iloc[0]['c_dj']

        # 优先级1：具体店
        cost = find_in_grp(store)
        if cost is not None: return cost
        
        # 优先级2：项目级
        cost = find_in_grp(proj if '项目' in proj else f"【{proj}】")
        if cost is not None: return cost
        
        # 优先级3：全局默认
        cost = find_in_grp('【全局默认配方】')
        return cost if cost is not None else 0.0

    return df_sales.apply(match_row_cost, axis=1)

# -----------------------------------------------------------------------------
# 4. 看板主体 (📊 经营分析)
# -----------------------------------------------------------------------------
app_mode = st.sidebar.radio("🧭 系统导航", ["📊 经营分析看板", "⚙️ 成本与配方中心"])

if app_mode == "📊 经营分析看板":
    with st.sidebar.expander("💾 数据管理 (ETL)", expanded=False):
        conn = get_db_conn()
        try:
            total_rows = pd.read_sql("SELECT COUNT(*) as c FROM sales_raw", conn).iloc[0]['c']
            available_periods = sorted(pd.read_sql("SELECT DISTINCT 统计周期 FROM sales_raw WHERE 统计周期 IS NOT NULL", conn)['统计周期'].tolist())
        except: total_rows = 0; available_periods = []
        finally: conn.close()
        st.markdown(f"库内已存：**{total_rows:,}** 条")
        files = st.file_uploader("📥 上传企迈日结流水", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            conn = get_db_conn()
            for f in files:
                df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                df.columns = [str(c).strip() for c in df.columns]
                for c in df.columns:
                    if '规格' in c: df.rename(columns={c: '规格'}, inplace=True)
                    elif any(k in c for k in ['做法', '口味', '属性']): df.rename(columns={c: '做法'}, inplace=True)
                df = df.rename(columns=RAW_COLUMN_MAPPING)
                df['统计周期'] = df['统计周期'].apply(lambda x: pd.to_datetime(x).strftime('%Y-%m-%d') if pd.notna(x) else datetime.now().strftime('%Y-%m-%d'))
                df['规格'] = df['规格'].replace(['nan', 'None', '', '0'], '常规').fillna('常规')
                df['做法'] = df['做法'].replace(['nan', 'None', '', '0'], '常规').fillna('常规')
                df['门店名称'] = df['门店名称'].apply(clean_store_name).ffill()
                for c in ['销售金额', '销售数量']:
                    if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(r'[¥$,￥]', '', regex=True), errors='coerce').fillna(0)
                df['source_file'] = f.name
                df[['门店名称', '商品名称', '商品类别', '规格', '做法', '统计周期', '销售金额', '销售数量', 'source_file']].to_sql('sales_raw', conn, if_exists='append', index=False)
            conn.close(); st.rerun()
        if st.button("🗑️ 清空销售库", use_container_width=True):
            c = get_db_conn(); c.execute("DELETE FROM sales_raw"); c.commit(); c.close(); st.rerun()

    if total_rows == 0: st.info("请先导入企迈销售数据。"); st.stop()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 经营周期与对比")
    parsed_dates = [datetime.strptime(p, '%Y-%m-%d').date() for p in available_periods if p]
    
    enable_comp = st.sidebar.checkbox("🌓 开启环比对比", value=False)
    sel_range = st.sidebar.date_input("本期范围", [min(parsed_dates), max(parsed_dates)], min_value=min(parsed_dates), max_value=max(parsed_dates))
    
    df_cur = pd.DataFrame(); df_prev = pd.DataFrame()
    if len(sel_range) == 2:
        s1, e1 = sel_range
        conn = get_db_conn()
        df_cur = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(s1.strftime('%Y-%m-%d'), e1.strftime('%Y-%m-%d')))
        if enable_comp:
            dur = (e1 - s1).days + 1
            s2, e2 = s1 - timedelta(days=dur), s1 - timedelta(days=1)
            prev_range = st.sidebar.date_input("对比上期", [s2, e2])
            if len(prev_range) == 2:
                df_prev = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(prev_range[0].strftime('%Y-%m-%d'), prev_range[1].strftime('%Y-%m-%d')))
        conn.close()

    if not df_cur.empty:
        df_cur = merge_category_map(df_cur)
        if not df_prev.empty: df_prev = merge_category_map(df_prev)
        
        # 联动筛选
        st.sidebar.markdown("---")
        all_l1 = sorted(df_cur['一级分类'].unique().tolist())
        sel_l1 = st.sidebar.multiselect("一级分类筛选", all_l1, default=all_l1)
        if sel_l1: 
            df_cur = df_cur[df_cur['一级分类'].isin(sel_l1)]
            if not df_prev.empty: df_prev = df_prev[df_prev['一级分类'].isin(sel_l1)]
            
        all_sts = sorted(df_cur['门店名称'].unique().tolist())
        sel_sts = st.sidebar.multiselect("门店筛选", all_sts)
        if sel_sts: 
            df_cur = df_cur[df_cur['门店名称'].isin(sel_sts)]
            if not df_prev.empty: df_prev = df_prev[df_prev['门店名称'].isin(sel_sts)]

        # 计算日均天数
        days_cur = max(1, df_cur['统计周期'].nunique())
        days_prev = max(1, df_prev['统计周期'].nunique())

        # ---------------------------------------------------------------------
        # 看板主界面 UI
        # ---------------------------------------------------------------------
        st.title("📊 顿角咖啡智能经营看板")
        
        q1, a1 = df_cur['销售数量'].sum(), df_cur['销售金额'].sum()
        q2, a2 = df_prev['销售数量'].sum(), df_prev['销售金额'].sum() if not df_prev.empty else (0, 0)

        # 2x2 布局核心指标
        m_col1, m_col2 = st.columns(2)
        m_col3, m_col4 = st.columns(2)
        
        def show_metric(target, label, v, pv, prefix="", suffix=""):
            delta = f"{(v-pv)/pv:.1%}" if pv and pv!=0 else None
            target.metric(label, f"{prefix}{v:,.2f}{suffix}".replace(".00", ""), delta)

        show_metric(m_col1, "总销售杯数", q1, q2 if q2>0 else None, suffix=" 杯")
        show_metric(m_col2, "总营业收入", a1, a2 if a2>0 else None, prefix="¥")
        show_metric(m_col3, "日均营业额", a1/days_cur, (a2/days_prev) if q2>0 else None, prefix="¥")
        show_metric(m_col4, "单杯均价", a1/q1 if q1>0 else 0, (a2/q2) if q2>0 else None, prefix="¥")

        # ---------------------------------------------------------------------
        # 🚀 找回并升级：多维度销售柱状图
        # ---------------------------------------------------------------------
        st.markdown("---")
        # 1. 一级分类
        st.subheader("🏗️ 一级分类大盘结构")
        l1_sum = df_cur.groupby('一级分类').agg({'销售数量':'sum','销售金额':'sum'}).reset_index()
        fig_l1 = go.Figure()
        fig_l1.add_trace(go.Bar(x=l1_sum['一级分类'], y=l1_sum['销售数量'], name='杯数', marker_color='#3B82F6', text=l1_sum['销售数量'], textposition='auto'))
        fig_l1.add_trace(go.Bar(x=l1_sum['一级分类'], y=l1_sum['销售金额'], name='营收', marker_color='#10B981', text=l1_sum['销售金额'].apply(lambda x:f"¥{x:,.0f}"), textposition='auto'))
        fig_l1.update_layout(barmode='group', height=350, margin=dict(l=10,r=10,t=30,b=10), plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_l1, use_container_width=True)

        # 2. 二级分类“三剑客”
        st.markdown("---")
        st.subheader("📈 二级分类精细化分析 (销量 / 营收 / 占比)")
        cat_df = df_cur.groupby('二级分类').agg({'销售数量':'sum', '销售金额':'sum'}).reset_index()
        cat_df['营收占比'] = (cat_df['销售金额'] / cat_df['销售金额'].sum() * 100).round(1)
        cat_df = cat_df.sort_values('销售数量', ascending=False)

        c_l, c_m, c_r = st.columns(3)
        with c_l:
            st.markdown("**1. 分类销量排行榜 (杯数)**")
            st.plotly_chart(px.bar(cat_df, x='二级分类', y='销售数量', text='销售数量', color_discrete_sequence=['#3B82F6']).update_layout(height=400, plot_bgcolor="rgba(0,0,0,0)"), use_container_width=True)
        with c_m:
            st.markdown("**2. 分类营收排行榜 (金额)**")
            st.plotly_chart(px.bar(cat_df, x='二级分类', y='销售金额', text=cat_df['销售金额'].apply(lambda x:f"¥{x:,.0f}"), color_discrete_sequence=['#10B981']).update_layout(height=400, plot_bgcolor="rgba(0,0,0,0)"), use_container_width=True)
        with c_r:
            st.markdown("**3. 品类业绩贡献占比 (%)**")
            st.plotly_chart(px.bar(cat_df, x='二级分类', y='营收占比', text=cat_df['营收占比'].apply(lambda x:f"{x}%"), color_discrete_sequence=['#F59E0B']).update_layout(height=400, plot_bgcolor="rgba(0,0,0,0)"), use_container_width=True)

        # ---------------------------------------------------------------------
        # 单品明细 (暂不看毛利)
        # ---------------------------------------------------------------------
        st.markdown("### 📄 单品销售实绩明细")
        v_df = df_cur.groupby(['商品名称'], as_index=False).agg({'一级分类':'first','二级分类':'first','销售数量':'sum','销售金额':'sum'}).sort_values('销售数量', ascending=False)
        v_df['营收占比'] = (v_df['销售金额'] / v_df['销售金额'].sum() * 100).round(2)
        st.dataframe(v_df[['商品名称','一级分类','二级分类','销售数量','销售金额','营收占比']], column_config={
            "销售数量": st.column_config.ProgressColumn("销量", format="%d", min_value=0, max_value=int(v_df['销售数量'].max())),
            "销售金额": st.column_config.NumberColumn("营收", format="¥%.2f"),
        }, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# ⚙️ 成本配方中心 (BOM 核心升级)
# -----------------------------------------------------------------------------
elif app_mode == "⚙️ 成本与配方中心":
    st.title("⚙️ 三级原物料与配方引擎")
    t1, t2, t3 = st.tabs(["📦 基础原物料库", "📋 配置单品配方 (覆盖更新模式)", "📚 成本卡库管理"])
    
    with t1:
        st.markdown("#### 1. 上传包含三种价格的物料表")
        f = st.file_uploader("上传物料价格档", type=["xlsx", "csv"])
        if f:
            df_u = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df_u.columns = [str(c).strip() for c in df_u.columns]
            ex = {'物流名称': '物料名称', '品项类别': '品项类别', '单价单位': '单位', '物流单价成本': '物流单价', '顿角单价成本': '顿角单价', '百度单价成本': '百度单价'}
            df_u = df_u.rename(columns={c: ex[c] for c in df_u.columns if c in ex})
            if '物料名称' in df_u.columns:
                for p in ['物流单价', '顿角单价', '百度单价']:
                    if p in df_u.columns: df_u[p] = pd.to_numeric(df_u[p], errors='coerce').fillna(0)
                conn = get_db_conn()
                df_u[['物料名称', '品项类别', '单位', '物流单价', '顿角单价', '百度单价']].to_sql('raw_materials', conn, if_exists='replace', index=False)
                conn.close(); st.success("物料单价库已同步"); st.rerun()
        conn = get_db_conn(); st.dataframe(pd.read_sql("SELECT * FROM raw_materials", conn), use_container_width=True); conn.close()

    with t2:
        conn = get_db_conn()
        try:
            df_o = pd.read_sql("SELECT DISTINCT 商品名称, 规格, 做法, 门店名称, 所属项目 FROM (SELECT *, '' as 所属项目 FROM sales_raw)", conn)
            # 补齐项目信息以便选择范围
            df_o = merge_category_map(df_o)
            raws = pd.read_sql("SELECT 物料名称 FROM raw_materials", conn)['物料名称'].tolist()
        except: df_o = pd.DataFrame(); raws = []
        
        if df_o.empty: st.warning("请先在看板导入报表。")
        else:
            c1, c2 = st.columns(2)
            db_t = c1.radio("1. 选择配方轨道", ["🏪 门店配方 (核算各店成本)", "📦 物流配方 (核算出厂成本)"])
            track = '物流' if '物流' in db_t else '门店'
            
            # 范围选择：支持全局、项目、单店
            all_scopes = ["【全局默认配方】", "百度项目", "顿角项目"] + sorted(df_o['门店名称'].unique().tolist())
            scope = c2.selectbox("2. 选择适用范围 (越精准优先级越高)", all_scopes)
            
            st.divider()
            cp1, cp2, cp3 = st.columns(3)
            p = cp1.selectbox("3. 选择商品", sorted(df_o['商品名称'].unique().tolist()))
            s = cp2.selectbox("4. 规格", sorted(df_o[df_o['商品名称']==p]['规格'].unique().tolist()))
            m = cp3.selectbox("5. 做法", sorted(df_o[(df_o['商品名称']==p)&(df_o['规格']==s)]['做法'].unique().tolist()))
            
            # --- 核心：临时物料清单 (Session State) ---
            if 'temp_bom' not in st.session_state: st.session_state.temp_bom = []
            
            with st.container(border=True):
                st.markdown("#### ➕ 录入物料明细")
                cs1, cs2, cs3 = st.columns([3, 1, 1])
                mat_sel = cs1.selectbox("搜索添加物料", ["--请选择--"] + raws)
                qty_sel = cs2.number_input("用量", min_value=0.0, step=0.1)
                if cs3.button("添加一行", use_container_width=True):
                    if mat_sel != "--请选择--" and qty_sel > 0:
                        st.session_state.temp_bom.append({'物料名称': mat_sel, '用量': qty_sel})
                
                if st.session_state.temp_bom:
                    st.markdown("---")
                    temp_df = pd.DataFrame(st.session_state.temp_bom)
                    edited_temp = st.data_editor(temp_df, num_rows="dynamic", use_container_width=True)
                    
                    if st.button("💾 确认并保存整张配方卡", type="primary", use_container_width=True):
                        cursor = conn.cursor()
                        # 覆盖逻辑：先删该轨道/范围/商品/规格/做法下的所有物料
                        cursor.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", (track, scope, p, s, m))
                        for _, row in edited_temp.dropna().iterrows():
                            cursor.execute("INSERT INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (track, scope, p, s, m, row['物料名称'], row['用量']))
                        conn.commit()
                        st.session_state.temp_bom = [] # 清空缓存
                        st.success(f"已成功保存：{p} ({s}/{m}) 的{track}配方卡")
                        st.rerun()
                    if st.button("❌ 放弃并清空上方临时表"):
                        st.session_state.temp_bom = []; st.rerun()

    with t3:
        st.markdown("#### 📚 成本卡库全局管理")
        if st.button("🗑️ 清空所有配方数据"):
            c = get_db_conn(); c.execute("DELETE FROM bom_recipes"); c.commit(); c.close(); st.rerun()
            
        conn = get_db_conn()
        db_b = pd.read_sql("SELECT * FROM bom_recipes", conn)
        db_r = pd.read_sql("SELECT * FROM raw_materials", conn)
        if not db_b.empty:
            merged = db_b.merge(db_r, on='物料名称', how='left').fillna(0)
            merged['lv'] = merged['用量'] * merged['物流单价']; merged['dv'] = merged['用量'] * merged['顿角单价']; merged['bv'] = merged['用量'] * merged['百度单价']
            grps = merged.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'])
            for (rt, sc, pdn, spc, mth), items in grps:
                with st.container(border=True):
                    st.markdown(f'<div class="recipe-card-header"><b>【{rt}】{pdn}</b> <span style="color:#64748B;">({spc}/{mth})</span><br><small>范围: {sc}</small></div>', unsafe_allow_html=True)
                    st.markdown(f'<span class="cost-tag">📦出厂:¥{items["lv"].sum():.2f}</span><span class="cost-tag">🏬顿角:¥{items["dv"].sum():.2f}</span><span class="cost-tag">🏢百度:¥{items["bv"].sum():.2f}</span>', unsafe_allow_html=True)
                    if st.button("🗑️ 彻底删除此整卡", key=f"dc_all_{rt}_{sc}_{pdn}_{spc}_{mth}", type="primary"):
                        conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? ", (rt, sc, pdn, spc, mth))
                        conn.commit(); st.rerun()
                    st.write("🌿 已包含: " + " 、 ".join([f"{r['物料名称']}({r['用量']}g)" for _,r in items.iterrows()]))
        else: st.info("库内为空。")
        conn.close()
