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
    # 请确保 st.secrets 中配置了 GITHUB_TOKEN 和 REPO_NAME
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
        # 如果文件不存在，创建一个带表头的空 DataFrame
        return pd.DataFrame(columns=['日期', '时间', 'Invoice', '客户', '货物', '金额', '状态']), None

# --- 5. 录入界面 ---
st.title("📱 XiuXiu Live 智能财务系统")

with st.form("my_form", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    inv = col_a.text_input("Invoice 号码")
    cust = col_b.text_input("顾客姓名")
    
    # 🚨 退款模式开关
    is_refund_mode = st.toggle("🚨 开启【全单退款】模式", value=False, help="开启后，系统会自动将所有录入金额转为负数")
    
    status = st.selectbox("当前状态", [
        "Done (已完成/已退款)", 
        "Pending (待处理)", 
        "Exchange (已换货)", 
        "Rebate (回扣)",
        "Overpaid (多汇款退回)"
    ])
    
    st.markdown("##### 💡 清单录入:")
    st.caption("支持格式：`Z014 物品 RM4.99 x3= 14.97` 或 `Z563 物品RM17.88(卡)`")
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
                
                amt_val = 0
                item_desc = ""

                # --- 核心解析正则：匹配 前缀 + RM + 金额 + 后续(含x或=) ---
                # \s* 处理 RM 后面是否有空格的情况
                pattern = r'^(.*?)(?:RM|rm)\s*(-?[\d.]+)(.*)$'
                match = re.search(pattern, line)
                
                if match:
                    prefix, price_str, suffix = match.groups()
                    price = float(price_str)
                    item_desc = f"{prefix.strip()} {suffix.strip()}".strip()
                    
                    # 优先逻辑 1: 寻找等号后的总价 (e.g., = 14.97)
                    if '=' in suffix:
                        total_match = re.search(r'(-?[\d.]+)', suffix.split('=')[1])
                        if total_match:
                            amt_val = float(total_match.group(1))
                    
                    # 优先逻辑 2: 寻找乘号计算 (e.g., x3 或 *3)
                    if amt_val == 0:
                        mult_match = re.search(r'[xX*]\s*(\d+)', suffix)
                        if mult_match:
                            qty = int(mult_match.group(1))
                            amt_val = price * qty
                        else:
                            # 普通单件情况
                            amt_val = price
                else:
                    st.warning(f"⚠️ 无法解析该行，请检查格式: {line}")
                    continue

                # --- 智能负数转换 ---
                neg_keywords = ["退", "多", "损", "坏", "扣", "赔", "overpaid", "refund"]
                if is_refund_mode or any(kw in item_desc.lower() for kw in neg_keywords):
                    amt_val = -abs(amt_val)
                
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
                new_data_df = pd.DataFrame(new_rows)
                updated_df = pd.concat([df, new_data_df], ignore_index=True)
                
                # 更新 GitHub 上的 CSV 文件
                repo.update_file(
                    "data.csv", 
                    f"Update {inv} by XiuXiu System", 
                    updated_df.to_csv(index=False, encoding='utf-8-sig'), 
                    file_sha
                )
                
                if this_batch_total < 0:
                    st.warning(f"✅ 录入成功！共计退款：RM {abs(this_batch_total):.2f}")
                else:
                    st.success(f"✅ 录入成功！共计收入：RM {this_batch_total:.2f}")
                
                st.cache_data.clear()
                st.rerun()

        except Exception as e:
            st.error(f"❌ 同步失败: {e}")
    else:
        st.warning("⚠️ 请输入 Invoice、客户姓名和清单内容！")

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
                in_amt = today_data[today_data['金额'] > 0]['金额'].sum()
                out_amt = today_data[today_data['金额'] < 0]['金额'].sum()
                net_amt = in_amt + out_amt
                
                c1, c2, c3 = st.columns(3)
                c1.metric("总入账", f"RM {in_amt:.2f}")
                c2.metric("总退款", f"RM {abs(out_amt):.2f}", delta=f"-{abs(out_amt):.2f}", delta_color="inverse")
                c3.metric("今日净收", f"RM {net_amt:.2f}")
                
                st.write("---")
                def color_negative(val):
                    color = 'red' if isinstance(val, (int, float)) and val < 0 else 'black'
                    return f'color: {color}'
                
                st.dataframe(
                    today_data.sort_index(ascending=False).style.map(color_negative, subset=['金额']), 
                    use_container_width=True
                )
            else:
                st.info("今日暂无数据。")

        with tab2:
            search_q = st.text_input("🔍 搜索任意内容 (如客户名、Invoice、货物):")
            if search_q:
                mask = show_df.apply(lambda row: row.astype(str).str.contains(search_q, case=False).any(), axis=1)
                st.dataframe(show_df[mask].sort_index(ascending=False), use_container_width=True)
            else:
                st.dataframe(show_df.sort_index(ascending=False).head(50), use_container_width=True)

        with tab3:
            csv_data = show_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载完整 CSV 报表", csv_data, f"Full_Report_{today_str}.csv", "text/csv")
            
            st.write("---")
            if st.checkbox("🛠️ 开启删除模式"):
                st.warning("删除操作不可撤销，请谨慎操作最近 10 条记录：")
                for i in reversed(show_df.index[-10:]):
                    row = show_df.iloc[i]
                    if st.button(f"🗑️ 删除: {row['客户']} - {row['货物']} (RM{row['金额']})", key=f"d_{i}"):
                        new_df = show_df.drop(i)
                        repo.update_file("data.csv", "Delete record", new_df.to_csv(index=False, encoding='utf-8-sig'), current_sha)
                        st.cache_data.clear()
                        st.rerun()
except Exception:
    st.info("正在连接云端数据库...")

