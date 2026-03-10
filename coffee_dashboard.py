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
        background-color: #FFFFFF; border-radius: 20px; border: 1px solid #F1F5F9;
        box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.04); padding: 24px; transition: all 0.3s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px); box-shadow: 0 12px 30px -5px rgba(15, 23, 42, 0.08); border-color: #E2E8F0;
    }
    [data-testid="stMetricValue"] {
        font-size: 34px !important;
        background: -webkit-linear-gradient(120deg, #1E40AF, #3B82F6);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
    }
</style>
""", unsafe_allow_html=True)

try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

def update_chart_layout(fig, title_text=""):
    fig.update_layout(
        plot_bgcolor="rgba(255,255,255,0)", paper_bgcolor="rgba(255,255,255,0)",
        margin=dict(l=10, r=20, t=45 if title_text else 20, b=10),
        hoverlabel=dict(bgcolor="rgba(255,255,255,0.98)", font_size=13),
        title=dict(text=title_text, font=dict(size=15, color="#1E293B", weight="bold"), x=0.01, y=0.98) if title_text else None,
        bargap=0.25, showlegend=False
    )
    fig.update_xaxes(showgrid=True, gridcolor='rgba(226, 232, 240, 0.6)', zeroline=False, showline=False, title_text="")
    fig.update_yaxes(showgrid=False, zeroline=False, showline=False, title_text="")
    return fig

# -----------------------------------------------------------------------------
# 2. 内置字典与映射
# -----------------------------------------------------------------------------
RAW_COLUMN_MAPPING = {
    '商品实收': '销售金额',
    '商品销量': '销售数量',
    '日期': '统计周期',     
    '商品分类': '商品类别',
    '规格': '规格',
    '做法': '做法'
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

    try:
        cursor.execute("SELECT 配方类型 FROM bom_recipes LIMIT 1")
    except:
        cursor.execute("DROP TABLE IF EXISTS bom_recipes")
        cursor.execute("DROP TABLE IF EXISTS raw_materials")
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS raw_materials (
            物料名称 TEXT PRIMARY KEY,
            单位 TEXT,
            物流单价 REAL,
            顿角单价 REAL,
            百度单价 REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bom_recipes (
            配方类型 TEXT,
            适用范围 TEXT,
            商品名称 TEXT,
            规格 TEXT,
            做法 TEXT,
            物料名称 TEXT,
            用量 REAL,
            UNIQUE(配方类型, 适用范围, 商品名称, 规格, 做法, 物料名称)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# -----------------------------------------------------------------------------
# 4. ETL 与计算逻辑
# -----------------------------------------------------------------------------
def clean_store_name(name):
    if pd.isna(name): return ""
    return str(name).strip().replace(" ", "").replace("(", "（").replace(")", "）") 

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

def load_data_from_buffer(uploaded_file):
    try:
        if uploaded_file.name.endswith(('.xlsx', '.xls')): return pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            for enc in ['utf-8', 'utf-8-sig', 'gbk', 'gb18030']:
                try: return pd.read_csv(uploaded_file, encoding=enc)
                except: continue
    except Exception as e: st.error(f"读取文件出错: {e}")
    return None

def ingest_sales_data(uploaded_files):
    conn = get_db_conn()
    success_count = 0
    for f in uploaded_files:
        file_name = f.name
        try:
            if pd.read_sql("SELECT COUNT(*) as cnt FROM sales_raw WHERE source_file = ?", conn, params=(file_name,)).iloc[0]['cnt'] > 0:
                st.toast(f"文件 '{file_name}' 已存在，跳过导入。", icon="⚠️")
                continue
        except: pass
            
        df = load_data_from_buffer(f)
        if df is None: continue
        
        df.columns = [str(c).strip() for c in df.columns]
        if '商品类别' in df.columns and '商品分类' in df.columns: df = df.drop(columns=['商品类别'])
        df = df.rename(columns=RAW_COLUMN_MAPPING)
        
        for c in ['商品名称', '商品类别', '门店名称', '统计周期', '规格', '做法']:
            if c in df.columns: df[c] = df[c].astype(str).str.replace('`', '', regex=False).str.strip()
                
        valid_categories = set([item["二级分类"] for item in CATEGORY_MAPPING_DATA])
        if '商品类别' in df.columns: df = df[df['商品类别'].isin(valid_categories)]
        if df.empty: continue 
        
        if '商品名称' in df.columns:
            df = df[~df['商品名称'].astype(str).str.contains("合计|总计|Total", na=False)]
            df = df.dropna(subset=['商品名称'])
        if '门店名称' in df.columns:
            df = df[~df['门店名称'].astype(str).str.contains("合计|总计", na=False)]
            df = df.dropna(subset=['门店名称'])
            df['门店名称'] = df['门店名称'].apply(clean_store_name)

        if '统计周期' not in df.columns: df['统计周期'] = os.path.splitext(file_name)[0]
        df['统计周期'] = df['统计周期'].apply(lambda x: standardize_date(x, file_name))
        
        if '规格' not in df.columns: df['规格'] = '常规'
        else: df['规格'] = df['规格'].replace(['nan', 'None', '', '--', 'NaN'], '常规').fillna('常规')
        if '做法' not in df.columns: df['做法'] = '常规'
        else: df['做法'] = df['做法'].replace(['nan', 'None', '', '--', 'NaN'], '常规').fillna('常规')

        if '门店名称' in df.columns: df['门店名称'] = df['门店名称'].ffill()
        for c in ['销售金额', '销售数量']:
            if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(r'[¥$,￥]', '', regex=True), errors='coerce').fillna(0)
            
        df['source_file'] = file_name
        keep_cols = ['门店名称', '商品名称', '商品类别', '规格', '做法', '统计周期', '销售金额', '销售数量', 'source_file']
        for col in keep_cols:
            if col not in df.columns: df[col] = None
                
        try:
            df[keep_cols].to_sql('sales_raw', conn, if_exists='append', index=False)
            success_count += 1
        except Exception as e: st.error(f"写入数据库失败: {e}")
        
    conn.close()
    if success_count > 0: st.success(f"✅ 成功导入 {success_count} 份有效数据！")

def merge_category_map(df_sales):
    if df_sales is None or df_sales.empty: return df_sales
    if '商品类别' in df_sales.columns:
        df_cat = pd.DataFrame(CATEGORY_MAPPING_DATA)
        df_sales['商品类别_clean'] = df_sales['商品类别'].astype(str).str.strip()
        df_cat = df_cat.drop_duplicates(subset=['二级分类'])
        df_sales = pd.merge(df_sales, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left')
        df_sales['一级分类'] = df_sales['一级分类'].fillna('未分类')
        df_sales['二级分类'] = df_sales['商品类别']
        df_sales = df_sales.drop(columns=['商品类别_clean'], errors='ignore')
    else:
        df_sales['一级分类'] = '未分类'; df_sales['二级分类'] = '未分类'

    if '门店名称' in df_sales.columns:
        store_to_project = {}
        for proj, stores in PROJECT_STORE_MAPPING.items():
            for s in stores: store_to_project[clean_store_name(s)] = proj
        df_sales['所属项目'] = df_sales['门店名称'].map(store_to_project).fillna('其他项目')
    return df_sales

def merge_dynamic_cost_data(df_sales):
    if df_sales is None or df_sales.empty: return df_sales
    conn = get_db_conn()
    try:
        df_bom = pd.read_sql("SELECT * FROM bom_recipes", conn)
        df_raw = pd.read_sql("SELECT * FROM raw_materials", conn)
    except:
        df_bom = pd.DataFrame()
        df_raw = pd.DataFrame()
    finally:
        conn.close()
        
    df_sales['物流单位成本'] = 0.0
    df_sales['门店单位成本'] = 0.0
    
    if not df_bom.empty and not df_raw.empty:
        bom_merged = df_bom.merge(df_raw, on='物料名称', how='left').fillna(0)
        bom_merged['用量'] = pd.to_numeric(bom_merged['用量'], errors='coerce').fillna(0)
        
        bom_merged['cost_log'] = bom_merged['用量'] * pd.to_numeric(bom_merged['物流单价'], errors='coerce').fillna(0)
        bom_merged['cost_dj'] = bom_merged['用量'] * pd.to_numeric(bom_merged['顿角单价'], errors='coerce').fillna(0)
        bom_merged['cost_bd'] = bom_merged['用量'] * pd.to_numeric(bom_merged['百度单价'], errors='coerce').fillna(0)
        
        bom_grouped = bom_merged.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'], as_index=False)[['cost_log', 'cost_dj', 'cost_bd']].sum()
        
        for col in ['规格', '做法']:
            if col not in df_sales.columns: df_sales[col] = '常规'
            
        log_boms = bom_grouped[bom_grouped['配方类型'] == '物流']
        log_boms = log_boms[['商品名称', '规格', '做法', 'cost_log']].rename(columns={'cost_log': '物流配方成本'})
        
        df_sales = df_sales.merge(log_boms, on=['商品名称', '规格', '做法'], how='left')
        df_sales['物流单位成本'] = df_sales['物流配方成本'].fillna(0.0)
        df_sales.drop(columns=['物流配方成本'], inplace=True, errors='ignore')

        store_boms = bom_grouped[bom_grouped['配方类型'] == '门店']
        
        boms_specific = store_boms.rename(columns={'适用范围': '门店名称', 'cost_dj': 's_dj', 'cost_bd': 's_bd'})
        df_sales = df_sales.merge(boms_specific[['门店名称', '商品名称', '规格', '做法', 's_dj', 's_bd']], on=['门店名称', '商品名称', '规格', '做法'], how='left')
        
        boms_project = store_boms.rename(columns={'适用范围': '所属项目', 'cost_dj': 'p_dj', 'cost_bd': 'p_bd'})
        df_sales = df_sales.merge(boms_project[['所属项目', '商品名称', '规格', '做法', 'p_dj', 'p_bd']], on=['所属项目', '商品名称', '规格', '做法'], how='left')
        
        boms_global = store_boms[store_boms['适用范围'] == '【全局默认配方】'].rename(columns={'cost_dj': 'g_dj', 'cost_bd': 'g_bd'}).drop(columns=['适用范围'])
        df_sales = df_sales.merge(boms_global[['商品名称', '规格', '做法', 'g_dj', 'g_bd']], on=['商品名称', '规格', '做法'], how='left')

        df_sales['门店单位成本_bd'] = df_sales['s_bd'].fillna(df_sales['p_bd']).fillna(df_sales['g_bd']).fillna(0.0)
        df_sales['门店单位成本_dj'] = df_sales['s_dj'].fillna(df_sales['p_dj']).fillna(df_sales['g_dj']).fillna(0.0)
        
        df_sales['门店单位成本'] = np.where(df_sales['所属项目'] == '百度项目', df_sales['门店单位成本_bd'], df_sales['门店单位成本_dj'])
        df_sales.drop(columns=['s_dj', 's_bd', 'p_dj', 'p_bd', 'g_dj', 'g_bd', '门店单位成本_bd', '门店单位成本_dj'], inplace=True, errors='ignore')
        
    df_sales['门店毛利'] = df_sales['销售金额'] - (df_sales['销售数量'] * df_sales['门店单位成本'])
    df_sales['物流毛利'] = df_sales['销售金额'] - (df_sales['销售数量'] * df_sales['物流单位成本'])
    return df_sales

def calculate_metrics(df, operate_days):
    if df.empty or operate_days <= 0: return 0, 0, 0, 0, 0, 0, 0, 0, 0
    qty = df['销售数量'].sum()
    amt = df['销售金额'].sum()
    profit_log = df['物流毛利'].sum()
    profit_store = df['门店毛利'].sum()
    cup_price = (amt / qty) if qty > 0 else 0 
    margin_log = (profit_log / amt * 100) if amt > 0 else 0
    margin_store = (profit_store / amt * 100) if amt > 0 else 0
    daily_qty = qty / operate_days
    daily_amt = amt / operate_days
    return qty, amt, profit_log, profit_store, cup_price, margin_log, margin_store, daily_qty, daily_amt


# -----------------------------------------------------------------------------
# 5. 导航与侧边栏
# -----------------------------------------------------------------------------
logo_path = "logo.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, width=120)
else: st.sidebar.image("https://cdn-icons-png.flaticon.com/512/751/751621.png", width=100)

app_mode = st.sidebar.radio("🧭 系统导航", ["📊 经营分析看板", "⚙️ 成本与配方中心"])

if app_mode == "📊 经营分析看板":
    with st.sidebar.expander("💾 数据管线 (ETL)", expanded=False):
        conn = get_db_conn()
        try:
            total_rows = pd.read_sql("SELECT COUNT(*) as c FROM sales_raw", conn).iloc[0]['c']
            df_periods_db = pd.read_sql("SELECT DISTINCT 统计周期 FROM sales_raw WHERE 统计周期 IS NOT NULL", conn)
            available_periods = sorted(df_periods_db['统计周期'].tolist())
        except:
            total_rows = 0; available_periods = []
        finally:
            conn.close()
        
        st.markdown(f"已存 **{total_rows:,}** 条日结")
        new_sales = st.file_uploader("📥 导入企迈日结表", type=["xlsx", "csv"], accept_multiple_files=True)
        if new_sales: ingest_sales_data(new_sales); st.rerun()
            
        st.divider()
        st.markdown("**⚠️ 危险操作**")
        if st.button("🗑️ 清空所有销售数据", use_container_width=True):
            conn = get_db_conn()
            conn.execute("DELETE FROM sales_raw") 
            conn.commit(); conn.close()
            st.success("✅ 销售数据已清空！请重新上传。")
            st.rerun()

    if total_rows == 0:
        st.markdown("<div style='text-align:center;padding:100px;'><h1>📥 欢迎使用</h1><p>请在左侧上传企迈日结报表以启动看板。</p></div>", unsafe_allow_html=True)
        st.stop()

    df_current = pd.DataFrame(); df_previous = pd.DataFrame()
    is_comparison_mode = False; days_current = 1; days_previous = 1

    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 自由日历")

    conn = get_db_conn()
    if available_periods:
        parsed_dates = []
        for p in available_periods:
            try: parsed_dates.append(datetime.strptime(p, '%Y-%m-%d').date())
            except: pass
            
        if parsed_dates:
            min_d, max_d = min(parsed_dates), max(parsed_dates)
            st.sidebar.markdown(f"<div style='font-size:13px; color:#64748B; margin-bottom:10px;'>💡 库内数据: {min_d.strftime('%m/%d')} 至 {max_d.strftime('%m/%d')}</div>", unsafe_allow_html=True)
            
            enable_comparison = st.sidebar.checkbox("开启环比对比", value=False)
            if enable_comparison:
                is_comparison_mode = True
                date_curr = st.sidebar.date_input("本期范围", [max_d, max_d], min_value=min_d, max_value=max_d, key="dc")
                date_prev = st.sidebar.date_input("上期范围 (对比)", [min_d, min_d], min_value=min_d, max_value=max_d, key="dp")
                
                start_c = date_curr[0] if len(date_curr) > 0 else max_d
                end_c = date_curr[1] if len(date_curr) == 2 else start_c
                start_p = date_prev[0] if len(date_prev) > 0 else min_d
                end_p = date_prev[1] if len(date_prev) == 2 else start_p
                
                df_current = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(start_c.strftime('%Y-%m-%d'), end_c.strftime('%Y-%m-%d')))
                df_previous = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(start_p.strftime('%Y-%m-%d'), end_p.strftime('%Y-%m-%d')))
                
                days_current = df_current['统计周期'].nunique() if not df_current.empty else 1
                days_previous = df_previous['统计周期'].nunique() if not df_previous.empty else 1
            else:
                date_curr = st.sidebar.date_input("汇总范围", [min_d, max_d], min_value=min_d, max_value=max_d, key="dc_single")
                start_c = date_curr[0] if len(date_curr) > 0 else min_d
                end_c = date_curr[1] if len(date_curr) == 2 else start_c
                
                df_current = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(start_c.strftime('%Y-%m-%d'), end_c.strftime('%Y-%m-%d')))
                days_current = df_current['统计周期'].nunique() if not df_current.empty else 1
    conn.close()

    if not df_current.empty: 
        df_current = merge_category_map(df_current)
        df_current = merge_dynamic_cost_data(df_current)
    if not df_previous.empty: 
        df_previous = merge_category_map(df_previous)
        df_previous = merge_dynamic_cost_data(df_previous)

    all_stores = sorted(list(df_current['门店名称'].dropna().unique())) if not df_current.empty else []
    with st.sidebar.expander("🛠️ 深度过滤", expanded=True):
        all_projects = sorted(list(df_current['所属项目'].dropna().unique())) if not df_current.empty else []
        selected_projects = st.multiselect("所属项目", all_projects)
        filtered_stores = sorted(list(df_current[df_current['所属项目'].isin(selected_projects)]['门店名称'].dropna().unique())) if selected_projects else all_stores
        selected_stores = st.multiselect("门店筛选", filtered_stores)
        
        all_l1 = sorted([str(x) for x in df_current['一级分类'].dropna().unique()]) if not df_current.empty else []
        selected_l1 = st.multiselect("一级分类", all_l1)
        available_l2 = sorted([str(x) for x in df_current[df_current['一级分类'].isin(selected_l1)]['二级分类'].dropna().unique()]) if selected_l1 else sorted([str(x) for x in df_current['二级分类'].dropna().unique()]) if not df_current.empty else []
        selected_l2 = st.multiselect("二级分类", available_l2)

    if selected_projects:
        df_current = df_current[df_current['所属项目'].isin(selected_projects)]
        if not df_previous.empty: df_previous = df_previous[df_previous['所属项目'].isin(selected_projects)]
    if selected_stores:
        df_current = df_current[df_current['门店名称'].isin(selected_stores)]
        if not df_previous.empty: df_previous = df_previous[df_previous['门店名称'].isin(selected_stores)]
    if selected_l1:
        df_current = df_current[df_current['一级分类'].isin(selected_l1)]
        if not df_previous.empty: df_previous = df_previous[df_previous['一级分类'].isin(selected_l1)]
    if selected_l2:
        df_current = df_current[df_current['二级分类'].isin(selected_l2)]
        if not df_previous.empty: df_previous = df_previous[df_previous['二级分类'].isin(selected_l2)]

    cur_qty, cur_amt, cur_profit_log, cur_profit_store, cur_cup_price, cur_margin_log, cur_margin_store, cur_daily_qty, cur_daily_amt = calculate_metrics(df_current, days_current)

    if is_comparison_mode and not df_previous.empty:
        prev_qty, prev_amt, _, _, prev_cup_price, prev_margin_log, prev_margin_store, prev_daily_qty, prev_daily_amt = calculate_metrics(df_previous, days_previous)
        delta_qty = ((cur_qty - prev_qty) / prev_qty) if prev_qty != 0 else 0
        delta_amt = ((cur_amt - prev_amt) / prev_amt) if prev_amt != 0 else 0
        delta_price = ((cur_cup_price - prev_cup_price) / prev_cup_price) if prev_cup_price != 0 else 0
        delta_margin_log = cur_margin_log - prev_margin_log
        delta_margin_store = cur_margin_store - prev_margin_store
        delta_daily_qty = ((cur_daily_qty - prev_daily_qty) / prev_daily_qty) if prev_daily_qty != 0 else 0
        delta_daily_amt = ((cur_daily_amt - prev_daily_amt) / prev_daily_amt) if prev_daily_amt != 0 else 0
    else: 
        delta_qty = delta_amt = delta_price = delta_margin_log = delta_margin_store = delta_daily_qty = delta_daily_amt = None

    st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf?auto=format&fit=crop&w=1200&h=250&q=80", use_container_width=True)
    c_title, c_period = st.columns([2, 1])
    with c_title: st.title("📊 顿角咖啡智能数据看板")
    with c_period:
        if available_periods and 'start_c' in locals():
            period_str = f"{start_c.strftime('%m/%d')} - {end_c.strftime('%m/%d')} ({days_current}天有效)"
            if is_comparison_mode: period_str += f" vs {start_p.strftime('%m/%d')}-{end_p.strftime('%m/%d')}"
        else:
            period_str = "暂无数据"
        st.markdown(f"<div style='text-align:right; padding-top:10px; color:#64748B;'><b>分析范围</b><br><span style='color:#3B82F6; font-size:1.1em'>{period_str}</span></div>", unsafe_allow_html=True)
    st.markdown("---")

    if df_current.empty:
        st.warning("⚠️ 当前筛选结果为空。")
        st.stop()

    def metric_card(title, value, delta, prefix="", suffix="", is_percent=False, icon=""):
        d_str = f"{delta:+.2f} pts" if is_percent and delta is not None else (f"{delta:+.2%}" if delta is not None else None)
        with st.container(border=True):
            st.metric(f"{icon} {title}", f"{prefix}{value}{suffix}", d_str, delta_color="inverse")

    st.subheader("📦 核心经营指标 (基于双轨配方核算)")
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("总销量", int(cur_qty), delta_qty, suffix=" 杯", icon="🛒")
    with c2: metric_card("总营收", f"{cur_amt:,.2f}", delta_amt, prefix="¥", icon="💰")
    with c3: metric_card("物流出厂毛利率", f"{cur_margin_log:.2f}", delta_margin_log, suffix="%", is_percent=True, icon="🚚")
    with c4: metric_card("门店综合毛利率", f"{cur_margin_store:.2f}", delta_margin_store, suffix="%", is_percent=True, icon="🏪")

    st.subheader("🚀 日均效率指标")
    c5, c6, c7 = st.columns(3)
    with c5: metric_card("日均杯数", f"{cur_daily_qty:.1f}", delta_daily_qty, suffix=" 杯", icon="📅")
    with c6: metric_card("日均营收", f"{cur_daily_amt:,.2f}", delta_daily_amt, prefix="¥", icon="💳")
    with c7: metric_card("平均客单价", f"{cur_cup_price:.2f}", delta_price, prefix="¥", icon="🏷️")

    st.markdown("---")
    st.markdown("### 📄 商品销售与配方成本明细")
    
    agg_dict = {
        '一级分类': 'first', '二级分类': 'first', '所属项目': 'first', 
        '销售数量': 'sum', '销售金额': 'sum', 
        '物流单位成本': 'first', '门店单位成本': 'first', 
        '物流毛利': 'sum', '门店毛利': 'sum'
    }
    df_view = df_current.groupby(['商品名称', '规格', '做法'], as_index=False).agg(agg_dict)
    df_view['物流毛利率'] = (df_view['物流毛利'] / df_view['销售金额'] * 100).fillna(0)
    df_view['门店毛利率'] = (df_view['门店毛利'] / df_view['销售金额'] * 100).fillna(0)
    df_view['销售占比'] = (df_view['销售金额'] / df_view['销售金额'].sum() * 100).fillna(0)
    df_view = df_view.sort_values('销售数量', ascending=False).round(2)
    df_view['序号'] = range(1, len(df_view) + 1)

    avg_s = df_view['销售数量'].mean(); avg_m = df_view['门店毛利率'].mean()
    def get_bcg(row):
        if row['销售数量'] >= avg_s and row['门店毛利率'] >= avg_m: return "🌟 明星"
        elif row['销售数量'] >= avg_s: return "🐮 金牛"
        elif row['门店毛利率'] >= avg_m: return "❓ 问题"
        return "🐕 瘦狗"
    df_view['BCG矩阵'] = df_view.apply(get_bcg, axis=1)

    conditions = [
        (df_view['门店单位成本'] == 0) & (df_view['物流单位成本'] == 0),
        (df_view['门店毛利率'] < 60), 
        (df_view['门店毛利率'] >= 60) & (df_view['门店毛利率'] <= 65)
    ]
    choices = ['⚠️ 未配配方', '🔴 低毛利', '🟡 预警']
    df_view['健康度'] = np.select(conditions, choices, default='🟢 健康')

    max_sales_val = df_view['销售数量'].max()
    safe_max_sales = int(max_sales_val) if pd.notna(max_sales_val) and max_sales_val > 0 else 1

    cols = ['序号', '商品名称', '规格', '做法', 'BCG矩阵', '健康度', '二级分类', '销售数量', '销售金额', '物流单位成本', '物流毛利率', '门店单位成本', '门店毛利率', '销售占比']
    with st.container(border=True):
        st.dataframe(df_view[cols], column_config={
            "序号": st.column_config.NumberColumn("排名", width="small"),
            "销售数量": st.column_config.ProgressColumn("总销量", format="%d", min_value=0, max_value=safe_max_sales),
            "销售金额": st.column_config.NumberColumn("营收", format="¥%.2f"),
            "物流单位成本": st.column_config.NumberColumn("物流配方成本", format="¥%.2f"),
            "物流毛利率": st.column_config.NumberColumn("物流毛利率", format="%.2f%%"),
            "门店单位成本": st.column_config.NumberColumn("到店配方成本", format="¥%.2f"),
            "门店毛利率": st.column_config.NumberColumn("门店毛利率", format="%.2f%%"),
            "销售占比": st.column_config.NumberColumn("营收占比", format="%.2f%%"),
        }, use_container_width=True, hide_index=True)


# =============================================================================
# 页面 2：⚙️ 成本配方中心 (BOM 管理)
# =============================================================================
elif app_mode == "⚙️ 成本与配方中心":
    st.title("⚙️ 三级原物料与配方引擎")
    st.markdown("为您提供从源头出厂到终端门店的精细化双轨成本核算。")
    
    tab_m, tab_b = st.tabs(["📦 第一步：基础原物料库上传", "📋 第二步：双轨配方(BOM)配置"])
    
    # --- Tab 1: 原物料管理 ---
    with tab_m:
        st.markdown("#### 1. 上传包含三种价格的原物料档")
        st.info("格式要求：表格需包含 `物流名称`, `品项类别`, `单价单位`, 以及 `物流单价成本`, `百度单价成本`, `顿角单价成本` 等列。")
        raw_file = st.file_uploader("上传原物料表", type=["xlsx", "csv"])
        if raw_file:
            df_raw_up = load_data_from_buffer(raw_file)
            if df_raw_up is not None:
                df_raw_up.columns = [str(c).strip() for c in df_raw_up.columns]
                col_map = {}
                
                # 🎯 步骤1：最高优先级 -> 严格精确匹配您指定的6个标准表头
                exact_targets = {
                    '物流名称': '物料名称',
                    '品项类别': '品项类别',
                    '单价单位': '单位',
                    '物流单价成本': '物流单价',
                    '顿角单价成本': '顿角单价',
                    '百度单价成本': '百度单价'
                }
                
                for c in df_raw_up.columns:
                    if c in exact_targets:
                        col_map[c] = exact_targets[c]

                # 🎯 步骤2：对没有精确匹配上的，进行智能模糊兜底 (完美避开大规格名称的干扰)
                mapped_vals = list(col_map.values())
                for c in df_raw_up.columns:
                    if c in col_map: 
                        continue
                    if '物料名称' not in mapped_vals and any(kw in c for kw in ['物料', '原料', '产品']):
                        col_map[c] = '物料名称'; mapped_vals.append('物料名称')
                    elif '品项类别' not in mapped_vals and any(kw in c for kw in ['类别', '分类']):
                        col_map[c] = '品项类别'; mapped_vals.append('品项类别')
                    elif '单位' not in mapped_vals and '单位' in c and '采购' not in c:
                        col_map[c] = '单位'; mapped_vals.append('单位')
                    elif '物流单价' not in mapped_vals and '物流' in c and '单价' in c:
                        col_map[c] = '物流单价'; mapped_vals.append('物流单价')
                    elif '顿角单价' not in mapped_vals and '顿角' in c and '单价' in c:
                        col_map[c] = '顿角单价'; mapped_vals.append('顿角单价')
                    elif '百度单价' not in mapped_vals and '百度' in c and '单价' in c:
                        col_map[c] = '百度单价'; mapped_vals.append('百度单价')
                
                df_raw_up = df_raw_up.rename(columns=col_map)
                
                if '物料名称' in df_raw_up.columns:
                    if isinstance(df_raw_up['物料名称'], pd.DataFrame): df_raw_up['物料名称'] = df_raw_up['物料名称'].iloc[:, 0]
                    
                    df_raw_up['品项类别'] = df_raw_up.get('品项类别', '未分类')
                    if isinstance(df_raw_up['品项类别'], pd.DataFrame): df_raw_up['品项类别'] = df_raw_up['品项类别'].iloc[:, 0]
                    
                    df_raw_up['单位'] = df_raw_up.get('单位', '未知')
                    if isinstance(df_raw_up['单位'], pd.DataFrame): df_raw_up['单位'] = df_raw_up['单位'].iloc[:, 0]
                    
                    for price_col in ['物流单价', '顿角单价', '百度单价']:
                        if price_col not in df_raw_up.columns: 
                            df_raw_up[price_col] = 0.0
                        else:
                            if isinstance(df_raw_up[price_col], pd.DataFrame):
                                df_raw_up[price_col] = df_raw_up[price_col].iloc[:, 0]
                        df_raw_up[price_col] = pd.to_numeric(df_raw_up[price_col], errors='coerce').fillna(0)
                        
                    conn = get_db_conn()
                    # 写入新结构
                    df_raw_up[['物料名称', '品项类别', '单位', '物流单价', '顿角单价', '百度单价']].to_sql('raw_materials', conn, if_exists='replace', index=False)
                    conn.close()
                    st.success("✅ 原物料三级价格库更新成功！")
                    st.rerun()
                else:
                    st.error("❌ 表格必须包含代表【物流名称/物料名称】的列！")
                    
        st.markdown("#### 2. 预览当前价格库")
        conn = get_db_conn()
        try:
            df_raw_view = pd.read_sql("SELECT * FROM raw_materials", conn)
            st.dataframe(df_raw_view, use_container_width=True)
        except: st.write("暂无原物料数据")
        conn.close()
        
    # --- Tab 2: 成本卡设置 (分离搜索与编辑) ---
    with tab_b:
        st.markdown("#### 1. 选择配置环境")
        conn = get_db_conn()
        
        # ✅ 解决空值导致无法选择的问题：对空值进行强制 '常规' 填充
        try: 
            # 🎯 新增：多提取一列 "商品类别"，用于稍后做分类判断
            df_opts = pd.read_sql("SELECT DISTINCT 门店名称, 商品名称, 商品类别, 规格, 做法 FROM sales_raw", conn)
            df_opts['规格'] = df_opts['规格'].fillna('常规').astype(str)
            df_opts['做法'] = df_opts['做法'].fillna('常规').astype(str)
            df_opts['商品名称'] = df_opts['商品名称'].fillna('未知').astype(str)
            df_opts['门店名称'] = df_opts['门店名称'].fillna('未知').astype(str)
            
            # 🎯 新增拦截机制：调用分类引擎，只要没有一级分类（即等于'未分类'）的商品，直接屏蔽不显示！
            df_opts = merge_category_map(df_opts)
            df_opts = df_opts[df_opts['一级分类'] != '未分类']
            
        except: df_opts = pd.DataFrame()
        
        try: raw_mat_list = pd.read_sql("SELECT 物料名称 FROM raw_materials", conn)['物料名称'].tolist()
        except: raw_mat_list = []
        
        if df_opts.empty: 
            st.warning("请先在看板导入企迈销售日结报表以获取商品目录。或当前报表中没有符合一级分类的饮品。")
        elif not raw_mat_list: 
            st.warning("请先在【第一步】上传原物料价格档案！")
        else:
            c_type, c_scope = st.columns(2)
            recipe_type = c_type.radio("配方轨道", ["🏪 门店配方 (核算各店终端毛利)", "📦 物流配方 (核算出厂原始毛利)"])
            
            if recipe_type == "📦 物流配方 (核算出厂原始毛利)":
                apply_scope = c_scope.selectbox("适用范围", ["【全局默认配方】"], disabled=True, help="物流层级计算统一出厂价格。")
                db_type = '物流'
            else:
                all_stores = sorted(df_opts['门店名称'].unique().tolist())
                store_options = ["【全局默认配方】", "【顿角项目配方】", "【百度项目配方】"] + all_stores
                apply_scope = c_scope.selectbox("门店适用范围", store_options, help="越具体的范围优先级越高。如果单店未设，会逐级向上寻找配方。")
                db_type = '门店'
                
            st.divider()
            c_prod, c_spec, c_meth = st.columns(3)
            
            all_prods = sorted(df_opts['商品名称'].unique().tolist())
            selected_prod = c_prod.selectbox("选择商品", all_prods if all_prods else ["无"])
            
            sub_opts_1 = df_opts[df_opts['商品名称'] == selected_prod]
            all_specs = sorted(sub_opts_1['规格'].unique().tolist())
            selected_spec = c_spec.selectbox("选择规格", all_specs if all_specs else ["常规"])
            
            sub_opts_2 = sub_opts_1[sub_opts_1['规格'] == selected_spec]
            all_meths = sorted(sub_opts_2['做法'].unique().tolist())
            selected_meth = c_meth.selectbox("选择做法", all_meths if all_meths else ["常规"])
            
            st.markdown(f"#### 🔍 搜索并添加物料: `{selected_prod}` | `{selected_spec}` | `{selected_meth}`")
            
            # ✅ 解决搜索问题：独立的下拉框天然支持打字拼音搜索！
            col_s1, col_s2, col_s3 = st.columns([3, 1, 1])
            with col_s1:
                search_mat = st.selectbox("输入文字搜索 (支持打字)", ["-- 请选择要添加的物料 --"] + raw_mat_list)
            with col_s2:
                new_qty = st.number_input("添加用量", min_value=0.0, value=0.0, step=1.0)
            with col_s3:
                st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
                if st.button("➕ 极速添加到下方配方", use_container_width=True):
                    if search_mat != "-- 请选择要添加的物料 --" and new_qty > 0:
                        cursor = conn.cursor()
                        # ✅ 解决无法保存和静默崩溃：使用 INSERT OR REPLACE 防冲突
                        cursor.execute("""
                            INSERT OR REPLACE INTO bom_recipes (配方类型, 适用范围, 商品名称, 规格, 做法, 物料名称, 用量)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (db_type, apply_scope, selected_prod, selected_spec, selected_meth, search_mat, new_qty))
                        conn.commit()
                        st.toast(f"成功添加物料：{search_mat}", icon="✅")
                        st.rerun()
                    else:
                        st.warning("⚠️ 请选择物料，并输入大于 0 的用量。")

            st.markdown("#### 📋 当前配方明细 (修改用量或删除请点下方保存)")
            query = """SELECT 物料名称, 用量 FROM bom_recipes 
                       WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?"""
            curr_bom = pd.read_sql(query, conn, params=(db_type, apply_scope, selected_prod, selected_spec, selected_meth))
            
            if not curr_bom.empty:
                # ✅ 解决瞎改报错：将表格内的物料名称锁死，只能改数字或删除行
                edited_bom = st.data_editor(
                    curr_bom,
                    column_config={
                        "物料名称": st.column_config.TextColumn("已添加物料 (请在上方搜索添加)", disabled=True),
                        "用量": st.column_config.NumberColumn("使用数量/克重", min_value=0.0, format="%.2f")
                    },
                    num_rows="dynamic", use_container_width=True, key="bom_editor"
                )
                
                if st.button("💾 保存用量修改与删除", type="primary"):
                    valid_bom = edited_bom.dropna(subset=['物料名称'])
                    valid_bom = valid_bom[valid_bom['用量'] > 0]
                    cursor = conn.cursor()
                    
                    # 先安全删除当前环境的所有该组合
                    cursor.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", 
                                   (db_type, apply_scope, selected_prod, selected_spec, selected_meth))
                    # 重新将表格里的行存入
                    for _, row in valid_bom.iterrows():
                        cursor.execute("""
                            INSERT INTO bom_recipes (配方类型, 适用范围, 商品名称, 规格, 做法, 物料名称, 用量)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (db_type, apply_scope, selected_prod, selected_spec, selected_meth, row['物料名称'], row['用量']))
                    conn.commit()
                    st.success("✅ 配方修改已保存生效！")
                    st.rerun()
            else:
                st.info("💡 当前配方为空，请在上方搜索框内选择物料并添加。")

        conn.close()
