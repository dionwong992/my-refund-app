import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

# --- 配置与连接 (保持不变) ---
st.set_page_config(page_title="XiuXiu Live 稳定版", layout="centered", page_icon="💰")

def get_kl_time():
    kl_tz = pytz.timezone('Asia/Kuala_Lumpur')
    return datetime.now(kl_tz)

@st.cache_resource
def get_repo_connection():
    g = Github(st.secrets["GITHUB_TOKEN"])
    return g.get_repo(st.secrets["REPO_NAME"])

repo = get_repo_connection()

# --- 登录逻辑 ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("✨ XiuXiu Live 系统登录")
    pwd = st.text_input("请输入口令:", type="password")
    if pwd == "xiuxiu888":
        st.session_state.authenticated = True
        st.rerun()
    st.stop()

st.title("📱 XiuXiu Live 退款录入")

# --- 录入表单 ---
with st.form("my_form", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    inv = col_a.text_input("Invoice 号码")
    cust = col_b.text_input("顾客姓名")
    status = st.selectbox("当前状态", ["Pending (待处理)", "Done (已退款)", "Exchange (已换货)"])
    
    st.markdown("##### 清单输入格式说明:")
    st.info("支持格式：`商品名称 RM16.66` 或 `商品名称 16.66` (每行一个)")
    items_text = st.text_area("清单录入", height=150, placeholder="例如：T044 KRATAI TSHIRT RM16.66")
    
    if st.form_submit_button("🚀 保存记录", use_container_width=True):
        if inv and cust and items_text:
            try:
                # 获取最新文件
                file = repo.get_contents("data.csv")
                df = pd.read_csv(io.StringIO(file.decoded_content.decode('utf-8-sig')))
                now_kl = get_kl_time()
                new_rows = []
                this_total = 0
                
                for line in items_text.strip().split('\n'):
                    line = line.strip()
                    if not line: continue
                    
                    # 改进的正则：
                    # ^(.*?)\s+          -> 匹配商品名（直到遇到最后一个空格）
                    # (?:RM|rm)?\s* -> 匹配可选的 RM 或 rm，以及可选的空格
                    # ([\d.]+)$          -> 匹配结尾的数字金额
                    pattern = r'^(.*?)\s+(?:RM|rm)?\s*([\d.]+)$'
                    match = re.search(pattern, line)
                    
                    if match:
                        name, amt = match.groups()
                        try:
                            amt_val = float(amt)
                            this_total += amt_val
                            new_rows.append({
                                '日期': now_kl.strftime("%Y-%m-%d"), 
                                '时间': now_kl.strftime("%H:%M"), 
                                'Invoice': inv, 
                                '客户': cust, 
                                '货物': name.strip(), 
                                '金额': amt_val, 
                                '状态': status
                            })
                        except ValueError:
                            st.error(f"金额格式错误: {line}")
                    else:
                        st.warning(f"无法识别该行内容，请检查格式: {line}")

                if new_rows:
                    updated_df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                    # 使用 utf-8-sig 确保中文不乱码
                    repo.update_file(file.path, f"Update {inv}", updated_df.to_csv(index=False, encoding='utf-8-sig'), file.sha)
                    st.success(f"✅ 已保存！总计金额: RM {this_total:.2f}")
                    st.cache_data.clear()
                    st.rerun()
            except Exception as e:
                st.error(f"发生错误: {e}")

# --- 查询与显示区 ---
# (此处保留你原有的 tab1, tab2, tab3 逻辑即可)
# 提示：在显示金额时，可以用 st.write(f"RM {row['金额']}") 来加上 RM 符号
