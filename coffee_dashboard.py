# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import re
from datetime import datetime, timedelta

# --- 核心驱动加载 ---
try:
    from google.cloud import firestore
    from google.oauth2 import service_account
    import plotly.express as px
    import plotly.graph_objects as go
    LIBS_READY = True
except ImportError:
    LIBS_READY = False

# =============================================================================
# 模块 1：后端数据资产层 (Firebase 持久化引擎)
# =============================================================================
class CloudDataManager:
    def __init__(self):
        self.db = None
        try:
            key_dict = json.loads(st.secrets["textkey"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            self.db = firestore.Client(credentials=creds, project=key_dict['project_id'])
        except Exception:
            self.db = None

    def save_sales(self, df):
        """流式上传销售流水，利用唯一ID自动覆盖更新，防止重复"""
        if not self.db: return
        coll = self.db.collection("sales_records")
        for _, row in df.iterrows():
            # 唯一ID生成：日期_门店_商品_规格_做法
            safe_id = f"{row['统计周期']}_{row['门店名称']}_{row['商品名称']}_{row['规格']}_{row['做法']}".replace("/", "_").replace(" ", "")
            coll.document(safe_id).set(row.to_dict())

    def fetch_sales(self, start, end):
        """从云端抓取指定周期流水"""
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
# 模块 2：逻辑计算引擎 (包含完整的品类和项目映射)
# =============================================================================
PROJECT_STORE_MAPPING = {
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"],
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "腾讯项目": ["北京总部image"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"]
}

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

def logic_parse_days(date_series):
    """智能识别报表天数（解决总额/日均相等的问题）"""
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
    df_cat = pd.DataFrame(CATEGORY_MAPPING_DATA)
    for c in ['一级分类', '二级分类', '所属项目']:
        if c in df.columns: df = df.drop(columns=[c], errors='ignore')
    
    df['商品类别_clean'] = df['商品类别'].astype(str).str.strip()
    df = pd.merge(df, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('其他')
    df['二级分类'] = df['二级分类'].fillna('其他')
    
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(str(x).strip(), '其他项目'))
    return df

# =============================================================================
# 模块 3：前端视图层 (保持经典美观布局)
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡经营BI系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        div[data-testid="stMetric"] { background-color: #FFFFFF; padding: 22px; border-radius: 18px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
        div[data-testid="stVerticalBlockBorderWrapper"] { background-color: #FFFFFF; border-radius: 15px; border: 1px solid #E2E8F0; padding: 25px; margin-bottom: 20px; }
        .recipe-card { background: #FFFFFF; padding: 15px; border-radius: 12px; border-left: 6px solid #3B82F6; margin-bottom: 10px; border-top: 1px solid #F1F5F9; border-right: 1px solid #F1F5F9; border-bottom: 1px solid #F1F5F9; }
        .scope-badge { background: #1E40AF; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-left: 8px; }
    </style>
    """, unsafe_allow_html=True)

def view_analytics_dashboard(db):
    st.title("📊 顿角咖啡·智能经营看板")
    
    with st.sidebar.expander("💾 云端同步 (Memory)", expanded=False):
        files = st.file_uploader("上传企迈流水", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            for f in files:
                df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                df.columns = [str(c).strip() for c in df.columns]
                # 智能列映射
                m = {'商品实收': '销售金额', '商品销量': '销售数量', '日期': '统计周期', '商品分类': '商品类别'}
                df = df.rename(columns={k: v for k, v in m.items() if k in df.columns})
                db.save_sales(df)
            st.success("☁️ 云端同步成功！")
            st.rerun()

    # --- 筛选与核心分析 ---
    dr = st.sidebar.date_input("周期选择", [datetime.now() - timedelta(days=7), datetime.now()])
    if len(dr) == 2:
        raw = db.fetch_sales(dr[0].strftime('%Y-%m-%d'), dr[1].strftime('%Y-%m-%d'))
        if raw.empty:
            st.info("💡 云端库暂无数据。请先在左侧上传流水。")
            return
        
        df = logic_clean_sales(raw)
        
        # 联动筛选
        sel_proj = st.sidebar.multiselect("筛选项目", sorted(df['所属项目'].unique()), default=sorted(df['所属项目'].unique()))
        df_f = df[df['所属项目'].isin(sel_proj)]
        
        # --- 2x2 核心指标卡 ---
        st.markdown("### 💎 核心经营指标")
        c1, c2, c3, c4 = st.columns(4)
        q_total, a_total = df_f['销售数量'].sum(), df_f['销售金额'].sum()
        days = logic_parse_days(df_f['统计周期'])
        
        c1.metric("总销售杯数", f"{q_total:,.0f} 杯")
        c2.metric("总营收金额", f"¥{a_total:,.2f}")
        c3.metric("日均营业额", f"¥{a_total/days:,.2f}")
        c4.metric("单杯平均价", f"¥{a_total/q_total if q_total>0 else 0:.2f}")

        # --- 可视化大盘 ---
        if LIBS_READY:
            st.divider()
            col_l, col_r = st.columns([3, 2])
            with col_l:
                st.subheader("🏗️ 品类结构分布 (一级分类)")
                l1_sum = df_f.groupby('一级分类').agg({'销售数量':'sum','销售金额':'sum'}).reset_index()
                fig = px.bar(l1_sum, x='一级分类', y=['销售数量','销售金额'], barmode='group', 
                             color_discrete_sequence=['#3B82F6', '#10B981'], text_auto='.2s')
                st.plotly_chart(fig, use_container_width=True)
            with col_r:
                st.subheader("📈 营收贡献占比 (二级分类)")
                cat_sum = df_f.groupby('二级分类')['销售金额'].sum().reset_index()
                st.plotly_chart(px.pie(cat_sum, values='销售金额', names='二级分类', hole=0.4), use_container_width=True)

        st.subheader("📄 单品销售排行明细")
        rank_df = df_f.groupby(['商品名称','二级分类']).agg({'销售数量':'sum','销售金额':'sum'}).sort_values('销售数量', ascending=False)
        st.dataframe(rank_df, use_container_width=True)

def view_recipe_center(db):
    st.title("⚙️ 云端成本与配方中心")
    t1, t2, t3 = st.tabs(["📦 原物料记忆库", "📋 配方构建器", "📚 云端卡库预览"])
    
    with t1:
        f = st.file_uploader("同步单价库", type=["xlsx", "csv"])
        if f:
            df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
            db.save_material(df)
            st.success("✅ 价格档案已锁定至云端")
        st.dataframe(db.get_materials(), use_container_width=True, hide_index=True)

    with t2:
        m_df = db.get_materials()
        rmats = sorted(m_df['物料名称'].tolist()) if not m_df.empty else []
        if not rmats: st.warning("请先同步原物料单价库。"); return
        
        c1, c2 = st.columns(2)
        tk = c1.radio("轨道", ["📦 物流", "🏪 门店"])
        sc = c2.selectbox("适用范围", ["【全局默认】", "百度项目", "顿角项目"])
        
        cp1, cp2, cp3 = st.columns(3)
        p_name = cp1.text_input("饮品名", placeholder="例如: 拿铁")
        p_spec = cp2.selectbox("规格", ["中杯", "大杯", "特大杯", "常规"])
        p_meth = cp3.selectbox("做法", ["去冰", "热", "正常", "加糖"])

        if 'ui_rows' not in st.session_state: st.session_state.ui_rows = []
        
        st.markdown(f"#### 📝 配置构建行 (目标: `{sc}`)")
        new_list = []
        for i, row in enumerate(st.session_state.ui_rows):
            with st.container(border=True):
                r_cols = st.columns([1, 4, 3, 1])
                r_cols[0].markdown(f"**#{i+1}**")
                idx = rmats.index(row['物料名称']) if row['物料名称'] in rmats else 0
                m_val = r_cols[1].selectbox(f"物料", rmats, index=idx, key=f"mat_{i}")
                q_val = r_cols[2].number_input(f"克数", value=float(row['用量']), key=f"qty_{i}")
                new_list.append({'物料名称': m_val, '用量': q_val})
                if r_cols[3].button("🗑️", key=f"del_{i}"):
                    st.session_state.ui_rows.pop(i); st.rerun()
        
        st.session_state.ui_rows = new_list
        if st.button("➕ 新增物料行", use_container_width=True):
            st.session_state.ui_rows.append({'物料名称': rmats[0], '用量': 0.0}); st.rerun()
        
        if st.button("💾 确认同步云端", type="primary", use_container_width=True):
            clean = [r for r in st.session_state.ui_rows if r['用量'] > 0]
            if clean:
                db.store_recipe(tk, sc, p_name, p_spec, p_meth, clean)
                st.success("✅ 已存入云端记忆！切规格后物料会自动保留。")
            else: st.error("内容为空")

    with t3:
        recipes = db.get_recipes()
        if not recipes: st.info("库内暂无配方卡")
        for r in recipes:
            with st.container():
                st.markdown(f"""<div class='recipe-card'>
                    <b>【{r['track']}】{r['product']}</b> ({r['spec']}/{r['method']}) 
                    <span class='scope-badge'>{r['scope']}</span><br>
                    <small>🌿 包含：{" 、 ".join([f"{i['物料名称']}({i['用量']}g)" for i in r['items']])}</small>
                </div>""", unsafe_allow_html=True)

# =============================================================================
# 4. 主程序入口
# =============================================================================
if __name__ == "__main__":
    init_ui()
    if not LIBS_READY:
        st.error("⚠️ 系统缺失必要库。请上传 requirements.txt 并重启。")
        st.stop()
        
    db_manager = CloudDataManager()
    app_mode = st.sidebar.radio("系统导航", ["📊 经营分析看板", "⚙️ 成本与配方中心"])
    
    if app_mode == "📊 经营分析看板":
        view_analytics_dashboard(db_manager)
    else:
        view_recipe_center(db_manager)
