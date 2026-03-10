# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import sqlite3
import re
from datetime import datetime

# -----------------------------------------------------------------------------
# 1. 核心配置与 CSS 注入
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="顿角咖啡智能数据看板",
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
    .stApp { background-color: #F8FAFC; font-family: 'Inter', 'Helvetica Neue', sans-serif; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; border-radius: 15px; border: 1px solid #E2E8F0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); padding: 20px; margin-bottom: 20px;
    }
    [data-testid="stMetricValue"] { font-size: 30px !important; font-weight: 800 !important; color: #1E40AF; }
    .recipe-card-header { background: #F1F5F9; padding: 10px 15px; border-radius: 10px; margin-bottom: 15px; border-left: 5px solid #3B82F6; }
    .cost-tag { background: #DBEAFE; color: #1E40AF; padding: 2px 8px; border-radius: 5px; font-size: 14px; font-weight: 600; margin-right: 10px; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. 内置字典与映射
# -----------------------------------------------------------------------------
RAW_COLUMN_MAPPING = {
    '商品实收': '销售金额', '商品销量': '销售数量', '日期': '统计周期', '商品分类': '商品类别'
}

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

# -----------------------------------------------------------------------------
# 3. 数据库引擎
# -----------------------------------------------------------------------------
DATA_DIR = "data_storage"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "coffee_master.db")

def get_db_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_raw (
            门店名称 TEXT, 商品名称 TEXT, 商品类别 TEXT, 规格 TEXT, 做法 TEXT,
            统计周期 TEXT, 销售金额 REAL, 销售数量 REAL, source_file TEXT
        )
    ''')
    try: cursor.execute("ALTER TABLE sales_raw ADD COLUMN 规格 TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE sales_raw ADD COLUMN 做法 TEXT")
    except: pass
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_materials (
            物料名称 TEXT PRIMARY KEY, 品项类别 TEXT, 单位 TEXT, 物流单价 REAL, 顿角单价 REAL, 百度单价 REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bom_recipes (
            配方类型 TEXT, 适用范围 TEXT, 商品名称 TEXT, 规格 TEXT, 做法 TEXT, 物料名称 TEXT, 用量 REAL,
            UNIQUE(配方类型, 适用范围, 商品名称, 规格, 做法, 物料名称)
        )
    ''')
    conn.commit(); conn.close()

init_db()

# -----------------------------------------------------------------------------
# 4. 辅助函数与计算引擎
# -----------------------------------------------------------------------------
def clean_store_name(name):
    if pd.isna(name): return ""
    return str(name).strip().replace(" ", "").replace("(", "（").replace(")", "）") 

def load_data_from_buffer(uploaded_file):
    try:
        if uploaded_file.name.endswith(('.xlsx', '.xls')): return pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            for enc in ['utf-8', 'utf-8-sig', 'gbk', 'gb18030']:
                try: return pd.read_csv(uploaded_file, encoding=enc)
                except: continue
    except Exception as e: st.error(f"读取文件出错: {e}")
    return None

def standardize_date(val, file_name=""):
    try:
        if pd.notna(val) and str(val).strip() != "": return pd.to_datetime(val).strftime('%Y-%m-%d')
    except: pass
    try:
        name_without_ext = os.path.splitext(file_name)[0]
        match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{8}', name_without_ext)
        if match: return pd.to_datetime(match.group()).strftime('%Y-%m-%d')
        return pd.to_datetime(name_without_ext).strftime('%Y-%m-%d')
    except: return str(name_without_ext)

def ingest_sales_data(uploaded_files):
    conn = get_db_conn()
    success_count = 0
    for f in uploaded_files:
        if pd.read_sql("SELECT COUNT(*) as cnt FROM sales_raw WHERE source_file = ?", conn, params=(f.name,)).iloc[0]['cnt'] > 0:
            st.toast(f"文件 '{f.name}' 已存在", icon="⚠️"); continue
        df = load_data_from_buffer(f)
        if df is None: continue
        df.columns = [str(c).strip() for c in df.columns]
        for c in df.columns:
            if '规格' in c: df.rename(columns={c: '规格'}, inplace=True)
            elif any(kw in c for kw in ['做法', '口味', '属性', '加料']): df.rename(columns={c: '做法'}, inplace=True)
        if '商品类别' in df.columns and '商品分类' in df.columns: df = df.drop(columns=['商品类别'])
        df = df.rename(columns=RAW_COLUMN_MAPPING)
        for c in ['商品名称', '商品类别', '门店名称', '统计周期', '规格', '做法']:
            if c in df.columns: df[c] = df[c].astype(str).str.replace('`', '', regex=False).str.strip()
        valid_cats = set([item["二级分类"] for item in CATEGORY_MAPPING_DATA])
        if '商品类别' in df.columns: df = df[df['商品类别'].isin(valid_cats)]
        if df.empty: continue 
        df = df.dropna(subset=['商品名称'])
        if '门店名称' in df.columns: df['门店名称'] = df['门店名称'].apply(clean_store_name).ffill()
        df['统计周期'] = df['统计周期'].apply(lambda x: standardize_date(x, f.name))
        df['规格'] = df['规格'].replace(['nan', 'None', '', '--', 'NaN'], '常规').fillna('常规') if '规格' in df.columns else '常规'
        df['做法'] = df['做法'].replace(['nan', 'None', '', '--', 'NaN'], '常规').fillna('常规') if '做法' in df.columns else '常规'
        for c in ['销售金额', '销售数量']:
            if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(r'[¥$,￥]', '', regex=True), errors='coerce').fillna(0)
        df['source_file'] = f.name
        try:
            df[['门店名称', '商品名称', '商品类别', '规格', '做法', '统计周期', '销售金额', '销售数量', 'source_file']].to_sql('sales_raw', conn, if_exists='append', index=False)
            success_count += 1
        except: pass
    conn.close()
    if success_count > 0: st.success(f"✅ 已导入 {success_count} 份数据！")

def merge_category_map(df_sales):
    if df_sales is None or df_sales.empty: return df_sales
    df_cat = pd.DataFrame(CATEGORY_MAPPING_DATA)
    if '商品类别' in df_sales.columns:
        df_sales['商品类别_clean'] = df_sales['商品类别'].astype(str).str.strip()
        df_cat = df_cat.drop_duplicates(subset=['二级分类'])
        df_sales = pd.merge(df_sales, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left')
        df_sales['一级分类'] = df_sales['一级分类'].fillna('未分类')
        df_sales['二级分类'] = df_sales['商品类别']
        df_sales = df_sales.drop(columns=['商品类别_clean'], errors='ignore')
    if '门店名称' in df_sales.columns:
        s2p = {}
        for proj, stores in PROJECT_STORE_MAPPING.items():
            for s in stores: s2p[clean_store_name(s)] = proj
        df_sales['所属项目'] = df_sales['门店名称'].map(s2p).fillna('其他项目')
    return df_sales

def merge_dynamic_cost_data(df_sales):
    if df_sales is None or df_sales.empty: return df_sales
    conn = get_db_conn()
    try:
        df_bom = pd.read_sql("SELECT * FROM bom_recipes", conn)
        df_raw = pd.read_sql("SELECT * FROM raw_materials", conn)
    except: df_bom = df_raw = pd.DataFrame()
    finally: conn.close()
    
    df_sales['物流单位成本'] = df_sales['门店单位成本'] = 0.0
    if not df_bom.empty and not df_raw.empty:
        merged = df_bom.merge(df_raw, on='物料名称', how='left').fillna(0)
        merged['用量'] = pd.to_numeric(merged['用量'], errors='coerce').fillna(0)
        merged['c_log'] = merged['用量'] * pd.to_numeric(merged['物流单价'], errors='coerce').fillna(0)
        merged['c_dj'] = merged['用量'] * pd.to_numeric(merged['顿角单价'], errors='coerce').fillna(0)
        merged['c_bd'] = merged['用量'] * pd.to_numeric(merged['百度单价'], errors='coerce').fillna(0)
        
        grp = merged.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'], as_index=False)[['c_log', 'c_dj', 'c_bd']].sum()
        for col in ['规格', '做法']: 
            if col not in df_sales.columns: df_sales[col] = '常规'
            
        # 物流
        log_boms = grp[grp['配方类型'] == '物流'][['商品名称', '规格', '做法', 'c_log']].rename(columns={'c_log': 'l_cost'})
        df_sales = df_sales.merge(log_boms, on=['商品名称', '规格', '做法'], how='left')
        df_sales['物流单位成本'] = df_sales['l_cost'].fillna(0.0)

        # 门店 (三级回退)
        st_boms = grp[grp['配方类型'] == '门店']
        # L1-Specific
        l1 = st_boms.rename(columns={'适用范围': '门店名称', 'c_dj': 's_dj', 'c_bd': 's_bd'})
        df_sales = df_sales.merge(l1[['门店名称', '商品名称', '规格', '做法', 's_dj', 's_bd']], on=['门店名称', '商品名称', '规格', '做法'], how='left')
        # L2-Project
        l2 = st_boms.rename(columns={'适用范围': '所属项目', 'c_dj': 'p_dj', 'c_bd': 'p_bd'})
        df_sales = df_sales.merge(l2[['所属项目', '商品名称', '规格', '做法', 'p_dj', 'p_bd']], on=['所属项目', '商品名称', '规格', '做法'], how='left')
        # L3-Global
        l3 = st_boms[st_boms['适用范围'] == '【全局默认配方】'].rename(columns={'c_dj': 'g_dj', 'c_bd': 'g_bd'}).drop(columns=['适用范围'])
        df_sales = df_sales.merge(l3[['商品名称', '规格', '做法', 'g_dj', 'g_bd']], on=['商品名称', '规格', '做法'], how='left')

        df_sales['m_bd'] = df_sales['s_bd'].fillna(df_sales['p_bd']).fillna(df_sales['g_bd']).fillna(0.0)
        df_sales['m_dj'] = df_sales['s_dj'].fillna(df_sales['p_dj']).fillna(df_sales['g_dj']).fillna(0.0)
        df_sales['门店单位成本'] = np.where(df_sales['所属项目'] == '百度项目', df_sales['m_bd'], df_sales['m_dj'])
        df_sales.drop(columns=['l_cost','s_dj','s_bd','p_dj','p_bd','g_dj','g_bd','m_bd','m_dj'], inplace=True, errors='ignore')
        
    df_sales['门店毛利'] = df_sales['销售金额'] - (df_sales['销售数量'] * df_sales['门店单位成本'])
    df_sales['物流毛利'] = df_sales['销售金额'] - (df_sales['销售数量'] * df_sales['物流单位成本'])
    return df_sales

def calculate_metrics(df, days):
    if df.empty or days <= 0: return 0,0,0,0,0,0,0,0,0
    qty, amt = df['销售数量'].sum(), df['销售金额'].sum()
    p_log, p_st = df['物流毛利'].sum(), df['门店毛利'].sum()
    return qty, amt, p_log, p_st, (amt/qty if qty>0 else 0), (p_log/amt*100 if amt>0 else 0), (p_st/amt*100 if amt>0 else 0), qty/days, amt/days

# -----------------------------------------------------------------------------
# 5. 界面渲染
# -----------------------------------------------------------------------------
logo_path = "logo.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, width=120)
else: st.sidebar.image("https://cdn-icons-png.flaticon.com/512/751/751621.png", width=100)

app_mode = st.sidebar.radio("🧭 系统导航", ["📊 经营分析看板", "⚙️ 成本与配方中心"])

if app_mode == "📊 经营分析看板":
    with st.sidebar.expander("💾 数据管理", expanded=False):
        conn = get_db_conn()
        try:
            total_rows = pd.read_sql("SELECT COUNT(*) as c FROM sales_raw", conn).iloc[0]['c']
            available_periods = sorted(pd.read_sql("SELECT DISTINCT 统计周期 FROM sales_raw WHERE 统计周期 IS NOT NULL", conn)['统计周期'].tolist())
        except: total_rows = 0; available_periods = []
        finally: conn.close()
        st.markdown(f"已存 **{total_rows:,}** 条记录")
        new_sales = st.file_uploader("📥 导入企迈日结表", type=["xlsx", "csv"], accept_multiple_files=True)
        if new_sales: ingest_sales_data(new_sales); st.rerun()
        if st.button("🗑️ 清空所有销售数据", use_container_width=True):
            conn = get_db_conn(); conn.execute("DELETE FROM sales_raw"); conn.commit(); conn.close(); st.rerun()

    if total_rows == 0: st.info("请先导入企迈日结表。"); st.stop()

    # 日历逻辑
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 自由日历分析")
    parsed_dates = [datetime.strptime(p, '%Y-%m-%d').date() for p in available_periods if p]
    if parsed_dates:
        min_d, max_d = min(parsed_dates), max(parsed_dates)
        date_curr = st.sidebar.date_input("选择汇总范围", [min_d, max_d], min_value=min_d, max_value=max_d)
        start_c = date_curr[0] if len(date_curr) > 0 else min_d
        end_c = date_curr[1] if len(date_curr) == 2 else start_c
        conn = get_db_conn()
        df_current = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(start_c.strftime('%Y-%m-%d'), end_c.strftime('%Y-%m-%d')))
        conn.close()
        days_current = df_current['统计周期'].nunique() if not df_current.empty else 1

        if not df_current.empty:
            df_current = merge_category_map(df_current)
            df_current = merge_dynamic_cost_data(df_current)
            
            st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf?auto=format&fit=crop&w=1200&h=250&q=80", use_container_width=True)
            st.title("📊 顿角咖啡经营看板")
            
            q, a, pl, ps, cp, ml, ms, dq, da = calculate_metrics(df_current, days_current)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("总销量", f"{int(q)} 杯")
            c2.metric("总营收", f"¥{a:,.2f}")
            c3.metric("出厂毛利", f"{ml:.2f}%")
            c4.metric("门店毛利", f"{ms:.2f}%")
            
            st.markdown("### 📄 商品销售明细")
            df_current['w_log'] = df_current['销售数量'] * df_current['物流单位成本']
            df_current['w_st'] = df_current['销售数量'] * df_current['门店单位成本']
            view = df_current.groupby('商品名称', as_index=False).agg({
                '二级分类': 'first', '销售数量': 'sum', '销售金额': 'sum', 'w_log': 'sum', 'w_st': 'sum', '物流毛利': 'sum', '门店毛利': 'sum'
            })
            view['物流单位'] = np.where(view['销售数量']>0, view['w_log']/view['销售数量'], 0)
            view['门店单位'] = np.where(view['销售数量']>0, view['w_st']/view['销售数量'], 0)
            view['门店毛利率'] = (view['门店毛利']/view['销售金额']*100).fillna(0)
            st.dataframe(view[['商品名称','二级分类','销售数量','销售金额','物流单位','门店单位','门店毛利率']], column_config={
                "销售数量": st.column_config.ProgressColumn("总销量", format="%d", min_value=0, max_value=int(view['销售数量'].max() if not view.empty else 1)),
                "销售金额": st.column_config.NumberColumn("营收", format="¥%.2f"),
                "物流单位": st.column_config.NumberColumn("加权出厂成本", format="¥%.2f"),
                "门店单位": st.column_config.NumberColumn("加权到店成本", format="¥%.2f"),
                "门店毛利率": st.column_config.NumberColumn("毛利率", format="%.2f%%"),
            }, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# ⚙️ 成本配方中心 (Tab 3 深度重构)
# -----------------------------------------------------------------------------
elif app_mode == "⚙️ 成本与配方中心":
    st.title("⚙️ 三级原物料与配方引擎")
    tab_m, tab_b, tab_v = st.tabs(["📦 第一步：基础原物料库", "📋 第二步：配置单品成本卡", "📚 第三步：成本卡总览与管理"])
    
    with tab_m:
        st.markdown("#### 1. 上传原物料价格档")
        raw_file = st.file_uploader("上传原物料表", type=["xlsx", "csv"])
        if raw_file:
            df = load_data_from_buffer(raw_file)
            if df is not None:
                df.columns = [str(c).strip() for c in df.columns]
                exact = {'物流名称': '物料名称', '品项类别': '品项类别', '单价单位': '单位', '物流单价成本': '物流单价', '顿角单价成本': '顿角单价', '百度单价成本': '百度单价'}
                col_map = {c: exact[c] for c in df.columns if c in exact}
                df = df.rename(columns=col_map)
                if '物料名称' in df.columns:
                    for p in ['物流单价', '顿角单价', '百度单价']:
                        if p in df.columns: df[p] = pd.to_numeric(df[p], errors='coerce').fillna(0)
                    conn = get_db_conn()
                    df[['物料名称', '品项类别', '单位', '物流单价', '顿角单价', '百度单价']].to_sql('raw_materials', conn, if_exists='replace', index=False)
                    conn.close(); st.success("✅ 更新成功！"); st.rerun()
        conn = get_db_conn()
        try: st.dataframe(pd.read_sql("SELECT * FROM raw_materials", conn), use_container_width=True)
        except: st.write("暂无数据")
        conn.close()

    with tab_b:
        conn = get_db_conn()
        try: 
            df_opts = pd.read_sql("SELECT DISTINCT 门店名称, 商品名称, 商品类别, 规格, 做法 FROM sales_raw", conn)
            df_opts['规格'] = df_opts['规格'].fillna('常规').astype(str)
            df_opts['做法'] = df_opts['做法'].fillna('常规').astype(str)
            df_opts = merge_category_map(df_opts)
            df_opts = df_opts[df_opts['一级分类'] != '未分类']
            raw_mat_list = pd.read_sql("SELECT 物料名称 FROM raw_materials", conn)['物料名称'].tolist()
        except: df_opts = pd.DataFrame(); raw_mat_list = []
        
        if df_opts.empty: st.warning("请先在看板导入报表。")
        else:
            c_type, c_scope = st.columns(2)
            recipe_type = c_type.radio("配方轨道", ["🏪 门店配方", "📦 物流配方"])
            db_type = '物流' if '物流' in recipe_type else '门店'
            if db_type == '物流': apply_scope = "【全局默认配方】"
            else:
                apply_scope = c_scope.selectbox("适用范围", ["【全局默认配方】", "【顿角项目配方】", "【百度项目配方】"] + sorted(df_opts['门店名称'].unique().tolist()))
                
            st.divider()
            c_prod, c_spec, c_meth = st.columns(3)
            all_prods = sorted(df_opts['商品名称'].unique().tolist())
            sp = c_prod.selectbox("选择商品", all_prods)
            ss = c_spec.selectbox("选择规格", sorted(df_opts[df_opts['商品名称']==sp]['规格'].unique().tolist()))
            sm = c_meth.selectbox("选择做法", sorted(df_opts[(df_opts['商品名称']==sp)&(df_opts['规格']==ss)]['做法'].unique().tolist()))
            
            with st.container(border=True):
                st.markdown(f"#### ➕ 添加新物料")
                col_s1, col_s2, col_s3 = st.columns([3, 1, 1])
                with col_s1: mat = st.selectbox("搜索物料", ["-- 请选择 --"] + raw_mat_list)
                with col_s2: qty = st.number_input("用量", min_value=0.0, step=1.0)
                with col_s3:
                    st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
                    if st.button("确认添加", type="primary", use_container_width=True):
                        if mat != "-- 请选择 --" and qty > 0:
                            cursor = conn.cursor()
                            cursor.execute("INSERT OR REPLACE INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (db_type, apply_scope, sp, ss, sm, mat, qty))
                            conn.commit(); st.toast("✅ 已添加"); st.rerun()

            curr_bom = pd.read_sql("SELECT 物料名称, 用量 FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", conn, params=(db_type, apply_scope, sp, ss, sm))
            if not curr_bom.empty:
                st.markdown("#### 📋 快捷修改清单")
                for i, r in curr_bom.iterrows():
                    c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
                    c1.markdown(f"☕ {r['物料名称']}")
                    nq = c2.number_input("用量", value=float(r['用量']), key=f"q_b_{i}_{r['物料名称']}", label_visibility="collapsed")
                    if c3.button("保存", key=f"s_b_{i}"):
                        conn.execute("UPDATE bom_recipes SET 用量=? WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", (nq, db_type, apply_scope, sp, ss, sm, r['物料名称']))
                        conn.commit(); st.rerun()
                    if c4.button("移除", key=f"d_b_{i}"):
                        conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", (db_type, apply_scope, sp, ss, sm, r['物料名称']))
                        conn.commit(); st.rerun()
        conn.close()

    # --- 📚 Tab 3: 极致简化版总览 (汇总与管理合二为一) ---
    with tab_v:
        st.markdown("#### 📚 成本卡全局总览与管理")
        if 'edit_mode' not in st.session_state: st.session_state.edit_mode = False
        
        conn = get_db_conn()
        try:
            df_b = pd.read_sql("SELECT * FROM bom_recipes", conn)
            df_r = pd.read_sql("SELECT * FROM raw_materials", conn)
            if df_b.empty: st.info("库内尚无配方。")
            else:
                # 顶部控制
                c_lock, _ = st.columns([1, 4])
                if not st.session_state.edit_mode:
                    if c_lock.button("📝 开启全局管理模式", type="primary", use_container_width=True):
                        st.session_state.edit_mode = True; st.rerun()
                else:
                    if c_lock.button("🔒 退出并锁定", use_container_width=True):
                        st.session_state.edit_mode = False; st.rerun()

                # 计算总成本数据用于卡片展示
                merged = df_b.merge(df_r, on='物料名称', how='left').fillna(0)
                merged['log_v'] = merged['用量'] * merged['物流单价']
                merged['dj_v'] = merged['用量'] * merged['顿角单价']
                merged['bd_v'] = merged['用量'] * merged['百度单价']
                
                # 按照“配方卡”维度进行聚合
                card_groups = merged.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'])
                
                for (rtype, scope, prod, spec, meth), items in card_groups:
                    with st.container(border=True):
                        # 1. 卡片页眉：商品信息与总成本汇总
                        c_log_total = items['log_v'].sum()
                        c_dj_total = items['dj_v'].sum()
                        c_bd_total = items['bd_v'].sum()
                        
                        st.markdown(f"""
                        <div class="recipe-card-header">
                            <span style="font-weight:800; font-size:18px;">【{rtype}】{prod}</span> 
                            <span style="color:#64748B;">({spec} / {meth})</span><br>
                            <span style="font-size:14px; color:#1E40AF;">📍 适用范围: {scope}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown(f"""
                        <span class="cost-tag">📦 物流: ¥{c_log_total:.2f}</span>
                        <span class="cost-tag">🏬 顿角: ¥{c_dj_total:.2f}</span>
                        <span class="cost-tag">🏢 百度: ¥{c_bd_total:.2f}</span>
                        """, unsafe_allow_html=True)
                        st.markdown("<div style='margin-top:15px'></div>", unsafe_allow_html=True)
                        
                        # 2. 卡片内容：物料清单与编辑
                        if st.session_state.edit_mode:
                            # 编辑模式下显示 Data Editor，仅编辑当前卡片的物料
                            edited = st.data_editor(
                                items[['物料名称', '用量']],
                                column_config={"用量": st.column_config.NumberColumn("用量(g/ml)", format="%.2f", min_value=0.0)},
                                key=f"edit_{rtype}_{scope}_{prod}_{spec}_{meth}",
                                use_container_width=True,
                                num_rows="dynamic"
                            )
                            
                            c_save, c_del_card, _ = st.columns([1.5, 1.5, 5])
                            if c_save.button("💾 保存此卡用量", key=f"save_card_{rtype}_{prod}_{spec}_{meth}"):
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", (rtype, scope, prod, spec, meth))
                                for _, r in edited.dropna(subset=['物料名称']).iterrows():
                                    if r['用量'] > 0:
                                        cursor.execute("INSERT INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (rtype, scope, prod, spec, meth, r['物料名称'], r['用量']))
                                conn.commit(); st.toast("✅ 已保存单品修改"); st.rerun()
                                
                            if c_del_card.button("🗑️ 彻底删除此卡", key=f"del_card_{rtype}_{prod}_{spec}_{meth}", type="primary"):
                                conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", (rtype, scope, prod, spec, meth))
                                conn.commit(); st.toast("🗑️ 已移除整张成本卡"); st.rerun()
                        else:
                            # 只读模式：显示物料摘要
                            mat_str = " 、 ".join([f"{r['物料名称']}({r['用量']}g)" for _, r in items.iterrows()])
                            st.markdown(f"**包含物料：** {mat_str}")
                
        except Exception as e: st.error(f"加载失败: {e}")
        finally: conn.close()
