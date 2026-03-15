# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import json
import re
from datetime import datetime, timedelta

# =============================================================================
# 1. 核心驱动加载与缓存
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

@st.cache_resource
def get_db_client():
    """缓存数据库连接对象，避免重复初始化"""
    try:
        if "textkey" not in st.secrets:
            return None
        raw_key = st.secrets["textkey"]
        key_dict = json.loads(raw_key) if isinstance(raw_key, str) else dict(raw_key)
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds, project=key_dict['project_id'])
    except:
        return None

# =============================================================================
# 2. 增强型云数据库管理 (带缓存逻辑)
# =============================================================================
class CloudDataManager:
    def __init__(self):
        self.db = get_db_client()

    @st.cache_data(ttl=600)  # 🌟 缓存 10 分钟：防止频繁刷新耗尽云端额度
    def _fetch_all_sales(_self):
        if not _self.db: return pd.DataFrame()
        try:
            docs = _self.db.collection("sales_records").stream()
            return pd.DataFrame([d.to_dict() for d in docs])
        except Exception as e:
            st.error(f"☁️ 读取销售流水失败: {e}")
            return pd.DataFrame()

    @st.cache_data(ttl=600)
    def _fetch_all_materials(_self):
        if not _self.db: return pd.DataFrame()
        try:
            docs = _self.db.collection("materials").stream()
            return pd.DataFrame([d.to_dict() for d in docs])
        except:
            return pd.DataFrame()

    def save_sales(self, df):
        if not self.db: return
        coll = self.db.collection("sales_records")
        for _, row in df.iterrows():
            doc_id = f"{row['统计周期']}_{row['门店名称']}_{row['商品名称']}_{row['规格']}_{row['做法']}"
            doc_id = doc_id.replace("/", "_").replace(" ", "").replace(":", "")
            coll.document(doc_id).set(row.to_dict())
        st.cache_data.clear() # 🌟 重要：上传新数据后清空缓存

    def store_recipe(self, tk, sc, pr, sp, me, items):
        if not self.db: return
        cid = f"{tk}_{sc}_{pr}_{sp}_{me}".replace("/", "_").replace(" ", "")
        self.db.collection("recipes").document(cid).set({
            "track": tk, "scope": sc, "product": pr, "spec": sp, "method": me,
            "items": items, "updated_at": datetime.now()
        })
        st.cache_data.clear()

    def get_sales_view(self, start, end):
        df = self._fetch_all_sales()
        if df.empty: return df
        return df[(df['统计周期'] >= start) & (df['统计周期'] <= end)]

    def get_materials(self):
        return self._fetch_all_materials()

    def get_recipes(self):
        if not self.db: return []
        try:
            return [d.to_dict() for d in self.db.collection("recipes").stream()]
        except:
            return []

# =============================================================================
# 3. 逻辑计算引擎
# =============================================================================
PROJECT_STORE_MAPPING = {
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"],
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"]
}

CATEGORY_MAPPING = [
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "咖啡饮品", "二级分类": "拿铁家族"}, {"一级分类": "咖啡饮品", "二级分类": "奶咖家族"},
    {"一级分类": "咖啡饮品", "二级分类": "果C美式"}, {"一级分类": "咖啡饮品", "二级分类": "手冲咖啡"},
    {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"}, {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"}
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
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(str(x).strip(), '其他项目'))
    df_cat = pd.DataFrame(CATEGORY_MAPPING)
    for col in ['一级分类', '二级分类']:
        if col in df.columns: df = df.drop(columns=[col])
    df['商品类别_clean'] = df['商品类别'].astype(str).str.strip()
    df = pd.merge(df, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('其他')
    df['二级分类'] = df['二级分类'].fillna('其他')
    return df

# =============================================================================
# 4. 前端视图层
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡智能分析系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        section[data-testid="stSidebar"] div.stVerticalBlock { padding-top: 3.5rem !important; }
        div[data-testid="stMetric"] { background-color: #FFFFFF; padding: 25px !important; border-radius: 20px !important; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
        .recipe-card { background: #FFFFFF; padding: 18px; border-radius: 15px; border-left: 6px solid #3B82F6; margin-bottom: 12px; border: 1px solid #F1F5F9; }
    </style>
    """, unsafe_allow_html=True)

def view_dashboard(db):
    st.title("📊 顿角咖啡·智能经营看板")
    
    with st.sidebar.expander("💾 云端同步中心", expanded=False):
        files = st.file_uploader("📥 上传报表", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            with st.spinner("数据正在存入云端，请稍候..."):
                for f in files:
                    df_u = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                    df_u.columns = [str(c).strip() for c in df_u.columns]
                    m = {'商品实收': '销售金额', '商品销量': '销售数量', '日期': '统计周期', '商品分类': '商品类别'}
                    df_u = df_u.rename(columns={k: v for k, v in m.items() if k in df_u.columns})
                    db.save_sales(df_u)
                st.success("✅ 云端同步完成并已刷新缓存！")
                st.rerun()

    st.sidebar.markdown("### 🔍 数据筛选")
    dr = st.sidebar.date_input("分析周期", [datetime.now() - timedelta(days=7), datetime.now()])
    
    if len(dr) == 2:
        with st.spinner("正在从云端调取数据..."):
            df_raw = db.get_sales_view(dr[0].strftime('%Y-%m-%d'), dr[1].strftime('%Y-%m-%d'))
        
        if df_raw.empty:
            st.info("💡 云端暂无数据，请先上传报表。")
            return
        
        df_clean = logic_clean_sales(df_raw)
        
        # 筛选联动逻辑 (不选即全选)
        all_projs = sorted(df_clean['所属项目'].unique())
        sel_proj = st.sidebar.multiselect("所属项目", all_projs)
        df_temp = df_clean if not sel_proj else df_clean[df_clean['所属项目'].isin(sel_proj)]
        
        all_stores = sorted(df_temp['门店名称'].unique())
        sel_store = st.sidebar.multiselect("门店名称", all_stores)
        
        all_l1 = sorted(df_temp['一级分类'].unique())
        sel_l1 = st.sidebar.multiselect("一级分类", all_l1)
        
        df_temp2 = df_temp if not sel_l1 else df_temp[df_temp['一级分类'].isin(sel_l1)]
        all_l2 = sorted(df_temp2['二级分类'].unique())
        sel_l2 = st.sidebar.multiselect("二级分类", all_l2)
        
        df_view = df_clean.copy()
        if sel_proj: df_view = df_view[df_view['所属项目'].isin(sel_proj)]
        if sel_store: df_view = df_view[df_view['门店名称'].isin(sel_store)]
        if sel_l1: df_view = df_view[df_view['一级分类'].isin(sel_l1)]
        if sel_l2: df_view = df_view[df_view['二级分类'].isin(sel_l2)]
        
        if df_view.empty:
            st.warning("⚠️ 筛选组合下无数据。")
            return

        q, a = df_view['销售数量'].sum(), df_view['销售金额'].sum()
        days = logic_parse_days(df_view['统计周期'])
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总杯数", f"{q:,.0f} 杯")
        c2.metric("总营收", f"¥{a:,.2f}")
        c3.metric("日均营收", f"¥{a/days:,.2f}")
        c4.metric("单杯均价", f"¥{a/q if q>0 else 0:.2f}")

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

        st.subheader("📋 单品表现详情")
        rank = df_view.groupby(['商品名称', '规格', '做法']).agg({'销售数量':'sum', '销售金额':'sum'}).sort_values('销售数量', ascending=False)
        st.dataframe(rank, use_container_width=True)

def view_recipes(db):
    st.title("⚙️ 成本与配方中心")
    t1, t2, t3 = st.tabs(["📦 原物料记忆库", "📋 配置构建器", "📚 云端卡库"])
    
    with t1:
        f = st.file_uploader("同步价格档案", type=["xlsx", "csv"])
        if f:
            df_m = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            db.save_material(df_m)
            st.success("✅ 云端价格已更新并清空缓存！")
        st.dataframe(db.get_materials(), use_container_width=True, hide_index=True)

    with t2:
        m_df = db.get_materials()
        rmats = sorted(m_df['物料名称'].tolist()) if not m_df.empty else []
        if not rmats: st.warning("请先同步原物料库。"); return
        
        c1, c2 = st.columns(2)
        tk = c1.radio("核算轨道", ["📦 物流", "🏪 门店"])
        sc = c2.selectbox("适用范围", ["【全局】", "百度项目", "顿角项目", "光大项目"])
        
        p_name = st.text_input("饮品名")
        
        if 'bom_rows' not in st.session_state: st.session_state.bom_rows = []
        new_list = []
        for i, row in enumerate(st.session_state.bom_rows):
            with st.container(border=True):
                r_cols = st.columns([1, 4, 3, 1])
                idx = rmats.index(row['物料名称']) if row['物料名称'] in rmats else 0
                m_val = r_cols[1].selectbox(f"物料", rmats, index=idx, key=f"mat_{i}")
                q_val = r_cols[2].number_input(f"克数", value=float(row['用量']), key=f"qty_{i}")
                new_list.append({'物料名称': m_val, '用量': q_val})
                if r_cols[3].button("🗑️", key=f"del_{i}"):
                    st.session_state.bom_rows.pop(i); st.rerun()
        st.session_state.bom_rows = new_list
        if st.button("➕ 新增物料行", use_container_width=True):
            st.session_state.bom_rows.append({'物料名称': rmats[0], '用量': 0.0}); st.rerun()
        if st.button("💾 确认保存并同步", type="primary", use_container_width=True):
            clean = [r for r in st.session_state.bom_rows if r['用量'] > 0]
            if clean:
                db.store_recipe(tk, sc, p_name, "常规", "正常", clean)
                st.success("✅ 配方已存入云端！")

    with t3:
        recipes = db.get_recipes()
        for r in recipes:
            with st.container():
                st.markdown(f"""<div class='recipe-card'>
                    <b>{r['product']}</b> <span style='font-size:12px; color:#64748B;'>{r['scope']}</span><br>
                    <small>🌿 配方：{" 、 ".join([f"{i['物料名称']}({i['用量']}g)" for i in r['items']])}</small>
                </div>""", unsafe_allow_html=True)

if __name__ == "__main__":
    init_ui()
    if LIBS_READY:
        db_mgr = CloudDataManager()
        if db_mgr.db:
            st.sidebar.markdown('<div style="background-color:#DCFCE7; color:#166534; padding:10px; border-radius:10px; text-align:center; font-weight:600; margin-bottom:20px;">✅ 云端数据库已联通</div>', unsafe_allow_html=True)
        else:
            st.sidebar.warning("🔒 钥匙未激活或额度耗尽")
        mode = st.sidebar.radio("功能导航", ["📊 经营看板", "⚙️ 配方中心"])
        if mode == "📊 经营看板": view_dashboard(db_mgr)
        else: view_recipes(db_mgr)
