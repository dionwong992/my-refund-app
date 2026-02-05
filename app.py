import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io
import re
import pytz

# --- 1. 页面配置 ---
st.set_page_config(page_title="XiuXiu Live 稳定版", layout="centered", page_icon="💰")

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
    # 请确保 Streamlit Cloud 的 Secrets 已配置 GITHUB_TOKEN 和 REPO_NAME
    g = Github(st.secrets["GITHUB_TOKEN"])
    return g.get_repo(st.secrets["REPO_NAME"])

repo = get_repo_connection()

# --- 4. 数据获取函数 ---
@st.cache_data(ttl=5) 
def fetch_data():
    try:
        file = repo.get_contents("data.csv")
        # 使用 utf-8-sig 处理中文，防止乱码
        df = pd.read_csv(io.StringIO(file.decoded_content.decode('utf-8-sig')))
        return df, file.sha
    except Exception as e:
        # 如果文件不存在，返回空表
        return pd.DataFrame(columns=['日期', '时间', 'Invoice', '客户', '货物', '金额', '状态']), None

# --- 5. 录入界面 ---
st.title("📱 XiuXiu Live 退款录入")

with st.form("my_form", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    inv = col_a.text_input("Invoice 号码")
    cust = col_b.text_input("顾客姓名")
    status = st.selectbox("当前状态", ["Pending (待处理)", "Done (已退款)", "Exchange (已换货)"])
    
    st.markdown("##### 清单输入格式说明:")
    st.caption("每行一个商品，支持 RM 格式 (例如: T044 TSHIRT RM16.66)")
    items_text = st.text_area("清单录入", height=150, placeholder="T044 TSHIRT RM16.66\nB002 BAG 25.00")
    
    submit_button = st.form_submit_button("🚀 保存记录", use_container_width=True)

if submit_button:
    if inv and cust and items_text:
        try:
            # 获取当前最新数据
            df, file_sha = fetch_data()
            now_kl = get_kl_time()
            new_rows = []
            this_total = 0
            
            for line in items_text.strip().split('\n'):
                line = line.strip()
                if not line: continue
                
                # --- 修复后的正则：支持有无 RM，支持商品名带空格 ---
                # 逻辑：匹配 [商品名] + [空格] + [可选RM] + [金额]
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
                        st.error(f"金额解析错误: {line}")
                        continue
                else:
                    st.warning(f"格式不符，跳过此行: {line}")

            if new_rows:
                updated_df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                # 保存时强制使用 utf-8-sig
                repo.update_file("data.csv", f"Update {inv}", updated_df.to_csv(index=False, encoding='utf-8-sig'), file_sha)
                st.success(f"✅ 已保存！总计: RM {this_total:.2f}")
                st.cache_data.clear() # 清除缓存
                st.rerun() # 刷新页面显示新数据
        except Exception as e:
            st.error(f"保存失败: {e}")
    else:
        st.warning("⚠️ 请完整填写单号、姓名和清单内容")

# --- 6. 下方展示与管理区 ---
st.divider()

try:
    show_df, current_sha = fetch_data()
    
    if not show_df.empty:
        tab1, tab2, tab3 = st.tabs(["📅 日期汇总", "🔍 记录查询", "📥 下载/管理"])

        with tab1:
            # 按日期求和并倒序排列
            daily = show_df.groupby('日期')['金额'].sum().reset_index().sort_values('日期', ascending=False)
            for _, row in daily.iterrows():
                st.write(f"📅 {row['日期']} --- **RM {row['金额']:.2f}**")

        with tab2:
            search_q = st.text_input("🔍 搜索名字或 Invoice:")
            res = show_df.copy()
            if search_q:
                res = res[res['客户'].str.contains(search_q, na=False, case=False) | 
                          res['Invoice'].str.contains(search_q, na=False, case=False)]
            
            # 排序：索引越大越靠前（即最新录入的在最上面）
            st.dataframe(res.sort_index(ascending=False), use_container_width=True)

        with tab3:
            st.subheader("⚙️ 管理操作")
            csv_data = show_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下载完整 CSV 表格", csv_data, f"Returns_{get_kl_time().strftime('%Y%m%d')}.csv", "text/csv")
            
            st.divider()
            if st.checkbox("🛠️ 开启删除模式"):
                st.info("展开下方卡片以删除单行记录")
                # 仅显示最近的 20 条记录供删除，防止页面太卡
                recent_indices = show_df.index[-20:]
                for i in reversed(recent_indices):
                    row = show_df.iloc[i]
                    with st.expander(f"删除: {row['客户']} - {row['货物']} (RM{row['金额']})"):
                        if st.button(f"确认删除此行", key=f"del_{i}"):
                            new_df = show_df.drop(i)
                            repo.update_file("data.csv", "Delete item", new_df.to_csv(index=False, encoding='utf-8-sig'), current_sha)
                            st.cache_data.clear()
                            st.rerun()
    else:
        st.info("💡 暂无数据记录，快去录入第一条吧！")

except Exception as e:
    st.error(f"数据加载异常: {e}")
