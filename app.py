import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

st.set_page_config(page_title="XiuXiu Live 稳定版", layout="centered", page_icon="💰")

def get_kl_time():
    kl_tz = pytz.timezone('Asia/Kuala_Lumpur')
    return datetime.now(kl_tz)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("✨ XiuXiu Live 系统登录")
    pwd = st.text_input("请输入口令:", type="password")
    if pwd == "xiuxiu888":
        st.session_state.authenticated = True
        st.rerun()
    st.stop()

# --- 缓存连接，减少重复握手 ---
@st.cache_resource
def get_repo_connection():
    g = Github(st.secrets["GITHUB_TOKEN"])
    return g.get_repo(st.secrets["REPO_NAME"])

repo = get_repo_connection()

st.title("📱 XiuXiu Live 退款录入")

with st.form("my_form", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    inv = col_a.text_input("Invoice 号码")
    cust = col_b.text_input("顾客姓名")
    status = st.selectbox("当前状态", ["Pending (待处理)", "Done (已退款)", "Exchange (已换货)"])
    items_text = st.text_area("清单 (产品 RM10)", height=100)
    
    if st.form_submit_button("🚀 保存记录", use_container_width=True):
        if inv and cust and items_text:
            file = repo.get_contents("data.csv")
            df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
            now_kl = get_kl_time()
            new_rows = []
            this_total = 0
            for line in items_text.strip().split('\n'):
                parts = re.findall(r'(.+?)\s*(?:RM)?\s*([\d.]+)', line, re.IGNORECASE)
                if parts:
                    name, amt = parts[0]
                    amt = float(amt)
                    this_total += amt
                    new_rows.append({'日期': now_kl.strftime("%Y-%m-%d"), '时间': now_kl.strftime("%H:%M"), 'Invoice': inv, '客户': cust, '货物': name.strip(), '金额': amt, '状态': status})
            if new_rows:
                updated_df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                repo.update_file(file.path, f"Update {inv}", updated_df.to_csv(index=False), file.sha)
                st.success(f"✅ 已保存！总计: RM {this_total:.2f}")
                st.rerun()

# --- 核心提速优化区 ---
try:
    # 使用缓存读取，提速 50%
    @st.cache_data(ttl=10) 
    def fetch_data():
        f = repo.get_contents("data.csv")
        return pd.read_csv(io.StringIO(f.decoded_content.decode())), f.sha

    show_df, file_sha = fetch_data()
    
    if not show_df.empty:
        st.divider()
        tab1, tab2, tab3 = st.tabs(["📅 日期汇总", "🔍 记录查询", "📥 下载/管理"])

        with tab1:
            daily = show_df.groupby('日期')['金额'].sum().reset_index().sort_values('日期', ascending=False)
            for _, row in daily.iterrows():
                st.write(f"📅 {row['日期']} --- **RM {row['金额']:.2f}**")

        with tab2:
            search_q = st.text_input("输入名字或 Invoice:")
            res = show_df.copy()
            if search_q:
                res = res[res['客户'].str.contains(search_q, na=False, case=False) | res['Invoice'].str.contains(search_q, na=False, case=False)]
            # 这里改回简单的表格显示，不加载按钮，速度极快
            st.dataframe(res.sort_index(ascending=False), use_container_width=True)

        with tab3:
            st.subheader("⚙️ 管理操作")
            csv = show_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载 Excel", csv, f"XiuXiu_{get_kl_time().strftime('%Y%m%d')}.csv", "text/csv")
            
            st.divider()
            # 只有勾选这个，才会加载沉重的删除按钮
            if st.checkbox("🛠️ 开启删除模式 (会导致加载变慢)"):
                for i, row in show_df.sort_index(ascending=False).iterrows():
                    with st.expander(f"🗑️ 删: {row['客户']} - {row['货物']} (RM{row['金额']})"):
                        if st.button(f"确认删除此行", key=f"del_{i}"):
                            new_df = show_df.drop(i)
                            repo.update_file("data.csv", "Delete", new_df.to_csv(index=False), file_sha)
                            st.cache_data.clear() # 清除缓存强制刷新
                            st.rerun()
except:
    st.info("数据连接中...")
