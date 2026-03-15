# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import json
import re
from datetime import datetime, timedelta

# =============================================================================
# 1. 核心驱动与缓存机制 (锁定查询压力)
# =============================================================================
try:
    from google.cloud import firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
    from google.oauth2 import service_account
    import plotly.express as px
    import plotly.graph_objects as go
    LIBS_READY = True
except Exception as e:
    st.error(f"❌ 核心驱动加载失败: {e}")
    LIBS_READY = False

@st.cache_resource
def get_db_client():
    """缓存数据库连接，避免重复握手"""
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
# 2. 增强型云数据库管理 (按需读取策略)
# =============================================================================
class CloudDataManager:
    def __init__(self):
        self.db = get_db_client()

    @st.cache_data(ttl=3600)  # 🌟 缓存 1 小时，大幅减少读取次数
    def fetch_sales_range(_self, start_str, end_str):
        """
        🌟 核心优化：只读取选定日期范围内的数据
        这会将配额消耗从 '全量' 降至 '极少量'
        """
        if not _self.db: return pd.DataFrame()
        try:
            # 在云端直接进行过滤，不下载无关数据
            query = _self.db.collection("sales_records")\
                .where(filter=FieldFilter("统计周期", ">=", start_str))\
                .where(filter=FieldFilter("统计周期", "<=", end_str))
            
            docs = query.stream()
            data = [d.to_dict() for d in docs]
            return pd.DataFrame(data)
        except Exception as e:
            # 如果配额已耗尽，这里会捕获错误并提示
            if "429" in str(e):
                st.error("🚨 Google 云端配方读取额度已耗尽 (Daily Limit Reached)。请等待几小时或明日再试。")
            else:
                st.error(f"☁️ 读取失败: {e}")
            return pd.DataFrame()

    @st.cache_data(ttl=3600)
    def get_materials(_self):
        if not _self.db: return pd.DataFrame()
        try:
            docs = _self.db.collection("materials").stream()
            return pd.DataFrame([d.to_dict() for d in docs])
        except:
            return pd.DataFrame()

    def save_sales(self, df):
        """保存数据并清空本地缓存以获取最新视图"""
        if not self.db: return
        coll = self.db.collection("sales_records")
        for _, row in df.iterrows():
            doc_id = f"{row['统计周期']}_{row['门店名称']}_{row['商品名称']}_{row['规格']}_{row['做法']}"
            doc_id = doc_id.replace("/", "_").replace(" ", "").replace(":", "")
            coll.document(doc_id).set(row.to_dict())
        st.cache_data.clear()

    def get_recipes(self):
        if not self.db: return []
        try:
            return [d.to_dict() for d in self.db.collection("recipes").stream()]
        except:
            return []

    def store_recipe(self, tk, sc, pr, sp, me, items):
        if not self.db: return
        cid = f"{tk}_{sc}_{pr}_{sp}_{me}".replace("/", "_").replace(" ", "")
        self.db.collection("recipes").document(cid).set({
            "track": tk, "scope": sc, "product": pr, "spec": sp, "method": me,
            "items": items, "updated_at": datetime.now()
        })
        st.cache_data.clear()

# =============================================================================
# 3. 逻辑与前端映射
# =============================================================================
PROJECT_STORE_MAPPING = {
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "联想总部店", "顿角咖啡研发中心店[高科岭]"]
}

CATEGORY_MAPPING = [
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "咖啡饮品", "二级分类": "拿铁家族"}, {"一级分类": "咖啡饮品", "二级分类": "奶咖家族"},
    {"一级分类": "咖啡饮品", "二级分类": "果C美式"}, {"一级分类": "咖啡饮品", "二级分类": "手冲咖啡"},
    {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"}, {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"}
]

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

def init_ui():
    st.set_page_config(page_title="顿角咖啡智能分析系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        section[data-testid="stSidebar"] div.stVerticalBlock { padding-top: 3.5rem !important; }
        div[data-testid="stMetric"] { background-color: #FFFFFF; padding: 25px !important; border-radius: 20px !important; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
    </style>
    """, unsafe_allow_html=True)

def view_dashboard(db):
    st.title("📊 顿角咖啡·智能经营看板")
    
    with st.sidebar.expander("💾 云端同步中心", expanded=False):
        files = st.file_uploader("📥 上传报表", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            with st.spinner("同步中..."):
                for f in files:
                    df_u = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                    df_u.columns = [str(c).strip() for c in df_u.columns]
                    m = {'商品实收': '销售金额', '商品销量': '销售数量', '日期': '统计周期', '商品分类': '商品类别'}
                    df_u = df_u.rename(columns={k: v for k, v in m.items() if k in df_u.columns})
                    db.save_sales(df_u)
                st.success("✅ 云端已同步！")
                st.rerun()

    st.sidebar.markdown("### 🔍 数据筛选")
    dr = st.sidebar.date_input("分析周期", [datetime.now() - timedelta(days=7), datetime.now()])
    
    if len(dr) == 2:
        with st.spinner("调取云端数据..."):
            df_raw = db.fetch_sales_range(dr[0].strftime('%Y-%m-%d'), dr[1].strftime('%Y-%m-%d'))
        
        if df_raw.empty:
            st.info("💡 选定日期内云端暂无数据，请尝试调整日期或上传报表。")
            return
        
        df_clean = logic_clean_sales(df_raw)
        
        # 联动筛选
        all_projs = sorted(df_clean['所属项目'].unique())
        sel_proj = st.sidebar.multiselect("所属项目", all_projs)
        df_temp = df_clean if not sel_proj else df_clean[df_clean['所属项目'].isin(sel_proj)]
        
        all_stores = sorted(df_temp['门店名称'].unique())
        sel_store = st.sidebar.multiselect("门店名称", all_stores)
        
        all_l1 = sorted(df_temp['一级分类'].unique())
        sel_l1 = st.sidebar.multiselect("一级分类", all_l1)
        
        df_view = df_clean.copy()
        if sel_proj: df_view = df_view[df_view['所属项目'].isin(sel_proj)]
        if sel_store: df_view = df_view[df_view['门店名称'].isin(sel_store)]
        if sel_l1: df_view = df_view[df_view['一级分类'].isin(sel_l1)]
        
        q, a = df_view['销售数量'].sum(), df_view['销售金额'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总销售杯数", f"{q:,.0f} 杯")
        c2.metric("总营收金额", f"¥{a:,.2f}")
        c3.metric("营收贡献占比", f"{a/(df_clean['销售金额'].sum())*100:.1f}%")
        c4.metric("单杯平均价", f"¥{a/q if q>0 else 0:.2f}")

        st.divider()
        st.subheader("📋 筛选数据详情")
        st.dataframe(df_view.groupby('商品名称').agg({'销售数量':'sum', '销售金额':'sum'}).sort_values('销售数量', ascending=False), use_container_width=True)

def view_recipes(db):
    st.title("⚙️ 成本与配方中心")
    t1, t2, t3 = st.tabs(["原物料库", "配方编辑器", "云端卡库"])
    
    with t1:
        f = st.file_uploader("同步单价", type=["xlsx", "csv"])
        if f:
            df_m = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            db.save_material(df_m)
            st.success("✅ 单价同步成功")
        st.dataframe(db.get_materials(), use_container_width=True, hide_index=True)

    with t2:
        m_df = db.get_materials()
        rmats = sorted(m_df['物料名称'].tolist()) if not m_df.empty else []
        if not rmats: st.warning("请先同步原物料库。"); return
        
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
        if st.button("💾 保存配方", type="primary", use_container_width=True):
            clean = [r for r in st.session_state.bom_rows if r['用量'] > 0]
            if clean:
                db.store_recipe("📦 物流", "【全局】", p_name, "常规", "正常", clean)
                st.success("✅ 配方已存入云端！")

    with t3:
        for r in db.get_recipes():
            with st.container():
                st.markdown(f"**{r['product']}** | {r['scope']}<br><small>🌿 配方：{' 、 '.join([f'{i['物料名称']}({i['用量']}g)' for i in r['items']])}</small>", unsafe_allow_html=True)

if __name__ == "__main__":
    init_ui()
    if LIBS_READY:
        db_mgr = CloudDataManager()
        mode = st.sidebar.radio("功能导航", ["📊 经营看板", "⚙️ 配方中心"])
        if mode == "📊 经营看板": view_dashboard(db_mgr)
        else: view_recipes(db_mgr)
