import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

# --- 1. 页面配置 ---
st.set_page_config(page_title="XiuXiu Live 财务增强版", layout="centered", page_icon="💰")

def get_kl_time():
    kl_tz = pytz.timezone('Asia/Kuala_Lumpur')
    return datetime.now(kl_tz)

# --- 2. 登录逻辑 ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("✨ XiuXiu Live 系统登录")
    pwd = st.text_input("请输入口令:", type="password")
    if pwd == "xiuxiu888":
        st.session_state.authenticated = True
        st.rerun()
    st.stop()

# --- 3. GitHub 连接 ---
@st.cache_resource
def get_repo_connection():
    g = Github(st.secrets["GITHUB_TOKEN"])
    return g.get_repo(st.secrets["REPO_NAME"])

repo = get_repo_connection()

# --- 4. 数据获取函数 ---
@st.cache_data(ttl=5) 
def fetch_data():
    try:
        file = repo.get_contents("data.csv")
        df = pd.read_csv(io.StringIO(file.decoded_content.decode('utf-8-sig')))
        return df, file.sha
    except Exception:
        return pd.DataFrame(columns=['日期', '时间', 'Invoice', '客户', '货物', '金额', '状态']), None

# --- 5. 录入界面 ---
st.title("📱 XiuXiu Live 智能财务系统")

with st.form("my_form", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    inv = col_a.text_input("Invoice 号码")
    cust = col_b.text_input("顾客姓名")
    
    # 🚨 退款模式开关：针对你提到的“全部都是退款”的情况
    is_refund_mode = st.toggle("🚨 开启【全单退款】模式", value=False, help="开启后，即使你粘贴的文字是正数，系统也会自动按退款（负数）处理")
    
    status = st.selectbox("当前状态", [
        "Done (已完成/已退款)", 
        "Pending (待处理)", 
        "Exchange (已换货)", 
        "Rebate (回扣)",
        "Overpaid (多汇款退回)"
    ])
    
    st.markdown("##### 💡 清单录入:")
    st.caption("支持直接粘贴：`T501 KElTIS家休闲百搭短裤 RM24.88 西马包邮(黑)`")
    items_text = st.text_area("在此粘贴清单 (每行一个)", height=200)
    
    submit_button = st.form_submit_button("🚀 自动计算并存入数据库", use_container_width=True)

if submit_button:
    if inv and cust and items_text:
        try:
            df, file_sha = fetch_data()
            now_kl = get_kl_time()
            new_rows = []
            this_batch_total = 0 
            
            for line in items_text.strip().split('\n'):
                line = line.strip()
                if not line: continue
                
                # --- 强大的正则解析：支持金额在中间或前后的长句子 ---
                p_back = r'^(.*?)\s+(?:RM|rm)?\s*(-?[\d.]+)(.*)$'
                p_front = r'^(?:RM|rm)?\s*(-?[\d.]+)\s*(.*)$'
                
                amt_val = 0
                item_desc = ""
                
                m_back = re.search(p_back, line)
                if m_back:
                    name, amt, suffix = m_back.groups()
                    amt_val = float(amt)
                    item_desc = f"{name.strip()} {suffix.strip()}".strip()
                else:
                    m_front = re.search(p_front, line)
                    if m_front:
                        amt, desc = m_front.groups()
                        amt_val = float(amt)
                        item_desc = desc.strip() if desc.strip() else "手工项目"
                    else:
                        st.warning(f"解析失败，请检查格式: {line}")
                        continue

                # --- 智能负数转换逻辑 ---
                # 触发条件：开启了退款模式，或者描述中包含退款关键词
                neg_keywords = ["退", "多", "损", "坏", "扣", "赔", "overpaid", "refund"]
                if is_refund_mode or any(kw in item_desc for kw in neg_keywords):
                    if amt_val > 0:
                        amt_val = -amt_val
                
                this_batch_total += amt_val
                new_rows.append({
                    '日期': now_kl.strftime("%Y-%m-%d"), 
                    '时间': now_kl.strftime("%H:%M"), 
                    'Invoice': inv, 
                    '客户': cust, 
                    '货物': item_desc, 
                    '金额': amt_val, 
                    '状态': status
                })

            if new_rows:
                updated_df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                repo.update_file("data.csv", f"Update {inv}", updated_df.to_csv(index=False, encoding='utf-8-sig'), file_sha)
                
                # 反馈结果
                if this_batch_total < 0:
                    st.warning(f"✅ 录入成功！这笔单子共计退款：RM {abs(this_batch_total):.2f}")
                else:
                    st.success(f"✅ 录入成功！这笔单子共计收入：RM {this_batch_total:.2f}")
                
                st.cache_data.clear()
                st.rerun()
        except Exception as e:
            st.error(f"同步失败: {e}")
    else:
        st.warning("⚠️ 请输入完整信息！")

# --- 6. 财务看板区 ---
st.divider()
try:
    show_df, current_sha = fetch_data()
    if not show_df.empty:
        tab1, tab2, tab3 = st.tabs(["📅 今日对账", "🔍 历史搜索", "📥 导出/删除"])

        with tab1:
            today_str = get_kl_time().strftime("%Y-%m-%d")
            today_data = show_df[show_df['日期'] == today_str]
            
            st.subheader(f"📊 今日统计 ({today_str})")
            if not today_data.empty:
                # 区分收入与退款
                in_amt = today_data[today_data['金额'] > 0]['金额'].sum()
                out_amt = today_data[today_data['金额'] < 0]['金额'].sum()
                net_amt = in_amt + out_amt
                
                c1, c2, c3 = st.columns(3)
                c1.metric("总入账 (销售)", f"RM {in_amt:.2f}")
                c2.metric("总退款 (支出)", f"RM {abs(out_amt):.2f}", delta=f"-{abs(out_amt):.2f}", delta_color="inverse")
                c3.metric("今日净收 (实收)", f"RM {net_amt:.2f}")
                
                st.write("---")
                # 自动为退款金额上色（红色）
                def color_negative(val):
                    color = 'red' if val < 0 else 'black'
                    return f'color: {color}'
                
                st.dataframe(
                    today_data.sort_index(ascending=False).style.applymap(color_negative, subset=['金额']), 
                    use_container_width=True
                )
            else:
                st.info("今日暂无录入数据。")

        with tab2:
            search_q = st.text_input("🔍 搜索任意内容:")
            if search_q:
                mask = show_df.apply(lambda row: row.astype(str).str.contains(search_q, case=False).any(), axis=1)
                st.dataframe(show_df[mask].sort_index(ascending=False), use_container_width=True)
            else:
                st.dataframe(show_df.sort_index(ascending=False).head(50), use_container_width=True)

        with tab3:
            csv_data = show_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载 CSV 报表", csv_data, f"Report_{today_str}.csv", "text/csv")
            
            st.write("---")
            if st.checkbox("🛠️ 危险操作：开启删除模式"):
                for i in reversed(show_df.index[-10:]):
                    row = show_df.iloc[i]
                    if st.button(f"🗑️ 删除: {row['客户']} - {row['货物']} (RM{row['金额']})", key=f"d_{i}"):
                        new_df = show_df.drop(i)
                        repo.update_file("data.csv", "Delete", new_df.to_csv(index=False, encoding='utf-8-sig'), current_sha)
                        st.cache_data.clear()
                        st.rerun()
except Exception:
    st.info("数据连接中...")

