# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import sqlite3
import re
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 1. 核心配置与 CSS 注入 (布局显示优化版)
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
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #E2E8F0;
    }
    [data-testid="stMetricValue"] {
        font-size: 32px !important;
        font-weight: 800 !important;
        background: -webkit-linear-gradient(120deg, #1E40AF, #3B82F6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* 配方中心管理卡片 */
    .recipe-card-header { background: #F1F5F9; padding: 12px 15px; border-radius: 10px; border-left: 6px solid #3B82F6; margin-bottom: 10px; }
    .cost-tag { background: #DBEAFE; color: #1E40AF; padding: 3px 8px; border-radius: 5px; font-size: 13px; font-weight: 700; margin-right: 5px; border: 1px solid #BFDBFE; }
    
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; border-radius: 15px; border: 1px solid #E2E8F0; padding: 20px;
    }
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
# 3. 核心 ETL 与计算引擎
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
    df['商品类别'] = df['商品类别'].astype(str).str.strip()
    df = pd.merge(df, df_cat, left_on='商品类别', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('未分类')
    s2p = {clean_store_name(s): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(clean_store_name(x), '其他项目'))
    return df

# -----------------------------------------------------------------------------
# 4. 侧边栏与数据管线
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
        files = st.file_uploader("📥 导入企迈流水", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            conn = get_db_conn()
            for f in files:
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
        if st.button("🗑️ 清空流水", use_container_width=True):
            c = get_db_conn(); c.execute("DELETE FROM sales_raw"); c.commit(); c.close(); st.rerun()

    if total_rows == 0: st.info("请先导入企迈销售数据。"); st.stop()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 日期与深度筛选")
    parsed_dates = [datetime.strptime(p, '%Y-%m-%d').date() for p in available_periods if p]
    if parsed_dates:
        sel_range = st.sidebar.date_input("日期范围", [min(parsed_dates), max(parsed_dates)], min_value=min(parsed_dates), max_value=max(parsed_dates))
        if len(sel_range) == 2:
            s, e = sel_range
            conn = get_db_conn()
            df_cur = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(s.strftime('%Y-%m-%d'), e.strftime('%Y-%m-%d')))
            conn.close()
            if not df_cur.empty:
                df_cur = merge_category_map(df_cur)
                # 筛选器
                all_projs = sorted(df_cur['所属项目'].unique().tolist())
                sel_projs = st.sidebar.multiselect("项目筛选", all_projs)
                if sel_projs: df_cur = df_cur[df_cur['所属项目'].isin(sel_projs)]
                all_sts = sorted(df_cur['门店名称'].unique().tolist())
                sel_sts = st.sidebar.multiselect("门店筛选", all_sts)
                if sel_sts: df_cur = df_cur[df_cur['门店名称'].isin(sel_sts)]
                
                days_cur = df_cur['统计周期'].nunique() if not df_cur.empty else 1
                
                # -------------------------------------------------------------
                # 找回精美看板 UI
                # -------------------------------------------------------------
                st.title("📊 顿角咖啡智能经营看板")
                st.markdown(f"📅 统计期：`{s.strftime('%Y-%m-%d')} - {e.strftime('%Y-%m-%d')}` ({days_cur}天有效数据)")
                
                qty = df_cur['销售数量'].sum()
                amt = df_cur['销售金额'].sum()
                cp = (amt / qty) if qty > 0 else 0
                dr = amt / days_cur

                # ✅ 顶部核心指标布局 (暂时隐藏毛利)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("总销量", f"{int(qty)} 杯")
                c2.metric("总营收", f"¥{amt:,.2f}")
                c3.metric("日均营收", f"¥{dr:,.2f}")
                c4.metric("平均客单价", f"¥{cp:.2f}")
                
                # -------------------------------------------------------------
                # 🚀 找回：二级分类销量与营收看板 (柱状图升级)
                # -------------------------------------------------------------
                st.markdown("---")
                st.subheader("📈 二级分类销售结构分析 (销量与营收)")
                
                cat_summary = df_cur.groupby('二级分类').agg({
                    '销售数量': 'sum',
                    '销售金额': 'sum'
                }).reset_index().sort_values('销售数量', ascending=False)
                
                if PLOTLY_AVAILABLE:
                    fig_cat = go.Figure()
                    
                    # 销量柱状图
                    fig_cat.add_trace(go.Bar(
                        x=cat_summary['二级分类'],
                        y=cat_summary['销售数量'],
                        name='销售数量 (杯)',
                        marker_color='#3B82F6',
                        text=cat_summary['销售数量'],
                        textposition='auto',
                    ))
                    
                    # 营收柱状图 (采用次轴或并列，这里选择并列显示更直观)
                    fig_cat.add_trace(go.Bar(
                        x=cat_summary['二级分类'],
                        y=cat_summary['销售金额'],
                        name='营收金额 (元)',
                        marker_color='#10B981',
                        text=cat_summary['销售金额'].apply(lambda x: f"¥{x:,.0f}"),
                        textposition='auto',
                    ))
                    
                    fig_cat.update_layout(
                        barmode='group',
                        margin=dict(l=10, r=10, t=20, b=10),
                        height=450,
                        plot_bgcolor="rgba(0,0,0,0)",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        xaxis=dict(showgrid=False),
                        yaxis=dict(showgrid=True, gridcolor='#F1F5F9')
                    )
                    st.plotly_chart(fig_cat, use_container_width=True)

                # -------------------------------------------------------------
                # 经营明细 (暂时隐藏成本和毛利列)
                # -------------------------------------------------------------
                st.markdown("### 📄 单品销售排行")
                
                v = df_cur.groupby('商品名称', as_index=False).agg({
                    '二级分类': 'first', 
                    '销售数量': 'sum', 
                    '销售金额': 'sum'
                }).sort_values('销售数量', ascending=False)
                
                # BCG 诊断（基于销量和平均营收，不依赖毛利）
                aq = v['销售数量'].mean()
                aa = v['销售金额'].mean()
                def get_tag(r):
                    if r['销售数量']>=aq and r['销售金额']>=aa: return "🌟明星商品"
                    elif r['销售数量']>=aq: return "🐮现金牛"
                    elif r['销售金额']>=aa: return "❓潜力股"
                    return "🐕长尾商品"
                v['产品诊断'] = v.apply(get_tag, axis=1)

                st.dataframe(v[['商品名称','二级分类','产品诊断','销售数量','销售金额']], column_config={
                    "销售数量": st.column_config.ProgressColumn("总销量", format="%d", min_value=0, max_value=int(v['销售数量'].max() if not v.empty else 1)),
                    "销售金额": st.column_config.NumberColumn("总营收", format="¥%.2f"),
                }, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# ⚙️ 成本配方中心 (保持功能不变，优化删除与管理)
# -----------------------------------------------------------------------------
elif app_mode == "⚙️ 成本与配方中心":
    st.title("⚙️ 三级原物料与配方引擎")
    tab1, tab2, tab3 = st.tabs(["📦 基础原物料库", "📋 配置单品配方", "📚 成本卡库管理"])
    
    with tab1:
        f = st.file_uploader("上传三级价格原物料表", type=["xlsx", "csv"])
        if f:
            df_up = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df_up.columns = [str(c).strip() for c in df_up.columns]
            ex = {'物流名称': '物料名称', '品项类别': '品项类别', '单价单位': '单位', '物流单价成本': '物流单价', '顿角单价成本': '顿角单价', '百度单价成本': '百度单价'}
            df_up = df_up.rename(columns={c: ex[c] for c in df_up.columns if c in ex})
            if '物料名称' in df_up.columns:
                for p in ['物流单价', '顿角单价', '百度单价']:
                    if p in df_up.columns: df_up[p] = pd.to_numeric(df_up[p], errors='coerce').fillna(0)
                c = get_db_conn(); df_up[['物料名称', '品项类别', '单位', '物流单价', '顿角单价', '百度单价']].to_sql('raw_materials', c, if_exists='replace', index=False); c.close(); st.success("物料库更新成功"); st.rerun()
        c = get_db_conn(); st.dataframe(pd.read_sql("SELECT * FROM raw_materials", c), use_container_width=True); c.close()

    with tab2:
        conn = get_db_conn()
        try:
            df_opt = pd.read_sql("SELECT DISTINCT 商品名称, 规格, 做法, 门店名称, 商品类别 FROM sales_raw", conn)
            df_opt['规格'] = df_opt['规格'].fillna('常规').astype(str)
            df_opt['做法'] = df_opt['做法'].fillna('常规').astype(str)
            df_opt = merge_category_map(df_opt); df_opt = df_opt[df_opt['一级分类'] != '未分类']
            rmats = pd.read_sql("SELECT 物料名称 FROM raw_materials", conn)['物料名称'].tolist()
        except: df_opt = pd.DataFrame(); rmats = []
        
        if df_opt.empty: st.warning("请在看板导入销售流水数据。")
        else:
            ct, cs = st.columns(2)
            db_type = '物流' if '物流' in ct.radio("计算轨道", ["🏪 门店配方", "📦 物流配方"]) else '门店'
            scope = "【全局默认配方】" if db_type == '物流' else cs.selectbox("适用范围", ["【全局默认配方】", "【顿角项目配方】", "【百度项目配方】"] + sorted(df_opt['门店名称'].unique().tolist()))
            
            p_sel = st.selectbox("1. 选择商品", sorted(df_opt['商品名称'].unique().tolist()))
            s_sel = st.selectbox("2. 选择规格", sorted(df_opt[df_opt['商品名称']==p_sel]['规格'].unique().tolist()))
            m_sel = st.selectbox("3. 选择做法", sorted(df_opt[(df_opt['商品名称']==p_sel)&(df_opt['规格']==s_sel)]['做法'].unique().tolist()))
            
            with st.container(border=True):
                st.markdown(f"#### ➕ 添加新物料")
                c1, c2, c3 = st.columns([3, 1, 1])
                mat = c1.selectbox("搜索物料", ["--请选择--"] + rmats)
                qty = c2.number_input("用量", min_value=0.0, step=1.0)
                if c3.button("添加", type="primary", use_container_width=True):
                    if mat != "--请选择--" and qty > 0:
                        conn.execute("INSERT OR REPLACE INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (db_type, scope, p_sel, s_sel, m_sel, mat, qty))
                        conn.commit(); st.rerun()

            cur = pd.read_sql("SELECT 物料名称, 用量 FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", conn, params=(db_type, scope, p_sel, s_sel, m_sel))
            for i, r in cur.iterrows():
                cc1, cc2, cc3, cc4 = st.columns([4, 2, 1, 1])
                cc1.write(f"☕ {r['物料名称']}")
                nq = cc2.number_input("用量", value=float(r['用量']), key=f"t2_q_{i}")
                if cc3.button("存", key=f"t2_s_{i}"):
                    conn.execute("UPDATE bom_recipes SET 用量=? WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", (nq, db_type, scope, p_sel, s_sel, m_sel, r['物料名称']))
                    conn.commit(); st.rerun()
                if cc4.button("删", key=f"t2_d_{i}"):
                    conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? AND 物料名称=?", (db_type, scope, p_sel, s_sel, m_sel, r['物料名称']))
                    conn.commit(); st.rerun()
        conn.close()

    with tab3:
        st.markdown("#### 📚 全局配方卡管理")
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
            merged['lv'] = merged['用量'] * merged['物流单价']
            merged['dv'] = merged['用量'] * merged['顿角单价']
            merged['bv'] = merged['用量'] * merged['百度单价']
            grps = merged.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'])
            for (rt, sc, pdn, spc, mth), items in grps:
                with st.container(border=True):
                    st.markdown(f'<div class="recipe-card-header"><b>【{rt}】{pdn}</b> <span style="color:#64748B;">({spc}/{mth})</span><br><small>适用: {sc}</small></div>', unsafe_allow_html=True)
                    st.markdown(f'<span class="cost-tag">📦出厂成本:¥{items["lv"].sum():.2f}</span><span class="cost-tag">🏬顿角成本:¥{items["dv"].sum():.2f}</span><span class="cost-tag">🏢百度成本:¥{items["bv"].sum():.2f}</span>', unsafe_allow_html=True)
                    if st.session_state.edit_m:
                        ed = st.data_editor(items[['物料名称', '用量']], key=f"ed_{rt}_{sc}_{pdn}_{spc}_{mth}", use_container_width=True, num_rows="dynamic")
                        col1, col2, _ = st.columns([1, 1, 3])
                        if col1.button("💾 保存", key=f"sv_{rt}_{pdn}_{spc}_{mth}"):
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", (rt, sc, pdn, spc, mth))
                            for _, row in ed.dropna(subset=['物料名称']).iterrows():
                                if row['用量'] > 0: cursor.execute("INSERT INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (rt, sc, pdn, spc, mth, row['物料名称'], row['用量']))
                            conn.commit(); st.rerun()
                        if col2.button("🗑️ 删除整卡", key=f"dc_{rt}_{pdn}_{spc}_{mth}", type="primary"):
                            conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? ", (rt, sc, pdn, spc, mth))
                            conn.commit(); st.rerun()
                    else:
                        st.write("🌿 **包含成分：** " + " 、 ".join([f"{r['物料名称']}({r['用量']}g)" for _,r in items.iterrows()]))
        conn.close()
