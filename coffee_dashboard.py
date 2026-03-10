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
    .recipe-card-header { background: #F1F5F9; padding: 12px 15px; border-radius: 10px; margin-bottom: 15px; border-left: 5px solid #3B82F6; }
    .cost-tag { background: #DBEAFE; color: #1E40AF; padding: 4px 10px; border-radius: 6px; font-size: 14px; font-weight: 700; margin-right: 10px; display: inline-block; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

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
    
    # ✅ 强力清洗补丁：修复数据库里可能存在的 "0" 或 "None" 乱象
    cursor.execute("UPDATE sales_raw SET 规格 = '常规' WHERE 规格 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE sales_raw SET 做法 = '常规' WHERE 做法 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE bom_recipes SET 规格 = '常规' WHERE 规格 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE bom_recipes SET 做法 = '常规' WHERE 做法 IN ('0', 'nan', 'None', '', 'NaN')")
    conn.commit(); conn.close()

init_db()

# -----------------------------------------------------------------------------
# 4. ETL 引擎
# -----------------------------------------------------------------------------
def standardize_date(val, f_name):
    try: return pd.to_datetime(val).strftime('%Y-%m-%d')
    except:
        match = re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{8}', f_name)
        if match: return pd.to_datetime(match.group()).strftime('%Y-%m-%d')
        return datetime.now().strftime('%Y-%m-%d')

def ingest_sales_data(uploaded_files):
    conn = get_db_conn()
    for f in uploaded_files:
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
        df['门店名称'] = df['门店名称'].apply(lambda x: str(x).strip().replace(" ", "")).ffill()
        df['source_file'] = f.name
        df[['门店名称', '商品名称', '商品类别', '规格', '做法', '统计周期', '销售金额', '销售数量', 'source_file']].to_sql('sales_raw', conn, if_exists='append', index=False)
    conn.close()

def merge_category_map(df):
    if df.empty: return df
    df_cat = pd.DataFrame(CATEGORY_MAPPING_DATA)
    df = pd.merge(df, df_cat, left_on='商品类别', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('未分类')
    s2p = {clean_store_name(s): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(clean_store_name(x), '其他项目'))
    return df

def clean_store_name(n): return str(n).strip().replace(" ", "").replace("(", "（").replace(")", "）")

def merge_dynamic_cost_data(df):
    if df.empty: return df
    conn = get_db_conn()
    df_b = pd.read_sql("SELECT * FROM bom_recipes", conn)
    df_r = pd.read_sql("SELECT * FROM raw_materials", conn)
    conn.close()
    df['物流单位成本'] = df['门店单位成本'] = 0.0
    if not df_b.empty and not df_r.empty:
        m = df_b.merge(df_r, on='物料名称', how='left').fillna(0)
        m['c_log'] = m['用量'] * m['物流单价']
        m['c_dj'] = m['用量'] * m['顿角单价']
        m['c_bd'] = m['用量'] * m['百度单价']
        g = m.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'], as_index=False)[['c_log', 'c_dj', 'c_bd']].sum()
        # 匹配物流
        l_bom = g[g['配方类型'] == '物流'][['商品名称', '规格', '做法', 'c_log']].rename(columns={'c_log': 'lc'})
        df = df.merge(l_bom, on=['商品名称', '规格', '做法'], how='left')
        df['物流单位成本'] = df['lc'].fillna(0.0)
        # 匹配门店 (专属 > 项目 > 全局)
        s_bom = g[g['配方类型'] == '门店']
        df = df.merge(s_bom[s_bom['适用范围'].isin(df['门店名称'].unique())].rename(columns={'适用范围':'门店名称','c_dj':'sdj','c_bd':'sbd'})[['门店名称','商品名称','规格','做法','sdj','sbd']], on=['门店名称','商品名称','规格','做法'], how='left')
        df = df.merge(s_bom[s_bom['适用范围'].str.contains('项目')].rename(columns={'适用范围':'所属项目','c_dj':'pdj','c_bd':'pbd'})[['所属项目','商品名称','规格','做法','pdj','pbd']], on=['所属项目','商品名称','规格','做法'], how='left')
        df = df.merge(s_bom[s_bom['适用范围'] == '【全局默认配方】'].rename(columns={'c_dj':'gdj','c_bd':'gbd'})[['商品名称','规格','做法','gdj','gbd']], on=['商品名称','规格','做法'], how='left')
        df['m_bd'] = df['sbd'].fillna(df['pbd']).fillna(df['gbd']).fillna(0.0)
        df['m_dj'] = df['sdj'].fillna(df['pdj']).fillna(df['gdj']).fillna(0.0)
        df['门店单位成本'] = np.where(df['所属项目'] == '百度项目', df['m_bd'], df['m_dj'])
    df['门店毛利'] = df['销售金额'] - (df['销售数量'] * df['门店单位成本'])
    df['物流毛利'] = df['销售金额'] - (df['销售数量'] * df['物流单位成本'])
    return df

# -----------------------------------------------------------------------------
# 5. UI 逻辑
# -----------------------------------------------------------------------------
app_mode = st.sidebar.radio("🧭 系统导航", ["📊 经营分析看板", "⚙️ 成本与配方中心"])

if app_mode == "📊 经营分析看板":
    with st.sidebar.expander("💾 数据管理", expanded=False):
        conn = get_db_conn()
        total_rows = pd.read_sql("SELECT COUNT(*) as c FROM sales_raw", conn).iloc[0]['c']
        available_periods = sorted(pd.read_sql("SELECT DISTINCT 统计周期 FROM sales_raw", conn)['统计周期'].tolist())
        conn.close()
        st.markdown(f"已存 **{total_rows:,}** 条记录")
        files = st.file_uploader("📥 导入企迈报表", type=["xlsx", "csv"], accept_multiple_files=True)
        if files: ingest_sales_data(files); st.rerun()
        if st.button("🗑️ 清空销售流水", use_container_width=True):
            c = get_db_conn(); c.execute("DELETE FROM sales_raw"); c.commit(); c.close(); st.rerun()

    if total_rows == 0: st.info("请先导入数据。"); st.stop()
    
    st.sidebar.markdown("---")
    parsed_dates = [datetime.strptime(p, '%Y-%m-%d').date() for p in available_periods if p]
    if parsed_dates:
        sel_range = st.sidebar.date_input("分析日期范围", [min(parsed_dates), max(parsed_dates)])
        if len(sel_range) == 2:
            s, e = sel_range
            conn = get_db_conn()
            df = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(s.strftime('%Y-%m-%d'), e.strftime('%Y-%m-%d')))
            conn.close()
            if not df.empty:
                df = merge_category_map(df); df = merge_dynamic_cost_data(df)
                st.title("📊 顿角咖啡经营看板")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("销量", f"{int(df['销售数量'].sum())} 杯")
                c2.metric("营收", f"¥{df['销售金额'].sum():,.2f}")
                c3.metric("出厂毛利", f"{(df['物流毛利'].sum()/df['销售金额'].sum()*100):.2f}%" if df['销售金额'].sum()>0 else "0%")
                c4.metric("门店毛利", f"{(df['门店毛利'].sum()/df['销售金额'].sum()*100):.2f}%" if df['销售金额'].sum()>0 else "0%")
                
                st.markdown("### 📄 单品销售明细")
                df['wl'] = df['销售数量'] * df['物流单位成本']
                df['ws'] = df['销售数量'] * df['门店单位成本']
                v = df.groupby('商品名称', as_index=False).agg({'销售数量':'sum','销售金额':'sum','wl':'sum','ws':'sum','门店毛利':'sum'})
                v['门店单位'] = v['ws']/v['销售数量']
                v['毛利率'] = (v['门店毛利']/v['销售金额']*100).fillna(0)
                st.dataframe(v[['商品名称','销售数量','销售金额','门店单位','毛利率']], use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# ⚙️ 成本配方中心
# -----------------------------------------------------------------------------
elif app_mode == "⚙️ 成本与配方中心":
    st.title("⚙️ 三级原物料与配方引擎")
    t1, t2, t3 = st.tabs(["📦 第一步：基础原物料库", "📋 第二步：配置单品成本卡", "📚 第三步：成本卡总览与删除"])
    
    with t1:
        f = st.file_uploader("上传原物料价格档", type=["xlsx", "csv"])
        if f:
            df = load_data_from_buffer(f)
            if df is not None:
                df.columns = [str(c).strip() for c in df.columns]
                ex = {'物流名称': '物料名称', '品项类别': '品项类别', '单价单位': '单位', '物流单价成本': '物流单价', '顿角单价成本': '顿角单价', '百度单价成本': '百度单价'}
                df = df.rename(columns={c: ex[c] for c in df.columns if c in ex})
                if '物料名称' in df.columns:
                    for p in ['物流单价', '顿角单价', '百度单价']:
                        if p in df.columns: df[p] = pd.to_numeric(df[p], errors='coerce').fillna(0)
                    c = get_db_conn(); df[['物料名称', '品项类别', '单位', '物流单价', '顿角单价', '百度单价']].to_sql('raw_materials', c, if_exists='replace', index=False); c.close(); st.success("已更新"); st.rerun()
        c = get_db_conn(); st.dataframe(pd.read_sql("SELECT * FROM raw_materials", c), use_container_width=True); c.close()

    with t2:
        conn = get_db_conn()
        try:
            df_o = pd.read_sql("SELECT DISTINCT 商品名称, 规格, 做法, 门店名称 FROM sales_raw", conn)
            df_o['规格'] = df_o['规格'].replace(['nan', 'None', '', '0'], '常规').fillna('常规')
            df_o['做法'] = df_o['做法'].replace(['nan', 'None', '', '0'], '常规').fillna('常规')
            raws = pd.read_sql("SELECT 物料名称 FROM raw_materials", conn)['物料名称'].tolist()
        except: df_o = pd.DataFrame(); raws = []
        
        if df_o.empty: st.warning("请先导入销售报表。")
        else:
            c_type, c_scope = st.columns(2)
            db_type = '物流' if '物流' in c_type.radio("配方轨道", ["🏪 门店配方", "📦 物流配方"]) else '门店'
            scope = "【全局默认配方】" if db_type == '物流' else c_scope.selectbox("适用范围", ["【全局默认配方】", "【顿角项目配方】", "【百度项目配方】"] + sorted(df_o['门店名称'].unique().tolist()))
            
            p = st.selectbox("选择商品", sorted(df_o['商品名称'].unique().tolist()))
            s = st.selectbox("选择规格", sorted(df_o[df_o['商品名称']==p]['规格'].unique().tolist()))
            m = st.selectbox("选择做法", sorted(df_o[(df_o['商品名称']==p)&(df_o['规格']==s)]['做法'].unique().tolist()))
            
            with st.container(border=True):
                st.markdown(f"➕ 添加物料")
                cs1, cs2, cs3 = st.columns([3, 1, 1])
                mat = cs1.selectbox("搜索物料", ["--请选择--"] + raws)
                qty = cs2.number_input("用量", min_value=0.0, step=1.0)
                if cs3.button("确认添加", type="primary"):
                    if mat != "--请选择--" and qty > 0:
                        cursor = conn.cursor()
                        cursor.execute("INSERT OR REPLACE INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (db_type, scope, p, s, m, mat, qty))
                        conn.commit(); st.toast("✅ 已更新"); st.rerun()

            curr = pd.read_sql("SELECT 物料名称, 用量 FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", conn, params=(db_type, scope, p, s, m))
            for i, r in curr.iterrows():
                c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
                c1.write(f"☕ {r['物料名称']}")
                nq = c2.number_input("用量", value=float(r['用量']), key=f"q2_{i}")
                if c3.button("保存", key=f"s2_{i}"):
                    conn.execute("UPDATE bom_recipes SET 用量=? WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", (nq, db_type, scope, p, s, m, r['物料名称']))
                    conn.commit(); st.rerun()
                if c4.button("移除", key=f"d2_{i}"):
                    conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", (db_type, scope, p, s, m, r['物料名称']))
                    conn.commit(); st.rerun()
        conn.close()

    with t3:
        st.markdown("#### 📚 成本卡库管理")
        if st.button("🗑️ 彻底清空所有配方库数据 (危险！)", type="secondary"):
            c = get_db_conn(); c.execute("DELETE FROM bom_recipes"); c.commit(); c.close(); st.rerun()
            
        if 'edit_m' not in st.session_state: st.session_state.edit_m = False
        if st.button("📝 开启/关闭 全局管理模式", type="primary"): 
            st.session_state.edit_m = not st.session_state.edit_m
            st.rerun()
        
        conn = get_db_conn()
        df_b = pd.read_sql("SELECT * FROM bom_recipes", conn)
        df_r = pd.read_sql("SELECT * FROM raw_materials", conn)
        if not df_b.empty:
            merged = df_b.merge(df_r, on='物料名称', how='left').fillna(0)
            merged['l_v'] = merged['用量'] * merged['物流单价']
            merged['d_v'] = merged['用量'] * merged['顿角单价']
            merged['b_v'] = merged['用量'] * merged['百度单价']
            
            groups = merged.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'])
            for (rt, sc, pdn, spc, mth), items in groups:
                with st.container(border=True):
                    # 强力格式化显示，确保即便有 0 也能精准匹配删除
                    st.markdown(f'<div class="recipe-card-header"><b>【{rt}】{pdn}</b> <span style="color:#64748B;">({spc}/{mth})</span><br><small>适用: {sc}</small></div>', unsafe_allow_html=True)
                    st.markdown(f'<span class="cost-tag">出厂:¥{items["l_v"].sum():.2f}</span><span class="cost-tag">顿角:¥{items["d_v"].sum():.2f}</span><span class="cost-tag">百度:¥{items["b_v"].sum():.2f}</span>', unsafe_allow_html=True)
                    
                    if st.session_state.edit_m:
                        ed = st.data_editor(items[['物料名称', '用量']], key=f"ed_{rt}_{sc}_{pdn}_{spc}_{mth}", use_container_width=True, num_rows="dynamic")
                        col1, col2, _ = st.columns([1, 1, 3])
                        if col1.button("💾 保存", key=f"sv_{rt}_{pdn}_{spc}_{mth}"):
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", (rt, sc, pdn, spc, mth))
                            for _, r in ed.dropna().iterrows():
                                if r['用量'] > 0: cursor.execute("INSERT INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (rt, sc, pdn, spc, mth, r['物料名称'], r['用量']))
                            conn.commit(); st.rerun()
                        if col2.button("🗑️ 删除整卡", key=f"dc_{rt}_{pdn}_{spc}_{mth}", type="primary"):
                            conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", (rt, sc, pdn, spc, mth))
                            conn.commit(); st.rerun()
                    else:
                        st.write("配方内容: " + " 、 ".join([f"{r['物料名称']}({r['用量']}g)" for _,r in items.iterrows()]))
        else: st.info("库内无配方。")
        conn.close()
