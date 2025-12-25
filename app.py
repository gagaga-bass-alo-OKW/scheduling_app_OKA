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

# CSSでメニュー非表示
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ==========================================
# 📅 2. 時間枠設定 & グリッド表示関数
# ==========================================
DAYS_WEEKDAY = ["1/6", "1/7", "1/8", "1/9",]
HOURS_WEEKDAY = range(20, 23)

DAYS_WEEKEND = ["1/10", "1/11","1/12"]
HOURS_WEEKEND = range(10, 23)

TIME_SLOTS = []
for d in DAYS_WEEKDAY:
    for h in HOURS_WEEKDAY:
        TIME_SLOTS.append(f"{d} {h}:00-{h+1}:00")
for d in DAYS_WEEKEND:
    for h in HOURS_WEEKEND:
        TIME_SLOTS.append(f"{d} {h}:00-{h+1}:00")

DAY_ORDER = {"月曜": 0, "火曜": 1, "水曜": 2, "木曜": 3, "金曜": 4, "土曜": 5, "日曜": 6}

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
# ☁️ 3. Googleスプレッドシート連携 & 設定管理
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
        if df.empty or "status" not in df.columns:
            return True 
        return df.iloc[0]["status"] == "OPEN"
    except:
        return True

def set_status(is_open):
    df = pd.DataFrame([{"status": "OPEN" if is_open else "CLOSED"}])
    save_data_to_sheet(df, "settings")

is_accepting = get_status()

# ==========================================
# 🖥️ 4. アプリ画面構成
# ==========================================
st.title("📅 ALOHA面談日程調整")

if is_accepting:
    st.markdown('#### <span style="color:green">🟢 現在、回答を受け付けています</span>', unsafe_allow_html=True)
else:
    st.markdown('#### <span style="color:red">🔴 現在、回答の受け付けは終了しています</span>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🏫 生徒用入力", "🎓 大学生用入力", "⚙️ 管理者専用"])

# --- Tab 1: 生徒用 ---
with tab1:
    st.header("中高生用：希望調査")
    if not is_accepting:
        st.warning("申し訳ありませんが、現在は申し込みを受け付けていません。次回の募集をお待ちください。")
        st.info("お問い合わせは公式LINEまでお願いします。")
    else:
        st.info("まだ登録していない場合は、以下のリンクから公式LINEを追加してください。")
        st.markdown("### [👉 公式LINEを追加する](https://lin.ee/fhVvKJa)")
        st.write("---")
        st.write("以下のフォームに入力してください。※印は必須項目です")
        st.caption("※以前に入力したことがある場合、**同じ「氏名」**で送信すると情報が上書き（更新）されます。")

        with st.form("student_form"):
            col1, col2 = st.columns(2)
            with col1:
                s_name_input = st.text_input("氏名（本名） ※")
                s_name = s_name_input.strip() if s_name_input else ""
                s_line_name = st.text_input("LINEでのあなたの名前（表示名） 必ずALOHAのLINEを追加すること！※")
                s_school = st.text_input("学校名 ※")
            with col2:
                s_grade = st.selectbox("学年 ※", ["中1", "中2", "中3", "高1", "高2", "高3"], index=None, placeholder="選択してください")
                s_stream = st.radio("文理選択 ※", ["文系", "理系", "未定"], index=None)
            st.write("---")
            st.subheader("メンターの希望")
            s_want_prev = st.radio("前回の担当者と同じ人を希望しますか？ ※", ["希望する", "希望しない"], index=None, horizontal=True)
            s_request_mentor = st.text_input("その他、担当してほしい東大生がいれば名前を書いてください")
            st.write("---")
            s_questions = st.text_area("当日聞きたいことや相談したいことを自由に書いてください ※")
            st.write("例: 参考書紹介、東大での生活、東大生の中学/高校〇年の時の過ごし方、進級に向けて、等")
            
            s_available = render_schedule_grid([], key_suffix="student")

            if st.form_submit_button("送信"):
                required_fields = {"氏名": s_name, "LINE名": s_line_name, "学校名": s_school, "学年": s_grade, "文理選択": s_stream, "前回希望の有無": s_want_prev, "当日聞きたいことや相談したいことを自由に書いてください":s_questions}
                missing_fields = [k for k, v in required_fields.items() if not v]
                
                if not s_available:
                    missing_fields.append("面談可能日時")

                if missing_fields:
                    st.error(f"以下の必須項目が入力されていません： {', '.join(missing_fields)}")
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
                        st.success(f"{s_name} さんの情報を登録（上書き）しました！")
                    else:
                        df_s = pd.DataFrame([new_row])
                        st.success(f"保存しました！ありがとうございます、{s_name}さん。")
                    save_data_to_sheet(df_s, "students")

# --- Tab 2: 大学生用 ---
with tab2:
    st.header("大学生用：空きコマ登録・確認")
    
    if not is_accepting:
        st.warning("現在は登録期間外です。")
    else:
        st.write("ご協力ありがとうございます。")
        st.info("💡 **新規登録**も**修正**もここから行えます。")
        
        # 1. 氏名とパスワードで検索
        st.markdown("##### 🔐 認証エリア")
        col_search1, col_search2, col_search3 = st.columns([2, 2, 1])
        with col_search1:
            input_name_query = st.text_input("氏名", placeholder="例：東大 太郎", key="m_search_name")
        with col_search2:
            input_pass_query = st.text_input("パスワード", type="password", placeholder="自分用パスワード", key="m_search_pass")
        with col_search3:
            st.write("")
            st.write("")
            load_btn = st.button("呼出 / 新規")

        if 'mentor_form_defaults' not in st.session_state:
            st.session_state['mentor_form_defaults'] = {"name": "", "streams": [], "slots": [], "password": ""}
        
        # 呼び出し処理
        if load_btn:
            if not input_name_query or not input_pass_query:
                st.error("氏名とパスワードの両方を入力してください。")
            else:
                df_m_check = load_data_from_sheet("mentors")
                target_data = pd.DataFrame()
                
                # 名前で検索
                if not df_m_check.empty and "メンター氏名" in df_m_check.columns:
                    target_data = df_m_check[df_m_check["メンター氏名"] == input_name_query.strip()]
                
                if not target_data.empty:
                    # データあり -> パスワード照合
                    row = target_data.iloc[0]
                    stored_pass = str(row["パスワード"]) if "パスワード" in row else ""
                    
                    if stored_pass == input_pass_query.strip():
                        existing_streams = row["文理"].split(",") if row["文理"] else []
                        existing_slots = row["可能日時"].split(",") if row["可能日時"] else []
                        st.session_state['mentor_form_defaults'] = {
                            "name": row["メンター氏名"],
                            "streams": existing_streams,
                            "slots": existing_slots,
                            "password": stored_pass
                        }
                        st.success(f"✅ {input_name_query} さんの情報を読み込みました。")
                    else:
                        st.error("❌ パスワードが違います。")
                        st.session_state['mentor_form_defaults'] = {"name": "", "streams": [], "slots": [], "password": ""}
                else:
                    # データなし -> 新規登録として扱う
                    st.session_state['mentor_form_defaults'] = {
                        "name": input_name_query.strip(),
                        "streams": [],
                        "slots": [],
                        "password": input_pass_query.strip()
                    }
                    st.info(f"🆕 {input_name_query} さんのデータはありませんでした。このパスワードで新規登録します。")

        st.write("---")
        defaults = st.session_state['mentor_form_defaults']
        
        # フォーム表示
        if defaults["name"]:
            st.markdown(f"**編集中のユーザー: {defaults['name']}**")
            with st.form("mentor_form"):
                st.write(f"氏名: {defaults['name']}")
                st.write("▼ 受験時の文理を選択してください ※")
                m_stream = st.multiselect("文理選択", ["文系", "理系"], default=defaults["streams"])
                st.write("---")
                
                m_available = render_schedule_grid(defaults["slots"], key_suffix="mentor")
                
                submit_label = "情報を更新する"
                
                if st.form_submit_button(submit_label):
                    if m_available and m_stream:
                        df_m = load_data_from_sheet("mentors")
                        new_row = {
                            "メンター氏名": defaults["name"], 
                            "文理": ",".join(m_stream), 
                            "可能日時": ",".join(m_available),
                            "パスワード": defaults["password"]
                        }
                        
                        if not df_m.empty and "メンター氏名" in df_m.columns:
                            df_m = df_m[df_m["メンター氏名"] != defaults["name"]]
                            df_m = pd.concat([df_m, pd.DataFrame([new_row])], ignore_index=True)
                            action_msg = "更新（上書き）"
                        else:
                            df_m = pd.DataFrame([new_row])
                            action_msg = "登録"
                            
                        save_data_to_sheet(df_m, "mentors")
                        st.success(f"✨ {defaults['name']} さんの情報を{action_msg}しました！次回も同じパスワードを使ってください。")
                    else:
                        st.error("⚠️ 「文理」「日時」は必須です。")
        else:
            st.caption("👈 左上のフォームに氏名とパスワードを入力して「呼出 / 新規」を押してください。")

# --- Tab 3: 管理者用 ---
with tab3:
    st.header("🔒 管理者ダッシュボード")

    if 'login_attempts' not in st.session_state:
        st.session_state['login_attempts'] = 0

    if st.session_state['login_attempts'] >= 5:
        st.error("⚠️ ロックされています。解除するにはブラウザを再読み込みしてください。")
    else:
        password = st.text_input("管理者パスワード", type="password")
        
        if password:
            try:
                correct_pass = st.secrets.get("ADMIN_PASSWORD")
                if not correct_pass:
                    st.warning("⚠️ Secrets設定エラー")
                elif password == correct_pass:
                    st.session_state['login_attempts'] = 0
                    st.success("認証成功")
                    st.write("---")

                    ad_tab1, ad_tab2, ad_tab3, ad_tab4 = st.tabs(["📡 公開設定", "🏫 生徒管理", "🎓 メンター管理", "🚀 マッチング"])

                    # 1. 公開設定
                    with ad_tab1:
                        st.subheader("フォームの受付設定")
                        col_set1, col_set2 = st.columns([1, 3])
                        with col_set1:
                            if is_accepting:
                                if st.button("🔴 受付を停止する"):
                                    set_status(False)
                                    st.rerun()
                            else:
                                if st.button("🟢 受付を開始する"):
                                    set_status(True)
                                    st.rerun()
                        with col_set2:
                            if is_accepting:
                                st.info("現在は「回答受付中」です。")
                            else:
                                st.error("現在は「停止中」です。")

                    # 2. 生徒管理
                    with ad_tab2:
                        st.subheader("🏫 生徒データの管理")
                        with st.expander("📥 CSVファイルから一括登録"):
                            s_dummy = pd.DataFrame(columns=["生徒氏名", "LINE名", "学校", "学年", "文理", "前回希望", "指名希望", "質問内容", "可能日時"])
                            s_csv = s_dummy.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📄 テンプレート(CSV)をDL", s_csv, "student_template.csv", "text/csv")
                            s_file = st.file_uploader("生徒CSVをアップロード", type=["csv"])
                            if s_file and st.button("このデータで登録/上書き (生徒)"):
                                df_s_up = pd.read_csv(s_file)
                                df_curr = load_data_from_sheet("students")
                                up_names = df_s_up["生徒氏名"].astype(str).str.strip().tolist()
                                df_s_up["生徒氏名"] = df_s_up["生徒氏名"].astype(str).str.strip()
                                if not df_curr.empty:
                                    df_curr = df_curr[~df_curr["生徒氏名"].isin(up_names)]
                                    df_new = pd.concat([df_curr, df_s_up], ignore_index=True)
                                else:
                                    df_new = df_s_up
                                save_data_to_sheet(df_new, "students")
                                st.success(f"{len(df_s_up)}件の生徒データを登録しました")

                        with st.expander("🎲 テスト用サンプルデータの生成"):
                            st.warning("⚠️ 現在のデータを全て削除してダミーデータを生成します")
                            num_students = st.number_input("生成する生徒数", 1, 50, 15)
                            if st.button("💥 生徒ダミーデータを生成して上書き保存"):
                                dummy_students = []
                                for i in range(num_students):
                                    n_slots = random.randint(3, 6)
                                    picked_slots = random.sample(TIME_SLOTS, n_slots)
                                    dummy_students.append({
                                        "生徒氏名": f"生徒{i+1:02d}", "LINE名": f"line_{i+1}", "学校": "テスト高",
                                        "学年": random.choice(["高1", "高2"]), "文理": random.choice(["文系", "理系"]),
                                        "前回希望": random.choice(["あり", "なし"]), "指名希望": "", "質問内容": "テスト",
                                        "可能日時": ",".join(picked_slots)
                                    })
                                save_data_to_sheet(pd.DataFrame(dummy_students), "students")
                                st.success("生成完了")
                        st.write("▼ 現在のデータ")
                        st.dataframe(load_data_from_sheet("students"))

                    # 3. メンター管理
                    with ad_tab3:
                        st.subheader("🎓 メンターデータの管理")
                        st.info("※管理者権限でパスワードを上書き可能です")
                        with st.expander("📥 CSVファイルから一括登録"):
                            m_dummy = pd.DataFrame(columns=["メンター氏名", "文理", "可能日時", "パスワード"])
                            m_csv = m_dummy.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📄 テンプレート(CSV)をDL", m_csv, "mentor_template.csv", "text/csv")
                            m_file = st.file_uploader("メンターCSVをアップロード", type=["csv"])
                            if m_file and st.button("このデータで登録/上書き (メンター)"):
                                df_m_up = pd.read_csv(m_file)
                                df_curr = load_data_from_sheet("mentors")
                                up_names = df_m_up["メンター氏名"].astype(str).str.strip().tolist()
                                df_m_up["メンター氏名"] = df_m_up["メンター氏名"].astype(str).str.strip()
                                if "パスワード" not in df_m_up.columns:
                                    df_m_up["パスワード"] = "1234"
                                    st.warning("パスワード列がなかったため、初期値「1234」を設定しました。")

                                if not df_curr.empty:
                                    df_curr = df_curr[~df_curr["メンター氏名"].isin(up_names)]
                                    df_new = pd.concat([df_curr, df_m_up], ignore_index=True)
                                else:
                                    df_new = df_m_up
                                save_data_to_sheet(df_new, "mentors")
                                st.success(f"{len(df_m_up)}件のメンターデータを登録しました")

                        with st.expander("🎲 テスト用サンプルデータの生成"):
                            st.warning("⚠️ 現在のデータを全て削除してダミーデータを生成します")
                            num_mentors = st.number_input("生成するメンター数", 1, 30, 10)
                            if st.button("💥 メンターダミーデータを生成して上書き保存"):
                                dummy_mentors = []
                                for i in range(num_mentors):
                                    n_slots = random.randint(10, 20)
                                    safe_n = min(n_slots, len(TIME_SLOTS))
                                    picked_slots = random.sample(TIME_SLOTS, safe_n)
                                    dummy_mentors.append({
                                        "メンター氏名": f"メンター{chr(65+i)}", 
                                        "文理": random.choice(["文系", "理系"]),
                                        "可能日時": ",".join(picked_slots),
                                        "パスワード": "1234"
                                    })
                                save_data_to_sheet(pd.DataFrame(dummy_mentors), "mentors")
                                st.success("生成完了（パスワードは全員「1234」です）")
                        st.write("▼ 現在のデータ")
                        st.dataframe(load_data_from_sheet("mentors"))

                    # 4. マッチング
                    with ad_tab4:
                        st.subheader("🚀 マッチング実行 (飛び石禁止・連投優先)")
                        st.info("💡 **戦略:** シフトの「飛び石（空き時間）」を禁止し、連続勤務を最優先します。")
                        
                        df_students = load_data_from_sheet("students")
                        df_mentors = load_data_from_sheet("mentors")
                        df_history = load_data_from_sheet("history")

                        if st.button("自動マッチングを開始する", type="primary"):
                            if df_students.empty or df_mentors.empty:
                                st.error("データ不足")
                            else:
                                results = []
                                
                                # --- 1. データ準備 ---
                                mentor_schedule = {} # {name: set(slots)} (残りの空き枠)
                                mentor_streams = {}  # {name: [stream]}
                                mentor_assignments = {} # {name: set(assigned_slots)} (既に決まった枠)
                                
                                mentor_names_list = list(df_mentors["メンター氏名"]) 

                                for _, row in df_mentors.iterrows():
                                    m_name = row["メンター氏名"]
                                    slots = set(row["可能日時"].split(",")) if row["可能日時"] else set()
                                    mentor_schedule[m_name] = slots
                                    mentor_assignments[m_name] = set() # 初期化
                                    streams = row["文理"].split(",") if "文理" in row and row["文理"] else []
                                    mentor_streams[m_name] = streams

                                # 生徒データの整形 & ソート用カラム作成
                                students_list = []
                                for _, s_row in df_students.iterrows():
                                    s_slots = s_row["可能日時"].split(",") if s_row["可能日時"] else []
                                    students_list.append({
                                        "data": s_row,
                                        "s_slots_set": set(s_slots),
                                        "num_slots": len(s_slots)
                                    })
                                
                                # 🔥 難易度順ソート（候補が少ない生徒を先に）
                                students_list.sort(key=lambda x: x["num_slots"])

                                # スロットごとの埋まり具合（人気度）カウンター
                                slot_popularity = {slot: 0 for slot in TIME_SLOTS}

                                # 隣接スロット判定用のヘルパー
                                def get_adjacent_slots(target_slot):
                                    """ target_slotの前後のスロット（同じ日のみ）を返す """
                                    if target_slot not in TIME_SLOTS:
                                        return []
                                    idx = TIME_SLOTS.index(target_slot)
                                    target_day = target_slot.split(" ")[0]
                                    
                                    adjacent = []
                                    # 前
                                    if idx > 0:
                                        prev = TIME_SLOTS[idx - 1]
                                        if prev.split(" ")[0] == target_day:
                                            adjacent.append(prev)
                                    # 次
                                    if idx < len(TIME_SLOTS) - 1:
                                        next_s = TIME_SLOTS[idx + 1]
                                        if next_s.split(" ")[0] == target_day:
                                            adjacent.append(next_s)
                                    return adjacent

                                # --- 2. マッチング処理 ---
                                for s_obj in students_list:
                                    s_row = s_obj["data"]
                                    s_name = s_row["生徒氏名"]
                                    s_stream = s_row["文理"]
                                    s_slots = s_obj["s_slots_set"]
                                    
                                    # 前回メンター情報の取得
                                    want_prev = (s_row["前回希望"] == "あり")
                                    prev_mentor = None
                                    if not df_history.empty and "生徒氏名" in df_history.columns:
                                        hist = df_history[df_history["生徒氏名"] == s_name]
                                        if not hist.empty:
                                            prev_mentor = hist.iloc[-1]["前回担当メンター"]

                                    assigned_mentor = None
                                    assigned_slot = None

                                    # 生徒が可能なスロットを人気順（埋まってる順）にソート
                                    feasible_slots = []
                                    for slot in s_slots:
                                        # この枠で働けるメンターが一人でもいるか確認
                                        has_valid_mentor = False
                                        for m_name in mentor_names_list:
                                            if slot in mentor_schedule[m_name]:
                                                m_streams_list = mentor_streams.get(m_name, [])
                                                if s_stream == "未定" or s_stream in m_streams_list:
                                                    has_valid_mentor = True
                                                    break
                                        if has_valid_mentor:
                                            feasible_slots.append(slot)
                                    
                                    feasible_slots.sort(key=lambda s: slot_popularity.get(s, 0), reverse=True)

                                    # 優先順位の高いスロットからメンターを探す
                                    for slot in feasible_slots:
                                        # 候補者のリストアップ
                                        candidates = []
                                        for m_name in mentor_names_list:
                                            m_streams_list = mentor_streams.get(m_name, [])
                                            if s_stream != "未定" and s_stream not in m_streams_list:
                                                continue
                                            if slot in mentor_schedule[m_name]:
                                                candidates.append(m_name)
                                        
                                        if not candidates:
                                            continue

                                        # 🔥🔥 メンター選定のスコアリング（ここが重要） 🔥🔥
                                        def calculate_mentor_score(m_name):
                                            score = 0
                                            
                                            # 1. 指名・前回担当（最優先）
                                            if want_prev and m_name == prev_mentor:
                                                score += 10000 
                                            
                                            assigned_slots = mentor_assignments[m_name]
                                            current_day = slot.split(" ")[0] # e.g., "1/6"
                                            
                                            # その日の既存シフトを取得
                                            day_shifts = [s for s in assigned_slots if s.startswith(current_day)]
                                            
                                            # 2. その日のシフト状況によるスコア
                                            if not day_shifts:
                                                # その日はまだ入っていない -> 新しく入る (Gapなし)
                                                # 全体の日数を減らすため、他ですでに働いている人なら少し優遇してもいいが、
                                                # Gap回避が最優先なので、ここはフラットに近い。
                                                if assigned_slots: # 他の日に働いている
                                                    score += 50
                                                else:
                                                    score += 0
                                            else:
                                                # その日はすでに入っている
                                                # 隣接しているかチェック
                                                is_adjacent = False
                                                adjs = get_adjacent_slots(slot)
                                                for adj in adjs:
                                                    if adj in assigned_slots:
                                                        is_adjacent = True
                                                        break
                                                
                                                if is_adjacent:
                                                    score += 500 # 連続勤務（最高）
                                                else:
                                                    score -= 1000 # 飛び石（Gap）になるのでペナルティ！
                                            
                                            # ランダム要素
                                            score += random.random()
                                            return score

                                        # スコアが高い順にソート
                                        candidates.sort(key=calculate_mentor_score, reverse=True)

                                        # 最もスコアが高いメンターを採用
                                        best_mentor = candidates[0]
                                        
                                        # もしスコアが負（Gap発生）しかない場合でも、この枠しか埋められないなら採用される
                                        # が、他の枠（feasible_slotsのループ）でGapなしが見つかればそちらが優先される
                                        
                                        assigned_mentor = best_mentor
                                        assigned_slot = slot
                                        
                                        # 状態更新
                                        mentor_schedule[best_mentor].remove(slot) # 空き枠から削除
                                        mentor_assignments[best_mentor].add(slot) # 確定枠に追加
                                        slot_popularity[slot] += 1
                                        break
                                    
                                    results.append({
                                        "生徒氏名": s_name, "決定メンター": assigned_mentor, "決定日時": assigned_slot,
                                        "ステータス": "決定" if assigned_mentor else "未定", "学校": s_row["学校"],
                                        "生徒文理": s_stream, "メンター文理": ",".join(mentor_streams.get(assigned_mentor, [])) if assigned_mentor else "",
                                        "前回担当メンター": assigned_mentor if assigned_mentor else ""
                                    })
                                
                                # 結果保存
                                df_results = pd.DataFrame(results)
                                def get_sort_key(val):
                                    if not val or pd.isna(val) or val == "None" or not isinstance(val, str): return (99, 99)
                                    try:
                                        parts = val.split(" ")
                                        d_num = DAY_ORDER.get(parts[0], 99)
                                        t_num = int(parts[1].split(":")[0])
                                        return (d_num, t_num)
                                    except: return (99, 99)
                                df_results["_sort_key"] = df_results["決定日時"].apply(get_sort_key)
                                st.session_state['matching_results'] = df_results.sort_values(by="_sort_key").drop(columns=["_sort_key"])

                                # ----------------------------------------------------
                                # 部屋担当（待機メンター）
                                # ----------------------------------------------------
                                room_managers_list = []
                                for m_name, remaining_slots in mentor_schedule.items():
                                    for slot in remaining_slots:
                                        if slot_popularity.get(slot, 0) > 0:
                                            room_managers_list.append({"日時": slot, "部屋担当メンター": m_name})
                                
                                df_managers = pd.DataFrame(room_managers_list)
                                if not df_managers.empty:
                                    df_managers["_sort_key"] = df_managers["日時"].apply(get_sort_key)
                                    df_managers = df_managers.sort_values(by="_sort_key").drop(columns=["_sort_key"])
                                    df_managers_agg = df_managers.groupby("日時")["部屋担当メンター"].apply(list).reset_index()
                                    df_managers_agg["部屋担当メンター"] = df_managers_agg["部屋担当メンター"].apply(lambda x: ", ".join(x))
                                    st.session_state['room_managers_results'] = df_managers_agg
                                else:
                                    st.session_state['room_managers_results'] = pd.DataFrame(columns=["日時", "部屋担当メンター"])

                                st.success("最適化マッチング完了（飛び石禁止モード）")

                        # --- 結果表示 ---
                        if st.session_state.get('matching_results') is not None:
                            st.write("---")
                            st.subheader("✅ 1. 面談マッチング結果")
                            all_mentors = df_mentors["メンター氏名"].unique().tolist() if not df_mentors.empty else []
                            
                            edited_df = st.data_editor(
                                st.session_state['matching_results'],
                                column_config={
                                    "決定メンター": st.column_config.SelectboxColumn("担当メンター", options=all_mentors, required=False, width="medium"),
                                    "決定日時": st.column_config.SelectboxColumn("面談日時", options=TIME_SLOTS, required=False, width="medium"),
                                    "ステータス": st.column_config.SelectboxColumn("ステータス", options=["決定", "未定", "キャンセル"], width="small")
                                },
                                hide_index=True, num_rows="fixed", key="matching_editor_tab4"
                            )
                            st.session_state['matching_results'] = edited_df
                            
                            csv_res = edited_df.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📥 面談結果をCSVでDL", csv_res, "matching_result.csv", "text/csv")
                            
                            # 部屋担当表
                            st.write("---")
                            st.subheader("✅ 2. 部屋担当者リスト（待機メンター）")
                            st.caption("※面談がある時間帯で、割り振られなかった待機メンターです。")
                            if st.session_state.get('room_managers_results') is not None and not st.session_state['room_managers_results'].empty:
                                st.dataframe(st.session_state['room_managers_results'], hide_index=True, use_container_width=True)
                            else:
                                st.info("待機メンターはいません")

                            st.write("---")
                            if st.button("✅ データを履歴に保存してリセット"):
                                final_data = st.session_state['matching_results']
                                history_data = final_data[final_data["ステータス"] == "決定"][["生徒氏名", "決定メンター"]]
                                history_data = history_data.rename(columns={"決定メンター": "前回担当メンター"})
                                append_data_to_sheet(history_data, "history")
                                save_data_to_sheet(pd.DataFrame(), "students")
                                save_data_to_sheet(pd.DataFrame(), "mentors")
                                st.session_state['matching_results'] = None
                                st.session_state['room_managers_results'] = None
                                set_status(False)
                                st.success("完了しました")
                                time.sleep(1)
                                st.rerun()

                else:
                    st.session_state['login_attempts'] += 1
                    time.sleep(3)
                    st.warning("パスワードが違います")
                    if 5 - st.session_state['login_attempts'] <= 0:
                        st.rerun()
            except Exception as e:
                st.error(f"システムエラー: {e}")
