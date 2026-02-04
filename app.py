import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="退款助手", layout="centered")
st.title("📱 永久记录器")

# 1. 建立连接
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 读取数据 (增加 ttl=0 强制刷新)
try:
    df = conn.read(ttl=0)
except:
    # 如果读取失败，创建一个标准结构的表格
    df = pd.DataFrame(columns=['日期', 'Invoice', '客户', '货物', '金额'])

# 3. 录入表单
with st.form("my_form", clear_on_submit=True):
    inv = st.text_input("Invoice 号码")
    cust = st.text_input("顾客姓名")
    prod = st.text_input("货物名称")
    amt = st.number_input("金额", min_value=0.0)
    
    if st.form_submit_button("🚀 保存并同步", use_container_width=True):
        if inv and cust:
            # 构造新行
            new_row = pd.DataFrame([{
                '日期': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'Invoice': inv,
                '客户': cust,
                '货物': prod,
                '金额': amt
            }])
            # 合并数据
            updated_df = pd.concat([df, new_row], ignore_index=True)
            # 核心：写入 Google Sheets
            conn.update(data=updated_df)
            st.success("✅ 存入成功！")
            st.rerun()

# 4. 历史查看
st.divider()
st.subheader("历史记录")
st.dataframe(df, use_container_width=True)
