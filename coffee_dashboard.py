# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import json
import re
from datetime import datetime, timedelta

# =============================================================================
# 核心驱动加固加载 (引入 FieldPath 解决中文路径报错)
# =============================================================================
try:
    from google.cloud import firestore
    from google.cloud.firestore import FieldPath  # 🌟 关键：用于处理查询中的中文字段名
    from google.oauth2 import service_account
    import plotly.express as px
    import plotly.graph_objects as go
    LIBS_READY = True
except Exception as e:
    st.error(f"⚠️ 驱动库加载失败: {e}")
    LIBS_READY = False

# =============================================================================
# 模块 1：后端数据资产层 (Firebase 持久化引擎)
# =============================================================================
class CloudDataManager:
    def __init__(self):
        self.db = None
        try:
            # 自动识别并解析 Secrets
            raw_key = st.secrets["textkey"]
            if isinstance(raw_key, str):
                key_dict = json.loads(raw_key)
            else:
                key_dict = dict(raw_key)
                
            creds = service_account.Credentials.from_service_account_info(key_dict)
            self.db = firestore.Client(credentials=creds, project=key_dict['project_id'])
        except Exception as e:
            st.warning(f"🔒 云数据库待连接: 请检查 Secrets 配置。提示: {e}")

    def save_sales(self, df):
        """上传流水，利用唯一ID自动去重"""
        if not self.db: return
        coll = self.db.collection("sales_records")
        for _, row in df.iterrows():
            # 唯一ID构造，防止数据重复
            safe_id = f"{row['统计周期']}_{row['门店名称']}_{row['商品名称']}_{row['规格']}_{row['做法']}".replace("/", "_").replace(" ", "")
            coll.document(safe_id).set(row.to_dict())

    def fetch_sales(self, start, end):
        """
        抓取指定周期流水
        🌟 修复点：使用 FieldPath 显式包裹中文字段名，防止 SDK 解析出错
        """
        if not self.db: return pd.DataFrame()
        try:
            # 将中文字段名放入 FieldPath 列表，这是解决 ValueError 的官方标准做法
            fp = FieldPath(["统计周期"])
            docs = self.db.collection("sales_records")\
                    .where(fp, ">=", start)\
                    .where(fp, "<=", end).stream()
            data = [doc.to_dict() for doc in docs]
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"🔍 查询过程出错: {e}")
            return pd.DataFrame()

    def save_material(self, df):
        if not self.db: return
        for _, row in df.iterrows():
            self.db.collection("materials").document(row['物料名称']).set(row.to_dict())

    def get_materials(self):
        if not self.db: return pd.DataFrame()
        return pd.DataFrame([doc.to_dict() for doc in self.db.collection("materials").stream()])

    def store_recipe(self, track, scope, prod, spec, meth, items):
        if not self.db: return
        card_id = f"{track}_{scope}_{prod}_{spec}_{meth}".replace("/", "_").replace(" ", "")
        self.db.collection("recipes").document(card_id).set({
            "track": track, "scope": scope, "product": prod, "spec": spec, "method": meth,
            "items": items, "updated_at": datetime.now()
        })

    def get_recipes(self):
        if not self.db: return []
        return [doc.to_dict() for doc in self.db.collection("recipes").stream()]

# =============================================================================
# 模块 2：逻辑计算引擎 (数据清洗与映射)
# =============================================================================
PROJECT_STORE_MAPPING = {
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"],
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"]
}

CATEGORY_CONFIG = [
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "咖啡饮品", "二级分类": "奶咖家族"}, {"一级分类": "咖啡饮品", "二级分类": "果C美式"},
    {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"}, {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"}
]

def logic_parse_days(date_series):
    """解析天数，支持单日或范围文本"""
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
    df_cat = pd.DataFrame(CATEGORY_CONFIG)
    for c in ['一级分类', '二级分类', '所属项目']:
        if c in df.columns: df = df.drop(columns=[c], errors='ignore')
    
    df['商品类别_clean'] = df['商品类别'].astype(str).str.strip()
    df = pd.merge(df, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('其他')
    
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(str(x).strip(), '其他项目'))
    return df

# =============================================================================
# 模块 3：前端视图层 (保持美观布局)
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡智能分析系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        .stApp { background-color: #F8FAFC; }
        div[data-testid="stMetric"] { background-color: #FFFFFF; padding: 22px; border-radius: 18px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
        .recipe-card { background: white; padding: 15px; border-radius: 12px; border-left: 6px solid #3B82F6; margin: 10px 0; border: 1px solid #F1F5F9; }
    </style>
    """, unsafe_allow_html=True)

def view_dashboard(db):
    st.title("📊 顿角咖啡·智能经营看板")
    with st.sidebar.expander("💾 云端同步中心", expanded=False):
        files = st.file_uploader("上传企迈报表", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            for f in files:
                df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                df.columns = [str(c).strip() for c in df.columns]
                m = {'商品实收': '销售金额', '商品销量': '销售数量', '日期': '统计周期', '商品分类': '商品类别'}
                df = df.rename(columns={k: v for k, v in m.items() if k in df.columns})
                db.save_sales(df)
            st.success("✅ 云端记忆已更新！")
            st.rerun()

    dr = st.sidebar.date_input("周期选择", [datetime.now() - timedelta(days=7), datetime.now()])
    if len(dr) == 2:
        df_raw = db.fetch_sales(dr[0].strftime('%Y-%m-%d'), dr[1].strftime('%Y-%m-%d'))
        if df_raw.empty:
            st.info("💡 云端暂无该周期数据，请先同步报表。")
            return
        
        df = logic_clean_sales(df_raw)
        c1, c2, c3, c4 = st.columns(4)
        q, a = df['销售数量'].sum(), df['销售金额'].sum()
        days = logic_parse_days(df['统计周期'])
        c1.metric("总销售杯数", f"{q:,.0f} 杯")
        c2.metric("总营收金额", f"¥{a:,.2f}")
        c3.metric("日均营业额", f"¥{a/days:,.2f}")
        c4.metric("单杯均价", f"¥{a/q if q>0 else 0:.2f}")

def view_recipes(db):
    st.title("⚙️ 成本配方引擎")
    t1, t2, t3 = st.tabs(["原物料记忆", "配置构建器", "云端卡库"])
    
    with t1:
        f = st.file_uploader("同步单价", type=["xlsx", "csv"])
        if f:
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            db.save_material(df)
            st.success("✅ 价格记忆成功")
        st.dataframe(db.get_materials(), use_container_width=True)

    with t2:
        m_df = db.get_materials()
        rmats = sorted(m_df['物料名称'].tolist()) if not m_df.empty else []
        if not rmats: st.warning("请先同步原物料库。"); return
        
        c1, c2 = st.columns(2)
        tk = c1.radio("核算轨道", ["📦 物流", "🏪 门店"])
        sc = c2.selectbox("适用项目", ["【全局】", "百度", "顿角"])
        
        p1, p2, p3 = st.columns(3)
        p_name = p1.text_input("饮品名")
        p_spec = p2.selectbox("规格", ["中杯", "大杯", "常规"])
        p_meth = p3.selectbox("做法", ["去冰", "热", "正常"])

        if 'ui_bom_rows' not in st.session_state: st.session_state.ui_bom_rows = []
        
        new_list = []
        for i, row in enumerate(st.session_state.ui_bom_rows):
            with st.container():
                cols = st.columns([1, 4, 3, 1])
                idx = rmats.index(row['物料名称']) if row['物料名称'] in rmats else 0
                m_val = cols[1].selectbox(f"物料", rmats, index=idx, key=f"mat_{i}")
                q_val = cols[2].number_input(f"量", value=float(row['用量']), key=f"qty_{i}")
                new_list.append({'物料名称': m_val, '用量': q_val})
                if cols[3].button("🗑️", key=f"del_{i}"):
                    st.session_state.ui_bom_rows.pop(i); st.rerun()
        
        st.session_state.ui_bom_rows = new_list
        if st.button("➕ 新增物料行"):
            st.session_state.ui_rows.append({'物料名称': rmats[0], '用量': 0.0}); st.rerun()
        
        if st.button("💾 确认并保存至云端", type="primary"):
            clean = [r for r in st.session_state.ui_bom_rows if r['用量'] > 0]
            if clean:
                db.store_recipe(tk, sc, p_name, p_spec, p_meth, clean)
                st.success("✅ 配方已存入云端记忆！")

    with t3:
        for r in db.get_recipes():
            with st.container():
                st.markdown(f"""<div class='recipe-card'>
                    <b>【{r['track']}】{r['product']}</b> ({r['spec']}/{r['method']}) | {r['scope']}<br>
                    <small>配方详情：{" 、 ".join([f"{i['物料名称']}({i['用量']}g)" for i in r['items']])}</small>
                </div>""", unsafe_allow_html=True)

if __name__ == "__main__":
    init_ui()
    if LIBS_READY:
        db_mgr = CloudDataManager()
        mode = st.sidebar.radio("导航", ["📊 经营看板", "⚙️ 配方中心"])
        if mode == "📊 经营看板":
            view_dashboard(db_mgr)
        else:
            view_recipes(db_mgr)
