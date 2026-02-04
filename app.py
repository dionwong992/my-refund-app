import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 页面配置
st.set_page_config(page_title="退货记录助手", layout="centered")

st.title("📱 退货记录助手")

# --- 核心连接部分 (就是你截图里问的地方) ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # ttl=0 强制每次都从 Google 读取最新数据，不使用缓存
    df = conn.read(ttl=0)
except Exception:
    # 如果读取失败（比如表格完全是空的），手动建立结构
    df = pd.DataFrame(columns=['日期', 'Invoice', '客户', '货物', '金额'])

# 确保金额是数字，防止报错
if not df.empty:
    df['金额'] = pd.to_numeric(df['金额'], errors='coerce').fillna(0)

# --- 输入表单 ---
with st.form("input_form", clear_on_submit=True):
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
            # 把新数据加到旧数据后面
            updated_df = pd.concat([df, new_row], ignore_index=True)
            # 写入 Google Sheets
            conn.update(data=updated_df)
            st.success("✅ 已同步到 Google Sheets！")
            st.rerun()
        else:
            st.warning("请填好 Invoice 和姓名")

# --- 显示历史 ---
with st.expander("📂 查看已保存记录"):
    st.dataframe(df.sort_index(ascending=False), use_container_width=True)
