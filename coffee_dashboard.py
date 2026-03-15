# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import json
import re
from datetime import datetime, timedelta

# =============================================================================
# 核心驱动加固加载 (针对云端环境优化)
# =============================================================================
try:
    from google.cloud import firestore
    from google.oauth2 import service_account
    import plotly.express as px
    import plotly.graph_objects as go
    LIBS_READY = True
except Exception as e:
    st.error(f"⚠️ 驱动库加载失败: {e}。请确保 requirements.txt 已正确安装。")
    LIBS_READY = False

# =============================================================================
# 模块 1：后端数据资产层 (Firebase 持久化引擎)
# =============================================================================
class CloudDataManager:
    def __init__(self):
        self.db = None
        try:
            # 智能识别 Secrets 格式
            raw_key = st.secrets["textkey"]
            if isinstance(raw_key, str):
                key_dict = json.loads(raw_key)
            else:
                key_dict = dict(raw_key)
                
            creds = service_account.Credentials.from_service_account_info(key_dict)
            self.db = firestore.Client(credentials=creds, project=key_dict['project_id'])
        except Exception as e:
            st.warning(f"🔒 云数据库待连接: 请检查 Streamlit Secrets 配置。错误提示: {e}")

    def save_sales(self, df):
        """流式上传流水，利用唯一ID自动去重"""
        if not self.db: return
        coll = self.db.collection("sales_records")
        for _, row in df.iterrows():
            # 唯一ID构造：日期_门店_商品_规格_做法
            safe_id = f"{row['统计周期']}_{row['门店名称']}_{row['商品名称']}_{row['规格']}_{row['做法']}".replace("/", "_").replace(" ", "")
            coll.document(safe_id).set(row.to_dict())

    def fetch_sales(self, start, end):
        """抓取指定周期流水"""
        if not self.db: return pd.DataFrame()
        docs = self.db.collection("sales_records")\
                .where("统计周期", ">=", start).where("统计周期", "<=", end).stream()
        return pd.DataFrame([doc.to_dict() for doc in docs])

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
# 模块 2：逻辑计算引擎 (数据映射与智能解析)
# =============================================================================
PROJECT_STORE_MAPPING = {
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"],
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"]
}

CATEGORY_DATA = [
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "咖啡饮品", "二级分类": "奶咖家族"}, {"一级分类": "咖啡饮品", "二级分类": "果C美式"},
    {"一级分类": "咖啡饮品", "二级分类": "手冲咖啡"}, {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"}, {"一级分类": "非咖啡饮品", "二级分类": "经典鲜果茶"}
]

def logic_parse_days(date_series):
    """智能解析报表天数（解决总额/日均相等的Bug）"""
    if date_series.empty: return 1
    sample = str(date_series.iloc[0])
    match = re.search(r'(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})', sample)
    if match:
        try:
            d1 = datetime.strptime(match.group(1), '%Y-%m-%d')
            d2 = datetime.strptime(match.group(2), '%Y-%m-%d')
            return max(1, (d2 - d1).days + 1)
        except: pass
    return max(1, date_series.nunique())

def logic_clean_sales(df):
    if df.empty: return df
    df_cat = pd.DataFrame(CATEGORY_DATA)
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
    st.set_page_config(page_title="顿角咖啡经营决策系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        div[data-testid="stMetric"] { background-color: #FFFFFF; padding: 22px; border-radius: 18px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
        div[data-testid="stVerticalBlockBorderWrapper"] { background-color: #FFFFFF; border-radius: 15px; border: 1px solid #E2E8F0; padding: 25px; margin-bottom: 20px; }
        .recipe-card { background: white; padding: 15px; border-radius: 12px; border-left: 6px solid #3B82F6; margin-bottom: 10px; border: 1px solid #F1F5F9; }
        .scope-badge { background: #1E40AF; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-left: 10px; }
    </style>
    """, unsafe_allow_html=True)

def view_dashboard(db):
    st.title("📊 顿角咖啡·智能经营看板")
    
    with st.sidebar.expander("💾 云端同步中心", expanded=False):
        files = st.file_uploader("上传报表同步云端", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            for f in files:
                df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                df.columns = [str(c).strip() for c in df.columns]
                m = {'商品实收': '销售金额', '商品销量': '销售数量', '日期': '统计周期', '商品分类': '商品类别'}
                df = df.rename(columns={k: v for k, v in m.items() if k in df.columns})
                db.save_sales(df)
            st.success("✅ 数据已永久保存至云端！")
            st.rerun()

    dr = st.sidebar.date_input("分析周期", [datetime.now() - timedelta(days=7), datetime.now()])
    if len(dr) == 2:
        raw = db.fetch_sales(dr[0].strftime('%Y-%m-%d'), dr[1].strftime('%Y-%m-%d'))
        if raw.empty:
            st.info("💡 云端库暂无数据。请先同步报表。")
            return
        
        df = logic_clean_sales(raw)
        
        # 核心指标卡 (2x2)
        c1, c2, c3, c4 = st.columns(4)
        q_total, a_total = df['销售数量'].sum(), df['销售金额'].sum()
        days = logic_parse_days(df['统计周期'])
        
        c1.metric("总销售杯数", f"{q_total:,.0f} 杯")
        c2.metric("总营收金额", f"¥{a_total:,.2f}")
        c3.metric("日均营业额", f"¥{a_total/days:,.2f}")
        c4.metric("单杯平均价", f"¥{a_total/q_total if q_total>0 else 0:.2f}")

        if LIBS_READY:
            st.divider()
            col_l, col_r = st.columns([3, 2])
            with col_l:
                st.subheader("🏗️ 品类结构分布")
                l1_sum = df.groupby('一级分类').agg({'销售数量':'sum','销售金额':'sum'}).reset_index()
                fig = px.bar(l1_sum, x='一级分类', y=['销售数量','销售金额'], barmode='group', color_discrete_sequence=['#3B82F6', '#10B981'])
                st.plotly_chart(fig, use_container_width=True)
            with col_r:
                st.subheader("📈 营收贡献占比")
                cat_sum = df.groupby('商品类别')['销售金额'].sum().reset_index()
                st.plotly_chart(px.pie(cat_sum, values='销售金额', names='商品类别', hole=0.4), use_container_width=True)

def view_recipes(db):
    st.title("⚙️ 成本与配方引擎")
    t1, t2, t3 = st.tabs(["原物料记忆", "配置构建器", "云端卡库"])
    
    with t1:
        f = st.file_uploader("同步单价库", type=["xlsx", "csv"])
        if f:
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            db.save_material(df)
            st.success("✅ 单价档案已锁定")
        st.dataframe(db.get_materials(), use_container_width=True, hide_index=True)

    with t2:
        m_df = db.get_materials()
        rmats = sorted(m_df['物料名称'].tolist()) if not m_df.empty else []
        if not rmats: st.warning("请先同步原物料库。"); return
        
        c1, c2 = st.columns(2)
        tk = c1.radio("轨道", ["📦 物流", "🏪 门店"])
        sc = c2.selectbox("范围", ["【全局】", "百度", "顿角"])
        
        cp1, cp2, cp3 = st.columns(3)
        p_name = cp1.text_input("饮品名", placeholder="例如: 拿铁")
        p_spec = cp2.selectbox("规格", ["中杯", "大杯", "常规"])
        p_meth = cp3.selectbox("做法", ["去冰", "热", "正常"])

        if 'ui_rows' not in st.session_state: st.session_state.ui_rows = []
        
        # 稳定行构建逻辑
        new_list = []
        for i, row in enumerate(st.session_state.ui_rows):
            with st.container(border=True):
                r_cols = st.columns([1, 4, 3, 1])
                idx = rmats.index(row['物料名称']) if row['物料名称'] in rmats else 0
                m_val = r_cols[1].selectbox(f"物料", rmats, index=idx, key=f"m_{i}")
                q_val = r_cols[2].number_input(f"量", value=float(row['用量']), key=f"q_{i}")
                new_list.append({'物料名称': m_val, '用量': q_val})
                if r_cols[3].button("🗑️", key=f"d_{i}"):
                    st.session_state.ui_rows.pop(i); st.rerun()
        
        st.session_state.ui_rows = new_list
        if st.button("➕ 新增物料行", use_container_width=True):
            st.session_state.ui_rows.append({'物料名称': rmats[0], '用量': 0.0}); st.rerun()
        
        if st.button("💾 确认并保存至云端", type="primary", use_container_width=True):
            clean = [r for r in st.session_state.ui_rows if r['用量'] > 0]
            if clean:
                db.store_recipe(tk, sc, p_name, p_spec, p_meth, clean)
                st.success("✅ 云端同步完成！")

    with t3:
        for r in db.get_recipes():
            with st.container():
                st.markdown(f"""<div class='recipe-card'>
                    <b>【{r['track']}】{r['product']}</b> ({r['spec']}/{r['method']}) 
                    <span class='scope-badge'>{r['scope']}</span><br>
                    <small>配方：{" 、 ".join([f"{i['物料名称']}({i['用量']}g)" for i in r['items']])}</small>
                </div>""", unsafe_allow_html=True)

# =============================================================================
# 程序入口
# =============================================================================
if __name__ == "__main__":
    init_ui()
    if LIBS_READY:
        db_mgr = CloudDataManager()
        mode = st.sidebar.radio("导航", ["📊 经营看板", "⚙️ 成本中心"])
        if mode == "📊 经营看板":
            view_dashboard(db_mgr)
        else:
            view_recipes(db_mgr)
