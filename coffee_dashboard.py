# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import sqlite3
import re
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 1. 核心配置与 CSS 注入 (布局与显示优化)
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
        background-color: #FFFFFF; padding: 18px; border-radius: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); border: 1px solid #E2E8F0;
    }
    [data-testid="stMetricValue"] {
        font-size: 28px !important; font-weight: 800 !important;
        background: -webkit-linear-gradient(120deg, #1E40AF, #3B82F6);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    
    /* 容器间距 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; border-radius: 15px; border: 1px solid #E2E8F0; padding: 20px;
    }
    
    /* 卡片页眉 */
    .recipe-card-header { background: #F1F5F9; padding: 12px 15px; border-radius: 10px; border-left: 6px solid #3B82F6; margin-bottom: 10px; }
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
    conn.commit(); conn.close()

init_db()

# -----------------------------------------------------------------------------
# 3. 计算与处理引擎
# -----------------------------------------------------------------------------
def standardize_date(val, f_name):
    try: return pd.to_datetime(val).strftime('%Y-%m-%d')
    except:
        match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{8}', f_name)
        return pd.to_datetime(match.group()).strftime('%Y-%m-%d') if match else datetime.now().strftime('%Y-%m-%d')

def clean_store_name(n): return str(n).strip().replace(" ", "").replace("(", "（").replace(")", "）")

def merge_category_map(df):
    if df.empty: return df
    df_cat = pd.DataFrame(CATEGORY_MAPPING_DATA)
    if '一级分类' in df.columns: df = df.drop(columns=['一级分类'], errors='ignore')
    if '二级分类' in df.columns: df = df.drop(columns=['二级分类'], errors='ignore')
    df = pd.merge(df, df_cat, left_on='商品类别', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('未分类')
    df['二级分类'] = df['二级分类'].fillna('未分类')
    s2p = {clean_store_name(s): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(clean_store_name(x), '其他项目'))
    return df

# -----------------------------------------------------------------------------
# 4. 侧边栏与数据管线 (ETL)
# -----------------------------------------------------------------------------
app_mode = st.sidebar.radio("🧭 系统导航", ["📊 经营分析看板", "⚙️ 成本与配方中心"])

if app_mode == "📊 经营分析看板":
    with st.sidebar.expander("💾 数据管理 (ETL)", expanded=False):
        conn = get_db_conn()
        try:
            total_rows = pd.read_sql("SELECT COUNT(*) as c FROM sales_raw", conn).iloc[0]['c']
            available_periods = sorted(pd.read_sql("SELECT DISTINCT 统计周期 FROM sales_raw", conn)['统计周期'].tolist())
        except: total_rows = 0; available_periods = []
        finally: conn.close()
        st.markdown(f"库内已存 **{total_rows:,}** 条流水")
        files = st.file_uploader("📥 导入流水表", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            conn = get_db_conn()
            for f in files:
                if pd.read_sql("SELECT COUNT(*) as c FROM sales_raw WHERE source_file=?", conn, params=(f.name,)).iloc[0]['c'] > 0: continue
                df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                df.columns = [str(c).strip() for c in df.columns]
                for c in df.columns:
                    if '规格' in c: df.rename(columns={c: '规格'}, inplace=True)
                    elif any(k in c for k in ['做法', '口味', '属性']): df.rename(columns={c: '做法'}, inplace=True)
                df = df.rename(columns=RAW_COLUMN_MAPPING)
                df['统计周期'] = df['统计周期'].apply(lambda x: standardize_date(x, f.name))
                df['规格'] = df['规格'].replace(['nan', 'None', '', '0'], '常规').fillna('常规')
                df['做法'] = df['做法'].replace(['nan', 'None', '', '0'], '常规').fillna('常规')
                df['门店名称'] = df['门店名称'].apply(clean_store_name).ffill()
                for c in ['销售金额', '销售数量']:
                    if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(r'[¥$,￥]', '', regex=True), errors='coerce').fillna(0)
                df['source_file'] = f.name
                df[['门店名称', '商品名称', '商品类别', '规格', '做法', '统计周期', '销售金额', '销售数量', 'source_file']].to_sql('sales_raw', conn, if_exists='append', index=False)
            conn.close(); st.rerun()
        if st.button("🗑️ 清空流水数据", use_container_width=True):
            c = get_db_conn(); c.execute("DELETE FROM sales_raw"); c.commit(); c.close(); st.rerun()

    if total_rows == 0: st.info("请先上传企迈日结表数据。"); st.stop()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 经营周期筛选")
    parsed_dates = [datetime.strptime(p, '%Y-%m-%d').date() for p in available_periods if p]
    
    # 🌓 找回环比开关
    enable_comp = st.sidebar.checkbox("🌓 开启环比对比", value=False)
    sel_range = st.sidebar.date_input("本期日期", [min(parsed_dates), max(parsed_dates)], min_value=min(parsed_dates), max_value=max(parsed_dates))
    
    df_cur = pd.DataFrame(); df_prev = pd.DataFrame()
    if len(sel_range) == 2:
        s1, e1 = sel_range
        conn = get_db_conn()
        df_cur = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(s1.strftime('%Y-%m-%d'), e1.strftime('%Y-%m-%d')))
        
        if enable_comp:
            # 自动计算上期
            dur = (e1 - s1).days + 1
            s2, e2 = s1 - timedelta(days=dur), s1 - timedelta(days=1)
            prev_range = st.sidebar.date_input("对比上期", [s2, e2])
            if len(prev_range) == 2:
                df_prev = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(prev_range[0].strftime('%Y-%m-%d'), prev_range[1].strftime('%Y-%m-%d')))
        conn.close()

    # 找回深度筛选
    if not df_cur.empty:
        df_cur = merge_category_map(df_cur)
        if not df_prev.empty: df_prev = merge_category_map(df_prev)
        
        st.sidebar.markdown("---")
        # 一级分类筛选
        all_l1 = sorted(df_cur['一级分类'].unique().tolist())
        sel_l1 = st.sidebar.multiselect("一级分类筛选", all_l1)
        if sel_l1: 
            df_cur = df_cur[df_cur['一级分类'].isin(sel_l1)]
            if not df_prev.empty: df_prev = df_prev[df_prev['一级分类'].isin(sel_l1)]

        # 项目筛选
        all_projs = sorted(df_cur['所属项目'].unique().tolist())
        sel_projs = st.sidebar.multiselect("所属项目筛选", all_projs)
        if sel_projs: 
            df_cur = df_cur[df_cur['所属项目'].isin(sel_projs)]
            if not df_prev.empty: df_prev = df_prev[df_prev['所属项目'].isin(sel_projs)]
            
        # 门店筛选
        all_sts = sorted(df_cur['门店名称'].unique().tolist())
        sel_sts = st.sidebar.multiselect("具体门店筛选", all_sts)
        if sel_sts: 
            df_cur = df_cur[df_cur['门店名称'].isin(sel_sts)]
            if not df_prev.empty: df_prev = df_prev[df_prev['门店名称'].isin(sel_sts)]

        days_cur = df_cur['统计周期'].nunique() if not df_cur.empty else 1
        days_prev = df_prev['统计周期'].nunique() if not df_prev.empty else 1

        # ---------------------------------------------------------------------
        # 找回核心看板 UI
        # ---------------------------------------------------------------------
        st.title("📊 顿角咖啡经营决策看板")
        
        def get_summary(df, days):
            if df.empty: return 0,0,0,0
            qty, amt = df['销售数量'].sum(), df['销售金额'].sum()
            return qty, amt, amt/days, amt/qty if qty>0 else 0

        q1, a1, dr1, cp1 = get_summary(df_cur, days_cur)
        q2, a2, dr2, cp2 = get_summary(df_prev, days_prev) if not df_prev.empty else (None,None,None,None)

        # 布局：2行2列，确保数字完全显示
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        
        def metric_ui(target, label, val, p_val, prefix="", suffix=""):
            delta = f"{(val-p_val)/p_val:.1%}" if p_val and p_val!=0 else None
            target.metric(label, f"{prefix}{val:,.2f}{suffix}".replace(".00", ""), delta)

        metric_ui(c1, "总销售数量", q1, q2, suffix=" 杯")
        metric_ui(c2, "总营业收入", a1, a2, prefix="¥")
        metric_ui(c3, "日均营业额", dr1, dr2, prefix="¥")
        metric_ui(c4, "平均杯单价", cp1, cp2, prefix="¥")

        # ---------------------------------------------------------------------
        # 🚀 找回并升级：二级分类销量、营收与占比柱状图
        # ---------------------------------------------------------------------
        st.markdown("---")
        st.subheader("📈 品类销售结构 (二级分类)")
        
        cat_data = df_cur.groupby('二级分类').agg({'销售数量':'sum', '销售金额':'sum'}).reset_index()
        cat_data['营收占比'] = (cat_data['销售金额'] / cat_data['销售金额'].sum() * 100).round(1)
        cat_data = cat_data.sort_values('销售数量', ascending=False)

        if PLOTLY_AVAILABLE:
            fig_cat = go.Figure()
            # 销量轴
            fig_cat.add_trace(go.Bar(
                x=cat_data['二级分类'], y=cat_data['销售数量'], name='销量 (杯)',
                marker_color='#3B82F6', text=cat_data['销售数量'], textposition='auto'
            ))
            # 营收轴
            fig_cat.add_trace(go.Bar(
                x=cat_data['二级分类'], y=cat_data['销售金额'], name='营收 (元)',
                marker_color='#10B981', text=cat_data['销售金额'].apply(lambda x: f"¥{x:,.0f}"), textposition='auto'
            ))
            fig_cat.update_layout(
                barmode='group', height=450, margin=dict(l=10, r=10, t=30, b=10),
                legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
                plot_bgcolor="rgba(0,0,0,0)", yaxis=dict(showgrid=True, gridcolor='#F1F5F9')
            )
            st.plotly_chart(fig_cat, use_container_width=True)

        # ---------------------------------------------------------------------
        # 找回：单品明细表 (含一级分类)
        # ---------------------------------------------------------------------
        st.markdown("### 📄 单品销售明细排行")
        
        view_df = df_cur.groupby(['商品名称'], as_index=False).agg({
            '一级分类': 'first',
            '二级分类': 'first',
            '销售数量': 'sum',
            '销售金额': 'sum'
        }).sort_values('销售数量', ascending=False)
        
        view_df['营收占比'] = (view_df['销售金额'] / view_df['销售金额'].sum() * 100).round(2)

        st.dataframe(view_df[['商品名称','一级分类','二级分类','销售数量','销售金额','营收占比']], column_config={
            "销售数量": st.column_config.ProgressColumn("总销量", format="%d", min_value=0, max_value=int(view_df['销售数量'].max())),
            "销售金额": st.column_config.NumberColumn("营收金额", format="¥%.2f"),
            "营收占比": st.column_config.NumberColumn("占比", format="%.2f%%"),
        }, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# ⚙️ 成本配方中心 (保持最新逻辑)
# -----------------------------------------------------------------------------
elif app_mode == "⚙️ 成本与配方中心":
    st.title("⚙️ 三级原物料与配方引擎")
    tab1, tab2, tab3 = st.tabs(["📦 基础原物料库", "📋 配置单品配方", "📚 成本卡库管理"])
    
    with tab1:
        f = st.file_uploader("上传原物料表", type=["xlsx", "csv"])
        if f:
            df_u = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df_u.columns = [str(c).strip() for c in df_u.columns]
            ex = {'物流名称': '物料名称', '品项类别': '品项类别', '单价单位': '单位', '物流单价成本': '物流单价', '顿角单价成本': '顿角单价', '百度单价成本': '百度单价'}
            df_u = df_u.rename(columns={c: ex[c] for c in df_u.columns if c in ex})
            if '物料名称' in df_u.columns:
                for p in ['物流单价', '顿角单价', '百度单价']:
                    if p in df_u.columns: df_u[p] = pd.to_numeric(df_u[p], errors='coerce').fillna(0)
                c = get_db_conn(); df_u[['物料名称', '品项类别', '单位', '物流单价', '顿角单价', '百度单价']].to_sql('raw_materials', c, if_exists='replace', index=False); c.close(); st.success("已更新"); st.rerun()
        c = get_db_conn(); st.dataframe(pd.read_sql("SELECT * FROM raw_materials", c), use_container_width=True); c.close()

    with tab2:
        conn = get_db_conn()
        try:
            df_o = pd.read_sql("SELECT DISTINCT 商品名称, 规格, 做法, 门店名称, 商品类别 FROM sales_raw", conn)
            df_o = merge_category_map(df_o); df_o = df_o[df_o['一级分类'] != '未分类']
            rmats = pd.read_sql("SELECT 物料名称 FROM raw_materials", conn)['物料名称'].tolist()
        except: df_o = pd.DataFrame(); rmats = []
        
        if df_o.empty: st.warning("请在看板导入销售报表。")
        else:
            c1, c2 = st.columns(2)
            db_t = '物流' if '物流' in c1.radio("核算轨道", ["🏪 门店配方", "📦 物流配方"]) else '门店'
            scp = "【全局默认配方】" if db_t == '物流' else c2.selectbox("适用范围", ["【全局默认配方】", "【顿角项目配方】", "【百度项目配方】"] + sorted(df_o['门店名称'].unique().tolist()))
            
            p = st.selectbox("选择商品", sorted(df_o['商品名称'].unique().tolist()))
            s = st.selectbox("选择规格", sorted(df_o[df_o['商品名称']==p]['规格'].unique().tolist()))
            m = st.selectbox("选择做法", sorted(df_o[(df_o['商品名称']==p)&(df_o['规格']==s)]['做法'].unique().tolist()))
            
            with st.container(border=True):
                st.markdown(f"#### ➕ 添加成分")
                cs1, cs2, cs3 = st.columns([3, 1, 1])
                mat = cs1.selectbox("物料名称", ["--请选择--"] + rmats)
                qty = cs2.number_input("用量(g/ml)", min_value=0.0, step=1.0)
                if cs3.button("确认添加", type="primary", use_container_width=True):
                    if mat != "--请选择--" and qty > 0:
                        conn.execute("INSERT OR REPLACE INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (db_t, scp, p, s, m, mat, qty))
                        conn.commit(); st.rerun()

            curr = pd.read_sql("SELECT 物料名称, 用量 FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", conn, params=(db_t, scp, p, s, m))
            for i, r in curr.iterrows():
                cc1, cc2, cc3, cc4 = st.columns([4, 2, 1, 1])
                cc1.write(f"☕ {r['物料名称']}")
                nq = cc2.number_input("用量", value=float(r['用量']), key=f"q_{i}", label_visibility="collapsed")
                if cc3.button("存", key=f"s_{i}"):
                    conn.execute("UPDATE bom_recipes SET 用量=? WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", (nq, db_t, scp, p, s, m, r['物料名称']))
                    conn.commit(); st.rerun()
                if cc4.button("删", key=f"d_{i}", type="secondary"):
                    conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", (db_t, scp, p, s, m, r['物料名称']))
                    conn.commit(); st.rerun()
        conn.close()

    with tab3:
        st.markdown("#### 📚 成本卡库管理")
        if st.button("🗑️ 清空所有配方库数据", type="secondary"):
            c = get_db_conn(); c.execute("DELETE FROM bom_recipes"); c.commit(); c.close(); st.rerun()
            
        if 'edit_m' not in st.session_state: st.session_state.edit_m = False
        if st.button("📝 开启/关闭 全局管理模式", type="primary"): 
            st.session_state.edit_m = not st.session_state.edit_m; st.rerun()
        
        conn = get_db_conn()
        db_b = pd.read_sql("SELECT * FROM bom_recipes", conn)
        db_r = pd.read_sql("SELECT * FROM raw_materials", conn)
        if not db_b.empty:
            merged = db_b.merge(df_r, on='物料名称', how='left').fillna(0)
            merged['lv'] = merged['用量'] * merged['物流单价']; merged['dv'] = merged['用量'] * merged['顿角单价']; merged['bv'] = merged['用量'] * merged['百度单价']
            grps = merged.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'])
            for (rt, sc, pdn, spc, mth), items in grps:
                with st.container(border=True):
                    st.markdown(f'<div class="recipe-card-header"><b>【{rt}】{pdn}</b> <span style="color:#64748B;">({spc}/{mth})</span><br><small>适用范围: {sc}</small></div>', unsafe_allow_html=True)
                    st.markdown(f'<span class="cost-tag">📦出厂:¥{items["lv"].sum():.2f}</span><span class="cost-tag">🏬顿角:¥{items["dv"].sum():.2f}</span><span class="cost-tag">🏢百度:¥{items["bv"].sum():.2f}</span>', unsafe_allow_html=True)
                    if st.session_state.edit_m:
                        ed = st.data_editor(items[['物料名称', '用量']], key=f"ed_{rt}_{sc}_{pdn}_{spc}_{mth}", use_container_width=True, num_rows="dynamic")
                        col1, col2, _ = st.columns([1, 1, 3])
                        if col1.button("💾 保存修改", key=f"sv_{rt}_{pdn}_{spc}_{mth}"):
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", (rt, sc, pdn, spc, mth))
                            for _, r in ed.dropna(subset=['物料名称']).iterrows():
                                if r['用量'] > 0: cursor.execute("INSERT INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (rt, sc, pdn, spc, mth, r['物料名称'], r['用量']))
                            conn.commit(); st.rerun()
                        if col2.button("🗑️ 删除整卡", key=f"dc_{rt}_{pdn}_{spc}_{mth}", type="primary"):
                            conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? ", (rt, sc, pdn, spc, mth))
                            conn.commit(); st.rerun()
                    else:
                        st.write("🌿 " + " 、 ".join([f"{r['物料名称']}({r['用量']}g)" for _,r in items.iterrows()]))
        conn.close()
