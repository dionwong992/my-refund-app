import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re

st.set_page_config(page_title="退款记录助手-专业版", layout="centered")
st.title("📱 退款记录 (多项录入)")

# 1. 自动连接 GitHub
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except:
    st.error("配置错误，请检查 Secrets 是否填对")
    st.stop()

# 2. 录入界面
with st.form("my_form", clear_on_submit=True):
    inv = st.text_input("Invoice 号码")
    cust = st.text_input("顾客姓名")
    
    st.info("💡 输入说明：\n每行一个产品，格式为：**产品名称 + 空格 + 金额**\n例如：\n苹果 10\n香蕉 25.5")
    items_text = st.text_area("货物清单及金额", height=150)
    
    submitted = st.form_submit_button("🚀 自动计算总额并保存", use_container_width=True)

    if submitted:
        if inv and cust and items_text:
            # 读取当前 data.csv
            file = repo.get_contents("data.csv")
            df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
            
            # 解析多行输入
            new_rows = []
            current_total = 0
            lines = items_text.strip().split('\n')
            
            for line in lines:
                # 寻找每一行末尾的数字作为金额
                parts = re.findall(r'(.+)\s+([\d.]+)', line)
                if parts:
                    p_name, p_amt = parts[0]
                    p_amt = float(p_amt)
                    current_total += p_amt
                    new_rows.append({
                        '日期': datetime.now().strftime("%Y-%m-%d %H:%M"),
                        'Invoice': inv,
                        '客户': cust,
                        '货物': p_name.strip(),
                        '金额': p_amt
                    })
            
            if new_rows:
                new_df = pd.DataFrame(new_rows)
                updated_df = pd.concat([df, new_df], ignore_index=True)
                # 推送回 GitHub
                repo.update_file(file.path, f"Update {inv}", updated_df.to_csv(index=False), file.sha)
                st.success(f"✅ 保存成功！本单总计: ${current_total:.2f}")
                st.balloons() # 撒花庆祝
                st.rerun()
        else:
            st.warning("请填好 Invoice、姓名和货品清单")

# 3. 统计功能
try:
    file = repo.get_contents("data.csv")
    show_df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
    
    if not show_df.empty:
        st.divider()
        st.subheader("📊 历史记录与统计")
        
        # 选人看总额
        all_customers = ["全部顾客"] + list(show_df['客户'].unique())
        selected_cust = st.selectbox("筛选顾客查看总退款:", all_customers)
        
        if selected_cust != "全部顾客":
            cust_total = show_df[show_df['客户'] == selected_cust]['金额'].sum()
            st.metric(label=f"{selected_cust} 的累计退款总额", value=f"${cust_total:.2f}")
        
        st.dataframe(show_df.sort_index(ascending=False), use_container_width=True)
except:
    st.info("正在加载历史数据...")
