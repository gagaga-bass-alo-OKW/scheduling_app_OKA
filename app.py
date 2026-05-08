import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import random

# ==========================================
# 🛡️ 1. 基本設定 & セキュリティ
# ==========================================
st.set_page_config(page_title="ALOHA面談日程調整システム", layout="wide")

# Streamlitのデフォルトメニューを隠す（運用用）
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 📅 2. 時間枠設定 & ソート用ロジック
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

def get_sort_key(val):
    if not val or pd.isna(val) or not isinstance(val, str): return (99, 99)
    try:
        parts = val.split(" ")
        d_index = ALL_DAYS_ORDER.index(parts[0]) if parts[0] in ALL_DAYS_ORDER else 99
        h_num = int(parts[1].split(":")[0])
        return (d_index, h_num)
    except: return (99, 99)

# ==========================================
# ☁️ 3. Googleスプレッドシート連携
# ==========================================
@st.cache_resource
def get_spreadsheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_url(st.secrets["spreadsheet_url"])

def load_data(sheet_name):
    try:
        sh = get_spreadsheet()
        ws = sh.worksheet(sheet_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data).fillna("")
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

# グリッドUI
def render_schedule_grid(default_selected=[], key_suffix=""):
    st.write("▼ 可能な日時にチェック ✅ を入れてください")
    times_wd = [f"{h}:00-{h+1}:00" for h in HOURS_WEEKDAY]
    df_wd = pd.DataFrame(False, index=times_wd, columns=DAYS_WEEKDAY)
    times_we = [f"{h}:00-{h+1}:00" for h in HOURS_WEEKEND]
    df_we = pd.DataFrame(False, index=times_we, columns=DAYS_WEEKEND)

    for s in default_selected:
        try:
            parts = s.split(" ")
            d, t = parts[0], parts[1]
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
# 🖥️ 4. メインアプリケーション
# ==========================================
st.title("📅 ALOHA面談日程調整システム")

# ステータス確認
status_df = load_data("settings")
is_open = status_df.iloc[0]["status"] == "OPEN" if not status_df.empty else True

if is_open:
    st.markdown('#### <span style="color:green">🟢 生徒申し込み受付中</span>', unsafe_allow_html=True)
else:
    st.markdown('#### <span style="color:red">🔴 現在、受付を停止しています</span>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🏫 生徒用入力", "🎓 大学生用入力", "⚙️ 管理者専用"])

# --- Tab 1: 生徒 ---
with tab1:
    if not is_open:
        st.warning("現在は申し込みを受け付けていません。次回案内をお待ちください。")
    else:
        with st.form("student_form"):
            col1, col2 = st.columns(2)
            with col1:
                s_name = st.text_input("氏名（本名フルネーム） ※").strip()
                s_school = st.text_input("学校名 ※")
            with col2:
                s_grade = st.selectbox("学年 ※", ["中1", "中2", "中3", "高1", "高2", "高3"], index=None)
                s_stream = st.radio("文理選択 ※", ["文系", "理系", "未定"], horizontal=True)
            s_q = st.text_area("当日相談したいこと ※")
            s_slots = render_schedule_grid([], "student")
            
            if st.form_submit_button("送信"):
                if s_name and s_slots and s_grade:
                    df = load_data("students")
                    new_row = {"生徒氏名": s_name, "学校": s_school, "学年": s_grade, "文理": s_stream, "質問内容": s_q, "可能日時": ",".join(s_slots)}
                    df = pd.concat([df[df["生徒氏名"] != s_name], pd.DataFrame([new_row])]) if not df.empty else pd.DataFrame([new_row])
                    save_data(df, "students")
                    st.success(f"{s_name}さんの希望を登録しました！")
                else:
                    st.error("氏名、学年、日時は必須入力です。")

# --- Tab 2: 大学生 ---
with tab2:
    st.header("メンター用：空きコマ登録")
    c1, c2, c3 = st.columns([2, 2, 1])
    m_name_in = c1.text_input("氏名")
    m_pass_in = c2.text_input("パスワード", type="password")
    if c3.button("読込/新規"):
        st.session_state["m_user"] = m_name_in
        st.session_state["m_pass"] = m_pass_in

    if "m_user" in st.session_state:
        m_user = st.session_state["m_user"]
        df_m = load_data("mentors")
        m_data = df_m[df_m["メンター氏名"] == m_user].iloc[0] if not df_m.empty and m_user in df_m["メンター氏名"].values else None
        
        # パスワードチェック（新規の場合はスルー）
        if m_data is not None and str(m_data["パスワード"]) != st.session_state["m_pass"]:
            st.error("パスワードが一致しません。")
        else:
            with st.form("mentor_form"):
                st.info(f"編集モード: {m_user}")
                m_stream = st.multiselect("対応可能文理", ["文系", "理系"], default=m_data["文理"].split(",") if m_data is not None else [])
                m_slots = render_schedule_grid(m_data["可能日時"].split(",") if m_data is not None else [], "mentor_in")
                if st.form_submit_button("保存"):
                    new_row = {"メンター氏名": m_user, "文理": ",".join(m_stream), "可能日時": ",".join(m_slots), "パスワード": st.session_state["m_pass"]}
                    df_m = pd.concat([df_m[df_m["メンター氏名"] != m_user], pd.DataFrame([new_row])]) if not df_m.empty else pd.DataFrame([new_row])
                    save_data(df_m, "mentors")
                    st.success("シフト情報を保存しました。")

# --- Tab 3: 管理者 ---
with tab3:
    if st.text_input("管理者パスワード", type="password") == st.secrets["ADMIN_PASSWORD"]:
        ad_tabs = st.tabs(["📊 データ確認・編集", "🎯 マッチング実行", "⚙️ システム設定"])
        
        # --- データ確認・編集 ---
        with ad_tabs[0]:
            st.subheader("生徒データ")
            df_s_all = load_data("students")
            ed_s = st.data_editor(df_s_all, num_rows="dynamic", use_container_width=True, key="admin_s")
            if st.button("生徒データを更新保存"): 
                save_data(ed_s, "students")
                st.rerun()
            
            st.write("---")
            st.subheader("メンターデータ")
            df_m_all = load_data("mentors")
            ed_m = st.data_editor(df_m_all, num_rows="dynamic", use_container_width=True, key="admin_m")
            if st.button("メンターデータを更新保存"): 
                save_data(ed_m, "mentors")
                st.rerun()

        # --- マッチング実行 ---
        with ad_tabs[1]:
            st.subheader("指名マッチング設定")
            if "fixed_pairs" not in st.session_state:
                st.session_state["fixed_pairs"] = pd.DataFrame(columns=["生徒氏名", "メンター氏名"])
            
            s_list = [""] + df_s_all["生徒氏名"].tolist() if not df_s_all.empty else [""]
            m_list = [""] + df_m_all["メンター氏名"].tolist() if not df_m_all.empty else [""]
            
            st.session_state["fixed_pairs"] = st.data_editor(
                st.session_state["fixed_pairs"],
                column_config={
                    "生徒氏名": st.column_config.SelectboxColumn("生徒", options=s_list),
                    "メンター氏名": st.column_config.SelectboxColumn("メンター", options=m_list)
                }, num_rows="dynamic"
            )

            if st.button("🚀 自動マッチング開始（均等化優先）", type="primary"):
                df_st = load_data("students")
                df_mt = load_data("mentors")
                
                if not df_st.empty and not df_mt.empty:
                    results = []
                    mentor_schedule = {m: set(row["可能日時"].split(",")) for m, row in df_mt.set_index("メンター氏名").iterrows()}
                    mentor_assignments = {m: set() for m in mentor_schedule.keys()}
                    mentor_streams = {m: row["文理"].split(",") for m, row in df_mt.set_index("メンター氏名").iterrows()}

                    # 均等化スコアリング関数（担当数が多いほど超減点）
                    def calc_score(m_name, slot):
                        count = len(mentor_assignments[m_name])
                        score = count * -1000  # 均等化ペナルティ
                        assigned = mentor_assignments[m_name]
                        idx = TIME_SLOTS.index(slot) if slot in TIME_SLOTS else -1
                        if idx != -1:
                            adj = [TIME_SLOTS[idx-1] if idx>0 else "", TIME_SLOTS[idx+1] if idx<len(TIME_SLOTS)-1 else ""]
                            if any(a in assigned for a in adj): score += 100 # 連続勤務加点
                        return score + random.random()

                    processed_s = set()
                    # PHASE 0: 指名ペア
                    for _, pair in st.session_state["fixed_pairs"].iterrows():
                        fs, fm = pair["生徒氏名"], pair["メンター氏名"]
                        if fs and fm and fs in df_st["生徒氏名"].values:
                            s_row = df_st[df_st["生徒氏名"]==fs].iloc[0]
                            s_slots = set(s_row["可能日時"].split(","))
                            common = list(s_slots & mentor_schedule.get(fm, set()))
                            if common:
                                common.sort(key=lambda s: calc_score(fm, s), reverse=True)
                                sel = common[0]
                                mentor_schedule[fm].remove(sel); mentor_assignments[fm].add(sel)
                                results.append({"生徒氏名":fs,"決定メンター":fm,"決定日時":sel,"ステータス":"決定(指名)","学年":s_row["学年"]})
                                processed_s.add(fs)

                    # PHASE 1: 一般マッチング
                    remaining_st = df_st[~df_st["生徒氏名"].isin(processed_s)].to_dict('records')
                    remaining_st.sort(key=lambda x: len(x["可能日時"].split(","))) # 候補が少ない生徒から

                    for s_row in remaining_st:
                        sn = s_row["生徒氏名"]
                        s_slots = set(s_row["可能日時"].split(","))
                        candidates = []
                        for slot in s_slots:
                            for mn in mentor_schedule.keys():
                                if slot in mentor_schedule[mn]:
                                    if s_row["文理"] == "未定" or s_row["文理"] in mentor_streams[mn]:
                                        candidates.append((mn, slot))
                        
                        if candidates:
                            candidates.sort(key=lambda x: calc_score(x[0], x[1]), reverse=True)
                            ms, ts = candidates[0]
                            mentor_schedule[ms].remove(ts); mentor_assignments[ms].add(ts)
                            results.append({"生徒氏名":sn,"決定メンター":ms,"決定日時":ts,"ステータス":"決定","学年":s_row["学年"]})
                        else:
                            results.append({"生徒氏名":sn,"決定メンター":None,"決定日時":None,"ステータス":"❌枠なし","学年":s_row["学年"]})
                    
                    st.session_state['matching_results'] = pd.DataFrame(results)

            if st.session_state.get('matching_results') is not None:
                st.write("---")
                st.subheader("調整と確認")
                final_ed = st.data_editor(st.session_state['matching_results'], use_container_width=True)
                
                counts = final_ed[final_ed["決定メンター"].notna()]["決定メンター"].value_counts()
                st.bar_chart(counts)
                st.write("📊 各メンターの合計担当回数")
                st.table(counts)

        # --- システム設定 ---
        with ad_tabs[2]:
            st.subheader("受付ステータス切替")
            new_status = st.radio("現在の受付状態", ["OPEN", "CLOSED"], index=0 if is_open else 1)
            if st.button("設定を保存"):
                save_data(pd.DataFrame([{"status": new_status}]), "settings")
                st.rerun()
