# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import json
import re
from datetime import datetime, timedelta

# =============================================================================
# 1. 核心驱动与可视化库
# =============================================================================
try:
    from google.cloud import firestore
    from google.oauth2 import service_account
    import plotly.express as px
    import plotly.graph_objects as go
    LIBS_READY = True
except Exception as e:
    st.error(f"❌ 驱动库加载失败: {e}")
    LIBS_READY = False

# =============================================================================
# 2. 后端：云数据库管理器
# =============================================================================
class CloudDataManager:
    def __init__(self):
        self.db = None
        self.err = None
        try:
            if "textkey" not in st.secrets:
                self.err = "未配置 Secrets 钥匙"
                return
            raw_key = st.secrets["textkey"]
            key_dict = json.loads(raw_key) if isinstance(raw_key, str) else dict(raw_key)
            creds = service_account.Credentials.from_service_account_info(key_dict)
            self.db = firestore.Client(credentials=creds, project=key_dict['project_id'])
        except Exception as e:
            self.err = str(e)

    def save_sales(self, df):
        if not self.db: return
        coll = self.db.collection("sales_records")
        for _, row in df.iterrows():
            # 唯一特征ID：日期_门店_商品_规格_做法
            doc_id = f"{row['统计周期']}_{row['门店名称']}_{row['商品名称']}_{row['规格']}_{row['做法']}"
            doc_id = doc_id.replace("/", "_").replace(" ", "").replace(":", "")
            coll.document(doc_id).set(row.to_dict())

    def fetch_sales(self, start, end):
        if not self.db: return pd.DataFrame()
        try:
            # 采用全量抓取+本地过滤，确保中文字段兼容性 100%
            docs = self.db.collection("sales_records").stream()
            full_df = pd.DataFrame([d.to_dict() for d in docs])
            if full_df.empty: return full_df
            return full_df[(full_df['统计周期'] >= start) & (full_df['统计周期'] <= end)]
        except:
            return pd.DataFrame()

    def save_material(self, df):
        if not self.db: return
        for _, row in df.iterrows():
            self.db.collection("materials").document(row['物料名称']).set(row.to_dict())

    def get_materials(self):
        if not self.db: return pd.DataFrame()
        return pd.DataFrame([d.to_dict() for d in self.db.collection("materials").stream()])

    def store_recipe(self, tk, sc, pr, sp, me, items):
        if not self.db: return
        cid = f"{tk}_{sc}_{pr}_{sp}_{me}".replace("/", "_").replace(" ", "")
        self.db.collection("recipes").document(cid).set({
            "track": tk, "scope": sc, "product": pr, "spec": sp, "method": me,
            "items": items, "updated_at": datetime.now()
        })

    def get_recipes(self):
        if not self.db: return []
        return [d.to_dict() for d in self.db.collection("recipes").stream()]

# =============================================================================
# 3. 逻辑计算引擎 (映射与清洗)
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
    {"一级分类": "咖啡饮品", "二级分类": "风味拿铁"}, {"一级分类": "咖啡饮品", "二级分类": "SOE冷萃"},
    {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"}, {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"},
    {"一级分类": "非咖啡饮品", "二级分类": "经典鲜果茶"}, {"一级分类": "非咖啡饮品", "二级分类": "手打柠"}
]

def logic_parse_days(date_series):
    if date_series.empty: return 1
    sample = str(date_series.iloc[0])
    match = re.search(r'(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})', sample)
    if match:
        try:
            d1, d2 = datetime.strptime(match.group(1), '%Y-%m-%d'), datetime.strptime(match.group(2), '%Y-%m-%d')
            return max(1, (d2 - d1).days + 1)
        except: pass
    return max(1, date_series.nunique())

def logic_clean_sales(df):
    if df.empty: return df
    # 1. 项目映射
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(str(x).strip(), '其他项目'))
    
    # 2. 品类映射
    df_cat = pd.DataFrame(CATEGORY_MAPPING)
    if '一级分类' in df.columns: df = df.drop(columns=['一级分类'])
    if '二级分类' in df.columns: df = df.drop(columns=['二级分类'])
    
    df['商品类别_clean'] = df['商品类别'].astype(str).str.strip()
    df = pd.merge(df, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('其他')
    df['二级分类'] = df['二级分类'].fillna('其他')
    return df

# =============================================================================
# 4. 前端视图层 (精装修样式)
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡智能经营系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            padding: 25px !important;
            border-radius: 20px !important;
            border: 1px solid #E2E8F0 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        }
        .recipe-card {
            background: #FFFFFF;
            padding: 18px;
            border-radius: 15px;
            border-left: 6px solid #3B82F6;
            margin-bottom: 12px;
            border: 1px solid #F1F5F9;
        }
    </style>
    """, unsafe_allow_html=True)

def view_dashboard(db):
    st.title("📊 顿角咖啡·智能经营看板")
    
    # --- 侧边栏：同步功能 ---
    with st.sidebar.expander("💾 数据同步中心", expanded=False):
        files = st.file_uploader("📥 上传企迈报表", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            for f in files:
                df_u = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                df_u.columns = [str(c).strip() for c in df_u.columns]
                m = {'商品实收': '销售金额', '商品销量': '销售数量', '日期': '统计周期', '商品分类': '商品类别'}
                df_u = df_u.rename(columns={k: v for k, v in m.items() if k in df_u.columns})
                db.save_sales(df_u)
            st.success("✅ 同步至云端！")
            st.rerun()

    # --- 侧边栏：核心筛选器 ---
    st.sidebar.subheader("🔍 数据筛选")
    dr = st.sidebar.date_input("分析周期", [datetime.now() - timedelta(days=7), datetime.now()])
    
    if len(dr) == 2:
        df_raw = db.fetch_sales(dr[0].strftime('%Y-%m-%d'), dr[1].strftime('%Y-%m-%d'))
        if df_raw.empty:
            st.info("💡 云端暂无数据，请先同步报表。")
            return
        
        df = logic_clean_sales(df_raw)
        
        # 1. 项目与门店筛选
        all_projs = sorted(df['所属项目'].unique())
        sel_proj = st.sidebar.multiselect("所属项目", all_projs, default=all_projs)
        
        filtered_df = df[df['所属项目'].isin(sel_proj)]
        all_stores = sorted(filtered_df['门店名称'].unique())
        sel_store = st.sidebar.multiselect("门店名称", all_stores, default=all_stores)
        
        # 2. 分类筛选
        all_l1 = sorted(filtered_df['一级分类'].unique())
        sel_l1 = st.sidebar.multiselect("一级分类", all_l1, default=all_l1)
        
        filtered_df = filtered_df[filtered_df['一级分类'].isin(sel_l1)]
        all_l2 = sorted(filtered_df['二级分类'].unique())
        sel_l2 = st.sidebar.multiselect("二级分类", all_l2, default=all_l2)
        
        # 最终视图数据
        df_view = filtered_df[(filtered_df['门店名称'].isin(sel_store)) & (filtered_df['二级分类'].isin(sel_l2))]
        
        # --- 核心指标展示 ---
        q, a = df_view['销售数量'].sum(), df_view['销售金额'].sum()
        days = logic_parse_days(df_view['统计周期'])
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总杯数", f"{q:,.0f} 杯")
        c2.metric("总营收", f"¥{a:,.2f}")
        c3.metric("日均营收", f"¥{a/days:,.2f}")
        c4.metric("单杯均价", f"¥{a/q if q>0 else 0:.2f}")

        # --- 图表展示 ---
        st.divider()
        col_l, col_r = st.columns([3, 2])
        with col_l:
            st.subheader("🏗️ 项目销售分布")
            proj_sum = df_view.groupby('所属项目')['销售金额'].sum().reset_index()
            fig = px.bar(proj_sum, x='所属项目', y='销售金额', color_discrete_sequence=['#3B82F6'], template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
        with col_r:
            st.subheader("📈 细分品类占比")
            cat_sum = df_view.groupby('二级分类')['销售金额'].sum().reset_index()
            st.plotly_chart(px.pie(cat_sum, values='销售金额', names='二级分类', hole=0.4), use_container_width=True)

        st.subheader("📋 单品销量榜单")
        rank = df_view.groupby(['商品名称', '规格', '做法']).agg({'销售数量':'sum', '销售金额':'sum'}).sort_values('销售数量', ascending=False)
        st.dataframe(rank, use_container_width=True)

def view_recipes(db):
    st.title("⚙️ 成本与配方中心")
    t1, t2, t3 = st.tabs(["📦 原物料记忆库", "📋 配置构建器", "📚 云端卡库"])
    
    with t1:
        f = st.file_uploader("同步单价档案", type=["xlsx", "csv"])
        if f:
            df_m = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            db.save_material(df_m)
            st.success("✅ 云端单价已更新")
        st.dataframe(db.get_materials(), use_container_width=True, hide_index=True)

    with t2:
        m_df = db.get_materials()
        rmats = sorted(m_df['物料名称'].tolist()) if not m_df.empty else []
        if not rmats: st.warning("请先同步原物料库。"); return
        
        c1, c2 = st.columns(2)
        tk = c1.radio("核算轨道", ["📦 物流", "🏪 门店"])
        sc = c2.selectbox("适用项目", ["【全局】", "百度项目", "顿角项目", "光大项目"])
        
        p1, p2, p3 = st.columns(3)
        p_name = p1.text_input("饮品名")
        p_spec = p2.selectbox("规格", ["中杯", "大杯", "常规"])
        p_meth = p3.selectbox("做法", ["去冰", "热", "正常"])

        if 'ui_rows' not in st.session_state: st.session_state.ui_rows = []
        
        new_list = []
        for i, row in enumerate(st.session_state.ui_rows):
            with st.container(border=True):
                r_cols = st.columns([1, 4, 3, 1])
                idx = rmats.index(row['物料名称']) if row['物料名称'] in rmats else 0
                m_val = r_cols[1].selectbox(f"物料", rmats, index=idx, key=f"mat_{i}")
                q_val = r_cols[2].number_input(f"克数", value=float(row['用量']), key=f"qty_{i}")
                new_list.append({'物料名称': m_val, '用量': q_val})
                if r_cols[3].button("🗑️", key=f"del_{i}"):
                    st.session_state.ui_rows.pop(i); st.rerun()
        
        st.session_state.ui_rows = new_list
        if st.button("➕ 新增物料行", use_container_width=True):
            st.session_state.ui_rows.append({'物料名称': rmats[0], '用量': 0.0}); st.rerun()
        
        if st.button("💾 确认保存并同步", type="primary", use_container_width=True):
            clean = [r for r in st.session_state.ui_rows if r['用量'] > 0]
            if clean:
                db.store_recipe(tk, sc, p_name, p_spec, p_meth, clean)
                st.success("✅ 配方已存入云端！")

    with t3:
        for r in db.get_recipes():
            with st.container():
                st.markdown(f"""<div class='recipe-card'>
                    <b>【{r['track']}】{r['product']}</b> ({r['spec']}/{r['method']}) <span style='font-size:12px; color:#64748B;'>{r['scope']}</span><br>
                    <small>🌿 配方：{" 、 ".join([f"{i['物料名称']}({i['用量']}g)" for i in r['items']])}</small>
                </div>""", unsafe_allow_html=True)

# =============================================================================
# 5. 入口
# =============================================================================
if __name__ == "__main__":
    init_ui()
    if LIBS_READY:
        db_mgr = CloudDataManager()
        
        # 侧边栏状态
        if db_mgr.db:
            st.sidebar.markdown('<div style="background-color:#DCFCE7; color:#166534; padding:10px; border-radius:10px; text-align:center; font-weight:600; margin-bottom:20px;">✅ 云数据库已联通</div>', unsafe_allow_html=True)
        else:
            st.sidebar.warning(f"🔒 云端待连接: {db_mgr.err}")

        mode = st.sidebar.radio("功能导航", ["📊 经营看板", "⚙️ 配方中心"])
        if mode == "📊 经营看板": view_dashboard(db_mgr)
        else: view_recipes(db_mgr)
