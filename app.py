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
        # 使用 utf-8-sig 处理中文，防止 Excel 打开乱码
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
    status = st.selectbox("当前状态", ["Pending (待处理)", "Done (已退款)", "Exchange (已换货)", "Rebate (回扣)"])
    
    st.markdown("##### 💡 格式支持说明:")
    st.caption("可以直接粘贴：`-Z589 GAOGAO RM26(紫)` 或 `回扣 -RM10` (每行一个)")
    items_text = st.text_area("清单录入", height=150)
    
    submit_button = st.form_submit_button("🚀 确认并保存到 GitHub", use_container_width=True)

if submit_button:
    if inv and cust and items_text:
        try:
            df, file_sha = fetch_data()
            now_kl = get_kl_time()
            new_rows = []
            this_total = 0
            
            for line in items_text.strip().split('\n'):
                line = line.strip()
                if not line: continue
                
                # --- 核心正则优化 ---
                # 能够处理: "-商品名 RM26(备注)" 或 "商品名 26" 或 "回扣 -10"
                pattern = r'^-?\s*(.*?)\s+(?:RM|rm)?\s*(-?[\d.]+)(.*)$'
                match = re.search(pattern, line)
                
                if match:
                    raw_name, amt, suffix = match.groups()
                    try:
                        amt_val = float(amt)
                        this_total += amt_val
                        # 自动清理商品名并合并颜色等备注
                        full_item_name = f"{raw_name.strip()} {suffix.strip()}".strip()
                        
                        new_rows.append({
                            '日期': now_kl.strftime("%Y-%m-%d"), 
                            '时间': now_kl.strftime("%H:%M"), 
                            'Invoice': inv, 
                            '客户': cust, 
                            '货物': full_item_name, 
                            '金额': amt_val, 
                            '状态': status
                        })
                    except ValueError:
                        st.error(f"金额解析错误: {line}")
                else:
                    st.warning(f"无法解析该行，请确保名称和金额之间有空格: {line}")

            if new_rows:
                updated_df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                repo.update_file("data.csv", f"Update {inv}", updated_df.to_csv(index=False, encoding='utf-8-sig'), file_sha)
                st.success(f"✅ 保存成功！单次总额: RM {this_total:.2f}")
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
        tab1, tab2, tab3 = st.tabs(["📅 财务汇总", "🔍 记录查询", "📥 数据导出/管理"])

        with tab1:
            st.subheader("每日净收支汇总")
            # 这里的金额会自动加减，得到真实对账额度
            daily = show_df.groupby('日期')['金额'].sum().reset_index().sort_values('日期', ascending=False)
            for _, row in daily.iterrows():
                color = "red" if row['金额'] < 0 else "green"
                st.markdown(f"📅 {row['日期']} --- <b style='color:{color}'>RM {row['金额']:.2f}</b>", unsafe_allow_html=True)

        with tab2:
            search_q = st.text_input("🔍 搜索（输入单号、名字、商品或日期）:")
            res = show_df.copy()
            if search_q:
                # 全表模糊搜索
                mask = res.apply(lambda row: row.astype(str).str.contains(search_q, case=False).any(), axis=1)
                res = res[mask]
            st.dataframe(res.sort_index(ascending=False), use_container_width=True)

        with tab3:
            st.subheader("⚙️ 管理选项")
            csv_data = show_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载完整 CSV 表格", csv_data, f"XiuXiu_Live_{get_kl_time().strftime('%Y%m%d')}.csv", "text/csv")
            
            st.divider()
            if st.checkbox("🛠️ 开启删除模式"):
                st.warning("删除后 GitHub 上的数据将同步更新")
                # 显示最近录入的 15 条记录
                for i in reversed(show_df.index[-15:]):
                    row = show_df.iloc[i]
                    with st.expander(f"🗑️ 删: {row['客户']} - {row['货物']} (RM{row['金额']})"):
                        if st.button(f"确定删除此记录", key=f"del_{i}"):
                            new_df = show_df.drop(i)
                            repo.update_file("data.csv", "Delete", new_df.to_csv(index=False, encoding='utf-8-sig'), current_sha)
                            st.cache_data.clear()
                            st.rerun()
    else:
        st.info("💡 库里空空如也，快去录入数据吧！")
except Exception:
    st.info("数据连接中...")
