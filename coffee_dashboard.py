# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import sqlite3
import re
from datetime import datetime

# -----------------------------------------------------------------------------
# 1. 核心配置与 CSS 注入 (全功能精装版)
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

# 注入企业级视觉样式
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
        font-size: 32px !important; font-weight: 800 !important;
        background: -webkit-linear-gradient(120deg, #1E40AF, #3B82F6);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    
    /* 图表和表格容器 */
    .stTable, .plotly-graph-div { border-radius: 15px; overflow: hidden; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; border-radius: 15px; border: 1px solid #E2E8F0; padding: 20px;
    }
    
    /* 配方中心管理卡片 */
    .recipe-card-header { background: #F1F5F9; padding: 12px 15px; border-radius: 10px; border-left: 6px solid #3B82F6; margin-bottom: 10px; }
    .cost-tag { background: #DBEAFE; color: #1E40AF; padding: 3px 8px; border-radius: 5px; font-size: 13px; font-weight: 700; margin-right: 5px; border: 1px solid #BFDBFE; }
</style>
""", unsafe_allow_html=True)

try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# -----------------------------------------------------------------------------
# 2. 核心字典与数据库
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
    cursor.execute("UPDATE sales_raw SET 规格 = '常规' WHERE 规格 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE sales_raw SET 做法 = '常规' WHERE 做法 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE bom_recipes SET 规格 = '常规' WHERE 规格 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE bom_recipes SET 做法 = '常规' WHERE 做法 IN ('0', 'nan', 'None', '', 'NaN')")
    conn.commit(); conn.close()

init_db()

# -----------------------------------------------------------------------------
# 3. 核心计算引擎
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
    if '二级分类' in df.columns: df = df.drop(columns=['二级分类'])
    df = pd.merge(df, df_cat, left_on='商品类别', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('未分类')
    s2p = {clean_store_name(s): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(clean_store_name(x), '其他项目'))
    return df

def merge_dynamic_cost_data(df):
    if df.empty: return df
    conn = get_db_conn()
    df_b = pd.read_sql("SELECT * FROM bom_recipes", conn)
    df_r = pd.read_sql("SELECT * FROM raw_materials", conn)
    conn.close()
    df['物流单位成本'] = df['门店单位成本'] = 0.0
    if not df_b.empty and not df_r.empty:
        m = df_b.merge(df_r, on='物料名称', how='left').fillna(0)
        m['cl'] = m['用量'] * m['物流单价']
        m['cdj'] = m['用量'] * m['顿角单价']
        m['cbd'] = m['用量'] * m['百度单价']
        g = m.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'], as_index=False)[['cl', 'cdj', 'cbd']].sum()
        # 物流成本
        lb = g[g['配方类型'] == '物流'][['商品名称', '规格', '做法', 'cl']].rename(columns={'cl': 'lc'})
        df = df.merge(lb, on=['商品名称', '规格', '做法'], how='left')
        df['物流单位成本'] = df['lc'].fillna(0.0)
        # 门店成本
        sb = g[g['配方类型'] == '门店']
        df = df.merge(sb.rename(columns={'适用范围':'门店名称','cdj':'sdj','cbd':'sbd'})[['门店名称','商品名称','规格','做法','sdj','sbd']], on=['门店名称','商品名称','规格','做法'], how='left')
        df = df.merge(sb.rename(columns={'适用范围':'所属项目','cdj':'pdj','cbd':'pbd'})[['所属项目','商品名称','规格','做法','pdj','pbd']], on=['所属项目','商品名称','规格','做法'], how='left')
        df = df.merge(sb[sb['适用范围'] == '【全局默认配方】'].rename(columns={'cdj':'gdj','cbd':'gbd'})[['商品名称','规格','做法','gdj','gbd']], on=['商品名称','规格','做法'], how='left')
        df['mbd'] = df['sbd'].fillna(df['pbd']).fillna(df['gbd']).fillna(0.0)
        df['mdj'] = df['sdj'].fillna(df['pdj']).fillna(df['gdj']).fillna(0.0)
        df['门店单位成本'] = np.where(df['所属项目'] == '百度项目', df['mbd'], df['mdj'])
        df.drop(columns=['lc','sdj','sbd','pdj','pbd','gdj','gbd','mbd','mdj'], inplace=True, errors='ignore')
    df['门店毛利'] = df['销售金额'] - (df['销售数量'] * df['门店单位成本'])
    df['物流毛利'] = df['销售金额'] - (df['销售数量'] * df['物流单位成本'])
    return df

# -----------------------------------------------------------------------------
# 4. 侧边栏与数据管线
# -----------------------------------------------------------------------------
app_mode = st.sidebar.radio("🧭 系统导航", ["📊 经营分析看板", "⚙️ 成本与配方中心"])

logo_path = "logo.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, width=120)
else: st.sidebar.image("https://cdn-icons-png.flaticon.com/512/751/751621.png", width=100)

if app_mode == "📊 经营分析看板":
    with st.sidebar.expander("💾 数据管线 (ETL)", expanded=False):
        conn = get_db_conn()
        try:
            total_rows = pd.read_sql("SELECT COUNT(*) as c FROM sales_raw", conn).iloc[0]['c']
            available_periods = sorted(pd.read_sql("SELECT DISTINCT 统计周期 FROM sales_raw", conn)['统计周期'].tolist())
        except: total_rows = 0; available_periods = []
        finally: conn.close()
        st.markdown(f"库内已存 **{total_rows:,}** 条流水")
        files = st.file_uploader("📥 导入企迈流水", type=["xlsx", "csv"], accept_multiple_files=True)
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
                valid_cats = set([i["二级分类"] for i in CATEGORY_MAPPING_DATA])
                if '商品类别' in df.columns: df = df[df['商品类别'].isin(valid_cats)]
                if df.empty: continue
                df['统计周期'] = df['统计周期'].apply(lambda x: standardize_date(x, f.name))
                df['规格'] = df['规格'].replace(['nan', 'None', '', '0'], '常规').fillna('常规')
                df['做法'] = df['做法'].replace(['nan', 'None', '', '0'], '常规').fillna('常规')
                df['门店名称'] = df['门店名称'].apply(clean_store_name).ffill()
                for c in ['销售金额', '销售数量']:
                    if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(r'[¥$,￥]', '', regex=True), errors='coerce').fillna(0)
                df['source_file'] = f.name
                df[['门店名称', '商品名称', '商品类别', '规格', '做法', '统计周期', '销售金额', '销售数量', 'source_file']].to_sql('sales_raw', conn, if_exists='append', index=False)
            conn.close(); st.rerun()
        if st.button("🗑️ 清空销售流水", use_container_width=True):
            c = get_db_conn(); c.execute("DELETE FROM sales_raw"); c.commit(); c.close(); st.rerun()

    if total_rows == 0: st.info("请先在左侧上传企迈日结表。"); st.stop()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 日期与深度筛选")
    parsed_dates = [datetime.strptime(p, '%Y-%m-%d').date() for p in available_periods if p]
    if parsed_dates:
        sel_range = st.sidebar.date_input("选择日期范围", [min(parsed_dates), max(parsed_dates)], min_value=min(parsed_dates), max_value=max(parsed_dates))
        if len(sel_range) == 2:
            s, e = sel_range
            conn = get_db_conn()
            df_cur = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(s.strftime('%Y-%m-%d'), e.strftime('%Y-%m-%d')))
            conn.close()
            if not df_cur.empty:
                df_cur = merge_category_map(df_cur)
                
                # -------------------------------------------------------------
                # 🚀 找回筛选器：项目与门店
                # -------------------------------------------------------------
                all_projs = sorted(df_cur['所属项目'].unique().tolist())
                sel_projs = st.sidebar.multiselect("所属项目", all_projs)
                if sel_projs: df_cur = df_cur[df_cur['所属项目'].isin(sel_projs)]
                
                all_sts = sorted(df_cur['门店名称'].unique().tolist())
                sel_sts = st.sidebar.multiselect("门店筛选", all_sts)
                if sel_sts: df_cur = df_cur[df_cur['门店名称'].isin(sel_sts)]
                
                df_cur = merge_dynamic_cost_data(df_cur)
                days_cur = df_cur['统计周期'].nunique() if not df_cur.empty else 1
                
                # -------------------------------------------------------------
                # 找回核心看板 UI
                # -------------------------------------------------------------
                st.title("📊 顿角咖啡智能经营看板")
                st.markdown(f"📅 分析周期：`{s.strftime('%Y/%m/%d')} - {e.strftime('%Y/%m/%d')}` ({days_cur}天有效数据)")
                
                qty = df_cur['销售数量'].sum()
                amt = df_cur['销售金额'].sum()
                ml = (df_cur['物流毛利'].sum() / amt * 100) if amt > 0 else 0
                ms = (df_cur['门店毛利'].sum() / amt * 100) if amt > 0 else 0
                cp = (amt / qty) if qty > 0 else 0
                dr = amt / days_cur
                
                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric("总销量", f"{int(qty)} 杯")
                c2.metric("总营收", f"¥{amt:,.0f}")
                c3.metric("日均营收", f"¥{dr:,.0f}")
                c4.metric("杯单价", f"¥{cp:.2f}")
                c5.metric("出厂毛利", f"{ml:.1f}%")
                c6.metric("门店毛利", f"{ms:.1f}%")
                
                # -------------------------------------------------------------
                # 找回图表排行
                # -------------------------------------------------------------
                st.markdown("---")
                chart_left, chart_right = st.columns(2)
                
                with chart_left:
                    st.subheader("🔥 销量排行 Top 10")
                    top10 = df_cur.groupby('商品名称')['销售数量'].sum().sort_values(ascending=True).tail(10).reset_index()
                    fig1 = px.bar(top10, y='商品名称', x='销售数量', orientation='h', text_auto='.1f', color_discrete_sequence=['#3B82F6'])
                    fig1.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=350, plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig1, use_container_width=True)
                    
                with chart_right:
                    st.subheader("💰 利润贡献 Top 10")
                    profit10 = df_cur.groupby('商品名称')['门店毛利'].sum().sort_values(ascending=True).tail(10).reset_index()
                    fig2 = px.bar(profit10, y='商品名称', x='门店毛利', orientation='h', text_auto='.0f', color_discrete_sequence=['#10B981'])
                    fig2.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=350, plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig2, use_container_width=True)

                # -------------------------------------------------------------
                # 找回智能表格：BCG矩阵 + 加权成本
                # -------------------------------------------------------------
                st.markdown("### 📄 商品经营明细 (规格加权核算)")
                df_cur['wlt'] = df_cur['销售数量'] * df_cur['物流单位成本']
                df_cur['wst'] = df_cur['销售数量'] * df_cur['门店单位成本']
                df_cur['is_m'] = ((df_cur['物流单位成本'] == 0) & (df_cur['门店单位成本'] == 0)).astype(int)
                
                view = df_cur.groupby('商品名称', as_index=False).agg({
                    '二级分类': 'first', '销售数量': 'sum', '销售金额': 'sum', 
                    'wlt': 'sum', 'wst': 'sum', '门店毛利': 'sum', 'is_m': 'max'
                })
                view['加权出厂价'] = np.where(view['销售数量']>0, view['wlt']/view['销售数量'], 0)
                view['加权到店价'] = np.where(view['销售数量']>0, view['wst']/view['销售数量'], 0)
                view['毛利率'] = (view['门店毛利']/view['销售金额']*100).fillna(0)
                
                avg_q, avg_m = view['销售数量'].mean(), view['毛利率'].mean()
                def get_tag(r):
                    if r['销售数量']>=avg_q and r['毛利率']>=avg_m: return "🌟明星"
                    elif r['销售数量']>=avg_q: return "🐮金牛"
                    elif r['毛利率']>=avg_m: return "❓问题"
                    return "🐕瘦狗"
                view['矩阵属性'] = view.apply(get_tag, axis=1)
                view['健康度'] = view.apply(lambda r: "⚠️缺配方" if r['is_m']==1 else ("🔴低毛利" if r['毛利率']<60 else "🟢正常"), axis=1)

                st.dataframe(view[['商品名称','二级分类','矩阵属性','健康度','销售数量','销售金额','加权出厂价','加权到店价','毛利率']], column_config={
                    "销售数量": st.column_config.ProgressColumn("总销量", format="%d", min_value=0, max_value=int(view['销售数量'].max())),
                    "销售金额": st.column_config.NumberColumn("营收", format="¥%.0f"),
                    "加权出厂价": st.column_config.NumberColumn("出厂价", format="¥%.2f"),
                    "加权到店价": st.column_config.NumberColumn("到店价", format="¥%.2f"),
                    "毛利率": st.column_config.NumberColumn("毛利率", format="%.2f%%"),
                }, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# ⚙️ 成本配方中心 (Tab 3 极简管理版)
# -----------------------------------------------------------------------------
elif app_mode == "⚙️ 成本与配方中心":
    st.title("⚙️ 三级原物料与配方引擎")
    t1, t2, t3 = st.tabs(["📦 第一步：基础原物料库", "📋 第二步：配置单品成本卡", "📚 第三步：成本卡总览与管理"])
    
    with t1:
        f = st.file_uploader("上传三级价格原物料表", type=["xlsx", "csv"])
        if f:
            df = load_data_from_buffer(f)
            if df is not None:
                df.columns = [str(c).strip() for c in df.columns]
                ex = {'物流名称': '物料名称', '品项类别': '品项类别', '单价单位': '单位', '物流单价成本': '物流单价', '顿角单价成本': '顿角单价', '百度单价成本': '百度单价'}
                df = df.rename(columns={c: ex[c] for c in df.columns if c in ex})
                if '物料名称' in df.columns:
                    for p in ['物流单价', '顿角单价', '百度单价']:
                        if p in df.columns: df[p] = pd.to_numeric(df[p], errors='coerce').fillna(0)
                    c = get_db_conn(); df[['物料名称', '品项类别', '单位', '物流单价', '顿角单价', '百度单价']].to_sql('raw_materials', c, if_exists='replace', index=False); c.close(); st.success("原物料库已刷新"); st.rerun()
        c = get_db_conn(); st.dataframe(pd.read_sql("SELECT * FROM raw_materials", c), use_container_width=True); c.close()

    with t2:
        conn = get_db_conn()
        try:
            df_o = pd.read_sql("SELECT DISTINCT 商品名称, 规格, 做法, 门店名称 FROM sales_raw", conn)
            df_o['规格'] = df_o['规格'].fillna('常规').astype(str)
            df_o['做法'] = df_o['做法'].fillna('常规').astype(str)
            df_o = merge_category_map(df_o); df_o = df_o[df_o['一级分类'] != '未分类']
            raws = pd.read_sql("SELECT 物料名称 FROM raw_materials", conn)['物料名称'].tolist()
        except: df_o = pd.DataFrame(); raws = []
        
        if df_o.empty: st.warning("请在看板导入销售报表。")
        else:
            c_type, c_scope = st.columns(2)
            db_type = '物流' if '物流' in c_type.radio("配方轨道", ["🏪 门店配方", "📦 物流配方"]) else '门店'
            scope = "【全局默认配方】" if db_type == '物流' else c_scope.selectbox("适用范围", ["【全局默认配方】", "【顿角项目配方】", "【百度项目配方】"] + sorted(df_o['门店名称'].unique().tolist()))
            
            cp1, cp2, cp3 = st.columns(3)
            p = cp1.selectbox("选择商品", sorted(df_o['商品名称'].unique().tolist()))
            s = cp2.selectbox("选择规格", sorted(df_o[df_o['商品名称']==p]['规格'].unique().tolist()))
            m = cp3.selectbox("选择做法", sorted(df_o[(df_o['商品名称']==p)&(df_o['规格']==s)]['做法'].unique().tolist()))
            
            with st.container(border=True):
                st.markdown(f"#### ➕ 添加物料")
                cs1, cs2, cs3 = st.columns([3, 1, 1])
                mat = cs1.selectbox("搜索物料", ["--请选择--"] + raws)
                qty = cs2.number_input("用量", min_value=0.0, step=1.0)
                if cs3.button("确认添加", type="primary", use_container_width=True):
                    if mat != "--请选择--" and qty > 0:
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR REPLACE INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (db_type, scope, p, s, m, mat, qty))
                        conn.commit(); st.toast("✅ 已添加"); st.rerun()

            curr = pd.read_sql("SELECT 物料名称, 用量 FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", conn, params=(db_type, scope, p, s, m))
            for i, r in curr.iterrows():
                cc1, cc2, cc3, cc4 = st.columns([4, 2, 1, 1])
                cc1.write(f"☕ {r['物料名称']}")
                nq = cc2.number_input("用量", value=float(r['用量']), key=f"t2q_{i}", label_visibility="collapsed")
                if cc3.button("存", key=f"t2s_{i}"):
                    conn.execute("UPDATE bom_recipes SET 用量=? WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", (nq, db_type, scope, p, s, m, r['物料名称']))
                    conn.commit(); st.rerun()
                if cc4.button("删", key=f"t2d_{i}"):
                    conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", (db_type, scope, p, s, m, r['物料名称']))
                    conn.commit(); st.rerun()
        conn.close()

    with t3:
        st.markdown("#### 📚 成本卡库全局管理")
        c_top1, c_top2 = st.columns([1, 4])
        if c_top1.button("🗑️ 清空配方库", type="secondary", use_container_width=True):
            c = get_db_conn(); c.execute("DELETE FROM bom_recipes"); c.commit(); c.close(); st.rerun()
            
        if 'edit_m' not in st.session_state: st.session_state.edit_m = False
        if st.button("📝 开启/关闭 全局管理模式 (支持改用量及整卡删除)", type="primary"): 
            st.session_state.edit_m = not st.session_state.edit_m
            st.rerun()
        
        conn = get_db_conn()
        df_b = pd.read_sql("SELECT * FROM bom_recipes", conn)
        df_r = pd.read_sql("SELECT * FROM raw_materials", conn)
        if not df_b.empty:
            merged = df_b.merge(df_r, on='物料名称', how='left').fillna(0)
            merged['lv'] = merged['用量'] * merged['物流单价']
            merged['dv'] = merged['用量'] * merged['顿角单价']
            merged['bv'] = merged['用量'] * merged['百度单价']
            grps = merged.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'])
            for (rt, sc, pdn, spc, mth), items in grps:
                with st.container(border=True):
                    st.markdown(f'<div class="recipe-card-header"><b>【{rt}】{pdn}</b> <span style="color:#64748B;">({spc}/{mth})</span><br><small>适用: {sc}</small></div>', unsafe_allow_html=True)
                    st.markdown(f'<span class="cost-tag">📦出厂:¥{items["lv"].sum():.2f}</span><span class="cost-tag">🏬顿角:¥{items["dv"].sum():.2f}</span><span class="cost-tag">🏢百度:¥{items["bv"].sum():.2f}</span>', unsafe_allow_html=True)
                    if st.session_state.edit_m:
                        ed = st.data_editor(items[['物料名称', '用量']], key=f"ed_{rt}_{sc}_{pdn}_{spc}_{mth}", use_container_width=True, num_rows="dynamic")
                        col1, col2, _ = st.columns([1, 1, 3])
                        if col1.button("💾 保存卡片", key=f"sv_{rt}_{pdn}_{spc}_{mth}"):
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", (rt, sc, pdn, spc, mth))
                            for _, row in ed.dropna(subset=['物料名称']).iterrows():
                                if row['用量'] > 0: cursor.execute("INSERT INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (rt, sc, pdn, spc, mth, row['物料名称'], row['用量']))
                            conn.commit(); st.toast("卡片已保存"); st.rerun()
                        if col2.button("🗑️ 删除整卡", key=f"dc_{rt}_{pdn}_{spc}_{mth}", type="primary"):
                            conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? ", (rt, sc, pdn, spc, mth))
                            conn.commit(); st.rerun()
                    else:
                        st.write("🌿 **已添加：** " + " 、 ".join([f"{r['物料名称']}({r['用量']}g)" for _,r in items.iterrows()]))
        else: st.info("当前配方库为空。")
        conn.close()
