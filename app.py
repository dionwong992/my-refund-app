import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

# --- 1. 页面配置 ---
st.set_page_config(page_title="XiuXiu Live 增强版", layout="centered", page_icon="💰")

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
st.title("📱 XiuXiu Live 智能录入系统")

with st.form("my_form", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    inv = col_a.text_input("Invoice 号码")
    cust = col_b.text_input("顾客姓名")
    status = st.selectbox("当前状态", [
        "Pending (待处理)", 
        "Done (已完成/退款)", 
        "Exchange (已换货)", 
        "Rebate (回扣)",
        "Overpaid (多汇款退回)"
    ])
    
    st.markdown("##### 💡 智能录入说明:")
    st.caption("系统会自动计算正负号。例如：`退款 RM50` 或 `rm10 多汇` 会自动识别为扣款。")
    items_text = st.text_area("清单录入 (每行一个)", height=150, placeholder="商品A 35\n退款 50\nrm10 多汇\n东西损坏退 5")
    
    submit_button = st.form_submit_button("🚀 自动计算并保存到 GitHub", use_container_width=True)

if submit_button:
    if inv and cust and items_text:
        try:
            df, file_sha = fetch_data()
            now_kl = get_kl_time()
            new_rows = []
            final_net_total = 0 # 用于计算这一单最后的盈亏
            
            for line in items_text.strip().split('\n'):
                line = line.strip()
                if not line: continue
                
                # --- 智能正则解析 ---
                # 模式1: 金额在后 (商品 35)
                # 模式2: 金额在前 (RM50 退款)
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
                        item_desc = desc.strip() if desc.strip() else "手工项"
                    else:
                        st.warning(f"无法解析该行，请检查格式: {line}")
                        continue

                # --- 核心：系统自动识别正负号 ---
                # 负面关键词库
                neg_keywords = ["退", "多", "损", "坏", "扣", "赔", "refund", "overpaid", "回扣"]
                
                # 如果描述包含关键词且金额还没被写成负数，则自动转负
                if any(kw in item_desc for kw in neg_keywords) and amt_val > 0:
                    amt_val = -amt_val
                
                # 累加这一单的总额
                final_net_total += amt_val
                
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
                
                # 根据最终结果弹出不同颜色的提示
                if final_net_total > 0:
                    st.success(f"✅ 保存成功！此单需收客户：RM {final_net_total:.2f}")
                elif final_net_total < 0:
                    st.warning(f"✅ 保存成功！此单需退回客户：RM {abs(final_net_total):.2f}")
                else:
                    st.info(f"✅ 保存成功！此单收支抵消为 0")
                
                st.cache_data.clear()
                st.rerun()
        except Exception as e:
            st.error(f"同步失败: {e}")
    else:
        st.warning("⚠️ 请填好单号、姓名和清单！")

# --- 6. 展示与管理区 ---
st.divider()
try:
    show_df, current_sha = fetch_data()
    if not show_df.empty:
        tab1, tab2, tab3 = st.tabs(["📅 今日财务", "🔍 历史记录", "📥 管理/导出"])

        with tab1:
            today_str = get_kl_time().strftime("%Y-%m-%d")
            today_data = show_df[show_df['日期'] == today_str]
            
            st.subheader(f"📅 今日对账 ({today_str})")
            if not today_data.empty:
                in_amt = today_data[today_data['金额'] > 0]['金额'].sum()
                out_amt = today_data[today_data['金额'] < 0]['金额'].sum()
                
                c1, c2, c3 = st.columns(3)
                c1.metric("总入账 (In)", f"RM {in_amt:.2f}")
                c2.metric("总退款/多汇 (Out)", f"RM {abs(out_amt):.2f}")
                c3.metric("今日净收", f"RM {in_amt + out_amt:.2f}")
                
                st.write("---")
                st.dataframe(today_data.sort_index(ascending=False), use_container_width=True)
            else:
                st.info("今天还没有录入数据哦。")

        with tab2:
            search_q = st.text_input("🔍 全局搜索:")
            res = show_df.copy()
            if search_q:
                mask = res.apply(lambda row: row.astype(str).str.contains(search_q, case=False).any(), axis=1)
                res = res[mask]
            st.dataframe(res.sort_index(ascending=False), use_container_width=True)

        with tab3:
            st.subheader("⚙️ 导出与删除")
            csv_data = show_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载完整 CSV 表格", csv_data, f"XiuXiu_Live_{get_kl_time().strftime('%Y%m%d')}.csv", "text/csv")
            
            if st.checkbox("🛠️ 开启删除模式"):
                for i in reversed(show_df.index[-15:]):
                    row = show_df.iloc[i]
                    with st.expander(f"🗑️ {row['日期']} | {row['客户']} - {row['货物']} (RM{row['金额']})"):
                        if st.button(f"删除记录", key=f"del_{i}"):
                            new_df = show_df.drop(i)
                            repo.update_file("data.csv", "Delete", new_df.to_csv(index=False, encoding='utf-8-sig'), current_sha)
                            st.cache_data.clear()
                            st.rerun()
    else:
        st.info("💡 库里空空如也，快去录入数据吧！")
except Exception:
    st.info("正在连接 GitHub 数据库...")
