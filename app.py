import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re

# 1. 页面配置
st.set_page_config(page_title="XiuXiu Live 终极对账助手", layout="centered", page_icon="💰")

# --- 简单密码保护 ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("✨ XiuXiu Live 财务系统")
        pwd = st.text_input("请输入专属口令进入:", type="password")
        if pwd == "xiuxiu888": # 你可以在这里修改你的密码
            st.session_state.authenticated = True
            st.rerun()
        elif pwd:
            st.error("口令错误，请输入正确的口令。")
        return False
    return True

if check_password():
    # 2. 连接 GitHub
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["REPO_NAME"]
        g = Github(token)
        repo = g.get_repo(repo_name)
    except:
        st.error("配置错误，请检查 Secrets")
        st.stop()

    st.title("✨ XiuXiu Live 财务录入")

    # 3. 录入界面
    with st.form("my_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        inv = col_a.text_input("Invoice 号码")
        cust = col_b.text_input("顾客姓名")
        
        status = st.selectbox("当前状态", ["Pending (待处理)", "Done (已退款)", "Exchange (已换货)"])
        items_text = st.text_area("货物清单 (格式：产品 RM10)", height=120)
        
        submitted = st.form_submit_button("🚀 自动计算并存入仓库", use_container_width=True)

        if submitted:
            if inv and cust and items_text:
                file = repo.get_contents("data.csv")
                df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
                
                # 防止重复提交校验
                if not df.empty and inv in df['Invoice'].values and cust in df['客户'].values:
                    st.warning("⚠️ 发现该 Invoice 已有记录，请确认是否重复录入？")
                
                new_rows = []
                current_total = 0
                lines = items_text.strip().split('\n')
                for line in lines:
                    parts = re.findall(r'(.+?)\s*(?:RM)?\s*([\d.]+)', line, re.IGNORECASE)
                    if parts:
                        p_name, p_amt = parts[0]
                        p_amt = float(p_amt)
                        current_total += p_amt
                        new_rows.append({
                            '日期': datetime.now().strftime("%Y-%m-%d"),
                            'Invoice': inv,
                            '客户': cust,
                            '货物': p_name.strip(),
                            '金额': p_amt,
                            '状态': status
                        })
                
                if new_rows:
                    new_df = pd.DataFrame(new_rows)
                    updated_df = pd.concat([df, new_df], ignore_index=True)
                    repo.update_file(file.path, f"Update {inv}", updated_df.to_csv(index=False), file.sha)
                    st.success(f"✅ 保存成功！单笔总额: RM {current_total:.2f}")
                    st.balloons()
                    st.rerun()

    # 4. 统计与查询
    try:
        file = repo.get_contents("data.csv")
        show_df = pd.read_csv(io.StringIO(file.decoded_content.decode()))
        
        if not show_df.empty:
            st.divider()
            tab1, tab2, tab3 = st.tabs(["📊 财务分析", "🔍 模糊搜索", "📑 下载报表"])

            with tab1:
                st.subheader("📅 日期汇总")
                daily = show_df.groupby('日期')['金额'].sum().reset_index().sort_values('日期', ascending=False)
                for _, row in daily.iterrows():
                    st.write(f"📅 {row['日期']} --- **RM {row['金额']:.2f}**")
                
                st.divider()
                st.subheader("👤 粉丝累计")
                sel_cust = st.selectbox("选择粉丝:", ["-- 查看总额 --"] + sorted(list(show_df['客户'].unique())))
                if sel_cust != "-- 查看总额 --":
                    c_sum = show_df[show_df['客户'] == sel_cust]['金额'].sum()
                    st.metric(label=f"{sel_cust} 累计总额", value=f"RM {c_sum:.2f}")

            with tab2:
                search_q = st.text_input("🔍 输入名字或 Invoice 搜索:")
                if search_q:
                    res = show_df[show_df['客户'].str.contains(search_q, na=False) | 
                                  show_df['Invoice'].str.contains(search_q, na=False)]
                    st.dataframe(res)
                else:
                    st.dataframe(show_df.sort_index(ascending=False))

            with tab3:
                st.subheader("📥 导出财务报表")
                csv = show_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="点击下载 Excel (CSV) 格式",
                    data=csv,
                    file_name=f'XiuXiu_Refund_{datetime.now().strftime("%Y%m%d")}.csv',
                    mime='text/csv',
                )
                st.info("提示：CSV文件可以用 Excel 直接打开。")
    except:
        st.info("数据准备中...")
