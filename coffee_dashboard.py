# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta

# =============================================================================
# 1. 业务逻辑配置：映射关系表 (按“商品类别”重新定义)
# =============================================================================
# 门店归属项目配置
PROJECT_STORE_MAPPING = {
    "百度项目": ["度咖啡（百度鹏寰店）", "度小满店", "度咖啡（百度科技园店）", "度咖啡（百度奎科店）", "度咖啡（百度大厦店）", "度咖啡（百度上研店）"],
    "顿角项目": ["中信建投店", "北京移动美惠大厦店", "嘉铭中心店", "天津联想创新科技园店", "小米上海店", "快手万家灯火店", "悦读+车公庄店", "悦读+阜成路店", "新华三集团店", "科大讯飞店", "网易店", "联想总部店", "顿角咖啡研发中心店[高科岭]"],
    "光大项目": ["光大咖啡上地店", "光大咖啡上海分行店", "光大咖啡总行店"]
}

# 🌟 核心修改：将“商品类别”映射到一级大类
# 这里填入报表【商品类别】列中实际出现的文字
CATEGORY_MAPPING = [
    {"一级分类": "咖啡饮品", "二级分类": "冰爽果咖"},
    {"一级分类": "咖啡饮品", "二级分类": "拿铁系列"},
    {"一级分类": "咖啡饮品", "二级分类": "常规咖啡"},
    {"一级分类": "咖啡饮品", "二级分类": "美式家族"},
    {"一级分类": "非咖啡饮品", "二级分类": "原叶轻乳茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "清爽果茶"},
    {"一级分类": "非咖啡饮品", "二级分类": "手打柠"},
    {"一级分类": "非咖啡饮品", "二级分类": "活力酸奶"},
    {"一级分类": "非咖啡饮品", "二级分类": "鲜果茶系列"},
    {"一级分类": "烘焙甜品", "二级分类": "餐厅产品"},
    {"一级分类": "烘焙甜品", "二级分类": "现烤烘焙"}
]

# =============================================================================
# 2. 核心算法：数据清洗引擎
# =============================================================================
def logic_parse_days(date_series):
    """精准解析天数"""
    if date_series.empty: return 1
    s = date_series.iloc[:, 0] if isinstance(date_series, pd.DataFrame) else date_series
    return max(1, s.nunique())

def logic_clean_data(df):
    """
    针对企迈报表优化的清洗逻辑
    """
    if df.empty: return df
    
    # 🌟 核心修复 1：重置索引
    df = df.copy().reset_index(drop=True)
    
    # 🌟 核心修复 2：暴力清洗列名并建立映射
    df.columns = [str(c).strip().replace('\n', '').replace('\r', '').replace('`', '') for c in df.columns]
    
    # 优先级映射：强制寻找“商品类别”而不是“商品分类”
    rename_map = {
        '日期': '统计周期',
        '门店名称': '门店名称',
        '商品类别': '二级分类_raw',  # 🌟 优先取“类别”
        '商品实收': '销售金额',
        '商品销量': '销售数量'
    }
    
    # 如果没有“商品类别”但有“商品分类”，作为备选（防止某些报表格式变化）
    if '商品类别' not in df.columns and '商品分类' in df.columns:
        rename_map['商品分类'] = '二级分类_raw'

    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # 验证关键列
    required = ['门店名称', '统计周期', '二级分类_raw', '销售金额', '销售数量']
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"⚠️ 识别失败！报表中缺少必要列：{', '.join(missing)}")
        st.info(f"💡 读取到的列名有：{list(df.columns)}")
        st.stop()

    # 清理所有数据中的反引号 `
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.replace('`', '').str.strip()
    
    # 项目映射
    s2p = {str(s).strip(): p for p, stores in PROJECT_STORE_MAPPING.items() for s in stores}
    df['所属项目'] = df['门店名称'].apply(lambda x: s2p.get(str(x).strip(), '其他项目')).values
    
    # 品类层级映射
    df_cat = pd.DataFrame(CATEGORY_MAPPING)
    if '一级分类' in df.columns: df = df.drop(columns=['一级分类'])
    if '二级分类' in df.columns: df = df.drop(columns=['二级分类'])
    
    df = pd.merge(df, df_cat, left_on='二级分类_raw', right_on='二级分类', how='left')
    df['一级分类'] = df['一级分类'].fillna('其他')
    df['二级分类'] = df['二级分类'].fillna(df['二级分类_raw'])
    
    return df.reset_index(drop=True)

# =============================================================================
# 3. UI 界面美化
# =============================================================================
def init_ui():
    st.set_page_config(page_title="顿角咖啡智能分析系统", page_icon="☕", layout="wide")
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        .stApp { background-color: #F8FAFC; font-family: 'Inter', sans-serif; }
        
        /* 🌟 修复月份切换按钮遮挡 */
        section[data-testid="stSidebar"] div.stVerticalBlock {
            padding-top: 5rem !important;
        }

        /* 美化的指标卡 */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            padding: 22px !important;
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
    
    if 'raw_data' not in st.session_state: st.session_state.raw_data = pd.DataFrame()

    with st.sidebar.expander("📥 上传原始报表 (企迈版)", expanded=True):
        files = st.file_uploader("支持多选 xlsx/csv", type=["xlsx", "csv"], accept_multiple_files=True)
        if files:
            all_dfs = []
            for f in files:
                try:
                    df = pd.read_excel(f) if f.name.endswith('.xlsx') else pd.read_csv(f)
                    all_dfs.append(df)
                except: pass
            if all_dfs:
                st.session_state.raw_data = pd.concat(all_dfs, ignore_index=True)
                st.success("报表加载成功")

    if st.session_state.raw_data.empty:
        st.info("💡 请上传企迈报表。系统会自动识别“商品类别”进行分类分析。")
        return

    # 数据清洗
    df_clean = logic_clean_data(st.session_state.raw_data)
    
    # --- 筛选器 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 智能筛选")
    
    sel_proj = st.sidebar.multiselect("项目", sorted(df_clean['所属项目'].unique()))
    df_f1 = df_clean if not sel_proj else df_clean[df_clean['所属项目'].isin(sel_proj)]
    
    sel_store = st.sidebar.multiselect("门店", sorted(df_f1['门店名称'].unique()))
    df_f2 = df_f1 if not sel_store else df_f1[df_f1['门店名称'].isin(sel_store)]
    
    sel_l1 = st.sidebar.multiselect("一级分类", sorted(df_f2['一级分类'].unique()))
    df_f3 = df_f2 if not sel_l1 else df_f2[df_f2['一级分类'].isin(sel_l1)]
    
    sel_l2 = st.sidebar.multiselect("商品类别 (二级)", sorted(df_f3['二级分类'].unique()))
    df_final = df_f3 if not sel_l2 else df_f3[df_f3['二级分类'].isin(sel_l2)]

    # --- 数据面板 ---
    q, a = df_final['销售数量'].sum(), df_final['销售金额'].sum()
    days = logic_parse_days(df_final['统计周期'])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总销售杯数", f"{q:,.0f} 杯")
    c2.metric("总营收金额", f"¥{a:,.2f}")
    c3.metric("日均营收", f"¥{a/days:,.2f}")
    c4.metric("单杯均价", f"¥{a/q if q>0 else 0:.2f}")

    # --- 可视化 ---
    import plotly.express as px
    st.divider()
    col_l, col_r = st.columns([3, 2])
    with col_l:
        st.subheader("🏗️ 项目销售贡献")
        p_sum = df_final.groupby('所属项目')['销售金额'].sum().reset_index()
        fig = px.bar(p_sum, x='所属项目', y='销售金额', color='所属项目', template="plotly_white", text_auto='.2s')
        st.plotly_chart(fig, use_container_width=True)
    with col_r:
        st.subheader("📈 类别营收占比")
        c_sum = df_final.groupby('二级分类')['销售金额'].sum().reset_index()
        st.plotly_chart(px.pie(c_sum, values='销售金额', names='二级分类', hole=0.4), use_container_width=True)

    st.subheader("📋 单品表现详情")
    rank = df_final.groupby(['商品名称', '规格', '做法']).agg({'销售数量':'sum', '销售金额':'sum'}).sort_values('销售数量', ascending=False)
    st.dataframe(rank, use_container_width=True)

# =============================================================================
# 5. 入口
# =============================================================================
if __name__ == "__main__":
    init_ui()
    menu = st.sidebar.radio("功能导航", ["📊 经营看板", "⚙️ 配方中心"])
    if menu == "📊 经营看板":
        view_dashboard()
    else:
        st.title("⚙️ 成本配方中心")
        st.info("数据看板已对齐“商品类别”。接下来我们将根据此维度，增加精准的原料配方和利润分析。")
