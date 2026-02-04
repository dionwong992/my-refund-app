import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io

st.set_page_config(page_title="退款助手 GitHub 版", layout="centered")
st.title("📱 退款记录 (GitHub 同步)")

# 1. 自动连接 GitHub
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except:
    st.error("请先在 Secrets 里配置好 GITHUB_TOKEN 和 REPO_NAME")
    st.stop()

# 2. 录入界面
with st.form("my_form", clear_on_submit=True):
    inv = st.text_input("Invoice 号码")
    cust = st.text_input("顾客姓名")
    prod = st.text_input("货物名称")
    amt = st.number_input("金额", min_value=0.0)
    
    if st.form_submit_button("🚀 保存到 GitHub"):
        if inv and cust:
            # 获取当前 data.csv 内容
            file = repo.get_contents("data.csv")
            df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
            
            # 增加新行
            new_row = pd.DataFrame([[datetime.now().strftime("%Y-%m-%d %H:%M"), inv, cust, prod, amt]], 
                                    columns=['日期', 'Invoice', '客户', '货物', '金额'])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            
            # 写回 GitHub
            repo.update_file(file.path, "Update data", updated_df.to_csv(index=False), file.sha)
            st.success("✅ 存入 GitHub 成功！")
            st.rerun()

# 3. 查看明细
try:
    file = repo.get_contents("data.csv")
    show_df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
    st.dataframe(show_df.sort_index(ascending=False))
except:
    st.info("数据加载中...")
