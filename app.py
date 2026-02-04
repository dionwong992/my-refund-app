import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 文件名
FILE_NAME = 'refund_records.csv'

# 手机适配设置
st.set_page_config(page_title="退款助手", layout="centered")

# 初始化数据
if not os.path.exists(FILE_NAME):
    df = pd.DataFrame(columns=['时间', 'Invoice', '客户', '货物', '金额'])
    df.to_csv(FILE_NAME, index=False, encoding='utf-8-sig')

st.title("📱 退款记录助手")

# 简单看板
df = pd.read_csv(FILE_NAME, encoding='utf-8-sig')
if not df.empty:
    total = df['金额'].sum()
    st.metric("累计退款金额", f"RM {total:,.2f}")

# 输入区域
with st.container():
    st.subheader("📝 录入新记录")
    inv = st.text_input("Invoice 号码")
    cust = st.text_input("顾客姓名")
    prod = st.text_input("货物名称")
    amt = st.number_input("退款金额", min_value=0.0, step=1.0)
    
    if st.form_submit_button or st.button("🚀 保存并更新", use_container_width=True):
        if inv and cust and prod:
            new_row = pd.DataFrame([[datetime.now().strftime("%m-%d %H:%M"), inv, cust, prod, amt]], 
                                    columns=['时间', 'Invoice', '客户', '货物', '金额'])
            df = pd.concat([df, new_row], ignore_index=True)
            df.to_csv(FILE_NAME, index=False, encoding='utf-8-sig')
            st.success("保存成功！")
            st.rerun()

# 历史记录
with st.expander("📂 查看历史明细"):
    st.dataframe(df.sort_index(ascending=False), use_container_width=True)
