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
    '商品分类': '商品类别'
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
            物料名称 TEXT PRIMARY KEY,
            品项类别 TEXT,
            单位 TEXT,
            物流单价 REAL,
            顿角单价 REAL,
            百度单价 REAL
        )
    ''')
    try: cursor.execute("ALTER TABLE raw_materials ADD COLUMN 品项类别 TEXT")
    except: pass
    
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
        
        for c in df.columns:
            if '规格' in c: 
                df.rename(columns={c: '规格'}, inplace=True)
            elif any(kw in c for kw in ['做法', '口味', '属性', '加料']): 
                df.rename(columns={c: '做法'}, inplace=True)
                
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
        
        if '规格' in df.columns:
            df['规格'] = df['规格'].replace(['nan', 'None', '', '--', 'NaN'], '常规').fillna('常规')
        else:
            df['规格'] = '常规'
            
        if '做法' in df.columns:
            df['做法'] = df['做法'].replace(['nan', 'None', '', '--', 'NaN'], '常规').fillna('常规')
        else:
            df['做法'] = '常规'

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
        df_bom = pd.DataFrame(); df_raw = pd.DataFrame()
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
        df_sales.drop(columns=['物流配方成本','s_dj', 's_bd', 'p_dj', 'p_bd', 'g_dj', 'g_bd', '门店单位成本_bd', '门店单位成本_dj'], inplace=True, errors='ignore')
        
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
        st.markdown("**🔍 库内规格抽检 (最新10条)**")
        if total_rows > 0:
            conn = get_db_conn()
            sample_df = pd.read_sql("SELECT 商品名称, 规格, 做法 FROM sales_raw ORDER BY rowid DESC LIMIT 10", conn)
            st.dataframe(sample_df, hide_index=True)
            conn.close()

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

    st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf?auto=format&fit=crop&w=1200&h=250&q=80", use_container_width=True)
    st.title("📊 顿角咖啡智能数据看板")
    st.markdown("---")

    if df_current.empty:
        st.warning("⚠️ 当前筛选结果为空。")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("总销量", f"{int(cur_qty)} 杯")
    with c2: st.metric("总营收", f"¥{cur_amt:,.2f}")
    with c3: st.metric("出厂毛利率", f"{cur_margin_log:.2f}%")
    with c4: st.metric("门店毛利率", f"{cur_margin_store:.2f}%")

    st.markdown("### 📄 商品销售明细 (加权成本核算)")
    df_current['物流总成本'] = df_current['销售数量'] * df_current['物流单位成本']
    df_current['门店总成本'] = df_current['销售数量'] * df_current['门店单位成本']
    df_current['是否缺配方'] = ((df_current['物流单位成本'] == 0) & (df_current['门店单位成本'] == 0)).astype(int)
    
    df_view = df_current.groupby('商品名称', as_index=False).agg({
        '二级分类': 'first', '销售数量': 'sum', '销售金额': 'sum', 
        '物流总成本': 'sum', '门店总成本': 'sum', '物流毛利': 'sum', '门店毛利': 'sum', '是否缺配方': 'max'
    })
    df_view['物流单位成本'] = np.where(df_view['销售数量'] > 0, df_view['物流总成本'] / df_view['销售数量'], 0)
    df_view['门店单位成本'] = np.where(df_view['销售数量'] > 0, df_view['门店总成本'] / df_view['销售数量'], 0)
    df_view['门店毛利率'] = (df_view['门店毛利'] / df_view['销售金额'] * 100).fillna(0)
    
    max_sales = df_view['销售数量'].max() if not df_view.empty else 1
    st.dataframe(df_view, column_config={
        "销售数量": st.column_config.ProgressColumn("总销量", format="%d", min_value=0, max_value=int(max_sales if max_sales > 0 else 1)),
        "销售金额": st.column_config.NumberColumn("营收", format="¥%.2f"),
        "物流单位成本": st.column_config.NumberColumn("加权出厂成本", format="¥%.2f"),
        "门店单位成本": st.column_config.NumberColumn("加权到店成本", format="¥%.2f"),
        "门店毛利率": st.column_config.NumberColumn("门店毛利率", format="%.2f%%"),
    }, use_container_width=True, hide_index=True)


# =============================================================================
# 页面 2：⚙️ 成本配方中心 (BOM 管理)
# =============================================================================
elif app_mode == "⚙️ 成本与配方中心":
    st.title("⚙️ 三级原物料与配方引擎")
    tab_m, tab_b, tab_v = st.tabs(["📦 第一步：基础原物料库", "📋 第二步：配置单品成本卡", "📚 第三步：成本卡全局编辑库"])
    
    with tab_m:
        st.markdown("#### 1. 上传原物料价格档")
        raw_file = st.file_uploader("上传原物料表", type=["xlsx", "csv"])
        if raw_file:
            df_raw_up = load_data_from_buffer(raw_file)
            if df_raw_up is not None:
                df_raw_up.columns = [str(c).strip() for c in df_raw_up.columns]
                col_map = {}
                exact_targets = {'物流名称': '物料名称', '品项类别': '品项类别', '单价单位': '单位', '物流单价成本': '物流单价', '顿角单价成本': '顿角单价', '百度单价成本': '百度单价'}
                for c in df_raw_up.columns:
                    if c in exact_targets: col_map[c] = exact_targets[c]
                df_raw_up = df_raw_up.rename(columns=col_map)
                if '物料名称' in df_raw_up.columns:
                    for price_col in ['物流单价', '顿角单价', '百度单价']:
                        if price_col in df_raw_up.columns: df_raw_up[price_col] = pd.to_numeric(df_raw_up[price_col], errors='coerce').fillna(0)
                    conn = get_db_conn()
                    df_raw_up[['物料名称', '品项类别', '单位', '物流单价', '顿角单价', '百度单价']].to_sql('raw_materials', conn, if_exists='replace', index=False)
                    conn.close(); st.success("✅ 更新成功！"); st.rerun()
                    
        st.markdown("#### 2. 预览当前价格库")
        conn = get_db_conn()
        try:
            df_raw_view = pd.read_sql("SELECT * FROM raw_materials", conn)
            st.dataframe(df_raw_view, use_container_width=True)
        except: st.write("暂无原物料数据")
        conn.close()

    with tab_b:
        st.markdown("#### 1. 选择配置环境")
        conn = get_db_conn()
        try: 
            df_opts = pd.read_sql("SELECT DISTINCT 门店名称, 商品名称, 商品类别, 规格, 做法 FROM sales_raw", conn)
            df_opts['规格'] = df_opts['规格'].replace(['nan', 'None', '', '--', 'NaN'], '常规').fillna('常规')
            df_opts['做法'] = df_opts['做法'].replace(['nan', 'None', '', '--', 'NaN'], '常规').fillna('常规')
            df_opts = merge_category_map(df_opts)
            df_opts = df_opts[df_opts['一级分类'] != '未分类']
        except: df_opts = pd.DataFrame()
        
        try: raw_mat_list = pd.read_sql("SELECT 物料名称 FROM raw_materials", conn)['物料名称'].tolist()
        except: raw_mat_list = []
        
        if df_opts.empty: st.warning("请先在看板清空并重新导入企迈报表。")
        else:
            c_type, c_scope = st.columns(2)
            recipe_type = c_type.radio("配方轨道", ["🏪 门店配方", "📦 物流配方"])
            db_type = '物流' if '物流' in recipe_type else '门店'
            
            if db_type == '物流':
                apply_scope = "【全局默认配方】"
                st.info("物流层级统一使用出厂价格核算。")
            else:
                all_stores = sorted(df_opts['门店名称'].unique().tolist())
                apply_scope = c_scope.selectbox("适用范围", ["【全局默认配方】", "【顿角项目配方】", "【百度项目配方】"] + all_stores)
                
            st.divider()
            c_prod, c_spec, c_meth = st.columns(3)
            all_prods = sorted(df_opts['商品名称'].unique().tolist())
            selected_prod = c_prod.selectbox("选择商品", all_prods)
            
            spec_opts = sorted(df_opts[df_opts['商品名称'] == selected_prod]['规格'].unique().tolist())
            selected_spec = c_spec.selectbox("选择规格", spec_opts)
            
            meth_opts = sorted(df_opts[(df_opts['商品名称'] == selected_prod) & (df_opts['规格'] == selected_spec)]['做法'].unique().tolist())
            selected_meth = c_meth.selectbox("选择做法", meth_opts)
            
            with st.container(border=True):
                st.markdown(f"#### ➕ 添加新物料到: `{selected_prod}`")
                col_s1, col_s2, col_s3 = st.columns([3, 1, 1])
                with col_s1: search_mat = st.selectbox("搜索物料", ["-- 请选择 --"] + raw_mat_list)
                with col_s2: new_qty = st.number_input("用量", min_value=0.0, step=1.0)
                with col_s3:
                    st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
                    if st.button("确认添加", type="primary", use_container_width=True):
                        if search_mat != "-- 请选择 --" and new_qty > 0:
                            cursor = conn.cursor()
                            cursor.execute("INSERT OR REPLACE INTO bom_recipes VALUES (?,?,?,?,?,?,?)", 
                                           (db_type, apply_scope, selected_prod, selected_spec, selected_meth, search_mat, new_qty))
                            conn.commit(); st.toast("✅ 已添加"); st.rerun()

            st.markdown("#### 📋 当前配方明细 (独立修改)")
            curr_bom = pd.read_sql("SELECT 物料名称, 用量 FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", 
                                   conn, params=(db_type, apply_scope, selected_prod, selected_spec, selected_meth))
            
            if not curr_bom.empty:
                for idx, row in curr_bom.iterrows():
                    m, q = row['物料名称'], row['用量']
                    c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
                    c1.markdown(f"☕ {m}")
                    new_q = c2.number_input("用量", value=float(q), key=f"q_tab2_{idx}_{m}", label_visibility="collapsed")
                    if c3.button("保存", key=f"s_tab2_{idx}_{m}"):
                        cursor = conn.cursor()
                        cursor.execute("UPDATE bom_recipes SET 用量=? WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", 
                                       (new_q, db_type, apply_scope, selected_prod, selected_spec, selected_meth, m))
                        conn.commit(); st.rerun()
                    if c4.button("移除", key=f"d_tab2_{idx}_{m}", type="primary"):
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", 
                                       (db_type, apply_scope, selected_prod, selected_spec, selected_meth, m))
                        conn.commit(); st.rerun()
            else: st.info("当前组合暂无配方。")
        conn.close()

    # --- Tab 3: 全局成本卡库 (核心升级：直接编辑) ---
    with tab_v:
        st.markdown("#### 📚 成本卡全局编辑大盘")
        st.info("💡 **说明**：您可以在下方表格中直接修改任一配方的【用量】或【删除行】。修改完成后请务必点击下方的蓝色【保存全部修改】按钮。")
        
        conn = get_db_conn()
        try:
            df_b = pd.read_sql("SELECT * FROM bom_recipes", conn)
            df_r = pd.read_sql("SELECT * FROM raw_materials", conn)
            
            if not df_b.empty:
                # 为了让用户看清楚成本，我们需要把单价接上来
                lib_view = df_b.merge(df_r, on='物料名称', how='left').fillna(0)
                
                # 记录原始主键信息，用于后期精准保存
                # 隐藏主键列不给用户看，但数据里得有
                edit_df = lib_view[['配方类型', '适用范围', '商品名称', '规格', '做法', '物料名称', '用量', '物流单价', '顿角单价', '百度单价']]
                
                # 启用表格编辑
                edited_result = st.data_editor(
                    edit_df,
                    column_config={
                        "配方类型": st.column_config.TextColumn("类型", disabled=True),
                        "适用范围": st.column_config.TextColumn("范围", disabled=True),
                        "商品名称": st.column_config.TextColumn("商品", disabled=True),
                        "规格": st.column_config.TextColumn("规格", disabled=True),
                        "做法": st.column_config.TextColumn("做法", disabled=True),
                        "物料名称": st.column_config.TextColumn("物料", disabled=True),
                        "用量": st.column_config.NumberColumn("用量(g/ml)", format="%.2f", min_value=0.0),
                        "物流单价": st.column_config.NumberColumn("物流单价", format="¥ %.4f", disabled=True),
                        "顿角单价": st.column_config.NumberColumn("顿角单价", format="¥ %.4f", disabled=True),
                        "百度单价": st.column_config.NumberColumn("百度单价", format="¥ %.4f", disabled=True),
                    },
                    use_container_width=True,
                    num_rows="dynamic", # 支持删除行
                    key="global_bom_editor"
                )
                
                # 按钮操作
                c_save, c_refresh, _ = st.columns([1,1,3])
                if c_save.button("💾 保存库内全部修改", type="primary", use_container_width=True):
                    # 清洗掉可能被删空的数据
                    final_df = edited_result.dropna(subset=['商品名称', '物料名称'])
                    final_df = final_df[final_df['用量'] > 0]
                    
                    cursor = conn.cursor()
                    # 暴力更新法：清空再存入
                    cursor.execute("DELETE FROM bom_recipes")
                    for _, r in final_df.iterrows():
                        cursor.execute("INSERT INTO bom_recipes (配方类型, 适用范围, 商品名称, 规格, 做法, 物料名称, 用量) VALUES (?,?,?,?,?,?,?)",
                                       (r['配方类型'], r['适用范围'], r['商品名称'], r['规格'], r['做法'], r['物料名称'], r['用量']))
                    conn.commit()
                    st.success("✅ 全局成本库已成功更新！")
                    st.rerun()
                
                if c_refresh.button("🔄 放弃修改并刷新", use_container_width=True):
                    st.rerun()
                
                # 底部自动呈现汇总后的总成本卡，方便核对
                st.divider()
                st.markdown("#### 🔍 最终成本核算预览 (核对专用)")
                lib_view['物流分项'] = lib_view['用量'] * lib_view['物流单价']
                lib_view['顿角分项'] = lib_view['用量'] * lib_view['顿角单价']
                lib_view['百度分项'] = lib_view['用量'] * lib_view['百度单价']
                
                sum_df = lib_view.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法']).agg({
                    '物流分项': 'sum', '顿角分项': 'sum', '百度分项': 'sum', '物料名称': lambda x: '、'.join(x)
                }).reset_index()
                
                st.dataframe(sum_df.rename(columns={
                    '物流分项':'物流总成本','顿角分项':'顿角总成本','百度分项':'百度总成本','物料名称':'包含成分'
                }), use_container_width=True, hide_index=True)
                
            else:
                st.info("配方库目前为空，请先前往【第二步】添加一些产品配方。")
        except Exception as e:
            st.error(f"加载预览失败: {e}")
        finally:
            conn.close()
