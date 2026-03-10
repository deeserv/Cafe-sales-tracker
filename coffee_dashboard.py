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
        background-color: #FFFFFF; padding: 22px; border-radius: 18px;
        box-shadow: 0 4px 10px -2px rgba(0, 0, 0, 0.05); border: 1px solid #E2E8F0;
    }
    [data-testid="stMetricValue"] {
        font-size: 30px !important; font-weight: 800 !important;
        background: -webkit-linear-gradient(120deg, #1E40AF, #3B82F6);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF; border-radius: 15px; border: 1px solid #E2E8F0; padding: 25px;
        margin-bottom: 25px;
    }
    
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
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度大厦店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
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
    # 强力数据清洗
    cursor.execute("UPDATE sales_raw SET 规格 = '常规' WHERE 规格 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE sales_raw SET 做法 = '常规' WHERE 做法 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE bom_recipes SET 规格 = '常规' WHERE 规格 IN ('0', 'nan', 'None', '', 'NaN')")
    cursor.execute("UPDATE bom_recipes SET 做法 = '常规' WHERE 做法 IN ('0', 'nan', 'None', '', 'NaN')")
    conn.commit(); conn.close()

init_db()

# -----------------------------------------------------------------------------
# 3. 核心计算引擎 (店 > 项目 > 全局 优先覆盖)
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
        files = st.file_uploader("📥 导入流水", type=["xlsx", "csv"], accept_multiple_files=True)
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
        if st.button("🗑️ 清空流水", use_container_width=True):
            c = get_db_conn(); c.execute("DELETE FROM sales_raw"); c.commit(); c.close(); st.rerun()

    if total_rows == 0: st.info("请先导入数据。"); st.stop()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 周期与对比筛选")
    parsed_dates = [datetime.strptime(p, '%Y-%m-%d').date() for p in available_periods if p]
    enable_comp = st.sidebar.checkbox("🌓 开启环比对比", value=False)
    sel_range = st.sidebar.date_input("本期日期", [min(parsed_dates), max(parsed_dates)], min_value=min(parsed_dates), max_value=max(parsed_dates))
    
    df_cur = pd.DataFrame(); df_prev = pd.DataFrame()
    if len(sel_range) == 2:
        s1, e1 = sel_range
        conn = get_db_conn()
        df_cur = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(s1.strftime('%Y-%m-%d'), e1.strftime('%Y-%m-%d')))
        if enable_comp:
            dur = (e1 - s1).days + 1
            df_prev = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=((s1 - timedelta(days=dur)).strftime('%Y-%m-%d'), (s1 - timedelta(days=1)).strftime('%Y-%m-%d')))
        conn.close()

    if not df_cur.empty:
        df_cur = merge_category_map(df_cur)
        if not df_prev.empty: df_prev = merge_category_map(df_prev)
        
        st.sidebar.markdown("---")
        all_l1 = sorted(df_cur['一级分类'].unique().tolist())
        sel_l1 = st.sidebar.multiselect("一级分类", all_l1, default=all_l1)
        if sel_l1: 
            df_cur = df_cur[df_cur['一级分类'].isin(sel_l1)]
            if not df_prev.empty: df_prev = df_prev[df_prev['一级分类'].isin(sel_l1)]
        all_sts = sorted(df_cur['门店名称'].unique().tolist())
        sel_sts = st.sidebar.multiselect("项目/门店筛选", all_sts)
        if sel_sts: 
            df_cur = df_cur[df_cur['门店名称'].isin(sel_sts)]
            if not df_prev.empty: df_prev = df_prev[df_prev['门店名称'].isin(sel_sts)]

        days_cur = max(1, df_cur['统计周期'].nunique())
        days_prev = max(1, df_prev['统计周期'].nunique()) if not df_prev.empty else 1

        st.title("📊 顿角咖啡智能经营看板")
        q1, a1 = df_cur['销售数量'].sum(), df_cur['销售金额'].sum()
        q2, a2 = (df_prev['销售数量'].sum(), df_prev['销售金额'].sum()) if not df_prev.empty else (None, None)

        c1, c2 = st.columns(2); c3, c4 = st.columns(2)
        def show_m(target, label, v, pv, prefix="", suffix=""):
            delta = f"{(v-pv)/pv:.1%}" if pv and pv!=0 else None
            target.metric(label, f"{prefix}{v:,.2f}{suffix}".replace(".00", ""), delta)

        show_m(c1, "总销售杯数", q1, q2, suffix=" 杯")
        show_m(c2, "总营收金额", a1, a2, prefix="¥")
        show_m(c3, "日均营业额", a1/days_cur, (a2/days_prev if a2 else None), prefix="¥")
        show_m(c4, "单杯平均价", a1/q1 if q1>0 else 0, (a2/q2 if a2 else None), prefix="¥")

        # 销售结构
        st.markdown("---")
        st.subheader("🏗️ 一级分类销售分布")
        l1_sum = df_cur.groupby('一级分类').agg({'销售数量':'sum','销售金额':'sum'}).reset_index()
        fig_l1 = go.Figure()
        fig_l1.add_trace(go.Bar(x=l1_sum['一级分类'], y=l1_sum['销售数量'], name='销量', marker_color='#3B82F6', text=l1_sum['销售数量'], textposition='auto'))
        fig_l1.add_trace(go.Bar(x=l1_sum['一级分类'], y=l1_sum['销售金额'], name='营收', marker_color='#10B981', text=l1_sum['销售金额'].apply(lambda x:f"¥{x:,.0f}"), textposition='auto'))
        fig_l1.update_layout(barmode='group', height=350, margin=dict(l=10,r=10,t=30,b=10), plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_l1, use_container_width=True)

        st.markdown("---")
        st.subheader("📈 二级分类精细化拆解")
        cat_df = df_cur.groupby('二级分类').agg({'销售数量':'sum', '销售金额':'sum'}).reset_index()
        cat_df['占比'] = (cat_df['销售金额'] / cat_df['销售金额'].sum() * 100).round(1)
        cat_df = cat_df.sort_values('销售数量', ascending=False)

        with st.container(border=True):
            st.markdown("**1. 销量排行榜 (杯数)**")
            st.plotly_chart(px.bar(cat_df, x='二级分类', y='销售数量', text='销售数量', color_discrete_sequence=['#3B82F6']).update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)"), use_container_width=True)
        with st.container(border=True):
            st.markdown("**2. 营收排行榜 (金额)**")
            st.plotly_chart(px.bar(cat_df, x='二级分类', y='销售金额', text=cat_df['销售金额'].apply(lambda x:f"¥{x:,.0f}"), color_discrete_sequence=['#10B981']).update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)"), use_container_width=True)
        with st.container(border=True):
            st.markdown("**3. 营收占比 (%)**")
            st.plotly_chart(px.bar(cat_df, x='二级分类', y='占比', text=cat_df['占比'].apply(lambda x:f"{x}%"), color_discrete_sequence=['#F59E0B']).update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)"), use_container_width=True)

        st.markdown("### 📄 单品销售排行")
        v_df = df_cur.groupby(['商品名称'], as_index=False).agg({'一级分类':'first', '二级分类':'first', '销售数量':'sum', '销售金额':'sum'}).sort_values('销售数量', ascending=False)
        st.dataframe(v_df[['商品名称','一级分类','二级分类','销售数量','销售金额']], use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# 5. 成本配方中心 (🚀 交互革命版本)
# -----------------------------------------------------------------------------
elif app_mode == "⚙️ 成本与配方中心":
    st.title("⚙️ 三级原物料与配方引擎")
    t1, t2, t3 = st.tabs(["📦 基础原物料库", "📋 配置单品配方 (表内极速录入)", "📚 成本卡库管理"])
    
    with t1:
        f = st.file_uploader("导入三级价格原物料表", type=["xlsx", "csv"])
        if f:
            df_u = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df_u.columns = [str(c).strip() for c in df_u.columns]
            ex = {'物流名称': '物料名称', '品项类别': '品项类别', '单价单位': '单位', '物流单价成本': '物流单价', '顿角单价成本': '顿角单价', '百度单价成本': '百度单价'}
            df_u = df_u.rename(columns={c: ex[c] for c in df_u.columns if c in ex})
            if '物料名称' in df_u.columns:
                for p in ['物流单价', '顿角单价', '百度单价']:
                    if p in df_u.columns: df_u[p] = pd.to_numeric(df_u[p], errors='coerce').fillna(0)
                c = get_db_conn(); df_u[['物料名称', '品项类别', '单位', '物流单价', '顿角单价', '百度单价']].to_sql('raw_materials', c, if_exists='replace', index=False); c.close(); st.success("物料库更新成功"); st.rerun()
        c = get_db_conn(); st.dataframe(pd.read_sql("SELECT * FROM raw_materials", c), use_container_width=True); c.close()

    with t2:
        conn = get_db_conn()
        try:
            df_opt = pd.read_sql("SELECT DISTINCT 商品名称, 规格, 做法, 门店名称 FROM sales_raw", conn)
            df_opt['规格'] = df_opt['规格'].fillna('常规').astype(str)
            df_opt['做法'] = df_opt['做法'].fillna('常规').astype(str)
            stores = sorted(df_opt['门店名称'].unique().tolist())
            # 获取物料清单用于下拉
            rmats = pd.read_sql("SELECT 物料名称 FROM raw_materials", conn)['物料名称'].tolist()
        except: df_opt = pd.DataFrame(); stores = []; rmats = []
        
        if df_opt.empty: st.warning("请在看板导入销售报表。")
        else:
            c_track, c_scope = st.columns(2)
            db_type = '物流' if '物流' in c_track.radio("1. 选择轨道", ["📦 物流配方", "🏪 门店配方"]) else '门店'
            scope = c_scope.selectbox("2. 适用范围 (店>项目>全局)", ["【全局默认配方】", "百度项目", "顿角项目"] + stores)
            
            st.divider()
            c_p, c_s, c_m = st.columns(3)
            p = c_p.selectbox("3. 选择商品", sorted(df_opt['商品名称'].unique().tolist()))
            s = c_s.selectbox("4. 规格", sorted(df_opt[df_opt['商品名称']==p]['规格'].unique().tolist()))
            m = c_m.selectbox("5. 做法", sorted(df_opt[(df_opt['商品名称']==p)&(df_opt['规格']==s)]['做法'].unique().tolist()))
            
            # --- 🌟 核心表内编辑器实现 🌟 ---
            st.markdown("#### 📝 配方清单编辑器")
            st.info("💡 **操作指引**：\n1. 点击下方表格最左侧的 **`+`** 号新增一行。\n2. 点击【物料名称】单元格，**直接输入搜索**并选择。\n3. 修改【用量】数值。\n4. 点击最下方的【💾 保存整张配方卡】。")
            
            # 从数据库读取现有数据作为初始化
            existing_df = pd.read_sql("SELECT 物料名称, 用量 FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", conn, params=(db_type, scope, p, s, m))
            
            # 使用 data_editor 进行交互
            edited_df = st.data_editor(
                existing_df,
                column_config={
                    "物料名称": st.column_config.SelectboxColumn(
                        "物料名称 (点击搜索)",
                        options=rmats,
                        required=True,
                        width="large"
                    ),
                    "用量": st.column_config.NumberColumn(
                        "用量 (g/ml)",
                        min_value=0.0,
                        format="%.2f",
                        required=True
                    )
                },
                num_rows="dynamic", # 允许用户自由增减行
                use_container_width=True,
                key=f"editor_{db_type}_{scope}_{p}_{s}_{m}" # 确保切换商品时重置表格
            )
            
            # 保存逻辑
            if st.button("💾 确认并保存整张配方卡", type="primary", use_container_width=True):
                # 数据清洗：去掉空行
                final_data = edited_df.dropna(subset=['物料名称'])
                final_data = final_data[final_data['用量'] > 0]
                
                cursor = conn.cursor()
                # 覆盖逻辑
                cursor.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", (db_type, scope, p, s, m))
                for _, row in final_data.iterrows():
                    cursor.execute("INSERT INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (db_type, scope, p, s, m, row['物料名称'], row['用量']))
                conn.commit()
                st.success(f"✅ 已成功同步 {p} ({s}/{m}) 的配方。")
                st.rerun()

        conn.close()

    with t3:
        st.markdown("#### 📚 全局成本卡库预览")
        conn = get_db_conn()
        db_b = pd.read_sql("SELECT * FROM bom_recipes", conn)
        db_r = pd.read_sql("SELECT * FROM raw_materials", conn)
        if not db_b.empty:
            merged = db_b.merge(df_r, on='物料名称', how='left').fillna(0)
            merged['lv'] = merged['用量'] * merged['物流单价']; merged['dv'] = merged['用量'] * merged['顿角单价']; merged['bv'] = merged['用量'] * merged['百度单价']
            grps = merged.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'])
            for (rt, sc, pdn, spc, mth), items in grps:
                with st.container(border=True):
                    st.markdown(f'<div class="recipe-card-header"><b>【{rt}】{pdn}</b> <span style="color:#64748B;">({spc}/{mth})</span><br><small>范围: {sc}</small></div>', unsafe_allow_html=True)
                    st.markdown(f'<span class="cost-tag">📦出厂:¥{items["lv"].sum():.2f}</span><span class="cost-tag">🏬顿角:¥{items["dv"].sum():.2f}</span><span class="cost-tag">🏢百度:¥{items["bv"].sum():.2f}</span>', unsafe_allow_html=True)
                    if st.button("🗑️ 删除整卡", key=f"del_all_{rt}_{sc}_{pdn}_{spc}_{mth}", type="primary"):
                        conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? ", (rt, sc, pdn, spc, mth))
                        conn.commit(); st.rerun()
                    st.write("🌿 " + " 、 ".join([f"{r['物料名称']}({r['量']}g)" for _,r in items.iterrows()]))
        else: st.info("库内为空。")
        conn.close()
