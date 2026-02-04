import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re

# 1. 页面配置 - 改为 XiuXiu Live
st.set_page_config(page_title="XiuXiu Live 退款助手", layout="centered", page_icon="📱")
st.title("✨ XiuXiu Live 退款财务记录")

# 连接 GitHub
try:
    token = st.secrets["GITHUB_TOKEN"]
    repo_name = st.secrets["REPO_NAME"]
    g = Github(token)
    repo = g.get_repo(repo_name)
except:
    st.error("配置错误，请检查 Secrets")
    st.stop()

# 2. 录入界面
with st.form("my_form", clear_on_submit=True):
    inv = st.text_input("Invoice 号码")
    cust = st.text_input("顾客姓名")
    
    st.info("💡 格式：产品名称 + 金额 (支持 RM)\n例如：T435大码宽衣 RM16.66")
    items_text = st.text_area("货物清单及金额", height=150)
    
    submitted = st.form_submit_button("🚀 自动计算并保存到 XiuXiu 记录", use_container_width=True)

    if submitted:
        if inv and cust and items_text:
            file = repo.get_contents("data.csv")
            df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
            
            new_rows = []
            current_total = 0
            lines = items_text.strip().split('\n')
            
            for line in lines:
                # 增强匹配：自动识别 RM 和金额
                parts = re.findall(r'(.+?)\s*(?:RM)?\s*([\d.]+)', line, re.IGNORECASE)
                if parts:
                    p_name, p_amt = parts[0]
                    p_amt = float(p_amt)
                    current_total += p_amt
                    new_rows.append({
                        '日期': datetime.now().strftime("%Y-%m-%d"),
                        '时间': datetime.now().strftime("%H:%M"),
                        'Invoice': inv,
                        '客户': cust,
                        '货物': p_name.strip(),
                        '金额': p_amt
                    })
            
            if new_rows:
                new_df = pd.DataFrame(new_rows)
                updated_df = pd.concat([df, new_df], ignore_index=True)
                repo.update_file(file.path, f"XiuXiu Update {inv}", updated_df.to_csv(index=False), file.sha)
                st.success(f"✅ 保存成功！本单总计: RM {current_total:.2f}")
                st.balloons()
                st.rerun()

# 3. 统计汇总区域
try:
    file = repo.get_contents("data.csv")
    show_df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
    
    if not show_df.empty:
        show_df['金额'] = pd.to_numeric(show_df['金额'])
        
        st.divider()
        tab1, tab2, tab3 = st.tabs(["📅 每日汇总", "👤 顾客对账", "📜 全部记录"])

        with tab1:
            st.subheader("📅 XiuXiu Live 每日汇总")
            daily_summary = show_df.groupby('日期')['金额'].sum().reset_index()
            daily_summary = daily_summary.sort_values('日期', ascending=False)
            
            for _, row in daily_summary.iterrows():
                col1, col2 = st.columns([2, 1])
                col1.markdown(f"**{row['日期']}**")
                col2.markdown(f"**RM {row['金额']:.2f}**")
                st.divider()

        with tab2:
            st.subheader("👤 顾客累计金额")
            all_customers = sorted(show_df['客户'].unique())
            selected_cust = st.selectbox("选择要查询的 XiuXiu 粉丝:", ["-- 请选择 --"] + list(all_customers))
            
            if selected_cust != "-- 请选择 --":
                cust_df = show_df[show_df['客户'] == selected_cust]
                total_sum = cust_df['金额'].sum()
                st.metric(label=f"{selected_cust} 累计退款总额", value=f"RM {total_sum:.2f}")
                
                st.write("📋 消费退款明细：")
                cust_display = cust_df[['日期', 'Invoice', '货物', '金额']].copy()
                cust_display['金额'] = cust_display['金额'].map(lambda x: f"RM {x:.2f}")
                st.table(cust_display)

        with tab3:
            st.subheader("📜 完整记录存档")
            final_df = show_df.copy()
            final_df['金额'] = final_df['金额'].map(lambda x: f"RM {x:.2f}")
            st.dataframe(final_df.sort_index(ascending=False), use_container_width=True)

except Exception as e:
    st.info("XiuXiu Live 数据加载中...")
