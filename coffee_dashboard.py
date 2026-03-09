# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import math
import glob
import re
import sqlite3
from datetime import datetime, date

# -----------------------------------------------------------------------------
# 1. 核心配置与 CSS 注入 (精装 UI 升级版)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="顿角咖啡智能数据看板",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === 🔐 安全登录系统 ===
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

# 全局极简现代 CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #F8FAFC; font-family: 'Inter', 'Helvetica Neue', sans-serif; }
    img { border-radius: 12px; transition: transform 0.3s ease; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E2E8F0; }
    h1 { color: #0F172A; font-weight: 800; letter-spacing: -0.03em; }
    h3, h4, h5 { color: #1E293B; font-weight: 600; letter-spacing: -0.01em; }
    
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
        letter-spacing: -0.02em;
    }
    
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #F8FAFC; padding: 6px; border-radius: 12px; border: 1px solid #E2E8F0;}
    .stTabs [data-baseweb="tab"] { height: 40px; border-radius: 8px; border: none; color: #64748B; font-weight: 600; background-color: transparent; }
    .stTabs [aria-selected="true"] { background-color: #FFFFFF; color: #3B82F6; box-shadow: 0 2px 4px rgba(0,0,0,0.05);}
    
    .insight-card { padding: 14px 18px; border-radius: 10px; margin-bottom: 10px; font-size: 14px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.02);}
    .insight-red { background-color: #FFF1F2; border-left: 4px solid #F43F5E; color: #881337; }
    .insight-green { background-color: #ECFDF5; border-left: 4px solid #10B981; color: #064E3B; }
    .insight-value-red { color: #F43F5E; font-weight: 700; font-size: 1.05em;}
    .insight-value-green { color: #10B981; font-weight: 700; font-size: 1.05em;}
</style>
""", unsafe_allow_html=True)

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

def update_chart_layout(fig, title_text=""):
    fig.update_layout(
        plot_bgcolor="rgba(255,255,255,0)", paper_bgcolor="rgba(255,255,255,0)",
        font_family="'Inter', 'Helvetica Neue', sans-serif", font_color="#475569",
        margin=dict(l=10, r=20, t=45 if title_text else 20, b=10),
        hoverlabel=dict(bgcolor="rgba(255,255,255,0.98)", font_size=13, font_family="'Inter', sans-serif", bordercolor="#E2E8F0", font_color="#0F172A"),
        title=dict(text=title_text, font=dict(size=15, color="#1E293B", weight="bold"), x=0.01, y=0.98) if title_text else None,
        bargap=0.25, showlegend=False
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(226, 232, 240, 0.6)', zeroline=False, showline=False, tickfont=dict(color="#94A3B8", size=12), title_text="")
    fig.update_yaxes(showgrid=False, zeroline=False, showline=False, tickfont=dict(color="#64748B", size=12), title_text="")
    fig.update_traces(opacity=0.85, textfont=dict(size=12, color="#475569", family="Inter"), hoverlabel_namelength=-1, marker_line_width=0)
    return fig

# -----------------------------------------------------------------------------
# 2. 内置字典与 ETL 翻译规则
# -----------------------------------------------------------------------------
# 🤖【免加工清洗字典】精准匹配您的 CSV 原始导出数据
RAW_COLUMN_MAPPING = {
    '商品实收': '销售金额',
    '商品销量': '销售数量',
    '日期': '统计周期',     # 👈 自动将 CSV 中的"日期"识别为日历引擎的依据
    '商品分类': '商品类别'  # 👈 将原始表的"商品分类"作为识别类别，以便剔除无效商品
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
# 3. 💾 本地 SQLite 数据库系统 (已移除 Supabase)
# -----------------------------------------------------------------------------
DATA_DIR = "data_storage"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_PATH = os.path.join(DATA_DIR, "coffee_master.db")

def get_db_conn():
    """获取本地 SQLite 数据库连接"""
    return sqlite3.connect(DB_PATH)

def init_db():
    """初始化数据库表结构 (如果不存在)"""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales_raw (
            门店名称 TEXT,
            商品名称 TEXT,
            商品类别 TEXT,
            统计周期 TEXT,
            销售金额 REAL,
            销售数量 REAL,
            source_file TEXT
        )
    ''')
    conn.commit()
    conn.close()

# 启动时确保数据库存在
init_db()

# -----------------------------------------------------------------------------
# 4. 数据清洗与入库引擎 (ETL)
# -----------------------------------------------------------------------------
def clean_store_name(name):
    if pd.isna(name): return ""
    name = str(name).strip().replace(" ", "").replace("(", "（").replace(")", "）") 
    return name

def standardize_date(val, file_name=""):
    try:
        if pd.notna(val) and str(val).strip() != "":
            return pd.to_datetime(val).strftime('%Y-%m-%d')
    except: pass
    
    try:
        name_without_ext = os.path.splitext(file_name)[0]
        match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{8}', name_without_ext)
        if match: return pd.to_datetime(match.group()).strftime('%Y-%m-%d')
        return pd.to_datetime(name_without_ext).strftime('%Y-%m-%d')
    except:
        return str(name_without_ext)

def load_data_from_buffer(uploaded_file):
    try:
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            return pd.read_excel(uploaded_file, engine='openpyxl')
        else:
            for enc in ['utf-8', 'utf-8-sig', 'gbk', 'gb18030']:
                try: return pd.read_csv(uploaded_file, encoding=enc)
                except: continue
    except Exception as e: st.error(f"读取文件出错: {e}")
    return None

def ingest_sales_data(uploaded_files):
    conn = get_db_conn()
    success_count = 0
    skip_count = 0
    
    for f in uploaded_files:
        file_name = f.name
        try:
            existing = pd.read_sql("SELECT COUNT(*) as cnt FROM sales_raw WHERE source_file = ?", conn, params=(file_name,))
            if existing.iloc[0]['cnt'] > 0:
                st.toast(f"文件 '{file_name}' 已存在，跳过导入。", icon="⚠️")
                skip_count += 1
                continue
        except: pass
            
        df = load_data_from_buffer(f)
        if df is None: continue
        
        # 应用自动列名映射
        df.columns = [str(c).strip() for c in df.columns]
        
        # ✅ 解决企迈系统重名冲突：如果原表同时存在“商品类别”和“商品分类”，以“商品分类”为准
        if '商品类别' in df.columns and '商品分类' in df.columns:
            df = df.drop(columns=['商品类别'])
            
        df = df.rename(columns=RAW_COLUMN_MAPPING)
        
        # ✅ 终极除垢：去除企迈等收银系统导出的前置反引号(`)和无用空格
        for c in ['商品名称', '商品类别', '门店名称', '统计周期']:
            if c in df.columns:
                df[c] = df[c].astype(str).str.replace('`', '', regex=False).str.strip()
                
        # 🚫 核心拦截门：只要没有配置一级分类（即不在内置字典里的商品），直接丢弃，不读取入库！
        valid_categories = set([item["二级分类"] for item in CATEGORY_MAPPING_DATA])
        if '商品类别' in df.columns:
            df = df[df['商品类别'].isin(valid_categories)]
        
        # 如果过滤完之后，这张表变空了，直接跳过
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

        if '门店名称' in df.columns: df['门店名称'] = df['门店名称'].ffill()
        for c in ['销售金额', '销售数量']:
            if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(r'[¥$,￥]', '', regex=True), errors='coerce').fillna(0)
            
        df['source_file'] = file_name
        keep_cols = ['门店名称', '商品名称', '商品类别', '统计周期', '销售金额', '销售数量', 'source_file']
        for col in keep_cols:
            if col not in df.columns: df[col] = None
                
        try:
            df[keep_cols].to_sql('sales_raw', conn, if_exists='append', index=False)
            success_count += 1
        except Exception as e: st.error(f"写入数据库失败: {e}")
        
    conn.close()
    if success_count > 0: st.success(f"✅ 成功将 {success_count} 份日报存入本地数据库！")

def ingest_config_data(uploaded_file, table_name):
    if uploaded_file is None: return
    df = load_data_from_buffer(uploaded_file)
    if df is not None:
        conn = get_db_conn()
        try:
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            st.success(f"✅ 本地档案更新成功！")
            st.rerun()
        except: pass
        finally:
            conn.close()

# -----------------------------------------------------------------------------
# 4.5 读取配置与加工逻辑
# -----------------------------------------------------------------------------
def get_config_df_from_db(table_name):
    conn = get_db_conn()
    try: 
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        conn.close()
        return df
    except: 
        conn.close()
        return None

def merge_category_map(df_sales):
    if df_sales is None or df_sales.empty: return df_sales
    if '商品类别' in df_sales.columns:
        df_cat = pd.DataFrame(CATEGORY_MAPPING_DATA)
        for c in ['一级分类','二级分类']: df_cat[c] = df_cat[c].astype(str).str.strip()
        df_sales['商品类别_clean'] = df_sales['商品类别'].astype(str).str.strip()
        df_cat = df_cat.drop_duplicates(subset=['二级分类'])
        df_sales = pd.merge(df_sales, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left', suffixes=('', '_map'))
        df_sales['一级分类'] = df_sales['一级分类'].fillna('未分类')
        df_sales['二级分类'] = df_sales['商品类别']
        df_sales = df_sales.drop(columns=['商品类别_clean', '二级分类_map'], errors='ignore')
    else:
        df_sales['一级分类'] = '未分类'; df_sales['二级分类'] = '未分类'

    if '门店名称' in df_sales.columns:
        store_to_project = {}
        for proj, stores in PROJECT_STORE_MAPPING.items():
            for s in stores: store_to_project[clean_store_name(s)] = proj
        df_sales['所属项目'] = df_sales['门店名称'].map(store_to_project).fillna('其他项目')
    else: df_sales['所属项目'] = '未知'
    return df_sales

def merge_cost_data(df_sales, df_logistics_cost, df_store_cost):
    if df_sales is None or df_sales.empty: return df_sales
    df_sales['物流成本'] = 0; df_sales['门店成本'] = 0
    if df_logistics_cost is not None:
        if '产品' in df_logistics_cost.columns: df_logistics_cost = df_logistics_cost.rename(columns={'产品': '商品名称'})
        if '商品名称' in df_logistics_cost.columns and '成本' in df_logistics_cost.columns:
            df_logistics_cost['商品名称'] = df_logistics_cost['商品名称'].astype(str).str.strip()
            df_logistics_cost['成本'] = pd.to_numeric(df_logistics_cost['成本'], errors='coerce').fillna(0)
            df_log_uniq = df_logistics_cost.groupby('商品名称', as_index=False)['成本'].mean().rename(columns={'成本': '物流成本_表'})
            df_sales = pd.merge(df_sales, df_log_uniq[['商品名称', '物流成本_表']], on='商品名称', how='left')
            df_sales['物流成本'] = df_sales['物流成本_表'].fillna(0)
            df_sales = df_sales.drop(columns=['物流成本_表'], errors='ignore')

    if df_store_cost is not None:
        if '产品' in df_store_cost.columns: df_store_cost = df_store_cost.rename(columns={'产品': '商品名称'})
        if '商品名称' in df_store_cost.columns and '成本' in df_store_cost.columns:
            df_store_cost['商品名称'] = df_store_cost['商品名称'].astype(str).str.strip()
            df_store_cost['成本'] = pd.to_numeric(df_store_cost['成本'], errors='coerce').fillna(0)
            df_store_uniq = df_store_cost.groupby('商品名称', as_index=False)['成本'].mean().rename(columns={'成本': '门店成本_表'})
            df_sales = pd.merge(df_sales, df_store_uniq[['商品名称', '门店成本_表']], on='商品名称', how='left')
            df_sales['门店成本'] = df_sales['门店成本_表'].fillna(0)
            df_sales = df_sales.drop(columns=['门店成本_表'], errors='ignore')

    df_sales['物流毛利'] = df_sales['销售金额'] - (df_sales['销售数量'] * df_sales['物流成本'])
    df_sales['门店毛利'] = df_sales['销售金额'] - (df_sales['销售数量'] * df_sales['门店成本'])
    return df_sales

def merge_target_data(df_store_stats, df_target):
    if df_store_stats is None or df_store_stats.empty: return df_store_stats
    if df_target is None:
        df_store_stats['日均目标'] = 0; df_store_stats['达成率'] = 0; df_store_stats['达成状态'] = '⚪ 未设定'
        return df_store_stats
        
    sample_store = df_store_stats['门店名称'].iloc[0] if not df_store_stats.empty else ""
    cols_str = " ".join([str(c) for c in df_target.columns])
    if "日均目标" not in df_target.columns and ("店" in cols_str or sample_store in cols_str):
        try:
            valid_cols = [c for c in df_target.columns if isinstance(c, str) and len(c) > 1]
            df_T = df_target[valid_cols].iloc[0:1].T.reset_index()
            df_T.columns = ['门店名称', '日均目标']
            df_target = df_T
        except: pass

    if '门店名称' in df_target.columns:
        df_target['门店名称'] = df_target['门店名称'].apply(clean_store_name)
        val_col = '日均目标'
        if val_col not in df_target.columns and len(df_target.columns) >= 2: val_col = df_target.columns[1]
            
        if val_col in df_target.columns:
            df_target['日均目标'] = pd.to_numeric(df_target[val_col], errors='coerce').fillna(0)
            df_target = df_target.groupby('门店名称', as_index=False)['日均目标'].max()
            df_merged = pd.merge(df_store_stats, df_target, on='门店名称', how='left')
            df_merged['日均目标'] = df_merged['日均目标'].fillna(0)
            
            def get_status(row):
                if row['日均目标'] <= 0.1: return '⚪ 未设定'
                elif row['日均杯数'] >= row['日均目标']: return '✅ 达成'
                else: return '❌ 未达成'
            df_merged['达成状态'] = df_merged.apply(get_status, axis=1)
            df_merged['达成率'] = np.where(df_merged['日均目标']>0, df_merged['日均杯数']/df_merged['日均目标'], 0)
            return df_merged

    df_store_stats['日均目标'] = 0; df_store_stats['达成率'] = 0; df_store_stats['达成状态'] = '⚪ 未设定 (格式错误)'
    return df_store_stats

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
# 5. 侧边栏布局
# -----------------------------------------------------------------------------
logo_path = "logo.png"
if os.path.exists(logo_path): st.sidebar.image(logo_path, width=120)
else: st.sidebar.image("https://cdn-icons-png.flaticon.com/512/751/751621.png", width=100)

st.sidebar.markdown("## 顿角咖啡智能数据看板")

with st.sidebar.expander("💾 本地数据库管理", expanded=True):
    conn = get_db_conn()
    try:
        total_rows = pd.read_sql("SELECT COUNT(*) as c FROM sales_raw", conn).iloc[0]['c']
        df_periods_db = pd.read_sql("SELECT DISTINCT 统计周期 FROM sales_raw WHERE 统计周期 IS NOT NULL", conn)
        available_periods = sorted(df_periods_db['统计周期'].tolist())
    except:
        total_rows = 0; available_periods = []
    finally:
        conn.close()
    
    st.markdown(f"<div style='background-color:#EFF6FF; padding:10px; border-radius:8px; margin-bottom:15px; text-align:center;'><b style='color:#1E40AF'>💾 本地已存 {total_rows:,} 条记录</b></div>", unsafe_allow_html=True)
    
    st.markdown("**📤 导入新营业日结表**")
    new_sales = st.file_uploader("支持按天批量上传", type=["xlsx", "csv"], accept_multiple_files=True)
    if new_sales: ingest_sales_data(new_sales); st.rerun()
        
    st.divider()
    st.markdown("**🚚 更新物流成本 (本地)**")
    df_log_cost_check = get_config_df_from_db("cost_logistics")
    if df_log_cost_check is not None: st.caption("✅ 已配置")
    new_log_cost = st.file_uploader("上传物流成本表", type=["xlsx", "csv"], key="log_up")
    if new_log_cost: ingest_config_data(new_log_cost, "cost_logistics")

    st.markdown("**🏪 更新门店成本 (本地)**")
    df_store_cost_check = get_config_df_from_db("cost_store")
    if df_store_cost_check is not None: st.caption("✅ 已配置")
    new_store_cost = st.file_uploader("上传门店成本表", type=["xlsx", "csv"], key="store_up")
    if new_store_cost: ingest_config_data(new_store_cost, "cost_store")
            
    st.markdown("**🎯 更新门店目标 (本地)**")
    df_target_check = get_config_df_from_db("target_store")
    if df_target_check is not None: st.caption("✅ 已配置")
    new_target = st.file_uploader("上传目标表", type=["xlsx", "csv"], key="tar_up")
    if new_target: ingest_config_data(new_target, "target_store")

    # 👇 这是新增的清空数据功能
    st.divider()
    st.markdown("**⚠️ 危险操作**")
    if st.button("🗑️ 清空所有销售数据", use_container_width=True):
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sales_raw") # 清空表数据
        conn.commit()
        conn.close()
        st.success("✅ 销售数据已全部清空！请重新上传。")
        st.rerun()

if total_rows == 0:
    st.markdown("<div style='text-align:center;padding:100px;'><h1>💾 欢迎进入本地开发模式</h1><p>本地数据库目前为空，请在左侧上传数据进行调试。</p></div>", unsafe_allow_html=True)
    st.stop()

# -----------------------------------------------------------------------------
# 6. 📅 智能日历与动态提取引擎
# -----------------------------------------------------------------------------
df_current = pd.DataFrame(); df_previous = pd.DataFrame()
is_comparison_mode = False
days_current = 1; days_previous = 1

st.sidebar.markdown("---")
st.sidebar.subheader("📅 自由日历分析")

conn = get_db_conn()

if available_periods:
    # 🌟 强制启用高级日历模式，隐藏文件名
    parsed_dates = []
    for p in available_periods:
        try: parsed_dates.append(datetime.strptime(p, '%Y-%m-%d').date())
        except: pass
        
    if parsed_dates:
        min_d, max_d = min(parsed_dates), max(parsed_dates)
        
        # 提示当前数据库存在的时间跨度
        st.sidebar.markdown(f"<div style='font-size:13px; color:#64748B; margin-bottom:10px;'>💡 数据库已有数据范围: {min_d.strftime('%m/%d')} 至 {max_d.strftime('%m/%d')}</div>", unsafe_allow_html=True)
        
        enable_comparison = st.sidebar.checkbox("开启环比对比", value=False)
        if enable_comparison:
            is_comparison_mode = True
            st.sidebar.markdown("##### 本期时间段")
            date_curr = st.sidebar.date_input("选择范围", [max_d, max_d], min_value=min_d, max_value=max_d, key="dc")
            st.sidebar.markdown("##### 上期 (对比) 时间段")
            date_prev = st.sidebar.date_input("选择范围", [min_d, min_d], min_value=min_d, max_value=max_d, key="dp")
            
            # 解析本期
            start_c = date_curr[0] if len(date_curr) > 0 else max_d
            end_c = date_curr[1] if len(date_curr) == 2 else start_c
            
            # 解析上期
            start_p = date_prev[0] if len(date_prev) > 0 else min_d
            end_p = date_prev[1] if len(date_prev) == 2 else start_p
            
            # 从数据库提取，自然合并所有项目的数据！
            df_current = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(start_c.strftime('%Y-%m-%d'), end_c.strftime('%Y-%m-%d')))
            df_previous = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(start_p.strftime('%Y-%m-%d'), end_p.strftime('%Y-%m-%d')))
            
            # 【智能实际天数】不管框选了几天，只算数据库里真正有数据的天数
            days_current = df_current['统计周期'].nunique() if not df_current.empty else 1
            days_previous = df_previous['统计周期'].nunique() if not df_previous.empty else 1
        else:
            date_curr = st.sidebar.date_input("选择汇总时间段", [min_d, max_d], min_value=min_d, max_value=max_d, key="dc_single")
            start_c = date_curr[0] if len(date_curr) > 0 else min_d
            end_c = date_curr[1] if len(date_curr) == 2 else start_c
            
            df_current = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(start_c.strftime('%Y-%m-%d'), end_c.strftime('%Y-%m-%d')))
            # 【智能实际天数】
            days_current = df_current['统计周期'].nunique() if not df_current.empty else 1
else:
    st.sidebar.info("请在上方上传日结表激活日历功能")

conn.close()

# --- 补充加工逻辑 ---
df_log_cost = get_config_df_from_db("cost_logistics")
df_store_cost = get_config_df_from_db("cost_store")
if not df_current.empty: df_current = merge_cost_data(df_current, df_log_cost, df_store_cost); df_current = merge_category_map(df_current)
if not df_previous.empty: df_previous = merge_cost_data(df_previous, df_log_cost, df_store_cost); df_previous = merge_category_map(df_previous)

# --- 侧边栏进一步筛选 ---
if not df_current.empty: all_stores = sorted(list(df_current['门店名称'].dropna().unique()))
else: all_stores = []

with st.sidebar.expander("🛠️ 深度筛选", expanded=True):
    all_projects = sorted(list(df_current['所属项目'].dropna().unique())) if not df_current.empty else []
    selected_projects = st.multiselect("所属项目", all_projects)
    if selected_projects: filtered_stores = sorted(list(df_current[df_current['所属项目'].isin(selected_projects)]['门店名称'].dropna().unique()))
    else: filtered_stores = all_stores
    selected_stores = st.multiselect("门店筛选", filtered_stores)
    
    all_l1 = sorted([str(x) for x in df_current['一级分类'].dropna().unique()]) if not df_current.empty else []
    selected_l1 = st.multiselect("一级分类", all_l1)
    if selected_l1: available_l2 = sorted([str(x) for x in df_current[df_current['一级分类'].isin(selected_l1)]['二级分类'].dropna().unique()])
    else: available_l2 = sorted([str(x) for x in df_current['二级分类'].dropna().unique()]) if not df_current.empty else []
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

# --- 指标解包 ---
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

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 单品透视搜索")
all_prods = sorted([str(x) for x in df_current['商品名称'].unique() if pd.notna(x)]) if not df_current.empty else []
search_products = st.sidebar.multiselect("输入商品名称", all_prods)

# -----------------------------------------------------------------------------
# 7. 主界面渲染
# -----------------------------------------------------------------------------
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
        label_text = f"{icon} {title}" if icon else title
        st.metric(label_text, f"{prefix}{value}{suffix}", d_str, delta_color="inverse")

st.subheader("📦 核心经营指标")
c1, c2, c3, c4 = st.columns(4)
with c1: metric_card("总销量", int(cur_qty), delta_qty, suffix=" 杯", icon="🛒")
with c2: metric_card("总营收", f"{cur_amt:,.2f}", delta_amt, prefix="¥", icon="💰")
with c3: metric_card("物流毛利率", f"{cur_margin_log:.2f}", delta_margin_log, suffix="%", is_percent=True, icon="🚚")
with c4: metric_card("门店毛利率", f"{cur_margin_store:.2f}", delta_margin_store, suffix="%", is_percent=True, icon="🏪")

st.subheader("🚀 日均效率指标")
c5, c6, c7 = st.columns(3)
with c5: metric_card("日均杯数", f"{cur_daily_qty:.1f}", delta_daily_qty, suffix=" 杯", icon="📅")
with c6: metric_card("日均营收", f"{cur_daily_amt:,.2f}", delta_daily_amt, prefix="¥", icon="💳")
with c7: metric_card("杯单价", f"{cur_cup_price:.2f}", delta_price, prefix="¥", icon="🏷️")

# --- 🎯 组合透视 ---
if search_products:
    st.markdown("---")
    st.markdown(f"### 🎯 搜索透视: {', '.join(search_products)}")
    prod_curr = df_current[df_current['商品名称'].isin(search_products)]
    p_qty, p_amt, p_profit_log, p_profit_store, p_cup_price, p_margin_log, p_margin_store, p_daily_qty, p_daily_amt = calculate_metrics(prod_curr, days_current)
    
    with st.container(border=True):
        cp1, cp2, cp3, cp4 = st.columns(4)
        cp1.metric("选中商品销量", f"{int(p_qty)} 杯")
        cp2.metric("选中商品营收", f"¥{p_amt:,.2f}")
        cp3.metric("物流毛利率", f"{p_margin_log:.2f}%")
        cp4.metric("门店毛利率", f"{p_margin_store:.2f}%")
    
    store_rank = prod_curr.groupby('门店名称', as_index=False)['销售数量'].sum().sort_values('销售数量', ascending=True)
    store_rank['销售数量'] = store_rank['销售数量'].round(2)
    if PLOTLY_AVAILABLE:
        fig_p = px.bar(store_rank, y='门店名称', x='销售数量', orientation='h', text='销售数量', title="各门店选中商品销量分布")
        fig_p.update_traces(marker_color='#6366F1', texttemplate='%{text:,.2f}', textposition='outside')
        fig_p = update_chart_layout(fig_p)
        st.plotly_chart(fig_p, use_container_width=True)

# -----------------------------------------------------------------------------
# 8. 图表展示区域 (精装版)
# -----------------------------------------------------------------------------
st.markdown("---")
c_left, c_right = st.columns(2)
df_chart = df_current.groupby('商品名称', as_index=False).agg({'销售数量':'sum', '销售金额':'sum', '物流毛利':'sum', '门店毛利':'sum'})

with c_left:
    with st.container(border=True):
        st.markdown("##### 🔥 销量排行 (Top 10)")
        top10 = df_chart.sort_values('销售数量', ascending=True).tail(10)
        top10['销售数量'] = top10['销售数量'].round(2)
        if PLOTLY_AVAILABLE:
            fig1 = px.bar(top10, y='商品名称', x='销售数量', orientation='h', text='销售数量')
            fig1.update_traces(marker_color='#3B82F6', texttemplate='%{text:,.2f}', textposition='outside')
            fig1 = update_chart_layout(fig1)
            st.plotly_chart(fig1, use_container_width=True)

with c_right:
    with st.container(border=True):
        st.markdown("##### 🏆 利润贡献排行")
        profit_type = st.radio("请选择分析维度：", ["门店毛利", "物流毛利"], horizontal=True, label_visibility="collapsed")
        target_col = profit_type
        
        t1, t2, t3 = st.tabs(["一级分类", "二级分类", "按单品"])
        total_profit = df_current[target_col].sum()
        with t1:
            if '一级分类' in df_current.columns:
                l1_profit = df_current.groupby('一级分类', as_index=False)[target_col].sum().sort_values(target_col, ascending=True)
                l1_profit[target_col] = l1_profit[target_col].round(2)
                l1_profit['贡献率'] = np.where(total_profit>0, l1_profit[target_col]/total_profit, 0)
                if PLOTLY_AVAILABLE:
                    fig2 = px.bar(l1_profit, y='一级分类', x=target_col, orientation='h', color=target_col, color_continuous_scale='Blues', text=l1_profit['贡献率'].apply(lambda x: f"{x:.2%}"))
                    fig2.update_traces(textposition='outside')
                    fig2 = update_chart_layout(fig2)
                    st.plotly_chart(fig2, use_container_width=True)
        with t2:
            if '二级分类' in df_current.columns:
                l2_profit = df_current.groupby('二级分类', as_index=False)[target_col].sum().sort_values(target_col, ascending=True)
                l2_profit[target_col] = l2_profit[target_col].round(2)
                l2_profit['贡献率'] = np.where(total_profit>0, l2_profit[target_col]/total_profit, 0)
                if PLOTLY_AVAILABLE:
                    fig3 = px.bar(l2_profit, y='二级分类', x=target_col, orientation='h', color=target_col, color_continuous_scale='Teal', text=l2_profit['贡献率'].apply(lambda x: f"{x:.2%}"))
                    fig3.update_traces(textposition='outside')
                    fig3 = update_chart_layout(fig3)
                    st.plotly_chart(fig3, use_container_width=True)
        with t3:
            df_prod_p = df_chart.sort_values(target_col, ascending=True).tail(10)
            df_prod_p[target_col] = df_prod_p[target_col].round(2)
            df_prod_p['贡献率'] = np.where(total_profit>0, df_prod_p[target_col]/total_profit, 0)
            if PLOTLY_AVAILABLE:
                fig4 = px.bar(df_prod_p, y='商品名称', x=target_col, orientation='h', color=target_col, color_continuous_scale='Purp', text=df_prod_p['贡献率'].apply(lambda x: f"{x:.2%}"))
                fig4.update_traces(textposition='outside')
                fig4 = update_chart_layout(fig4)
                st.plotly_chart(fig4, use_container_width=True)

# 品类涨跌瀑布
if is_comparison_mode and not df_previous.empty and '二级分类' in df_current.columns:
    cat_curr = df_current.groupby('二级分类')['销售数量'].sum() / days_current
    cat_prev = df_previous.groupby('二级分类')['销售数量'].sum() / days_previous
    cat_diff = (cat_curr - cat_prev).fillna(0).reset_index()
    cat_diff.columns = ['二级分类', '变动值']
    cat_diff['变动值'] = cat_diff['变动值'].round(2)
    cat_diff = cat_diff.sort_values('变动值')
    cat_diff['颜色'] = np.where(cat_diff['变动值']>=0, '#F43F5E', '#10B981')
    
    with st.container(border=True):
        st.markdown("##### 📈 二级分类日均销量涨跌")
        if PLOTLY_AVAILABLE:
            fig_diff = px.bar(cat_diff, y='二级分类', x='变动值', text='变动值')
            fig_diff.update_traces(marker_color=cat_diff['颜色'], texttemplate='%{text:+.2f}', textposition='outside')
            fig_diff = update_chart_layout(fig_diff)
            st.plotly_chart(fig_diff, use_container_width=True)

# -----------------------------------------------------------------------------
# 9. 智能经营诊断 (AI Insights) 
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🤖 智能经营诊断 (AI Insights)")
with st.container(border=True):
    st.markdown("#### 📋 全门店涨跌龙虎榜")
    tab_s1, tab_s2, tab_s3, tab_s4, tab_s5, tab_s6 = st.tabs([
        "日均杯数", "日均营收", "🚚 日均物流毛利", "🏪 日均门店毛利", "📉 物流毛利率变动", "📉 门店毛利率变动"
    ])
    
    if is_comparison_mode and not df_previous.empty:
        s_curr = df_current.groupby('门店名称').agg({'销售数量':'sum', '销售金额':'sum', '物流毛利':'sum', '门店毛利':'sum'})
        s_curr['日均杯数'] = s_curr['销售数量'] / days_current
        s_curr['日均营收'] = s_curr['销售金额'] / days_current
        s_curr['日均物流毛利'] = s_curr['物流毛利'] / days_current
        s_curr['日均门店毛利'] = s_curr['门店毛利'] / days_current
        s_curr['物流毛利率'] = np.where(s_curr['销售金额']>0, s_curr['物流毛利']/s_curr['销售金额'], 0)
        s_curr['门店毛利率'] = np.where(s_curr['销售金额']>0, s_curr['门店毛利']/s_curr['销售金额'], 0)
        
        s_prev = df_previous.groupby('门店名称').agg({'销售数量':'sum', '销售金额':'sum', '物流毛利':'sum', '门店毛利':'sum'})
        s_prev['日均杯数'] = s_prev['销售数量'] / days_previous
        s_prev['日均营收'] = s_prev['销售金额'] / days_previous
        s_prev['日均物流毛利'] = s_prev['物流毛利'] / days_previous
        s_prev['日均门店毛利'] = s_prev['门店毛利'] / days_previous
        s_prev['物流毛利率'] = np.where(s_prev['销售金额']>0, s_prev['物流毛利']/s_prev['销售金额'], 0)
        s_prev['门店毛利率'] = np.where(s_prev['销售金额']>0, s_prev['门店毛利']/s_prev['销售金额'], 0)
        
        s_merge = pd.DataFrame({
            'curr_qty': s_curr['日均杯数'], 'prev_qty': s_prev['日均杯数'],
            'curr_amt': s_curr['日均营收'], 'prev_amt': s_prev['日均营收'],
            'curr_profit_log': s_curr['日均物流毛利'], 'prev_profit_log': s_prev['日均物流毛利'],
            'curr_profit_store': s_curr['日均门店毛利'], 'prev_profit_store': s_prev['日均门店毛利'],
            'curr_margin_log': s_curr['物流毛利率'], 'prev_margin_log': s_prev['物流毛利率'],
            'curr_margin_store': s_curr['门店毛利率'], 'prev_margin_store': s_prev['门店毛利率']
        }).fillna(0)
        
        s_merge['qty_diff'] = s_merge['curr_qty'] - s_merge['prev_qty']
        s_merge['amt_diff'] = s_merge['curr_amt'] - s_merge['prev_amt']
        s_merge['profit_log_diff'] = s_merge['curr_profit_log'] - s_merge['prev_profit_log']
        s_merge['profit_store_diff'] = s_merge['curr_profit_store'] - s_merge['prev_profit_store']
        s_merge['margin_log_diff'] = s_merge['curr_margin_log'] - s_merge['prev_margin_log']
        s_merge['margin_store_diff'] = s_merge['curr_margin_store'] - s_merge['prev_margin_store']
        
        s_merge['qty_pct'] = np.where(s_merge['prev_qty']>0, s_merge['qty_diff']/s_merge['prev_qty'], 0)
        s_merge['amt_pct'] = np.where(s_merge['prev_amt']>0, s_merge['amt_diff']/s_merge['prev_amt'], 0)
        s_merge['profit_log_pct'] = np.where(s_merge['prev_profit_log']>0, s_merge['profit_log_diff']/s_merge['prev_profit_log'], 0)
        s_merge['profit_store_pct'] = np.where(s_merge['prev_profit_store']>0, s_merge['profit_store_diff']/s_merge['prev_profit_store'], 0)
        
        s_merge = s_merge.round(4)
        def color_change(val): return f'color: {"#F43F5E" if val > 0 else "#10B981" if val < 0 else "#475569"}'

        with tab_s1:
            show_df = s_merge[['curr_qty', 'prev_qty', 'qty_diff', 'qty_pct']].sort_values('qty_pct', ascending=False)
            show_df.columns = ['本期日均', '上期日均', '变动(杯)', '环比']
            st.dataframe(show_df.style.format({'本期日均':'{:.1f}','上期日均':'{:.1f}','变动(杯)':'{:+.1f}','环比':'{:.2%}'}).map(color_change, subset=['变动(杯)','环比']), use_container_width=True, height=400)
        with tab_s2:
            show_df_a = s_merge[['curr_amt', 'prev_amt', 'amt_diff', 'amt_pct']].sort_values('amt_pct', ascending=False)
            show_df_a.columns = ['本期日均', '上期日均', '变动(元)', '环比']
            st.dataframe(show_df_a.style.format({'本期日均':'¥{:.0f}','上期日均':'¥{:.0f}','变动(元)':'{:+.0f}','环比':'{:.2%}'}).map(color_change, subset=['变动(元)','环比']), use_container_width=True, height=400)
        with tab_s3:
            df_log_cost_check = get_config_df_from_db("cost_logistics")
            if df_log_cost_check is not None:
                show_df_p1 = s_merge[['curr_profit_log', 'prev_profit_log', 'profit_log_diff', 'profit_log_pct']].sort_values('profit_log_pct', ascending=False)
                show_df_p1.columns = ['本期日均', '上期日均', '变动(元)', '环比']
                st.dataframe(show_df_p1.style.format({'本期日均':'¥{:.0f}','上期日均':'¥{:.0f}','变动(元)':'{:+.0f}','环比':'{:.2%}'}).map(color_change, subset=['变动(元)','环比']), use_container_width=True, height=400)
            else: st.info("请在左侧上传物流成本档案")
        with tab_s4:
            df_store_cost_check = get_config_df_from_db("cost_store")
            if df_store_cost_check is not None:
                show_df_p2 = s_merge[['curr_profit_store', 'prev_profit_store', 'profit_store_diff', 'profit_store_pct']].sort_values('profit_store_pct', ascending=False)
                show_df_p2.columns = ['本期日均', '上期日均', '变动(元)', '环比']
                st.dataframe(show_df_p2.style.format({'本期日均':'¥{:.0f}','上期日均':'¥{:.0f}','变动(元)':'{:+.0f}','环比':'{:.2%}'}).map(color_change, subset=['变动(元)','环比']), use_container_width=True, height=400)
            else: st.info("请在左侧上传门店成本档案")
        with tab_s5:
            if df_log_cost_check is not None:
                show_df_m1 = s_merge[['curr_margin_log', 'prev_margin_log', 'margin_log_diff']].sort_values('margin_log_diff', ascending=False)
                show_df_m1.columns = ['本期毛利率', '上期毛利率', '变动 (pts)']
                st.dataframe(show_df_m1.style.format({'本期毛利率':'{:.2%}','上期毛利率':'{:.2%}','变动 (pts)':'{:+.2%}'}).map(color_change, subset=['变动 (pts)']), use_container_width=True, height=400)
            else: st.info("请在左侧上传物流成本档案")
        with tab_s6:
            if df_store_cost_check is not None:
                show_df_m2 = s_merge[['curr_margin_store', 'prev_margin_store', 'margin_store_diff']].sort_values('margin_store_diff', ascending=False)
                show_df_m2.columns = ['本期毛利率', '上期毛利率', '变动 (pts)']
                st.dataframe(show_df_m2.style.format({'本期毛利率':'{:.2%}','上期毛利率':'{:.2%}','变动 (pts)':'{:+.2%}'}).map(color_change, subset=['变动 (pts)']), use_container_width=True, height=400)
            else: st.info("请在左侧上传门店成本档案")
    else: st.info("开启环比模式以查看诊断")

# -----------------------------------------------------------------------------
# 9.5 单店深度透视
# -----------------------------------------------------------------------------
if is_comparison_mode and '二级分类' in df_current.columns:
    st.markdown("---")
    st.markdown("### 🏪 单店品类深度透视")
    all_store_list_dd = sorted(df_current['门店名称'].unique().tolist())
    cat_col = '二级分类'
    
    if all_store_list_dd:
        c_sel, _ = st.columns([1, 2])
        with c_sel: selected_store_dd = st.selectbox("👉 选择分析门店", all_store_list_dd)
        
        store_curr = df_current[df_current['门店名称'] == selected_store_dd]
        store_prev = df_previous[df_previous['门店名称'] == selected_store_dd] if not df_previous.empty else pd.DataFrame()
        
        s_day_c = store_curr['销售数量'].sum() / days_current
        s_day_p = (store_prev['销售数量'].sum() / days_previous) if not store_prev.empty else 0
        s_delta = (s_day_c - s_day_p)
        s_pct = (s_delta / s_day_p) if s_day_p > 0 else 0
        
        sc_curr = store_curr.groupby(cat_col, as_index=False)['销售数量'].sum()
        sc_curr['日均'] = sc_curr['销售数量'] / days_current
        if not store_prev.empty:
            sc_prev = store_prev.groupby(cat_col, as_index=False)['销售数量'].sum()
            sc_prev['日均'] = sc_prev['销售数量'] / days_previous
        else: sc_prev = pd.DataFrame(columns=[cat_col, '日均'])
            
        sc_merge = pd.merge(sc_curr, sc_prev, on=cat_col, suffixes=('_curr', '_prev'), how='outer').fillna(0)
        sc_merge['变动'] = sc_merge['日均_curr'] - sc_merge['日均_prev']
        sc_merge['变动'] = sc_merge['变动'].round(2)
        sc_merge = sc_merge.sort_values('变动', ascending=True) 
        
        with st.container(border=True):
            c_s_kpi, c_s_chart = st.columns([1, 2])
            with c_s_kpi:
                st.markdown(f"#### 🏠 {selected_store_dd}")
                st.metric("该店总日均杯数", f"{s_day_c:.1f}", f"{s_delta:+.1f} 杯 ({s_pct:+.1%})", delta_color="inverse")
                st.divider()
                st.markdown(f"**📋 {cat_col}变动详情**")
                
                display_tbl = sc_merge[[cat_col, '变动']].sort_values('变动', ascending=False)
                total_row = pd.DataFrame({cat_col: ['🔴 全店合计'], '变动': [s_delta]})
                display_tbl = pd.concat([total_row, display_tbl], ignore_index=True)
                
                st.dataframe(display_tbl, column_config={cat_col: st.column_config.TextColumn("品类"), "变动": st.column_config.NumberColumn("日均变动", format="%+.2f 杯")}, hide_index=True, use_container_width=True, height=300)
            with c_s_chart:
                st.markdown("**📊 品类涨跌瀑布图**")
                if PLOTLY_AVAILABLE:
                    sc_merge['颜色'] = np.where(sc_merge['变动'] >= 0, '#F43F5E', '#10B981')
                    fig_s = px.bar(sc_merge, y=cat_col, x='变动', text='变动', orientation='h')
                    fig_s.update_traces(marker_color=sc_merge['颜色'], texttemplate='%{text:+.2f}', textposition='outside')
                    fig_s = update_chart_layout(fig_s)
                    st.plotly_chart(fig_s, use_container_width=True)

# -----------------------------------------------------------------------------
# 10. 🎯 门店目标达成看板
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("🎯 门店目标达成看板")

df_target = get_config_df_from_db("target_store")

if df_target is not None and not df_target.empty:
    df_store_stats = df_current.groupby('门店名称', as_index=False).agg({'销售数量':'sum'})
    df_store_stats['日均杯数'] = df_store_stats['销售数量'] / days_current
    df_goal = merge_target_data(df_store_stats, df_target)
    
    if df_goal is not None and '达成率' in df_goal.columns:
        achieved_count = len(df_goal[df_goal['达成状态'] == '✅ 达成'])
        failed_count = len(df_goal[df_goal['达成状态'] == '❌ 未达成'])
        unset_count = len(df_goal[df_goal['达成状态'].str.contains('未设定', na=False)])
        
        valid_stores = achieved_count + failed_count
        achieved_rate = achieved_count / valid_stores if valid_stores > 0 else 0
        
        valid_df = df_goal[df_goal['日均目标'] > 0]
        total_actual_cups = valid_df['日均杯数'].sum()
        total_target_cups = valid_df['日均目标'].sum()
        cup_achieved_rate = total_actual_cups / total_target_cups if total_target_cups > 0 else 0
        
        g1, g2, g3, g4 = st.columns(4)
        with g1: metric_card("✅ 达标门店", f"{achieved_count} 家", None, icon="🎉")
        with g2: metric_card("门店达标率", f"{achieved_rate:.1%}", None, icon="📊")
        with g3: metric_card("总杯数达成率", f"{cup_achieved_rate:.1%}", None, icon="☕")
        with g4: metric_card("❌ 未达标", f"{failed_count} 家", None, icon="⚠️")
        
        with st.expander("🔍 查看未匹配/数据异常的门店", expanded=False):
            st.markdown("##### 1. 销售表中有，但目标表中没有 (或名字不一致)")
            missing_targets = df_goal[df_goal['达成状态'].str.contains('未设定', na=False)]['门店名称'].tolist()
            if missing_targets: st.write(missing_targets)
            else: st.success("所有门店均已匹配到目标！")
            
            st.markdown("##### 2. 目标为 0 或读取失败")
            zero_targets = df_goal[df_goal['日均目标'] == 0]['门店名称'].tolist()
            if zero_targets: st.write(zero_targets)
            else: st.success("没有目标为 0 的门店。")

        df_goal = df_goal.sort_values('达成率', ascending=False)
        df_goal['日均杯数'] = df_goal['日均杯数'].round(1)
        
        def format_gap(row):
            if '未设定' in str(row['达成状态']): return "-"
            gap = row['日均目标'] - row['日均杯数']
            return f"差 {gap:.1f} 杯" if gap > 0 else "🎉 超额"
        df_goal['差距'] = df_goal.apply(format_gap, axis=1)
        
        with st.container(border=True):
            st.dataframe(df_goal[['门店名称', '日均杯数', '日均目标', '达成率', '达成状态', '差距']], column_config={
                "门店名称": st.column_config.TextColumn("门店", width="medium"),
                "日均杯数": st.column_config.NumberColumn("实际日均", format="%.1f 杯"),
                "日均目标": st.column_config.NumberColumn("目标日均", format="%.1f 杯"),
                "达成率": st.column_config.ProgressColumn("达成进度", format="%.1%", min_value=0, max_value=1.5),
                "达成状态": st.column_config.TextColumn("状态", width="small"),
                "差距": st.column_config.TextColumn("距离目标", width="small"),
            }, hide_index=True, use_container_width=True)
else: st.info("请在左侧上传门店目标表以开启达成诊断")

# -----------------------------------------------------------------------------
# 11. 明细表格 
# -----------------------------------------------------------------------------
st.markdown("---")
st.markdown("### 📄 商品经营明细")
agg_dict = {
    '一级分类': 'first', '二级分类': 'first', '所属项目': 'first', 
    '销售数量': 'sum', '销售金额': 'sum', 
    '物流毛利': 'sum', '门店毛利': 'sum'
}
df_view = df_current.groupby('商品名称', as_index=False).agg(agg_dict)
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
df_view['BCG属性'] = df_view.apply(get_bcg, axis=1)

conditions = [(df_view['门店毛利率'] >= 99.9), (df_view['门店毛利率'] < 60), (df_view['门店毛利率'] >= 60) & (df_view['门店毛利率'] <= 65)]
choices = ['⚠️ 缺成本', '🔴 低毛利', '🟡 毛利预警']
df_view['健康度'] = np.select(conditions, choices, default='🟢 健康')

cols = ['序号', '商品名称', 'BCG属性', '健康度', '一级分类', '二级分类', '销售数量', '销售金额', '物流毛利', '物流毛利率', '门店毛利', '门店毛利率', '销售占比']
with st.container(border=True):
    st.dataframe(df_view[cols], column_config={
        "序号": st.column_config.NumberColumn("排名", width="small"),
        "销售数量": st.column_config.ProgressColumn("总销量", format="%d", min_value=0, max_value=int(df_view['销售数量'].max())),
        "销售金额": st.column_config.NumberColumn("营收", format="¥%.2f"),
        "物流毛利": st.column_config.NumberColumn("物流毛利", format="¥%.2f"),
        "物流毛利率": st.column_config.NumberColumn("物流毛利率", format="%.2f%%"),
        "门店毛利": st.column_config.NumberColumn("门店毛利", format="¥%.2f"),
        "门店毛利率": st.column_config.NumberColumn("门店毛利率", format="%.2f%%"),
        "销售占比": st.column_config.NumberColumn("营收占比", format="%.2f%%"),
    }, use_container_width=True, hide_index=True)
