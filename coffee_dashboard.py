# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta

# =============================================================================
# 1. 业务逻辑配置：映射关系表 (这是系统的“灵魂”)
# =============================================================================
# 这里定义门店属于哪个项目，系统会自动根据“门店名称”进行归类
PROJECT_STORE_MAPPING = {
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"],
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"]
}

# 这里定义二级分类（报表里的分类）属于哪一个一级大类
CATEGORY_MAPPING = [
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"}, {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "咖啡饮品", "二级分类": "拿铁家族"}, {"一级分类": "咖啡饮品", "二级分类": "奶咖家族"},
    {"一级分类": "咖啡饮品", "二级分类": "果C美式"}, {"一级分类": "咖啡饮品", "二级分类": "手冲咖啡"},
    {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"}, {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"},
    {"一级分类": "非咖啡饮品", "二级分类": "经典鲜果茶"}, {"一级分类": "非咖啡饮品", "二级分类": "新鲜果蔬汁"}
]

# =============================================================================
# 2. 核心算法：数据处理引擎
# =============================================================================
def logic_parse_days(date_series):
    """精准解析报表天数，解决“日均=总额”的计算问题"""
    if date_series.empty: return 1
    # 强制取第一列防止多列冲突
    s = date_series.iloc[:, 0] if isinstance(date_series, pd.DataFrame) else date_series
    sample = str(s.iloc[0])
    # 匹配报表中的日期范围文本，例如 "2024-03-01 至 2024-03-15"
    match = re.search(r'(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})', sample)
    if match:
        try:
            d1 = datetime.strptime(match.group(1), '%Y-%m-%d')
            d2 = datetime.strptime(match.group(2), '%Y-%m-%d')
            return max(1, (d2 - d1).days + 1)
        except: pass
    return max(1, s.nunique())

def logic_clean_data(df):
    """
    数据标准化清洗：重置索引、识别列名、层级映射
    """
    if df.empty: return df
    
    # 🌟 核心修复 1：重置索引，彻底杜绝多文件合并导致的 ValueError 冲突
    df = df.copy().reset_index(drop=True)
    
    # 🌟 核心修复 2：暴力清洗列名（去掉空格、换行、特殊字符）
    df.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df.columns]
    
    # 🌟 核心修复 3：智能模糊匹配列名
    std_map = {
        '统计周期': ['周期', '日期', '时间', '统计日期'],
        '门店名称': ['门店', '门店名称', '机构', '店铺'],
        '商品类别': ['分类', '品类', '类别', '商品类别'],
        '销售金额': ['实收', '金额', '销售额', '商品实收'],
        '销售数量': ['销量', '数量', '商品销量', '杯数']
    }
    
    final_rename = {}
    found_targets = set()
    for col in df.columns:
        for target, keywords in std_map.items():
            if target not in found_targets and any(k in col for k in keywords):
                final_rename[col] = target
                found_targets.add(target)
                break
    
    df = df.rename(columns=final_rename)

    # 验证关键列，识别失败则报错提示并打印现有列名
    required = ['门店名称', '统计周期', '商品类别', '销售金额', '销售数量']
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"⚠️ 识别失败！报表中缺少关键列：{', '.join(missing)}")
        st.info(f"💡 当前识别到的列名为：{list(df.columns)}")
        st.stop()
    
    # 项目归属映射 (强制使用 .values 避免索引对齐错误)
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(str(x).strip(), '其他项目')).values
    
    # 商品类别层级对撞
    df_cat = pd.DataFrame(CATEGORY_MAPPING).drop_duplicates('二级分类')
    for col in ['一级分类', '二级分类']:
        if col in df.columns: df = df.drop(columns=[col])
    
    df['商品类别_clean'] = df['商品类别'].astype(str).str.strip().values
    df = pd.merge(df, df_cat, left_on='商品类别_clean', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('其他')
    df['二级分类'] = df['二级分类'].fillna('其他')
    
    return df.reset_index(drop=True)

# =============================================================================
# 3. UI 界面美化与布局
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡智能分析系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        
        /* 🌟 核心修复：侧边栏内容压低，防止日期月份按钮被顶部导航遮挡 */
        section[data-testid="stSidebar"] div.stVerticalBlock {
            padding-top: 5rem !important;
        }

        /* 指标卡美化 */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            padding: 25px !important;
            border-radius: 20px !important;
            border: 1px solid #E2E8F0 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# 4. 视图：经营分析看板
# =============================================================================
def view_dashboard():
    st.title("📊 顿角咖啡·智能经营看板")
    
    # 使用 session_state 实现本地会话数据存储
    if 'raw_data' not in st.session_state: st.session_state.raw_data = pd.DataFrame()

    # --- 侧边栏：数据上传 (支持多选文件) ---
    with st.sidebar.expander("📥 上传原始报表", expanded=True):
        files = st.file_uploader("支持多选 Excel/CSV", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            all_dfs = []
            for f in files:
                try:
                    # 读取并强制重置索引
                    temp_df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                    all_dfs.append(temp_df)
                except Exception as e:
                    st.error(f"文件 {f.name} 读取失败: {e}")
            
            if all_dfs:
                # 🌟 修复合并冲突：忽略索引
                st.session_state.raw_data = pd.concat(all_dfs, ignore_index=True).drop_duplicates()
                st.success("数据加载成功！")

    if st.session_state.raw_data.empty:
        st.info("💡 系统已就绪。请在左侧上传您的销售报表开始分析。")
        return

    # 数据清洗
    df_base = logic_clean_data(st.session_state.raw_data)
    
    # --- 侧边栏：智能筛选体系 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 智能筛选")
    
    # 1. 项目与门店
    all_projs = sorted(df_base['所属项目'].unique())
    sel_proj = st.sidebar.multiselect("所属项目", all_projs)
    df_f1 = df_base if not sel_proj else df_base[df_base['所属项目'].isin(sel_proj)]
    
    all_stores = sorted(df_f1['门店名称'].unique())
    sel_store = st.sidebar.multiselect("门店名称", all_stores)

    # 2. 类别层级 (不选即代表全选该层级)
    all_l1 = sorted(df_f1['一级分类'].unique())
    sel_l1 = st.sidebar.multiselect("一级分类", all_l1)
    df_f2 = df_f1 if not sel_l1 else df_f1[df_f1['一级分类'].isin(sel_l1)]
    
    all_l2 = sorted(df_f2['二级分类'].unique())
    sel_l2 = st.sidebar.multiselect("二级分类", all_l2)

    # 执行最终筛选
    df_view = df_base.copy()
    if sel_proj: df_view = df_view[df_view['所属项目'].isin(sel_proj)]
    if sel_store: df_view = df_view[df_view['门店名称'].isin(sel_store)]
    if sel_l1: df_view = df_view[df_view['一级分类'].isin(sel_l1)]
    if sel_l2: df_view = df_view[df_view['二级分类'].isin(sel_l2)]

    # --- 核心数据指标 ---
    q, a = df_view['销售数量'].sum(), df_view['销售金额'].sum()
    days = logic_parse_days(df_view[['统计周期']])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总杯数", f"{q:,.0f} 杯")
    c2.metric("总营收", f"¥{a:,.2f}")
    c3.metric("日均营收", f"¥{a/days:,.2f}")
    c4.metric("单杯均价", f"¥{a/q if q>0 else 0:.2f}")

    # --- 图表呈现 ---
    import plotly.express as px
    st.divider()
    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.subheader("🏗️ 项目销售贡献")
        p_sum = df_view.groupby('所属项目')['销售金额'].sum().reset_index()
        fig = px.bar(p_sum, x='所属项目', y='销售金额', color_discrete_sequence=['#3B82F6'], template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
    with col_r:
        st.subheader("📈 品类分布占比")
        c_sum = df_view.groupby('二级分类')['销售金额'].sum().reset_index()
        st.plotly_chart(px.pie(c_sum, values='销售金额', names='二级分类', hole=0.4), use_container_width=True)

    st.subheader("📋 单品表现详情表")
    rank = df_view.groupby(['商品名称', '规格', '做法']).agg({'销售数量':'sum', '销售金额':'sum'}).sort_values('销售数量', ascending=False)
    st.dataframe(rank, use_container_width=True)

# =============================================================================
# 5. 主程序入口
# =============================================================================
if __name__ == "__main__":
    init_ui()
    menu = st.sidebar.radio("系统导航", ["📊 经营看板", "⚙️ 配方中心"])
    if menu == "📊 经营看板":
        view_dashboard()
    else:
        st.title("⚙️ 成本配方中心")
        st.info("本地版 4.0 已就绪。请确认看板功能运行无误，我们再通过 Session State 补全这里的配方录入逻辑。")
