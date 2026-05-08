import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

# ==========================================
# 🛡️ 1. 基本設定 & カスタムCSS（デザイン・縁取り）
# ==========================================
st.set_page_config(page_title="ALOHA面談日程調整システム", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 通常ボタン（緑の縁取り） */
    div.stButton > button {
        border: 2px solid #4CAF50 !important;
        border-radius: 12px !important;
        color: #4CAF50 !important;
        background-color: white !important;
        font-weight: bold !important;
        padding: 0.6rem 2.5rem !important;
        transition: all 0.3s ease-in-out !important;
    }
    div.stButton > button:hover {
        background-color: #4CAF50 !important;
        color: white !important;
    }

    /* 実行ボタン（青の縁取り） */
    div.stButton > button[kind="primary"] {
        border: 2px solid #1E90FF !important;
        color: #1E90FF !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #1E90FF !important;
        color: white !important;
    }

    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 📅 2. 日時・スプレッドシート設定
# ==========================================
DAYS_WEEKDAY = ["5/18", "5/19", "5/20", "5/21", "5/22"]
HOURS_WEEKDAY = range(19, 23)
DAYS_WEEKEND = ["5/23", "5/24"]
HOURS_WEEKEND = range(10, 23)
ALL_DAYS_ORDER = DAYS_WEEKDAY + DAYS_WEEKEND

TIME_SLOTS = []
for d in DAYS_WEEKDAY:
    for h in HOURS_WEEKDAY: TIME_SLOTS.append(f"{d} {h}:00-{h+1}:00")
for d in DAYS_WEEKEND:
    for h in HOURS_WEEKEND: TIME_SLOTS.append(f"{d} {h}:00-{h+1}:00")

@st.cache_resource
def get_spreadsheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    return gspread.authorize(creds).open_by_url(st.secrets["spreadsheet_url"])

def load_data(sheet_name):
    try:
        sh = get_spreadsheet()
        ws = sh.worksheet(sheet_name)
        df = pd.DataFrame(ws.get_all_records()).fillna("")
        if "パスワード" in df.columns: df["パスワード"] = df["パスワード"].astype(str)
        return df
    except: return pd.DataFrame()

def save_data(df, sheet_name):
    sh = get_spreadsheet()
    try: ws = sh.worksheet(sheet_name)
    except: ws = sh.add_worksheet(title=sheet_name, rows=100, cols=20)
    ws.clear()
    if not df.empty:
        df = df.fillna("")
        ws.update([df.columns.values.tolist()] + df.values.tolist())

def render_schedule_grid(default_selected=[], key_suffix=""):
    st.write("▼ 希望する日時にチェック ✅")
    times_wd = [f"{h}:00-{h+1}:00" for h in HOURS_WEEKDAY]
    df_wd = pd.DataFrame(False, index=times_wd, columns=DAYS_WEEKDAY)
    times_we = [f"{h}:00-{h+1}:00" for h in HOURS_WEEKEND]
    df_we = pd.DataFrame(False, index=times_we, columns=DAYS_WEEKEND)
    for s in default_selected:
        try:
            d, t = s.split(" ")[0], s.split(" ")[1]
            if d in DAYS_WEEKDAY: df_wd.at[t, d] = True
            else: df_we.at[t, d] = True
        except: pass
    ed_wd = st.data_editor(df_wd, key=f"wd_{key_suffix}", use_container_width=True)
    ed_we = st.data_editor(df_we, key=f"we_{key_suffix}", use_container_width=True, height=350)
    res = []
    for t in ed_wd.index:
        for d in ed_wd.columns:
            if ed_wd.at[t, d]: res.append(f"{d} {t}")
    for t in ed_we.index:
        for d in ed_we.columns:
            if ed_we.at[t, d]: res.append(f"{d} {t}")
    return res

# ==========================================
# 🖥️ 3. メインアプリ
# ==========================================
st.title("📅 ALOHA面談日程調整システム")

status_df = load_data("settings")
is_open = status_df.iloc[0]["status"] == "OPEN" if not status_df.empty else True

tab1, tab2, tab3 = st.tabs(["🏫 生徒用入力", "🎓 大学生シフト登録", "⚙️ 管理者パネル"])

with tab1:
    if not is_open: st.error("現在、受付を停止しております。")
    else:
        with st.form("student_form"):
            col1, col2 = st.columns(2)
            with col1:
                s_name = st.text_input("生徒氏名 (フルネーム) ※").strip()
                s_line = st.text_input("あなたのLINE名 ※")
            with col2:
                s_grade = st.selectbox("学年 ※", ["中1", "中2", "中3", "高1", "高2", "高3"], index=None)
                s_stream = st.radio("文理選択 ※", ["文系", "理系", "未定"], horizontal=True)
            s_req = st.text_input("指名・担当希望 (特定のメンター名や属性)")
            s_q = st.text_area("当日相談したいこと ※")
            s_slots = render_schedule_grid([], "student")
            if st.form_submit_button("上記の内容で送信する"):
                if s_name and s_line and s_grade and s_slots:
                    df = load_data("students")
                    row = {"生徒氏名": s_name, "LINE名": s_line, "学年": s_grade, "文理": s_stream, "指名希望": s_req, "質問内容": s_q, "可能日時": ",".join(s_slots)}
                    df = pd.concat([df[df["生徒氏名"] != s_name], pd.DataFrame([row])]) if not df.empty else pd.DataFrame([row])
                    save_data(df, "students"); st.success("送信完了しました！")
                else: st.error("未入力項目があります。")

with tab2:
    st.header("メンター用シフト登録")
    c1, c2, c3 = st.columns([2, 2, 1])
    m_name_in = c1.text_input("メンター氏名")
    m_pass_in = c2.text_input("パスワード", type="password")
    if c3.button("ログイン / 新規"):
        st.session_state["m_user"], st.session_state["m_pass"] = m_name_in, m_pass_in
    if "m_user" in st.session_state:
        m_user = st.session_state["m_user"]
        df_m = load_data("mentors")
        m_data = df_m[df_m["メンター氏名"] == m_user].iloc[0] if not df_m.empty and m_user in df_m["メンター氏名"].values else None
        if m_data is not None and str(m_data["パスワード"]) != st.session_state["m_pass"]: st.error("パスワード不一致")
        else:
            with st.form("mentor_form"):
                st.info(f"編集: {m_user}")
                m_stream = st.multiselect("対応可能文理", ["文系", "理系"], default=m_data["文理"].split(",") if m_data is not None else [])
                m_slots = render_schedule_grid(m_data["可能日時"].split(",") if m_data is not None else [], "mentor_in")
                if st.form_submit_button("この内容で保存する"):
                    new_row = {"メンター氏名": m_user, "文理": ",".join(m_stream), "可能日時": ",".join(m_slots), "パスワード": st.session_state["m_pass"]}
                    df_m = pd.concat([df_m[df_m["メンター氏名"] != m_user], pd.DataFrame([new_row])]) if not df_m.empty else pd.DataFrame([new_row])
                    save_data(df_m, "mentors"); st.success("保存しました。")

with tab3:
    if st.text_input("管理者認証", type="password") == st.secrets["ADMIN_PASSWORD"]:
        ad_tabs = st.tabs(["📊 データ管理", "🚀 マッチング実行", "🔧 設定"])
        
        with ad_tabs[0]:
            st.subheader("生徒データ")
            df_s_all = load_data("students")
            ed_s = st.data_editor(df_s_all, num_rows="dynamic", use_container_width=True)
            if st.button("生徒更新"): save_data(ed_s, "students"); st.rerun()
            st.subheader("メンターデータ")
            df_m_all = load_data("mentors")
            ed_m = st.data_editor(df_m_all, num_rows="dynamic", use_container_width=True)
            if st.button("メンター更新"): save_data(ed_m, "mentors"); st.rerun()

        with ad_tabs[1]:
            st.subheader("🎯 指名マッチング設定（最優先）")
            if "fixed_pairs" not in st.session_state:
                st.session_state["fixed_pairs"] = pd.DataFrame(columns=["生徒氏名", "メンター氏名"])
            
            s_list = [""] + df_s_all["生徒氏名"].tolist() if not df_s_all.empty else [""]
            m_list = [""] + df_m_all["メンター氏名"].tolist() if not df_m_all.empty else [""]
            
            # 管理者がここで「この生徒はこのメンター」と固定できる
            st.session_state["fixed_pairs"] = st.data_editor(
                st.session_state["fixed_pairs"],
                column_config={
                    "生徒氏名": st.column_config.SelectboxColumn("生徒を選択", options=s_list),
                    "メンター氏名": st.column_config.SelectboxColumn("メンターを固定", options=m_list)
                }, num_rows="dynamic"
            )

            if st.button("🚀 自動マッチング（指名優先・均等化）", type="primary"):
                df_st, df_mt = load_data("students"), load_data("mentors")
                if not df_st.empty and not df_mt.empty:
                    results = []
                    m_sched = {m: set(row["可能日時"].split(",")) for m, row in df_mt.set_index("メンター氏名").iterrows()}
                    m_assign = {m: set() for m in m_sched.keys()}
                    m_streams = {m: row["文理"].split(",") for m, row in df_mt.set_index("メンター氏名").iterrows()}

                    def get_score(m_name, slot):
                        score = len(m_assign[m_name]) * -1000 # 担当数多いほど回避
                        idx = TIME_SLOTS.index(slot) if slot in TIME_SLOTS else -1
                        if any(a in m_assign[m_name] for a in ([TIME_SLOTS[idx-1] if idx>0 else "", TIME_SLOTS[idx+1] if idx<len(TIME_SLOTS)-1 else ""])):
                            score += 100 # 連続コマ優先
                        return score + random.random()

                    processed_s = set()
                    # 1. 指名マッチング
                    for _, pair in st.session_state["fixed_pairs"].iterrows():
                        fs, fm = pair["生徒氏名"], pair["メンター氏名"]
                        if fs and fm and fs in df_st["生徒氏名"].values:
                            s_row = df_st[df_st["生徒氏名"]==fs].iloc[0]
                            common = list(set(s_row["可能日時"].split(",")) & m_sched.get(fm, set()))
                            if common:
                                common.sort(key=lambda s: get_score(fm, s), reverse=True)
                                sel = common[0]
                                m_sched[fm].remove(sel); m_assign[fm].add(sel)
                                results.append({"生徒":fs,"メンター":fm,"日時":sel,"区分":"指名確定","LINE":s_row["LINE名"]})
                                processed_s.add(fs)

                    # 2. 一般マッチング（枠の少ない生徒から）
                    rem_st = df_st[~df_st["生徒氏名"].isin(processed_s)].to_dict('records')
                    rem_st.sort(key=lambda x: len(x["可能日時"].split(",")))
                    for s_row in rem_st:
                        s_slots = set(s_row["可能日時"].split(","))
                        cands = []
                        for slot in s_slots:
                            for mn, slots in m_sched.items():
                                if slot in slots and (s_row["文理"] == "未定" or s_row["文理"] in m_streams[mn]):
                                    cands.append((mn, slot))
                        if cands:
                            cands.sort(key=lambda x: get_score(x[0], x[1]), reverse=True)
                            ms, ts = cands[0]
                            m_sched[ms].remove(ts); m_assign[ms].add(ts)
                            results.append({"生徒":s_row["生徒氏名"],"メンター":ms,"日時":ts,"区分":"自動決定","LINE":s_row["LINE名"]})
                        else:
                            results.append({"生徒":s_row["生徒氏名"],"メンター":None,"日時":None,"区分":"❌枠なし","LINE":s_row["LINE名"]})
                    st.session_state['matching_results'] = pd.DataFrame(results)

            if st.session_state.get('matching_results') is not None:
                st.write("---")
                st.data_editor(st.session_state['matching_results'], use_container_width=True)
                counts = st.session_state['matching_results'][st.session_state['matching_results']["メンター"].notna()]["メンター"].value_counts()
                st.bar_chart(counts); st.table(counts)

        with ad_tabs[2]:
            st.subheader("システム設定")
            new_status = st.radio("フォーム受付", ["OPEN", "CLOSED"], index=0 if is_open else 1)
            if st.button("設定保存"): save_data(pd.DataFrame([{"status": new_status}]), "settings"); st.rerun()
