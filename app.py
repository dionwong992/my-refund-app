import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

# 1. 页面配置
st.set_page_config(page_title="XiuXiu Live 智慧财务", layout="centered", page_icon="📈")

def get_malaysia_time():
    kl_tz = pytz.timezone('Asia/Kuala_Lumpur')
    return datetime.now(kl_tz)

# --- 登录系统 ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🚀 XiuXiu Live 内部系统")
    pwd = st.text_input("请输入专属口令:", type="password")
    if pwd == "xiuxiu888":
        st.session_state.authenticated = True
        st.rerun()
    st.stop()

# --- 连接数据 ---
token = st.secrets["GITHUB_TOKEN"]
repo_name = st.secrets["REPO_NAME"]
g = Github(token)
repo = g.get_repo(repo_name)

# 2. 录入界面
st.title("✨ 财务录入中心")
with st.form("input_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    inv = col1.text_input("Invoice 号码")
    cust = col2.text_input("顾客姓名")
    
    status = st.selectbox("当前状态", ["Pending (待处理)", "Done (已退款)", "Exchange (已换货)"])
    items_text = st.text_area("清单 (产品 RM10)", placeholder="例如：T435 RM16.66\n加绒裤 RM20", height=120)
    
    if st.form_submit_button("🚀 录入并更新看板", use_container_width=True):
        if inv and cust and items_text:
            file = repo.get_contents("data.csv")
            df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
            
            now_kl = get_malaysia_time()
            new_rows = []
            this_total = 0
            
            for line in items_text.strip().split('\n'):
                parts = re.findall(r'(.+?)\s*(?:RM)?\s*([\d.]+)', line, re.IGNORECASE)
                if parts:
                    name, amt = parts[0]
                    amt = float(amt)
                    this_total += amt
                    new_rows.append({
                        '日期': now_kl.strftime("%Y-%m-%d"),
                        '时间': now_kl.strftime("%H:%M"),
                        'Invoice': inv, '客户': cust, '货物': name.strip(), '金额': amt, '状态': status
                    })
            
            if new_rows:
                updated_df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                repo.update_file(file.path, f"Live Update {inv}", updated_df.to_csv(index=False), file.sha)
                st.success(f"✅ 已记录！单笔总计：RM {this_total:.2f}")
                st.balloons()
                st.rerun()

# 3. 智慧看板
try:
    file = repo.get_contents("data.csv")
    df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
    
    if not df.empty:
        df['金额'] = pd.to_numeric(df['金额'])
        st.divider()
        tab1, tab2, tab3 = st.tabs(["📊 数据看板", "🔍 智能搜索", "📥 下载报表"])

        with tab1:
            # 顶部数据卡片
            m_col1, m_col2 = st.columns(2)
            total_rm = df['金额'].sum()
            pending_count = len(df[df['状态'].str.contains("Pending")])
            m_col1.metric("总退款累计", f"RM {total_rm:.2f}")
            m_col2.metric("待处理单量", f"{pending_count} 单", delta_color="inverse")
            
            # 趋势图
            st.write("📈 近期退款趋势")
            daily_chart = df.groupby('日期')['金额'].sum()
            st.line_chart(daily_chart)
            
            # 状态分布
            st.write("📋 状态分布统计")
            status_summary = df.groupby('状态').size()
            st.bar_chart(status_summary)

        with tab2:
            q = st.text_input("🔍 输入名字、产品或 Invoice 搜索")
            if q:
                res = df[df.apply(lambda row: q.lower() in row.astype(str).str.lower().values, axis=1)]
                st.dataframe(res, use_container_width=True)
            else:
                st.dataframe(df.sort_index(ascending=False), use_container_width=True)

        with tab3:
            st.subheader("📥 导出备份")
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("下载 Excel 对账单", csv, f"XiuXiu_Report_{get_malaysia_time().strftime('%Y%m%d')}.csv", "text/csv")
except:
    st.info("数据同步中...")
