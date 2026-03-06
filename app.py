import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import random

# ==========================================
# 🛡️ 1. 基本設定・検索除け
# ==========================================
st.set_page_config(page_title="ALOHA面談日程調整", layout="wide")
st.markdown("""<meta name="robots" content="noindex, nofollow">""", unsafe_allow_html=True)

hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ==========================================
# 📅 2. 時間枠設定 & ソート用ロジック
# ==========================================
DAYS_WEEKDAY = ["3/23", "3/24", "3/25", "3/26","3/27"]
HOURS_WEEKDAY = range(19, 23)

DAYS_WEEKEND = ["3/28", "3/29"]
HOURS_WEEKEND = range(10, 23)

ALL_DAYS_ORDER = DAYS_WEEKDAY + DAYS_WEEKEND

TIME_SLOTS = []
for d in DAYS_WEEKDAY:
    for h in HOURS_WEEKDAY:
        TIME_SLOTS.append(f"{d} {h}:00-{h+1}:00")
for d in DAYS_WEEKEND:
    for h in HOURS_WEEKEND:
        TIME_SLOTS.append(f"{d} {h}:00-{h+1}:00")

def get_sort_key(val):
    if not val or pd.isna(val) or not isinstance(val, str):
        return (99, 99)
    try:
        parts = val.split(" ")
        if len(parts) < 2: return (99, 99)
        date_part, time_part = parts[0], parts[1]
        d_index = ALL_DAYS_ORDER.index(date_part) if date_part in ALL_DAYS_ORDER else 99
        h_num = int(time_part.split(":")[0])
        return (d_index, h_num)
    except:
        return (99, 99)

def render_schedule_grid(default_selected=[], key_suffix=""):
    st.write("▼ 以下の表で、可能な日時にチェック ✅ を入れてください")
    
    st.markdown("**📅 平日 (20:00 〜 23:00)**")
    times_wd = [f"{h}:00-{h+1}:00" for h in HOURS_WEEKDAY]
    df_wd = pd.DataFrame(False, index=times_wd, columns=DAYS_WEEKDAY)
    
    times_we = [f"{h}:00-{h+1}:00" for h in HOURS_WEEKEND]
    df_we = pd.DataFrame(False, index=times_we, columns=DAYS_WEEKEND)

    for slot_str in default_selected:
        try:
            parts = slot_str.split(" ")
            d, t = parts[0], parts[1]
            if d in DAYS_WEEKDAY and t in times_wd:
                df_wd.at[t, d] = True
            elif d in DAYS_WEEKEND and t in times_we:
                df_we.at[t, d] = True
        except:
            pass

    edited_wd = st.data_editor(
        df_wd,
        column_config={day: st.column_config.CheckboxColumn(day, width="small") for day in DAYS_WEEKDAY},
        use_container_width=True,
        key=f"grid_wd_{key_suffix}"
    )
    
    st.markdown("**📅 土日祝 (10:00 〜 23:00)**")
    edited_we = st.data_editor(
        df_we,
        column_config={day: st.column_config.CheckboxColumn(day, width="small") for day in DAYS_WEEKEND},
        use_container_width=True,
        height=500,
        key=f"grid_we_{key_suffix}"
    )

    selected_slots = []
    for t in edited_wd.index:
        for d in edited_wd.columns:
            if edited_wd.at[t, d]:
                selected_slots.append(f"{d} {t}")
    for t in edited_we.index:
        for d in edited_we.columns:
            if edited_we.at[t, d]:
                selected_slots.append(f"{d} {t}")
    
    return selected_slots

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

def load_data_from_sheet(sheet_name):
    try:
        sh = get_spreadsheet()
        try:
            worksheet = sh.worksheet(sheet_name)
        except:
            return pd.DataFrame()
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        if "パスワード" in df.columns:
            df["パスワード"] = df["パスワード"].astype(str)
        return df.fillna("")
    except Exception:
        return pd.DataFrame()

def save_data_to_sheet(df, sheet_name):
    sh = get_spreadsheet()
    try:
        worksheet = sh.worksheet(sheet_name)
    except:
        worksheet = sh.add_worksheet(title=sheet_name, rows=100, cols=20)
    df = df.fillna("")
    worksheet.clear()
    if not df.empty:
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())

def append_data_to_sheet(df, sheet_name):
    sh = get_spreadsheet()
    try:
        worksheet = sh.worksheet(sheet_name)
    except:
        worksheet = sh.add_worksheet(title=sheet_name, rows=100, cols=20)
    df = df.fillna("")
    existing_data = worksheet.get_all_values()
    if not existing_data:
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    else:
        worksheet.append_rows(df.values.tolist())

def get_status():
    try:
        df = load_data_from_sheet("settings")
        if df.empty or "status" not in df.columns: return True 
        return df.iloc[0]["status"] == "OPEN"
    except: return True

def set_status(is_open):
    df = pd.DataFrame([{"status": "OPEN" if is_open else "CLOSED"}])
    save_data_to_sheet(df, "settings")

is_accepting = get_status()

# ==========================================
# 🖥️ 4. アプリ画面構成
# ==========================================
st.title("📅 ALOHA面談日程調整")

if is_accepting:
    st.markdown('#### <span style="color:green">🟢 現在、生徒の申し込みを受け付けています</span>', unsafe_allow_html=True)
else:
    st.markdown('#### <span style="color:red">🔴 現在、生徒の申し込み受け付けは終了しています</span>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🏫 生徒用入力", "🎓 大学生用入力", "⚙️ 管理者専用"])

# --- Tab 1: 生徒用 ---
with tab1:
    st.header("中高生用：希望調査")
    if not is_accepting:
        st.warning("申し訳ありませんが、現在は申し込みを受け付けていません。")
        st.info("お問い合わせは公式LINEまでお願いします。")
    else:
        st.info("まだ登録していない場合は、以下のリンクから公式LINEを追加してください。")
        st.markdown("### [👉 公式LINEを追加する](https://lin.ee/fhVvKJa)")
        st.write("---")
        with st.form("student_form"):
            col1, col2 = st.columns(2)
            with col1:
                s_name_input = st.text_input("氏名（本名フルネーム） ※")
                s_name = s_name_input.strip() if s_name_input else ""
                s_line_name = st.text_input("LINEでのあなたの名前 ※")
                s_school = st.text_input("学校名 ※")
            with col2:
                s_grade = st.selectbox("学年 ※", ["中1", "中2", "中3", "高1", "高2", "高3"], index=None)
                s_stream = st.radio("文理選択 ※", ["文系", "理系", "未定"], index=None)
            st.write("---")
            s_request_mentor = st.text_input("担当してほしい東大生がいれば名前または属性（出身校・専攻など）を書いてください。")
            st.write("---")
            s_questions = st.text_area("当日聞きたいこと ※")
            
            s_available = render_schedule_grid([], key_suffix="student")

            if st.form_submit_button("送信"):
                required_fields = {"氏名": s_name, "LINE名": s_line_name, "学校名": s_school, "学年": s_grade, "文理": s_stream, "前回希望": s_want_prev, "質問": s_questions}
                missing = [k for k, v in required_fields.items() if not v]
                if not s_available: missing.append("日時")
                
                if missing:
                    st.error(f"未入力があります: {', '.join(missing)}")
                else:
                    df_s = load_data_from_sheet("students")
                    new_row = {
                        "生徒氏名": s_name, "LINE名": s_line_name, "学校": s_school, "学年": s_grade, "文理": s_stream,
                        "前回希望": "あり" if s_want_prev == "希望する" else "なし",
                        "指名希望": s_request_mentor, "質問内容": s_questions,
                        "可能日時": ",".join(s_available)
                    }
                    if not df_s.empty and "生徒氏名" in df_s.columns:
                        df_s = df_s[df_s["生徒氏名"] != s_name]
                        df_s = pd.concat([df_s, pd.DataFrame([new_row])], ignore_index=True)
                        st.success(f"{s_name} さんの情報を更新しました！")
                    else:
                        df_s = pd.DataFrame([new_row])
                        st.success("登録しました！")
                    save_data_to_sheet(df_s, "students")

# --- Tab 2: 大学生用 ---
with tab2:
    st.header("大学生用：空きコマ登録・確認")
    st.info("💡 生徒側の受付状況に関わらず、いつでも入力・修正可能です。")
    
    col_search1, col_search2, col_search3 = st.columns([2, 2, 1])
    with col_search1:
        input_name_query = st.text_input("氏名（フルネーム）", key="m_search_name")
    with col_search2:
        input_pass_query = st.text_input("パスワード", type="password", key="m_search_pass")
    with col_search3:
        st.write("")
        st.write("")
        load_btn = st.button("呼出 / 新規")

    if 'mentor_form_defaults' not in st.session_state:
        st.session_state['mentor_form_defaults'] = {"name": "", "streams": [], "slots": [], "password": ""}
    
    if load_btn:
        if not input_name_query or not input_pass_query:
            st.error("氏名とパスワードを入力してください。")
        else:
            df_m_check = load_data_from_sheet("mentors")
            target_data = pd.DataFrame()
            if not df_m_check.empty and "メンター氏名" in df_m_check.columns:
                target_data = df_m_check[df_m_check["メンター氏名"] == input_name_query.strip()]
            
            if not target_data.empty:
                row = target_data.iloc[0]
                if str(row["パスワード"]) == input_pass_query.strip():
                    st.session_state['mentor_form_defaults'] = {
                        "name": row["メンター氏名"],
                        "streams": row["文理"].split(",") if row["文理"] else [],
                        "slots": row["可能日時"].split(",") if row["可能日時"] else [],
                        "password": str(row["パスワード"])
                    }
                    st.success(f"✅ {input_name_query} さんを読み込みました。")
                else:
                    st.error("❌ パスワードが違います。")
            else:
                st.session_state['mentor_form_defaults'] = {
                    "name": input_name_query.strip(), "streams": [], "slots": [], "password": input_pass_query.strip()
                }
                st.info("🆕 新規登録します。")

    st.write("---")
    defaults = st.session_state['mentor_form_defaults']
    if defaults["name"]:
        with st.form("mentor_form"):
            st.markdown(f"**編集中のユーザー: {defaults['name']}**")
            m_stream = st.multiselect("文理選択", ["文系", "理系"], default=defaults["streams"])
            st.write("")
            is_unavailable = st.checkbox("🚫 今回は全日程参加できません（不参加）", value=(defaults["slots"] == ["参加不可"]))
            
            m_available = []
            if not is_unavailable:
                m_available = render_schedule_grid(defaults["slots"], key_suffix="mentor")
            else:
                st.warning("「参加不可」として登録・更新します。")
            if st.form_submit_button("更新 / 登録"):
                if m_available and m_stream:
                    df_m = load_data_from_sheet("mentors")
                    new_row = {"メンター氏名": defaults["name"], "文理": ",".join(m_stream), "可能日時": ",".join(m_available), "パスワード": defaults["password"]}
                    if not df_m.empty and "メンター氏名" in df_m.columns:
                        df_m = df_m[df_m["メンター氏名"] != defaults["name"]]
                        df_m = pd.concat([df_m, pd.DataFrame([new_row])], ignore_index=True)
                    else:
                        df_m = pd.DataFrame([new_row])
                    save_data_to_sheet(df_m, "mentors")
                    st.success("保存しました！")
                else:
                    st.error("文理と日時は必須です。")

# --- Tab 3: 管理者 ---
with tab3:
    st.header("🔒 管理者ダッシュボード")
    if 'login_attempts' not in st.session_state: st.session_state['login_attempts'] = 0
    
    if st.session_state['login_attempts'] >= 5:
        st.error("ロックされています。リロードしてください。")
    else:
        password = st.text_input("管理者パスワード", type="password")
        if password and password == st.secrets.get("ADMIN_PASSWORD"):
            st.session_state['login_attempts'] = 0
            st.success("認証成功")
            st.write("---")

            ad_tab1, ad_tab2, ad_tab3, ad_tab4 = st.tabs(["公開設定", "生徒管理", "メンター管理", "マッチング"])
            
            with ad_tab1:
                col_set1, col_set2 = st.columns([1, 3])
                with col_set1:
                    if st.button("🔴 受付停止" if is_accepting else "🟢 受付開始"):
                        set_status(not is_accepting)
                        st.rerun()
                with col_set2:
                    st.info(f"現在の生徒受付ステータス: {'受付中' if is_accepting else '停止中'}")

            with ad_tab2:
                st.dataframe(load_data_from_sheet("students"))
                with st.expander("データ削除・生成"):
                    if st.button("💥 生徒データ全削除＆ダミー生成"):
                        dummy = []
                        for i in range(15):
                            dummy.append({
                                "生徒氏名": f"生徒{i+1:02d}", "LINE名": f"L{i}", "学校": "A高", "学年": "高2", "文理": "理系",
                                "前回希望": "なし", "指名希望": "", "質問内容": "test",
                                "可能日時": ",".join(random.sample(TIME_SLOTS, 5))
                            })
                        save_data_to_sheet(pd.DataFrame(dummy), "students")
                        st.success("生成完了")

            with ad_tab3:
                st.dataframe(load_data_from_sheet("mentors"))
                with st.expander("データ削除・生成"):
                    if st.button("💥 メンターデータ全削除＆ダミー生成"):
                        dummy = []
                        for i in range(10):
                            dummy.append({
                                "メンター氏名": f"メンター{chr(65+i)}", "文理": "理系",
                                "可能日時": ",".join(random.sample(TIME_SLOTS, 15)), "パスワード": "1234"
                            })
                        save_data_to_sheet(pd.DataFrame(dummy), "mentors")
                        st.success("生成完了")

            with ad_tab4:
                df_st = load_data_from_sheet("students")
                df_mt = load_data_from_sheet("mentors")
                df_hist = load_data_from_sheet("history")

                # ==========================================
                # 🔒 指名固定設定エリア (NEW)
                # ==========================================
                st.subheader("🔒 指名マッチング (優先確定)")
                st.info("ここで指定したペアは、他の条件より優先してマッチングされます。")
                
                # 指名用データフレームの初期化
                if "fixed_pairs_df" not in st.session_state:
                    st.session_state["fixed_pairs_df"] = pd.DataFrame(columns=["生徒氏名", "メンター氏名"])
                
                student_options = df_st["生徒氏名"].tolist() if not df_st.empty else []
                mentor_options = df_mt["メンター氏名"].tolist() if not df_mt.empty else []

                # Data Editorで入力を受け付ける
                fixed_pairs = st.data_editor(
                    st.session_state["fixed_pairs_df"],
                    column_config={
                        "生徒氏名": st.column_config.SelectboxColumn(
                            "生徒を選択",
                            options=student_options,
                            width="medium",
                            required=True
                        ),
                        "メンター氏名": st.column_config.SelectboxColumn(
                            "メンターを選択",
                            options=mentor_options,
                            width="medium",
                            required=True
                        )
                    },
                    num_rows="dynamic",
                    key="fixed_pairs_editor"
                )

                st.write("---")

                st.subheader("🚀 自動マッチング実行")
                if st.button("自動マッチング実行", type="primary"):
                    if df_st.empty or df_mt.empty:
                        st.error("データ不足")
                    else:
                        results = []
                        mentor_schedule = {}
                        mentor_streams = {}
                        mentor_assignments = {}
                        mentor_names_list = list(df_mt["メンター氏名"]) 

                        for _, row in df_mt.iterrows():
                            m_name = row["メンター氏名"]
                            mentor_schedule[m_name] = set(row["可能日時"].split(",")) if row["可能日時"] else set()
                            mentor_assignments[m_name] = set()
                            mentor_streams[m_name] = row["文理"].split(",") if row["文理"] else []

                        students_list = []
                        for _, s_row in df_st.iterrows():
                            s_slots = s_row["可能日時"].split(",") if s_row["可能日時"] else []
                            students_list.append({"data": s_row, "s_slots_set": set(s_slots), "num_slots": len(s_slots)})
                        
                        # 通常は空き枠が少ない順に処理するが、指名固定を最優先するためにリストからは除外せず、処理済みフラグ管理を行う
                        students_list.sort(key=lambda x: x["num_slots"])
                        
                        processed_students = set()

                        def get_adjacent_slots(target_slot):
                            if target_slot not in TIME_SLOTS: return []
                            idx = TIME_SLOTS.index(target_slot)
                            target_day = target_slot.split(" ")[0]
                            adjacent = []
                            if idx > 0 and TIME_SLOTS[idx-1].split(" ")[0] == target_day: adjacent.append(TIME_SLOTS[idx-1])
                            if idx < len(TIME_SLOTS)-1 and TIME_SLOTS[idx+1].split(" ")[0] == target_day: adjacent.append(TIME_SLOTS[idx+1])
                            return adjacent

                        def calculate_shift_score(m_name, target_slot):
                            score = 0
                            assigned = mentor_assignments[m_name]
                            current_day = target_slot.split(" ")[0]
                            day_shifts = [s for s in assigned if s.startswith(current_day)]
                            
                            if not day_shifts:
                                if assigned: score += 50 
                            else:
                                is_adj = any(adj in assigned for adj in get_adjacent_slots(target_slot))
                                if is_adj: score += 500
                                else: score -= 1000
                            
                            score += random.random()
                            return score
                        
                        # ==========================================
                        # PHASE 0: 指名固定マッチング (NEW)
                        # ==========================================
                        for _, pair in fixed_pairs.iterrows():
                            f_student = pair["生徒氏名"]
                            f_mentor = pair["メンター氏名"]
                            
                            if not f_student or not f_mentor: continue
                            if f_student in processed_students: continue # 重複防止

                            # 生徒データを探す
                            s_obj = next((x for x in students_list if x["data"]["生徒氏名"] == f_student), None)
                            if not s_obj: continue

                            s_slots = s_obj["s_slots_set"]
                            
                            # メンターの空きを確認
                            if f_mentor not in mentor_schedule:
                                results.append({"生徒氏名": f_student, "決定メンター": None, "決定日時": None, "ステータス": "指名エラー(メンター不在)", "学校": s_obj["data"]["学校"], "学年": s_obj["data"]["学年"], "生徒文理": s_obj["data"]["文理"]})
                                processed_students.add(f_student)
                                continue

                            # 共通日時
                            common_slots = list(s_slots & mentor_schedule[f_mentor])
                            
                            if common_slots:
                                # 共通日時の中から、メンターにとって都合の良い時間（連投など）を選ぶ
                                common_slots.sort(key=lambda s: calculate_shift_score(f_mentor, s), reverse=True)
                                assigned_slot = common_slots[0]
                                
                                # 確定
                                mentor_schedule[f_mentor].remove(assigned_slot)
                                mentor_assignments[f_mentor].add(assigned_slot)
                                
                                results.append({
                                    "生徒氏名": f_student, "決定メンター": f_mentor, "決定日時": assigned_slot,
                                    "ステータス": "決定(指名)", 
                                    "学校": s_obj["data"]["学校"], "学年": s_obj["data"]["学年"], "生徒文理": s_obj["data"]["文理"]
                                })
                            else:
                                # マッチング不可
                                results.append({
                                    "生徒氏名": f_student, "決定メンター": None, "決定日時": None,
                                    "ステータス": "指名エラー(日時不一致)", 
                                    "学校": s_obj["data"]["学校"], "学年": s_obj["data"]["学年"], "生徒文理": s_obj["data"]["文理"]
                                })
                            
                            processed_students.add(f_student)

                        # ==========================================
                        # PHASE 1 & 2: 通常マッチング (既存ロジック)
                        # ==========================================
                        for s_obj in students_list:
                            s_row = s_obj["data"]
                            s_name = s_row["生徒氏名"]
                            
                            # 既に指名で決まっていればスキップ
                            if s_name in processed_students: continue

                            s_stream = s_row["文理"]
                            s_slots = s_obj["s_slots_set"]
                            
                            want_prev = (s_row["前回希望"] == "あり")
                            prev_mentor = None
                            if not df_hist.empty and "生徒氏名" in df_hist.columns:
                                hist = df_hist[df_hist["生徒氏名"] == s_name]
                                if not hist.empty: prev_mentor = hist.iloc[-1]["前回担当メンター"]

                            assigned_mentor, assigned_slot = None, None

                            # --- 前回担当優先 ---
                            if want_prev and prev_mentor and prev_mentor in mentor_schedule:
                                common_slots = list(s_slots & mentor_schedule[prev_mentor])
                                if common_slots:
                                    common_slots.sort(key=lambda s: calculate_shift_score(prev_mentor, s), reverse=True)
                                    assigned_mentor = prev_mentor
                                    assigned_slot = common_slots[0]
                                    mentor_schedule[prev_mentor].remove(assigned_slot)
                                    mentor_assignments[prev_mentor].add(assigned_slot)

                            # --- 通常マッチング ---
                            if not assigned_mentor:
                                feasible_slots = []
                                for slot in s_slots:
                                    for m_name in mentor_names_list:
                                        if slot in mentor_schedule[m_name]:
                                            m_streams_list = mentor_streams.get(m_name, [])
                                            if s_stream == "未定" or s_stream in m_streams_list:
                                                feasible_slots.append(slot)
                                                break
                                feasible_slots = list(set(feasible_slots))
                                random.shuffle(feasible_slots)

                                for slot in feasible_slots:
                                    candidates = []
                                    for m_name in mentor_names_list:
                                        m_streams_list = mentor_streams.get(m_name, [])
                                        if s_stream != "未定" and s_stream not in m_streams_list: continue
                                        if slot in mentor_schedule[m_name]:
                                            candidates.append(m_name)
                                    
                                    if not candidates: continue
                                    candidates.sort(key=lambda m: calculate_shift_score(m, slot), reverse=True)
                                    
                                    best_mentor = candidates[0]
                                    assigned_mentor = best_mentor
                                    assigned_slot = slot
                                    mentor_schedule[best_mentor].remove(slot)
                                    mentor_assignments[best_mentor].add(slot)
                                    break
                            
                            results.append({
                                "生徒氏名": s_name, "決定メンター": assigned_mentor, "決定日時": assigned_slot,
                                "ステータス": "決定" if assigned_mentor else "未定", 
                                "学校": s_row["学校"], "学年": s_row["学年"], "生徒文理": s_stream
                            })
                            processed_students.add(s_name)
                        
                        df_res = pd.DataFrame(results)
                        df_res["_sort"] = df_res["決定日時"].apply(get_sort_key)
                        st.session_state['matching_results'] = df_res.sort_values(by="_sort").drop(columns=["_sort"])

                if st.session_state.get('matching_results') is not None:
                    st.write("---")
                    st.subheader("✅ 1. 面談マッチング結果")
                    all_mentors = df_mt["メンター氏名"].unique().tolist() if not df_mt.empty else []
                    
                    edited_df = st.data_editor(
                        st.session_state['matching_results'],
                        column_config={
                            "決定メンター": st.column_config.SelectboxColumn("担当", options=all_mentors, width="medium"),
                            "決定日時": st.column_config.SelectboxColumn("日時", options=TIME_SLOTS, width="medium"),
                            "ステータス": st.column_config.SelectboxColumn("状態", options=["決定", "未定", "キャンセル", "決定(指名)", "指名エラー(日時不一致)"], width="small")
                        },
                        hide_index=True, num_rows="fixed", key="editor_final"
                    )
                    st.session_state['matching_results'] = edited_df

                    # バリデーション
                    st.write("---")
                    st.subheader("🔍 設定チェック")
                    
                    student_requests = {}
                    for _, r in df_st.iterrows():
                        raw_slots = r["可能日時"].split(",") if r["可能日時"] else []
                        student_requests[r["生徒氏名"]] = set([s.strip() for s in raw_slots])
                    
                    mentor_availabilities = {}
                    for _, r in df_mt.iterrows():
                        raw_slots = r["可能日時"].split(",") if r["可能日時"] else []
                        mentor_availabilities[r["メンター氏名"]] = set([s.strip() for s in raw_slots])

                    errors = []
                    
                    for idx, row in edited_df.iterrows():
                        s_name = row["生徒氏名"]
                        m_name = row["決定メンター"]
                        slot = str(row["決定日時"]).strip()
                        status = row["ステータス"]

                        if "決定" in status:
                            if s_name in student_requests:
                                if slot not in student_requests[s_name]:
                                    true_wishes = list(student_requests[s_name])
                                    true_wishes.sort(key=get_sort_key)
                                    wishes_str = ", ".join(true_wishes) if true_wishes else "なし"
                                    errors.append(f"❌ **{s_name}** さんはこの日時 ({slot}) を希望していません。\n　👉 **本来の希望**: {wishes_str}")
                            
                            if m_name in mentor_availabilities:
                                if slot not in mentor_availabilities[m_name]:
                                    true_avail = list(mentor_availabilities[m_name])
                                    true_avail.sort(key=get_sort_key)
                                    avail_str = ", ".join(true_avail) if true_avail else "空きなし"
                                    errors.append(f"⚠️ **{m_name}** さんはこの時間空いていません ({slot})。\n　👉 **本来の空き**: {avail_str}")
                            elif m_name:
                                errors.append(f"❓ **{m_name}** というメンターは登録されていません")

                    if errors:
                        st.error(f"以下の問題が見つかりました ({len(errors)}件):")
                        for err in errors:
                            st.write(err)
                            st.write("---")
                    else:
                        st.success("✅ すべての設定が「生徒の希望内」かつ「メンターの空き時間内」です。")

                    st.write("---")
                    
                    st.markdown("### 💾 データ保存とリセット")
                    
                    csv = edited_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 結果CSVダウンロード", csv, "result.csv", "text/csv")
                    
                    st.write("") 

                    col_save_only, col_delete_all = st.columns(2)
                    
                    with col_save_only:
                        if st.button("① 決定内容を「履歴」に保存 (データは残す)", type="primary"):
                            history_df = edited_df[edited_df["ステータス"].str.contains("決定")][["生徒氏名", "決定メンター", "学校", "学年", "生徒文理"]]
                            history_df = history_df.rename(columns={"決定メンター": "前回担当メンター", "生徒文理": "文理"})
                            append_data_to_sheet(history_df, "history")
                            st.success("✅ 履歴シート(history)に「氏名・メンター・学校・学年・文理」を保存しました！")
                            st.info("データはまだ残っています。続けて編集可能です。")

                    with col_delete_all:
                        if st.button("🗑️ ② データを全消去してリセット (次回の準備)"):
                            save_data_to_sheet(pd.DataFrame(), "students")
                            save_data_to_sheet(pd.DataFrame(), "mentors")
                            st.session_state['matching_results'] = None
                            st.session_state['room_managers_results'] = None
                            st.warning("生徒・メンターデータを全消去しました。画面をリロードします。")
                            time.sleep(2)
                            st.rerun()
        elif password:
            st.session_state['login_attempts'] += 1
            st.warning("パスワードが違います")
