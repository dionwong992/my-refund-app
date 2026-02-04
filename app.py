import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 适配手机
st.set_page_config(page_title="退款助手", layout="centered")
st.title("📱 永久记录器")

# 建立连接
conn = st.connection("gsheets", type=GSheetsConnection)

# 强刷数据 (ttl=0)
try:
    df = conn.read(ttl=0)
except:
    df = pd.DataFrame(columns=['日期', 'Invoice', '客户', '货物', '金额'])

# 录入表单
with st.form("my_form", clear_on_submit=True):
    inv = st.text_input("Invoice 号码")
    cust = st.text_input("顾客姓名")
    prod = st.text_input("货物名称")
    amt = st.number_input("金额", min_value=0.0)
    
    if st.form_submit_button("🚀 保存并同步", use_container_width=True):
        if inv and cust:
            new_row = pd.DataFrame([[datetime.now().strftime("%Y-%m-%d %H:%M"), inv, cust, prod, amt]], 
                                    columns=['日期', 'Invoice', '客户', '货物', '金额'])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            # 这一步会执行写入
            conn.update(data=updated_df)
            st.success("✅ 存入成功！")
            st.rerun()

# 历史查看
with st.expander("📂 查看历史"):
    st.dataframe(df.sort_index(ascending=False), use_container_width=True)
