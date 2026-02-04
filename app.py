import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 手机版适配
st.set_page_config(page_title="退款助手(云端版)", layout="centered")

st.title("📱 永久记录器")

# 连接 Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 读取现有数据
try:
    df = conn.read()
except:
    df = pd.DataFrame(columns=['日期', 'Invoice', '客户', '货物', '金额'])

# 录入表单
with st.form("refund_form", clear_on_submit=True):
    st.subheader("📝 录入新记录")
    inv = st.text_input("Invoice 号码")
    cust = st.text_input("顾客姓名")
    prod = st.text_input("货物名称")
    amt = st.number_input("退款金额", min_value=0.0, step=1.0)
    
    if st.form_submit_button("🚀 保存并同步到表格", use_container_width=True):
        if inv and cust:
            new_row = pd.DataFrame([{
                '日期': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'Invoice': inv,
                '客户': cust,
                '货物': prod,
                '金额': amt
            }])
            updated_df = pd.concat([df, new_row], ignore_index=True)
            conn.update(data=updated_df)
            st.success("✅ 已存入 Google Sheets！")
            st.rerun()

# 历史预览
with st.expander("📂 查看已保存记录"):
    st.dataframe(df.sort_index(ascending=False), use_container_width=True)
