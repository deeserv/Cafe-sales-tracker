# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import math
import glob
import re

# -----------------------------------------------------------------------------
# 1. 核心配置与 CSS 注入
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="顿角咖啡智能数据看板",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === 🔐 安全登录系统 ===
def check_password():
    """检查密码是否正确"""
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

# 注入自定义 CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
    img { border-radius: 12px; transition: transform 0.3s ease; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E2E8F0; }
    h1 { color: #0F172A; font-weight: 800; letter-spacing: -0.03em; }
    h3 { color: #334155; font-weight: 600; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; border-radius: 16px; border: 1px solid #F1F5F9;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); padding: 24px; transition: all 0.3s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        transform: translateY(-2px); box-shadow: 0 12px 20px -5px rgba(0, 0, 0, 0.1); border-color: #E2E8F0;
    }
    [data-testid="stMetricValue"] {
        font-size: 36px !important;
        background: -webkit-linear-gradient(120deg, #2563EB, #06B6D4);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #FFFFFF; padding: 8px; border-radius: 12px; }
    .stTabs [data-baseweb="tab"] { height: 44px; border-radius: 8px; border: none; color: #64748B; font-weight: 600; background-color: #F8FAFC; }
    .stTabs [aria-selected="true"] { background-color: #EFF6FF; color: #2563EB; }
    div[data-testid="stMultiSelect"] label { font-weight: bold; color: #2563EB; }
    
    .insight-card { padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; font-size: 14px; display: flex; justify-content: space-between; align-items: center; }
    .insight-red { background-color: #FEF2F2; border-left: 4px solid #EF4444; color: #991B1B; }
    .insight-green { background-color: #F0FDF4; border-left: 4px solid #10B981; color: #065F46; }
    .insight-value-red { color: #EF4444; font-weight: bold; }
    .insight-value-green { color: #10B981; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# 尝试导入 Plotly
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

COLOR_PALETTE = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

# -----------------------------------------------------------------------------
# 2. 内置数据字典
# -----------------------------------------------------------------------------
CATEGORY_MAPPING_DATA = [
    # 咖啡
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "咖啡饮品", "二级分类": "奶咖家族"},
    {"一级分类": "咖啡饮品", "二级分类": "果C美式"},
    {"一级分类": "咖啡饮品", "二级分类": "手冲咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "优选咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "经典意式"},
    {"一级分类": "咖啡饮品", "二级分类": "甄选咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "soe冷萃"},
    {"一级分类": "咖啡饮品", "二级分类": "SOE冷萃"}, 
    {"一级分类": "咖啡饮品", "二级分类": "风味拿铁"},
    {"一级分类": "咖啡饮品", "二级分类": "冰爽果咖"},
    {"一级分类": "咖啡饮品", "二级分类": "中式茶咖"},
    # 非咖啡
    {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"},
    {"一级分类": "非咖啡饮品", "二级分类": "经典鲜果茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "手打柠"},
    {"一级分类": "非咖啡饮品", "二级分类": "清爽果茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "新鲜果蔬汁"},
    {"一级分类": "非咖啡饮品", "二级分类": "不喝咖啡"},
    {"一级分类": "非咖啡饮品", "二级分类": "果茶系列"},
    {"一级分类": "非咖啡饮品", "二级分类": "抹茶家族"},
    {"一级分类": "非咖啡饮品", "二级分类": "柠檬茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "原叶鲜奶茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "经典果茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "经典奶茶"},
]

PROJECT_STORE_MAPPING = {
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"],
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "腾讯项目": ["北京总部image"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"]
}

# -----------------------------------------------------------------------------
# 3. 本地仓库
# -----------------------------------------------------------------------------
DATA_DIR = "data_storage"
LOGISTICS_COST_FILE_NAME = "logistics_cost_data.xlsx"
STORE_COST_FILE_NAME = "store_cost_data.xlsx"
TARGET_FILE_NAME = "target_data.xlsx"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def save_uploaded_file(uploaded_file, file_type="sales"):
    if uploaded_file is None: return None
    if file_type == "logistics_cost": file_path = os.path.join(DATA_DIR, LOGISTICS_COST_FILE_NAME)
    elif file_type == "store_cost": file_path = os.path.join(DATA_DIR, STORE_COST_FILE_NAME)
    elif file_type == "target": file_path = os.path.join(DATA_DIR, TARGET_FILE_NAME)
    else: file_path = os.path.join(DATA_DIR, uploaded_file.name)
    with open(file_path, "wb") as f: f.write(uploaded_file.getbuffer())
    return file_path

def get_saved_sales_files():
    files = glob.glob(os.path.join(DATA_DIR, "*"))
    exclude = [LOGISTICS_COST_FILE_NAME, STORE_COST_FILE_NAME, TARGET_FILE_NAME]
    sales = [f for f in files if os.path.basename(f) not in exclude and (f.endswith('.csv') or f.endswith('.xlsx') or f.endswith('.xls'))]
    sales.sort()
    return sales

def get_saved_config_file(file_name):
    path = os.path.join(DATA_DIR, file_name)
    return path if os.path.exists(path) else None

# -----------------------------------------------------------------------------
# 4. 数据处理 (核心清洗逻辑增强)
# -----------------------------------------------------------------------------
def clean_store_name(name):
    """强力清洗门店名称：去空格、统一括号"""
    if pd.isna(name): return ""
    name = str(name).strip()
    name = name.replace(" ", "") # 去除中间空格
    name = name.replace("(", "（").replace(")", "）") # 英文括号转中文
    return name

def load_data_from_path(file_path):
    if not file_path: return None
    try:
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            try: return pd.read_excel(file_path, engine='openpyxl')
            except ImportError:
                st.error("❌ 缺少 `openpyxl` 库"); return None
        else:
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb18030']
            for enc in encodings:
                try: return pd.read_csv(file_path, encoding=enc)
                except: continue
    except Exception as e: st.error(f"读取错误: {e}")
    return None

def process_sales_dataframe(df_sales, file_name=""):
    if df_sales is None: return None
    
    # 1. 强力清洗列名 (防止列名带有空格导致无法识别)
    df_sales.columns = [str(c).strip() for c in df_sales.columns]
    
    column_mapping = {'商品实收': '销售金额', '商品销量': '销售数量'}
    df_sales = df_sales.rename(columns=column_mapping)
    
    # 2. 剔除合计行
    if '商品名称' in df_sales.columns:
        df_sales = df_sales[~df_sales['商品名称'].astype(str).str.contains("合计|总计|Total", na=False)]
        df_sales = df_sales.dropna(subset=['商品名称'])
    if '门店名称' in df_sales.columns:
        df_sales = df_sales[~df_sales['门店名称'].astype(str).str.contains("合计|总计", na=False)]
        df_sales = df_sales.dropna(subset=['门店名称'])
        df_sales['门店名称'] = df_sales['门店名称'].apply(clean_store_name)

    # 3. 基础字符串清洗
    cols = ['商品名称', '商品类别']
    for c in cols: 
        if c in df_sales.columns: df_sales[c] = df_sales[c].astype(str).str.strip()

    # 4. 统计周期智能解析与兜底 (核心修复点)
    if '统计周期' not in df_sales.columns and file_name:
        # 如果根本没有这一列，使用文件名作为周期名 (例如: W6.xlsx -> W6)
        base_name = os.path.splitext(file_name)[0]
        df_sales['统计周期'] = base_name
        
    if '统计周期' in df_sales.columns:
        df_sales['统计周期'] = df_sales['统计周期'].astype(str).str.strip()
        df_sales['统计周期'] = df_sales['统计周期'].replace(['nan', 'NaN', 'None', ''], np.nan).ffill()
        # 如果填补后还是有空值，再次使用文件名兜底
        if file_name:
            df_sales['统计周期'] = df_sales['统计周期'].fillna(os.path.splitext(file_name)[0])

    if '门店名称' in df_sales.columns: df_sales['门店名称'] = df_sales['门店名称'].ffill()
    
    for c in ['销售金额', '销售数量']:
        if c in df_sales.columns:
            df_sales[c] = pd.to_numeric(df_sales[c].astype(str).str.replace(r'[¥$,￥]', '', regex=True), errors='coerce').fillna(0)
    return df_sales

def merge_category_map(df_sales):
    if df_sales is None: return None
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
    else:
        df_sales['所属项目'] = '未知'
    return df_sales

def merge_cost_data(df_sales, df_logistics_cost, df_store_cost):
    if df_sales is None: return None
    
    df_sales['物流成本'] = 0
    df_sales['门店成本'] = 0
    
    # 1. 处理物流成本
    if df_logistics_cost is not None:
        if '产品' in df_logistics_cost.columns: df_logistics_cost = df_logistics_cost.rename(columns={'产品': '商品名称'})
        if '商品名称' in df_logistics_cost.columns and '成本' in df_logistics_cost.columns:
            df_logistics_cost['商品名称'] = df_logistics_cost['商品名称'].astype(str).str.strip()
            df_logistics_cost['成本'] = pd.to_numeric(df_logistics_cost['成本'], errors='coerce').fillna(0)
            df_log_uniq = df_logistics_cost.groupby('商品名称', as_index=False)['成本'].mean().rename(columns={'成本': '物流成本_表'})
            df_sales = pd.merge(df_sales, df_log_uniq[['商品名称', '物流成本_表']], on='商品名称', how='left')
            df_sales['物流成本'] = df_sales['物流成本_表'].fillna(0)
            df_sales = df_sales.drop(columns=['物流成本_表'], errors='ignore')

    # 2. 处理门店成本
    if df_store_cost is not None:
        if '产品' in df_store_cost.columns: df_store_cost = df_store_cost.rename(columns={'产品': '商品名称'})
        if '商品名称' in df_store_cost.columns and '成本' in df_store_cost.columns:
            df_store_cost['商品名称'] = df_store_cost['商品名称'].astype(str).str.strip()
            df_store_cost['成本'] = pd.to_numeric(df_store_cost['成本'], errors='coerce').fillna(0)
            df_store_uniq = df_store_cost.groupby('商品名称', as_index=False)['成本'].mean().rename(columns={'成本': '门店成本_表'})
            df_sales = pd.merge(df_sales, df_store_uniq[['商品名称', '门店成本_表']], on='商品名称', how='left')
            df_sales['门店成本'] = df_sales['门店成本_表'].fillna(0)
            df_sales = df_sales.drop(columns=['门店成本_表'], errors='ignore')

    # 3. 计算双毛利
    df_sales['物流毛利'] = df_sales['销售金额'] - (df_sales['销售数量'] * df_sales['物流成本'])
    df_sales['门店毛利'] = df_sales['销售金额'] - (df_sales['销售数量'] * df_sales['门店成本'])
    
    return df_sales

def merge_target_data(df_store_stats, df_target):
    if df_store_stats is None or df_store_stats.empty: return df_store_stats
    
    if df_target is None:
        df_store_stats['日均目标'] = 0
        df_store_stats['达成率'] = 0
        df_store_stats['达成状态'] = '⚪ 未设定'
        return df_store_stats
        
    sample_store = df_store_stats['门店名称'].iloc[0] if not df_store_stats.empty else ""
    is_horizontal = False
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
        if val_col not in df_target.columns and len(df_target.columns) >= 2:
            val_col = df_target.columns[1]
            
        if val_col in df_target.columns:
            df_target['日均目标'] = pd.to_numeric(df_target[val_col], errors='coerce').fillna(0)
            df_target = df_target.groupby('门店名称', as_index=False)['日均目标'].max()
            
            df_merged = pd.merge(df_store_stats, df_target, on='门店名称', how='left')
            df_merged['日均目标'] = df_merged['日均目标'].fillna(0)
            
            def get_status(row):
                target = row['日均目标']
                actual = row['日均杯数']
                if target <= 0.1: return '⚪ 未设定'
                elif actual >= target: return '✅ 达成'
                else: return '❌ 未达成'
            
            df_merged['达成状态'] = df_merged.apply(get_status, axis=1)
            df_merged['达成率'] = np.where(df_merged['日均目标']>0, df_merged['日均杯数']/df_merged['日均目标'], 0)
            return df_merged

    df_store_stats['日均目标'] = 0
    df_store_stats['达成率'] = 0
    df_store_stats['达成状态'] = '⚪ 未设定 (格式错误)'
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

with st.sidebar.expander("💾 数据仓库管理", expanded=True):
    # --- 物流成本 ---
    st.markdown("**🚚 物流成本档案**")
    saved_logistics_path = get_saved_config_file(LOGISTICS_COST_FILE_NAME)
    if saved_logistics_path:
        st.success("✅ 已有存档")
        if st.checkbox("更新物流成本?", key="log_check"):
            new_log_cost = st.file_uploader("上传新物流成本表", type=["xlsx", "csv"], key="log_up")
            if new_log_cost: save_uploaded_file(new_log_cost, "logistics_cost"); st.rerun()
    else:
        new_log_cost = st.file_uploader("请上传物流成本表", type=["xlsx", "csv"], key="log_up")
        if new_log_cost: save_uploaded_file(new_log_cost, "logistics_cost"); st.rerun()

    st.divider()
    
    # --- 门店成本 ---
    st.markdown("**🏪 门店成本档案**")
    saved_store_path = get_saved_config_file(STORE_COST_FILE_NAME)
    if saved_store_path:
        st.success("✅ 已有存档")
        if st.checkbox("更新门店成本?", key="store_check"):
            new_store_cost = st.file_uploader("上传新门店成本表", type=["xlsx", "csv"], key="store_up")
            if new_store_cost: save_uploaded_file(new_store_cost, "store_cost"); st.rerun()
    else:
        new_store_cost = st.file_uploader("请上传门店成本表", type=["xlsx", "csv"], key="store_up")
        if new_store_cost: save_uploaded_file(new_store_cost, "store_cost"); st.rerun()
            
    st.divider()
    
    # --- 目标表 ---
    st.markdown("**🎯 门店目标表 (横向/纵向)**")
    saved_target_path = get_saved_config_file(TARGET_FILE_NAME)
    if saved_target_path:
        st.success("✅ 已有存档")
        if st.checkbox("更新目标表?"):
            new_target = st.file_uploader("上传目标表", type=["xlsx", "csv"])
            if new_target: save_uploaded_file(new_target, "target"); st.rerun()
    else:
        st.warning("⚠️ 暂无")
        new_target = st.file_uploader("请上传目标表", type=["xlsx", "csv"])
        if new_target: save_uploaded_file(new_target, "target"); st.rerun()

    st.divider()
    st.markdown("**📤 上传销售数据**")
    new_sales = st.file_uploader("支持多选上传", type=["xlsx", "csv"], accept_multiple_files=True)
    if new_sales:
        for f in new_sales: save_uploaded_file(f, "sales")
        st.success(f"已存入 {len(new_sales)} 个文件!"); st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📂 选择分析数据")
saved_sales_files = get_saved_sales_files()

if not saved_sales_files:
    st.sidebar.warning("仓库为空，请先在上方上传数据。")
    df_final = None
else:
    file_names = [os.path.basename(f) for f in saved_sales_files]
    selected_files = st.sidebar.multiselect("请勾选要分析的历史文件", file_names, default=file_names)
    
    if selected_files:
        all_dfs = []
        for fname in selected_files:
            fpath = os.path.join(DATA_DIR, fname)
            df = load_data_from_path(fpath)
            if df is not None:
                df = process_sales_dataframe(df, file_name=fname)
                all_dfs.append(df)
        
        if all_dfs:
            df_sales_merged = pd.concat(all_dfs, ignore_index=True)
            # 加载双成本
            df_log_cost = load_data_from_path(saved_logistics_path) if saved_logistics_path else None
            df_store_cost = load_data_from_path(saved_store_path) if saved_store_path else None
            
            df_sales_merged = merge_cost_data(df_sales_merged, df_log_cost, df_store_cost)
            df_final = merge_category_map(df_sales_merged)
            st.sidebar.success(f"已加载 {len(selected_files)} 个周期数据")
        else: df_final = None
    else: df_final = None

if df_final is None:
    st.markdown("<div style='text-align:center;padding:100px;'><h1>👋 欢迎回来</h1><p>请在左侧上传或勾选数据。</p></div>", unsafe_allow_html=True)
    st.stop()

# -----------------------------------------------------------------------------
# 6. 核心筛选
# -----------------------------------------------------------------------------
if '统计周期' in df_final.columns: available_periods = sorted(list(df_final['统计周期'].dropna().unique()))
else: available_periods = []
df_current = pd.DataFrame(); df_previous = pd.DataFrame()
is_comparison_mode = False
days_current = 5; days_previous = 5
if '门店名称' in df_final.columns: all_stores = sorted(list(df_final['门店名称'].dropna().unique()))
else: all_stores = []

with st.sidebar.expander("🛠️ 筛选与参数", expanded=True):
    # 项目
    all_projects = sorted(list(df_final['所属项目'].dropna().unique()))
    selected_projects = st.multiselect("所属项目", all_projects)
    if selected_projects:
        filtered_stores = sorted(list(df_final[df_final['所属项目'].isin(selected_projects)]['门店名称'].dropna().unique()))
    else: filtered_stores = all_stores
    
    # 门店
    selected_stores = st.multiselect("门店筛选", filtered_stores)
    
    # 品类
    all_l1 = sorted([str(x) for x in df_final['一级分类'].dropna().unique()])
    selected_l1 = st.multiselect("一级分类", all_l1)
    if selected_l1:
        available_l2 = sorted([str(x) for x in df_final[df_final['一级分类'].isin(selected_l1)]['二级分类'].dropna().unique()])
    else: available_l2 = sorted([str(x) for x in df_final['二级分类'].dropna().unique()])
    selected_l2 = st.multiselect("二级分类", available_l2)
    
    st.divider()
    if len(available_periods) >= 2:
        enable_comparison = st.checkbox("开启环比分析", value=True)
        if enable_comparison:
            is_comparison_mode = True
            # 增加 key 锁定状态
            p_current = st.selectbox("本期", available_periods, index=len(available_periods)-1, key="period_current")
            
            # 安全降级，防止报错
            if p_current not in available_periods: p_current = available_periods[-1]
                
            prev_options = [p for p in available_periods if p != p_current]
            if not prev_options: prev_options = available_periods
            p_previous = st.selectbox("上期 (对比)", prev_options, index=0, key="period_previous")
            
            c1_day, c2_day = st.columns(2)
            days_current = c1_day.number_input("本期天数", 1, 31, 5)
            days_previous = c2_day.number_input("上期天数", 1, 31, 5)
            df_current = df_final[df_final['统计周期'] == p_current].copy()
            df_previous = df_final[df_final['统计周期'] == p_previous].copy()
        else:
            selected_periods = st.multiselect("周期选择", available_periods, default=available_periods)
            days_current = st.number_input("营业天数", 1, 31, 5)
            df_current = df_final[df_final['统计周期'].isin(selected_periods)].copy()
    else:
        days_current = st.number_input("营业天数", 1, 31, 5)
        df_current = df_final.copy()

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
st.sidebar.subheader("🔍 商品/组合搜索")
all_prods = sorted([str(x) for x in df_current['商品名称'].unique() if pd.notna(x)])
search_products = st.sidebar.multiselect("搜索商品", all_prods)

# -----------------------------------------------------------------------------
# 7. 主界面
# -----------------------------------------------------------------------------
st.image("https://images.unsplash.com/photo-1497935586351-b67a49e012bf?auto=format&fit=crop&w=1200&h=250&q=80", use_container_width=True)
c_title, c_period = st.columns([2, 1])
with c_title: st.title("📊 顿角咖啡智能数据看板")
with c_period:
    if is_comparison_mode:
        st.markdown(f"<div style='text-align:right; padding-top:10px; color:#64748B;'><b>分析周期</b><br><span style='color:#3B82F6; font-size:1.1em'>{p_current}</span> vs <span style='color:#94A3B8'>{p_previous}</span></div>", unsafe_allow_html=True)
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
# --- 展示双毛利 ---
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

def update_chart_layout(fig):
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_family="Inter", font_color="#4B5563", margin=dict(l=20, r=20, t=40, b=20))
    return fig

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
        fig_p.update_traces(texttemplate='%{text:,.2f}', textposition='outside', marker_color='#3B82F6')
        fig_p = update_chart_layout(fig_p)
        st.plotly_chart(fig_p, use_container_width=True)

# --- 图表区域 ---
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
            fig1.update_traces(texttemplate='%{text:,.2f}', textposition='outside', marker_color='#10B981')
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
                    fig2 = px.bar(l1_profit, y='一级分类', x=target_col, orientation='h', color=target_col, color_continuous_scale='Mint', text=l1_profit['贡献率'].apply(lambda x: f"{x:.2%}"))
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
                fig4 = px.bar(df_prod_p, y='商品名称', x=target_col, orientation='h', color=target_col, color_continuous_scale='Oranges', text=df_prod_p['贡献率'].apply(lambda x: f"{x:.2%}"))
                fig4.update_traces(textposition='outside')
                fig4 = update_chart_layout(fig4)
                st.plotly_chart(fig4, use_container_width=True)

# 品类涨跌
if is_comparison_mode and not df_previous.empty and '二级分类' in df_current.columns:
    cat_curr = df_current.groupby('二级分类')['销售数量'].sum() / days_current
    cat_prev = df_previous.groupby('二级分类')['销售数量'].sum() / days_previous
    cat_diff = (cat_curr - cat_prev).fillna(0).reset_index()
    cat_diff.columns = ['二级分类', '变动值']
    cat_diff['变动值'] = cat_diff['变动值'].round(2)
    cat_diff = cat_diff.sort_values('变动值')
    cat_diff['颜色'] = np.where(cat_diff['变动值']>=0, '#EF4444', '#10B981')
    
    with st.container(border=True):
        st.markdown("##### 📈 二级分类日均销量涨跌")
        if PLOTLY_AVAILABLE:
            fig_diff = px.bar(cat_diff, y='二级分类', x='变动值', text='变动值')
            fig_diff.update_traces(marker_color=cat_diff['颜色'], texttemplate='%{text:+.2f}')
            fig_diff = update_chart_layout(fig_diff)
            st.plotly_chart(fig_diff, use_container_width=True)

# --- AI 诊断 (全量榜单) ---
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
        def color_change(val): return f'color: {"#EF4444" if val > 0 else "#10B981" if val < 0 else "black"}'

        with tab_s1:
            show_df = s_merge[['curr_qty', 'prev_qty', 'qty_diff', 'qty_pct']].sort_values('qty_pct', ascending=False)
            show_df.columns = ['本期日均', '上期日均', '变动(杯)', '环比']
            st.dataframe(show_df.style.format({'本期日均':'{:.1f}','上期日均':'{:.1f}','变动(杯)':'{:+.1f}','环比':'{:.2%}'}).map(color_change, subset=['变动(杯)','环比']), use_container_width=True, height=400)
        with tab_s2:
            show_df_a = s_merge[['curr_amt', 'prev_amt', 'amt_diff', 'amt_pct']].sort_values('amt_pct', ascending=False)
            show_df_a.columns = ['本期日均', '上期日均', '变动(元)', '环比']
            st.dataframe(show_df_a.style.format({'本期日均':'¥{:.0f}','上期日均':'¥{:.0f}','变动(元)':'{:+.0f}','环比':'{:.2%}'}).map(color_change, subset=['变动(元)','环比']), use_container_width=True, height=400)
        with tab_s3:
            if saved_logistics_path:
                show_df_p1 = s_merge[['curr_profit_log', 'prev_profit_log', 'profit_log_diff', 'profit_log_pct']].sort_values('profit_log_pct', ascending=False)
                show_df_p1.columns = ['本期日均', '上期日均', '变动(元)', '环比']
                st.dataframe(show_df_p1.style.format({'本期日均':'¥{:.0f}','上期日均':'¥{:.0f}','变动(元)':'{:+.0f}','环比':'{:.2%}'}).map(color_change, subset=['变动(元)','环比']), use_container_width=True, height=400)
            else: st.info("请上传物流成本档案")
        with tab_s4:
            if saved_store_path:
                show_df_p2 = s_merge[['curr_profit_store', 'prev_profit_store', 'profit_store_diff', 'profit_store_pct']].sort_values('profit_store_pct', ascending=False)
                show_df_p2.columns = ['本期日均', '上期日均', '变动(元)', '环比']
                st.dataframe(show_df_p2.style.format({'本期日均':'¥{:.0f}','上期日均':'¥{:.0f}','变动(元)':'{:+.0f}','环比':'{:.2%}'}).map(color_change, subset=['变动(元)','环比']), use_container_width=True, height=400)
            else: st.info("请上传门店成本档案")
        with tab_s5:
            if saved_logistics_path:
                show_df_m1 = s_merge[['curr_margin_log', 'prev_margin_log', 'margin_log_diff']].sort_values('margin_log_diff', ascending=False)
                show_df_m1.columns = ['本期毛利率', '上期毛利率', '变动 (pts)']
                st.dataframe(show_df_m1.style.format({'本期毛利率':'{:.2%}','上期毛利率':'{:.2%}','变动 (pts)':'{:+.2%}'}).map(color_change, subset=['变动 (pts)']), use_container_width=True, height=400)
            else: st.info("请上传物流成本档案")
        with tab_s6:
            if saved_store_path:
                show_df_m2 = s_merge[['curr_margin_store', 'prev_margin_store', 'margin_store_diff']].sort_values('margin_store_diff', ascending=False)
                show_df_m2.columns = ['本期毛利率', '上期毛利率', '变动 (pts)']
                st.dataframe(show_df_m2.style.format({'本期毛利率':'{:.2%}','上期毛利率':'{:.2%}','变动 (pts)':'{:+.2%}'}).map(color_change, subset=['变动 (pts)']), use_container_width=True, height=400)
            else: st.info("请上传门店成本档案")
    else: st.info("开启环比模式以查看诊断")

# --- 目标达成看板 ---
st.markdown("---")
st.subheader("🎯 门店目标达成看板")

if saved_target_path:
    df_store_stats = df_current.groupby('门店名称', as_index=False).agg({'销售数量':'sum'})
    df_store_stats['日均杯数'] = df_store_stats['销售数量'] / days_current
    df_target = load_data_from_path(saved_target_path)
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
else: st.info("请上传门店目标表")

# --- 明细表格 (双毛利体系) ---
st.markdown("---")
st.markdown("### 📄 商品经营明细")
# 聚合字典增加物流和门店毛利
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

# BCG 默认基于“门店毛利率”计算
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
