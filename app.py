import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

# 1. 页面配置
st.set_page_config(page_title="XiuXiu Live 退款助手-标准版", layout="centered", page_icon="💰")

def get_kl_time():
    kl_tz = pytz.timezone('Asia/Kuala_Lumpur')
    return datetime.now(kl_tz)

# --- 登录系统 ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("✨ XiuXiu Live 系统登录")
    pwd = st.text_input("请输入口令:", type="password")
    if pwd == "xiuxiu888":
        st.session_state.authenticated = True
        st.rerun()
    st.stop()

# 2. 连接 GitHub
token = st.secrets["GITHUB_TOKEN"]
repo_name = st.secrets["REPO_NAME"]
g = Github(token)
repo = g.get_repo(repo_name)

st.title("📱 XiuXiu Live 退款录入")

# 3. 录入界面
with st.form("my_form", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    inv = col_a.text_input("Invoice 号码")
    cust = col_b.text_input("顾客姓名")
    
    status = st.selectbox("当前状态", ["Pending (待处理)", "Done (已退款)", "Exchange (已换货)"])
    items_text = st.text_area("清单 (产品 RM10)", height=100)
    
    submitted = st.form_submit_button("🚀 保存记录", use_container_width=True)

    if submitted:
        if inv and cust and items_text:
            file = repo.get_contents("data.csv")
            df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
            
            now_kl = get_kl_time()
            new_rows = []
            this_total = 0
            
            for line in items_text.strip().split('\n'):
                parts = re.findall(r'(.+?)\s*(?:RM)?\s*([\d.]+)', line, re.IGNORECASE)
                if parts:
                    p_name, p_amt = parts[0]
                    p_amt = float(p_amt)
                    this_total += p_amt
                    new_rows.append({
                        '日期': now_kl.strftime("%Y-%m-%d"),
                        '时间': now_kl.strftime("%H:%M"),
                        'Invoice': inv,
                        '客户': cust,
                        '货物': p_name.strip(),
                        '金额': p_amt,
                        '状态': status
                    })
            
            if new_rows:
                updated_df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                repo.update_file(file.path, f"Update {inv}", updated_df.to_csv(index=False), file.sha)
                st.success(f"✅ 已保存！总计: RM {this_total:.2f}")
                st.rerun()

# 4. 统计与查询
try:
    file = repo.get_contents("data.csv")
    show_df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
    
    if not show_df.empty:
        st.divider()
        tab1, tab2, tab3 = st.tabs(["📅 日期汇总", "🔍 搜索/删除", "📥 下载"])

        with tab1:
            st.subheader("📅 每日退款汇总")
            daily = show_df.groupby('日期')['金额'].sum().reset_index().sort_values('日期', ascending=False)
            for _, row in daily.iterrows():
                st.write(f"📅 {row['日期']} --- **RM {row['金额']:.2f}**")

        with tab2:
            st.subheader("🔍 记录管理")
            search_q = st.text_input("输入名字或 Invoice 查询:")
            
            # 过滤数据
            if search_q:
                display_df = show_df[show_df['客户'].str.contains(search_q, na=False, case=False) | 
                                     show_df['Invoice'].str.contains(search_q, na=False, case=False)]
            else:
                display_df = show_df.copy()

            # 显示带删除按钮的列表
            for i, row in display_df.sort_index(ascending=False).iterrows():
                with st.expander(f"📌 {row['日期']} | {row['客户']} | RM {row['金额']}"):
                    st.write(f"Invoice: {row['Invoice']}")
                    st.write(f"产品: {row['货物']}")
                    st.write(f"状态: {row['状态']}")
                    
                    # 删除按钮
                    if st.button(f"🗑️ 删除此条记录", key=f"del_{i}"):
                        # 执行删除逻辑
                        new_df = show_df.drop(i)
                        repo.update_file(file.path, "Delete record", new_df.to_csv(index=False), file.sha)
                        st.error("⚠️ 记录已删除！")
                        st.rerun()

        with tab3:
            csv = show_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载 Excel (CSV)", csv, f"XiuXiu_{get_kl_time().strftime('%Y%m%d')}.csv", "text/csv")
except:
    st.info("数据同步中...")
