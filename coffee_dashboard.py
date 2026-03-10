# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import sqlite3
import re
from datetime import datetime, timedelta

# --- 尝试导入可视化库，并做好安全保护 ---
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# =============================================================================
# 1. 全局配置与常量定义 (后端逻辑核心)
# =============================================================================
PROJECT_STORE_MAPPING = {
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"],
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "腾讯项目": ["北京总部image"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"]
}

CATEGORY_MAPPING = [
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "咖啡饮品", "二级分类": "拿铁家族"}, {"一级分类": "咖啡饮品", "二级分类": "奶咖家族"},
    {"一级分类": "咖啡饮品", "二级分类": "果C美式"}, {"一级分类": "咖啡饮品", "二级分类": "手冲咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "优选咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "经典意式"},
    {"一级分类": "咖啡饮品", "二级分类": "甄选咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "soe冷萃"},
    {"一级分类": "咖啡饮品", "二级分类": "SOE冷萃"}, {"一级分类": "咖啡饮品", "二级分类": "风味拿铁"},
    {"一级分类": "咖啡饮品", "二级分类": "冰爽果咖"}, {"一级分类": "咖啡饮品", "二级分类": "中式茶咖"},
    {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"}, {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"},
    {"一级分类": "非咖啡饮品", "二级分类": "经典鲜果茶"}, {"一级分类": "非咖啡饮品", "二级分类": "手打柠"},
    {"一级分类": "非咖啡饮品", "二级分类": "清爽果茶"}, {"一级分类": "非咖啡饮品", "二级分类": "新鲜果蔬汁"},
    {"一级分类": "非咖啡饮品", "二级分类": "不喝咖啡"}, {"一级分类": "非咖啡饮品", "二级分类": "果茶系列"},
    {"一级分类": "非咖啡饮品", "二级分类": "抹茶家族"}, {"一级分类": "非咖啡饮品", "二级分类": "柠檬茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "原叶鲜奶茶"}, {"一级分类": "非咖啡饮品", "二级分类": "经典果茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "经典奶茶"}
]

# =============================================================================
# 2. 模块化：UI 样式与数据库引擎
# =============================================================================
def init_ui_styles():
    st.set_page_config(page_title="顿角咖啡智能经营系统", page_icon="☕", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        div[data-testid="stMetric"] {
            background-color: #FFFFFF; padding: 22px; border-radius: 18px;
            box-shadow: 0 4px 10px -2px rgba(0, 0, 0, 0.05); border: 1px solid #E2E8F0;
        }
        [data-testid="stMetricValue"] {
            font-size: 32px !important; font-weight: 800 !important;
            background: -webkit-linear-gradient(120deg, #1E40AF, #3B82F6);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #FFFFFF; border-radius: 15px; border: 1px solid #E2E8F0; padding: 25px; margin-bottom: 20px;
        }
        .recipe-card-header { background: #F8FAFC; padding: 15px; border-radius: 12px; border-left: 8px solid #3B82F6; margin-bottom: 12px; }
        .cost-tag { background: #EFF6FF; color: #1E40AF; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: 700; border: 1px solid #DBEAFE; margin-right: 8px; }
        .scope-badge { background: #1E40AF; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-left: 10px; }
    </style>
    """, unsafe_allow_html=True)

DB_PATH = os.path.join("data_storage", "coffee_master.db")
os.makedirs("data_storage", exist_ok=True)

def get_db_conn(): return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales_raw (门店名称 TEXT, 商品名称 TEXT, 商品类别 TEXT, 规格 TEXT, 做法 TEXT, 统计周期 TEXT, 销售金额 REAL, 销售数量 REAL, source_file TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS raw_materials (物料名称 TEXT PRIMARY KEY, 品项类别 TEXT, 单位 TEXT, 物流单价 REAL, 顿角单价 REAL, 百度单价 REAL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS bom_recipes (配方类型 TEXT, 适用范围 TEXT, 商品名称 TEXT, 规格 TEXT, 做法 TEXT, 物料名称 TEXT, 用量 REAL, UNIQUE(配方类型, 适用范围, 商品名称, 规格, 做法, 物料名称))''')
    conn.commit(); conn.close()

# =============================================================================
# 3. 模块化：核心 Logic 计算引擎 (后端)
# =============================================================================
def logic_process_sales_data(df):
    if df.empty: return df
    df_cat = pd.DataFrame(CATEGORY_MAPPING)
    # 清理列冲突
    for c in ['一级分类', '二级分类']:
        if c in df.columns: df = df.drop(columns=[c], errors='ignore')
    df['商品类别_clean'] = df['商品类别'].astype(str).str.strip()
    df = pd.merge(df, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('未分类')
    df['二级分类'] = df['二级分类'].fillna('未分类')
    # 项目映射
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(str(x).strip(), '其他项目'))
    return df

# =============================================================================
# 4. Page - 经营分析看板 (前端视图)
# =============================================================================
def page_analytics_dashboard():
    with st.sidebar.expander("💾 数据管理 (ETL)", expanded=False):
        conn = get_db_conn()
        try:
            total_rows = pd.read_sql("SELECT COUNT(*) as c FROM sales_raw", conn).iloc[0]['c']
            available_periods = sorted(pd.read_sql("SELECT DISTINCT 统计周期 FROM sales_raw WHERE 统计周期 IS NOT NULL", conn)['统计周期'].tolist())
        except: total_rows = 0; available_periods = []
        finally: conn.close()
        st.markdown(f"库内流水：**{total_rows:,}** 条")
        files = st.file_uploader("📥 导入企迈流水", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            conn = get_db_conn()
            for f in files:
                df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                df.columns = [str(c).strip() for c in df.columns]
                # 兼容不同列名
                for c in df.columns:
                    if '规格' in c: df.rename(columns={c: '规格'}, inplace=True)
                    elif any(k in c for k in ['做法', '口味', '属性']): df.rename(columns={c: '做法'}, inplace=True)
                df = df.rename(columns={'商品实收': '销售金额', '商品销量': '销售数量', '日期': '统计周期', '商品分类': '商品类别'})
                df['统计周期'] = df['统计周期'].apply(lambda x: pd.to_datetime(x).strftime('%Y-%m-%d') if pd.notna(x) else datetime.now().strftime('%Y-%m-%d'))
                df['规格'] = df['规格'].replace(['nan', 'None', '', '0'], '常规').fillna('常规')
                df['做法'] = df['做法'].replace(['nan', 'None', '', '0'], '常规').fillna('常规')
                for c in ['销售金额', '销售数量']:
                    if c in df.columns: df[c] = pd.to_numeric(df[c].astype(str).str.replace(r'[¥$,￥]', '', regex=True), errors='coerce').fillna(0)
                df[['门店名称', '商品名称', '商品类别', '规格', '做法', '统计周期', '销售金额', '销售数量']].to_sql('sales_raw', conn, if_exists='append', index=False)
            conn.close(); st.rerun()
        if st.button("🗑️ 清空销售库"):
            c = get_db_conn(); c.execute("DELETE FROM sales_raw"); c.commit(); c.close(); st.rerun()

    if total_rows == 0: st.info("请先导入流水数据。"); return
    
    st.sidebar.markdown("---")
    parsed_dates = [datetime.strptime(p, '%Y-%m-%d').date() for p in available_periods if p]
    enable_comp = st.sidebar.checkbox("🌓 开启环比对比", value=False)
    sel_range = st.sidebar.date_input("本期范围", [min(parsed_dates), max(parsed_dates)], min_value=min(parsed_dates), max_value=max(parsed_dates))
    
    df_cur = pd.DataFrame(); df_prev = pd.DataFrame()
    if len(sel_range) == 2:
        s1, e1 = sel_range
        conn = get_db_conn()
        df_cur = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=(s1.strftime('%Y-%m-%d'), e1.strftime('%Y-%m-%d')))
        if enable_comp:
            dur = (e1 - s1).days + 1
            df_prev = pd.read_sql("SELECT * FROM sales_raw WHERE 统计周期 >= ? AND 统计周期 <= ?", conn, params=((s1 - timedelta(days=dur)).strftime('%Y-%m-%d'), (s1 - timedelta(days=1)).strftime('%Y-%m-%d')))
        conn.close()

    if df_cur.empty: st.warning("当前筛选无数据。"); return
    
    df_cur = logic_process_sales_data(df_cur)
    if not df_prev.empty: df_prev = logic_process_sales_data(df_prev)
    
    # 联动筛选器
    st.sidebar.markdown("---")
    all_l1 = sorted(df_cur['一级分类'].unique().tolist())
    sel_l1 = st.sidebar.multiselect("一级分类筛选", all_l1, default=all_l1)
    if sel_l1:
        df_cur = df_cur[df_cur['一级分类'].isin(sel_l1)]
        if not df_prev.empty: df_prev = df_prev[df_prev['一级分类'].isin(sel_l1)]
    all_sts = sorted(df_cur['门店名称'].unique().tolist())
    sel_sts = st.sidebar.multiselect("门店/项目筛选", all_sts)
    if sel_sts:
        df_cur = df_cur[df_cur['门店名称'].isin(sel_sts)]
        if not df_prev.empty: df_prev = df_prev[df_prev['门店名称'].isin(sel_sts)]

    st.title("📊 顿角咖啡智能经营看板")
    
    days_cur = max(1, df_cur['统计周期'].nunique())
    days_prev = max(1, df_prev['统计周期'].nunique()) if not df_prev.empty else 1
    q1, a1 = df_cur['销售数量'].sum(), df_cur['销售金额'].sum()
    q2, a2 = (df_prev['销售数量'].sum(), df_prev['销售金额'].sum()) if not df_prev.empty else (None, None)

    # 1. 指标卡片 2x2
    c1, c2 = st.columns(2); c3, c4 = st.columns(2)
    def metric_box(target, label, v, pv, prefix="", suffix=""):
        delta = f"{(v-pv)/pv:.1%}" if pv and pv!=0 else None
        target.metric(label, f"{prefix}{v:,.2f}{suffix}".replace(".00", ""), delta)

    metric_box(c1, "总销售杯数", q1, q2, suffix=" 杯")
    metric_box(c2, "总营收金额", a1, a2, prefix="¥")
    metric_box(c3, "日均营业额", a1/days_cur, (a2/days_prev if a2 else None), prefix="¥")
    metric_box(c4, "单杯平均价", a1/q1 if q1>0 else 0, (a2/q2 if a2 else None), prefix="¥")

    if not PLOTLY_AVAILABLE:
        st.error("检测到运行环境缺失 `plotly` 库，无法渲染图表。请检查 requirements.txt")
        return

    # 2. 一级大盘
    st.markdown("---")
    st.subheader("🏗️ 品类结构宏观分布 (一级分类)")
    l1_s = df_cur.groupby('一级分类').agg({'销售数量':'sum','销售金额':'sum'}).reset_index()
    fig_l1 = go.Figure()
    fig_l1.add_trace(go.Bar(x=l1_s['一级分类'], y=l1_s['销售数量'], name='杯数', marker_color='#3B82F6', text=l1_s['销售数量'], textposition='auto'))
    fig_l1.add_trace(go.Bar(x=l1_s['一级分类'], y=l1_s['销售金额'], name='营收', marker_color='#10B981', text=l1_s['销售金额'].apply(lambda x:f"¥{x:,.0f}"), textposition='auto'))
    fig_l1.update_layout(barmode='group', height=350, margin=dict(l=10,r=10,t=30,b=10), plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_l1, use_container_width=True)

    # 3. 二级三剑客
    st.markdown("---")
    st.subheader("📈 二级分类精细拆解 (独立看板)")
    cat_df = df_cur.groupby('二级分类').agg({'销售数量':'sum', '销售金额':'sum'}).reset_index()
    cat_df['占比'] = (cat_df['销售金额'] / cat_df['销售金额'].sum() * 100).round(1)
    cat_df = cat_df.sort_values('销售数量', ascending=False)

    with st.container(border=True):
        st.plotly_chart(px.bar(cat_df, x='二级分类', y='销售数量', title="销量对比排行", text='销售数量', color_discrete_sequence=['#3B82F6']).update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)"), use_container_width=True)
    with st.container(border=True):
        st.plotly_chart(px.bar(cat_df, x='二级分类', y='销售金额', title="营收对比排行", text=cat_df['销售金额'].apply(lambda x:f"¥{x:,.0f}"), color_discrete_sequence=['#10B981']).update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)"), use_container_width=True)
    with st.container(border=True):
        st.plotly_chart(px.bar(cat_df, x='二级分类', y='占比', title="业绩贡献占比 (%)", text=cat_df['占比'].apply(lambda x:f"{x}%"), color_discrete_sequence=['#F59E0B']).update_layout(height=350, plot_bgcolor="rgba(0,0,0,0)"), use_container_width=True)

    st.markdown("### 📄 单品销售实绩排行")
    v_df = df_cur.groupby(['商品名称'], as_index=False).agg({'一级分类':'first', '二级分类':'first', '销售数量':'sum', '销售金额':'sum'}).sort_values('销售数量', ascending=False)
    st.dataframe(v_df[['商品名称','一级分类','二级分类','销售数量','销售金额']], use_container_width=True, hide_index=True)

# =============================================================================
# 5. Page - 成本与配方中心
# =============================================================================
def page_recipe_management():
    st.title("⚙️ 三级原物料与配方引擎")
    t1, t2, t3 = st.tabs(["📦 基础原物料库", "📋 配置单品配方 (稳健构建模式)", "📚 成本卡库管理"])
    
    with t1:
        f = st.file_uploader("导入价格档", type=["xlsx", "csv"])
        if f:
            df_up = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            df_up.columns = [str(c).strip() for c in df_up.columns]
            ex = {'物流名称': '物料名称', '品项类别': '品项类别', '单价单位': '单位', '物流单价成本': '物流单价', '顿角单价成本': '顿角单价', '百度单价成本': '百度单价'}
            df_up = df_up.rename(columns={c: ex[c] for c in df_up.columns if c in ex})
            if '物料名称' in df_up.columns:
                for p in ['物流单价', '顿角单价', '百度单价']:
                    if p in df_up.columns: df_up[p] = pd.to_numeric(df_up[p], errors='coerce').fillna(0)
                conn = get_db_conn(); df_up[['物料名称', '品项类别', '单位', '物流单价', '顿角单价', '百度单价']].to_sql('raw_materials', conn, if_exists='replace', index=False); conn.close(); st.success("同步完成"); st.rerun()
        c = get_db_conn(); st.dataframe(pd.read_sql("SELECT * FROM raw_materials", c), use_container_width=True, hide_index=True); c.close()

    with t2:
        conn = get_db_conn()
        try:
            df_opt = pd.read_sql("SELECT DISTINCT 商品名称, 规格, 做法, 门店名称 FROM sales_raw", conn)
            stores = sorted(df_opt['门店名称'].unique().tolist())
            rmats = sorted(pd.read_sql("SELECT 物料名称 FROM raw_materials", conn)['物料名称'].tolist())
        except: df_opt = pd.DataFrame(); stores = []; rmats = []
        
        if df_opt.empty: st.warning("请在看板导入流水数据。"); return
        
        c_tr, c_sc = st.columns(2)
        db_t = '物流' if '物流' in c_tr.radio("计算轨道", ["📦 物流配方", "🏪 门店配方"]) else '门店'
        scope = c_sc.selectbox("适用范围", ["【全局默认配方】", "百度项目", "顿角项目"] + stores)
        
        st.divider()
        c_p, c_s, c_m = st.columns(3)
        p = c_p.selectbox("饮品", sorted(df_opt['商品名称'].unique().tolist()))
        s = c_s.selectbox("规格", sorted(df_opt[df_opt['商品名称']==p]['规格'].unique().tolist()) if '规格' in df_opt.columns else ['常规'])
        m = c_m.selectbox("做法", sorted(df_opt[(df_opt['商品名称']==p)]['做法'].unique().tolist()) if '做法' in df_opt.columns else ['常规'])
        
        if 'active_prod_builder' not in st.session_state: st.session_state.active_prod_builder = p
        if 'bom_rows_buffer' not in st.session_state: st.session_state.bom_rows_buffer = []

        if st.session_state.active_prod_builder != p:
            if st.session_state.bom_rows_buffer:
                if st.button("🗑️ 切换了商品，清空当前行"):
                    st.session_state.bom_rows_buffer = []; st.session_state.active_prod_builder = p; st.rerun()
            else: st.session_state.active_prod_builder = p

        if st.button("📥 载入数据库现有配方作为模板"):
            db_d = pd.read_sql("SELECT 物料名称, 用量 FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", conn, params=(db_t, scope, p, s, m))
            if not db_d.empty: st.session_state.bom_rows_buffer = db_d.to_dict('records'); st.rerun()
            else: st.toast("无配方")

        new_rows = []
        for i, row in enumerate(st.session_state.bom_rows_buffer):
            with st.container(border=True):
                r_cols = st.columns([1, 4, 3, 1])
                r_cols[0].markdown(f"**#{i+1}**")
                m_idx = rmats.index(row['物料名称']) if row['物料名称'] in rmats else 0
                m_val = r_cols[1].selectbox(f"物料", rmats, index=m_idx, key=f"msel_{i}")
                q_val = r_cols[2].number_input(f"用量", value=float(row['用量']), step=1.0, key=f"qsel_{i}")
                new_rows.append({'物料名称': m_val, '用量': q_val})
                if r_cols[3].button("🗑️", key=f"drow_{i}"):
                    st.session_state.bom_rows_buffer.pop(i); st.rerun()
        
        st.session_state.bom_rows_buffer = new_rows
        c_b1, c_b2, _ = st.columns([2, 2, 4])
        if c_b1.button("➕ 新增配方行", use_container_width=True):
            st.session_state.bom_rows_buffer.append({'物料名称': rmats[0] if rmats else "", '用量': 0.0}); st.rerun()
        if c_b2.button("🧹 清空所有行", use_container_width=True):
            st.session_state.bom_rows_buffer = []; st.rerun()

        if st.button(f"💾 保存到【{scope}】", type="primary", use_container_width=True):
            valid_save = [r for r in st.session_state.bom_rows_buffer if r['用量'] > 0]
            if valid_save:
                save_df = pd.DataFrame(valid_save).groupby('物料名称', as_index=False)['用量'].sum()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=?", (db_t, scope, p, s, m))
                for _, r in save_df.iterrows():
                    cursor.execute("INSERT INTO bom_recipes VALUES (?,?,?,?,?,?,?)", (db_t, scope, p, s, m, r['物料名称'], r['用量']))
                conn.commit(); st.success("✅ 保存成功！"); st.rerun()
            else: st.error("内容为空")
        conn.close()

    with t3:
        st.markdown("#### 📚 成本卡库管理与预览")
        conn = get_db_conn()
        db_b = pd.read_sql("SELECT * FROM bom_recipes", conn)
        db_r = pd.read_sql("SELECT * FROM raw_materials", conn)
        if not db_b.empty:
            lib = db_b.merge(db_r, on='物料名称', how='left').fillna(0)
            lib['lv'] = lib['用量'] * lib['物流单价']; lib['dv'] = lib['用量'] * lib['顿角单价']; lib['bv'] = lib['用量'] * lib['百度单价']
            f_sc = st.multiselect("🔍 按【范围】筛选", sorted(lib['适用范围'].unique().tolist()))
            if f_sc: lib = lib[lib['适用范围'].isin(f_sc)]
            grps = lib.groupby(['配方类型', '适用范围', '商品名称', '规格', '做法'])
            for (rt, sc, pdn, spc, mth), items in grps:
                with st.container(border=True):
                    sc_disp = f'<span class="scope-badge">{sc}</span>' if sc != '【全局默认配方】' else f'({sc})'
                    st.markdown(f'<div class="recipe-card-header"><b>【{rt}】{pdn}</b> ({spc}/{mth}) {sc_disp}</div>', unsafe_allow_html=True)
                    st.markdown(f'<span class="cost-tag">📦出厂:¥{items["lv"].sum():.2f}</span><span class="cost-tag">🏬顿角:¥{items["dv"].sum():.2f}</span><span class="cost-tag">🏢百度:¥{items["bv"].sum():.2f}</span>', unsafe_allow_html=True)
                    if st.button("🗑️ 删除整卡", key=f"df_{rt}_{sc}_{pdn}_{spc}_{mth}", type="primary"):
                        conn.execute("DELETE FROM bom_recipes WHERE 配方类型=? AND 适用范围=? AND 商品名称=? AND 规格=? AND 做法=? ", (rt, sc, pdn, spc, mth))
                        conn.commit(); st.rerun()
                    st.write("🌿 包含: " + " 、 ".join([f"{r['物料名称']}({r['用量']}g)" for _,r in items.iterrows()]))
        conn.close()

# =============================================================================
# 6. 程序入口
# =============================================================================
if __name__ == "__main__":
    init_ui_styles()
    init_db()
    app_mode = st.sidebar.radio("🧭 系统导航", ["📊 经营分析看板", "⚙️ 成本与配方中心"])
    if app_mode == "📊 经营分析看板":
        page_analytics_dashboard()
    else:
        page_recipe_management()
