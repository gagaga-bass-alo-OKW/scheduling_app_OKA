import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import io
import streamlit as st

# --- 画面のメニューバーとフッターを隠すCSS ---
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ... 以下、通常のコード ...
# ==========================================
# 🛡️ 1. 基本設定・検索除け
# ==========================================
st.set_page_config(page_title="ALOHA面談日程調整", layout="wide")
st.markdown("""<meta name="robots" content="noindex, nofollow">""", unsafe_allow_html=True)

# ==========================================
# 📅 2. 時間枠の自動生成
# ==========================================
TIME_SLOTS = []
WEEKDAYS = ["月曜", "火曜", "水曜", "木曜", "金曜"]
WD_START, WD_END = 20, 23
for day in WEEKDAYS:
    for hour in range(WD_START, WD_END):
        TIME_SLOTS.append(f"{day} {hour}:00-{hour+1}:00")

WEEKENDS = ["土曜", "日曜"]
WE_START, WE_END = 9, 23
for day in WEEKENDS:
    for hour in range(WE_START, WE_END):
        TIME_SLOTS.append(f"{day} {hour}:00-{hour+1}:00")

DAY_ORDER = {"月曜": 0, "火曜": 1, "水曜": 2, "木曜": 3, "金曜": 4, "土曜": 5, "日曜": 6}

# ==========================================
# ☁️ 3. Googleスプレッドシート連携 & 設定管理
# ==========================================
@st.cache_resource
def get_spreadsheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # 鍵データの自動修復
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

# --- 公開設定の読み書き機能 ---
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
                s_line_name = st.text_input("公式LINEでのあなたの名前（表示名） ※")
                s_school = st.text_input("学校名 ※")
            with col2:
                s_grade = st.selectbox("学年 ※", ["中1", "中2", "中3", "高1", "高2", "高3"], index=None, placeholder="選択してください")
                s_stream = st.radio("文理選択 ※", ["文系", "理系", "未定"], index=None)
            
            st.write("---")
            st.subheader("メンターの希望")
            s_want_prev = st.radio("前回の担当者と同じ人を希望しますか？ ※", ["希望する", "希望しない"], index=None, horizontal=True)
            s_request_mentor = st.text_input("その他、担当してほしい東大生がいれば名前を書いてください")
            st.write("---")
            s_questions = st.text_area("当日聞きたいことや相談したいことがあれば自由に書いてください")
            st.write("▼ **面談可能な**時間帯を選択（複数選択可） 2026年1/5~11※")
            st.write("【受験生限定！】共通テスト直後にも面談を希望される方は、上の自由欄にその旨を回答ください")
            s_available = st.multiselect("面談可能日時", TIME_SLOTS)

            if st.form_submit_button("送信"):
                required_fields = {
                    "氏名": s_name, "LINE名": s_line_name, "学校名": s_school,
                    "学年": s_grade, "文理選択": s_stream,
                    "前回希望の有無": s_want_prev, "面談可能日時": s_available
                }
                missing_fields = [k for k, v in required_fields.items() if not v]
                
                if missing_fields:
                    st.error(f"以下の必須項目が入力されていません： {', '.join(missing_fields)}")
                else:
                    df_s = load_data_from_sheet("students")
                    new_row = {
                        "生徒氏名": s_name, "LINE名": s_line_name, "学校": s_school,
                        "学年": s_grade, "文理": s_stream,
                        "前回希望": "あり" if s_want_prev == "希望する" else "なし",
                        "指名希望": s_request_mentor, "質問内容": s_questions,
                        "可能日時": ",".join(s_available)
                    }
                    if not df_s.empty and "生徒氏名" in df_s.columns:
                        df_s = df_s[df_s["生徒氏名"] != s_name]
                        df_s = pd.concat([df_s, pd.DataFrame([new_row])], ignore_index=True)
                        st.success(f"{s_name} さんの情報を更新（上書き）しました！")
                    else:
                        df_s = pd.DataFrame([new_row])
                        st.success(f"保存しました！ありがとうございます、{s_name}さん。")
                    save_data_to_sheet(df_s, "students")

# --- Tab 2: 大学生用 ---
with tab2:
    st.header("大学生用：空きコマ登録")
    
    if not is_accepting:
        st.warning("現在は登録期間外です。")
    else:
        st.write("ご協力ありがとうございます。自身の属性と空き時間を入力してください。")
        st.caption("※同じ「氏名」で再送信すると、以前の情報が上書きされます。")
        
        with st.form("mentor_form"):
            m_name_input = st.text_input("氏名（大学生） ※")
            m_name = m_name_input.strip() if m_name_input else ""
            st.write("▼ 受験時の文理を選択してください（両方対応可能な場合は複数選択可） ※")
            m_stream = st.multiselect("文理選択", ["文系", "理系"])
            st.write("---")
            st.write("▼ 対応可能な時間帯を選択 2026年1/5~11※")
            m_available = st.multiselect("対応可能日時", TIME_SLOTS)
            
            if st.form_submit_button("登録"):
                if m_name and m_available and m_stream:
                    df_m = load_data_from_sheet("mentors")
                    new_row = {
                        "メンター氏名": m_name, "文理": ",".join(m_stream),
                        "可能日時": ",".join(m_available)
                    }
                    if not df_m.empty and "メンター氏名" in df_m.columns:
                        df_m = df_m[df_m["メンター氏名"] != m_name]
                        df_m = pd.concat([df_m, pd.DataFrame([new_row])], ignore_index=True)
                        st.success(f"{m_name} さんの情報を更新（上書き）しました！")
                    else:
                        df_m = pd.DataFrame([new_row])
                        st.success(f"登録しました！ありがとうございます、{m_name}さん。")
                    save_data_to_sheet(df_m, "mentors")
                else:
                    st.error("「氏名」「文理」「日時」はすべて必須です。")

# ※ ファイルの先頭に import random を追加してください
import random 

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
                # パスワードチェック
                correct_pass = st.secrets.get("ADMIN_PASSWORD")
                
                if not correct_pass:
                    st.warning("⚠️ システム設定エラー: Secretsにパスワードが設定されていません。")
                
                elif password == correct_pass:
                    st.session_state['login_attempts'] = 0
                    st.success("認証成功")
                    st.write("---")

                    # 管理者用の内部タブを作成
                    ad_tab1, ad_tab2, ad_tab3, ad_tab4 = st.tabs(["📡 公開設定", "🏫 生徒管理", "🎓 メンター管理", "🚀 マッチング"])

                    # ----------------------------------------
                    # 1. 公開設定
                    # ----------------------------------------
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

                    # ----------------------------------------
                    # 2. 生徒管理 (CSV & サンプル生成)
                    # ----------------------------------------
                    with ad_tab2:
                        st.subheader("🏫 生徒データの管理")
                        
                        # A. CSVアップロード
                        with st.expander("📥 CSVファイルから一括登録"):
                            st.write("Excelなどで作成した生徒名簿を一括で読み込めます。")
                            s_dummy = pd.DataFrame(columns=["生徒氏名", "LINE名", "学校", "学年", "文理", "前回希望", "指名希望", "質問内容", "可能日時"])
                            s_csv = s_dummy.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📄 テンプレート(CSV)をDL", s_csv, "student_template.csv", "text/csv")
                            
                            s_file = st.file_uploader("生徒CSVをアップロード", type=["csv"])
                            if s_file:
                                try:
                                    df_s_up = pd.read_csv(s_file)
                                    if st.button("このデータで登録/上書き (生徒)"):
                                        df_curr = load_data_from_sheet("students")
                                        req = ["生徒氏名", "学校", "学年"]
                                        if not all(c in df_s_up.columns for c in req):
                                            st.error(f"必須列不足: {req}")
                                        else:
                                            # 上書き処理
                                            up_names = df_s_up["生徒氏名"].astype(str).str.strip().tolist()
                                            df_s_up["生徒氏名"] = df_s_up["生徒氏名"].astype(str).str.strip()
                                            if not df_curr.empty:
                                                df_curr = df_curr[~df_curr["生徒氏名"].isin(up_names)]
                                                df_new = pd.concat([df_curr, df_s_up], ignore_index=True)
                                            else:
                                                df_new = df_s_up
                                            save_data_to_sheet(df_new, "students")
                                            st.success(f"{len(df_s_up)}件の生徒データを登録しました")
                                except Exception as e:
                                    st.error(f"エラー: {e}")

                        st.write("---")

                        # B. サンプルデータ生成
                        with st.expander("🎲 テスト用サンプルデータの生成"):
                            st.warning("⚠️ 注意: これを実行すると、現在の「生徒データ」が全て削除され、ダミーデータに置き換わります。")
                            num_students = st.number_input("生成する生徒数", min_value=1, max_value=50, value=15)
                            
                            if st.button("💥 生徒ダミーデータを生成して上書き保存"):
                                dummy_students = []
                                grades = ["中1", "中2", "中3", "高1", "高2", "高3"]
                                streams = ["文系", "理系", "未定"]
                                
                                for i in range(num_students):
                                    # ランダムに3~6個の時間枠を選ぶ
                                    n_slots = random.randint(3, 6)
                                    picked_slots = random.sample(TIME_SLOTS, n_slots)
                                    
                                    dummy_students.append({
                                        "生徒氏名": f"生徒{i+1:02d}", # 生徒01, 生徒02...
                                        "LINE名": f"line_user_{i+1}",
                                        "学校": "テスト高校",
                                        "学年": random.choice(grades),
                                        "文理": random.choice(streams),
                                        "前回希望": random.choice(["あり", "なし"]),
                                        "指名希望": "",
                                        "質問内容": "テスト用の質問です。",
                                        "可能日時": ",".join(picked_slots)
                                    })
                                
                                df_dummy_s = pd.DataFrame(dummy_students)
                                save_data_to_sheet(df_dummy_s, "students")
                                st.success(f"{num_students}名の生徒ダミーデータを生成・保存しました！")

                        # 現在のデータ表示
                        st.write("▼ 現在の登録データ")
                        df_s_now = load_data_from_sheet("students")
                        st.dataframe(df_s_now)

                    # ----------------------------------------
                    # 3. メンター管理 (CSV & サンプル生成)
                    # ----------------------------------------
                    with ad_tab3:
                        st.subheader("🎓 メンターデータの管理")

                        # A. CSVアップロード
                        with st.expander("📥 CSVファイルから一括登録"):
                            m_dummy = pd.DataFrame(columns=["メンター氏名", "文理", "可能日時"])
                            m_csv = m_dummy.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📄 テンプレート(CSV)をDL", m_csv, "mentor_template.csv", "text/csv")
                            
                            m_file = st.file_uploader("メンターCSVをアップロード", type=["csv"])
                            if m_file:
                                try:
                                    df_m_up = pd.read_csv(m_file)
                                    if st.button("このデータで登録/上書き (メンター)"):
                                        df_curr = load_data_from_sheet("mentors")
                                        req = ["メンター氏名", "文理", "可能日時"]
                                        if not all(c in df_m_up.columns for c in req):
                                            st.error(f"必須列不足: {req}")
                                        else:
                                            # 上書き処理
                                            up_names = df_m_up["メンター氏名"].astype(str).str.strip().tolist()
                                            df_m_up["メンター氏名"] = df_m_up["メンター氏名"].astype(str).str.strip()
                                            if not df_curr.empty:
                                                df_curr = df_curr[~df_curr["メンター氏名"].isin(up_names)]
                                                df_new = pd.concat([df_curr, df_m_up], ignore_index=True)
                                            else:
                                                df_new = df_m_up
                                            save_data_to_sheet(df_new, "mentors")
                                            st.success(f"{len(df_m_up)}件のメンターデータを登録しました")
                                except Exception as e:
                                    st.error(f"エラー: {e}")

                        st.write("---")

                        # B. サンプルデータ生成
                        with st.expander("🎲 テスト用サンプルデータの生成"):
                            st.warning("⚠️ 注意: これを実行すると、現在の「メンターデータ」が全て削除され、ダミーデータに置き換わります。")
                            num_mentors = st.number_input("生成するメンター数", min_value=1, max_value=30, value=10)
                            
                            if st.button("💥 メンターダミーデータを生成して上書き保存"):
                                dummy_mentors = []
                                m_streams_opts = ["文系", "理系", "文系,理系"]
                                
                                for i in range(num_mentors):
                                    # メンターは多めに時間枠を開ける (10~20枠)
                                    n_slots = random.randint(10, 20)
                                    # 時間枠リストの範囲内でランダム取得
                                    safe_n = min(n_slots, len(TIME_SLOTS))
                                    picked_slots = random.sample(TIME_SLOTS, safe_n)
                                    
                                    dummy_mentors.append({
                                        "メンター氏名": f"メンター{chr(65+i)}", # メンターA, メンターB...
                                        "文理": random.choice(m_streams_opts),
                                        "可能日時": ",".join(picked_slots)
                                    })
                                
                                df_dummy_m = pd.DataFrame(dummy_mentors)
                                save_data_to_sheet(df_dummy_m, "mentors")
                                st.success(f"{num_mentors}名のメンターダミーデータを生成・保存しました！")

                        # 現在のデータ表示
                        st.write("▼ 現在の登録データ")
                        df_m_now = load_data_from_sheet("mentors")
                        st.dataframe(df_m_now)

                    # ----------------------------------------
                    # 4. マッチング実行 & 編集
                    # ----------------------------------------
                    with ad_tab4:
                        st.subheader("🚀 マッチング実行")
                        
                        if 'matching_results' not in st.session_state:
                            st.session_state['matching_results'] = None
                        if 'managers_results' not in st.session_state:
                            st.session_state['managers_results'] = None

                        # データの再ロード
                        df_students = load_data_from_sheet("students")
                        df_mentors = load_data_from_sheet("mentors")
                        df_history = load_data_from_sheet("history")
                        
                        st.caption(f"現在の対象データ: 生徒 {len(df_students)}名 / メンター {len(df_mentors)}名")

                        if st.button("自動マッチングを開始する", type="primary"):
                            if df_students.empty or df_mentors.empty:
                                st.error("データがありません。「生徒管理」「メンター管理」タブでデータを登録してください。")
                            else:
                                # --- マッチングロジック開始 ---
                                results = []
                                mentor_schedule = {} 
                                mentor_streams = {}  
                                mentor_original_availability = {}

                                for _, row in df_mentors.iterrows():
                                    m_name = row["メンター氏名"]
                                    slots = set(row["可能日時"].split(",")) if row["可能日時"] else set()
                                    mentor_schedule[m_name] = slots
                                    for s in slots:
                                        day = s.split(" ")[0]
                                        if day not in mentor_original_availability:
                                            mentor_original_availability[day] = []
                                        mentor_original_availability[day].append(m_name)
                                    
                                    streams = row["文理"].split(",") if "文理" in row and row["文理"] else []
                                    mentor_streams[m_name] = streams

                                for _, s_row in df_students.iterrows():
                                    s_name = s_row["生徒氏名"]
                                    s_stream = s_row["文理"]
                                    s_slots = set(s_row["可能日時"].split(",")) if s_row["可能日時"] else set()
                                    want_prev = (s_row["前回希望"] == "あり")
                                    
                                    prev_mentor = None
                                    if not df_history.empty and "生徒氏名" in df_history.columns:
                                        hist = df_history[df_history["生徒氏名"] == s_name]
                                        if not hist.empty:
                                            prev_mentor = hist.iloc[-1]["前回担当メンター"]

                                    assigned_mentor = None
                                    assigned_slot = None
                                    candidates = list(mentor_schedule.keys())
                                    if want_prev and prev_mentor in candidates:
                                        candidates.remove(prev_mentor)
                                        candidates.insert(0, prev_mentor)

                                    for m_name in candidates:
                                        m_streams_list = mentor_streams.get(m_name, [])
                                        if s_stream != "未定" and s_stream not in m_streams_list:
                                            continue 
                                        common = s_slots.intersection(mentor_schedule[m_name])
                                        if common:
                                            slot = list(common)[0]
                                            assigned_mentor = m_name
                                            assigned_slot = slot
                                            mentor_schedule[m_name].remove(slot)
                                            break
                                    
                                    results.append({
                                        "生徒氏名": s_name,
                                        "決定メンター": assigned_mentor,
                                        "決定日時": assigned_slot,
                                        "ステータス": "決定" if assigned_mentor else "未定",
                                        "学校": s_row["学校"],
                                        "生徒文理": s_stream,
                                        "メンター文理": ",".join(mentor_streams.get(assigned_mentor, [])) if assigned_mentor else "",
                                        "前回担当メンター": assigned_mentor if assigned_mentor else ""
                                    })

                                df_results = pd.DataFrame(results)

                                # ソート
                                def get_sort_key(val):
                                    if not val or pd.isna(val) or val == "None" or not isinstance(val, str):
                                        return (99, 99)
                                    try:
                                        parts = val.split(" ")
                                        d_str = parts[0]
                                        t_str = parts[1].split(":")[0]
                                        d_num = DAY_ORDER.get(d_str, 99)
                                        return (d_num, int(t_str))
                                    except:
                                        return (99, 99)

                                df_results["_sort_key"] = df_results["決定日時"].apply(get_sort_key)
                                df_results = df_results.sort_values(by="_sort_key").drop(columns=["_sort_key"])
                                
                                st.session_state['matching_results'] = df_results
                                st.success("マッチング完了！下にスクロールして結果を確認・編集してください。")

                        # --- 結果編集 ---
                        if st.session_state['matching_results'] is not None:
                            st.write("---")
                            st.subheader("✅ マッチング結果の編集")
                            st.info("セルをクリックして担当者や時間を変更できます。変更は自動保存されます。")

                            all_mentors = df_mentors["メンター氏名"].unique().tolist()
                            
                            edited_df = st.data_editor(
                                st.session_state['matching_results'],
                                column_config={
                                    "決定メンター": st.column_config.SelectboxColumn(
                                        "担当メンター", options=all_mentors, required=False, width="medium"
                                    ),
                                    "決定日時": st.column_config.SelectboxColumn(
                                        "面談日時", options=TIME_SLOTS, required=False, width="medium"
                                    ),
                                    "ステータス": st.column_config.SelectboxColumn(
                                        "ステータス", options=["決定", "未定", "キャンセル"], width="small"
                                    )
                                },
                                hide_index=True,
                                num_rows="fixed",
                                key="matching_editor_tab4"
                            )
                            st.session_state['matching_results'] = edited_df

                            # ダウンロード
                            csv_res = edited_df.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📥 結果CSVをダウンロード", csv_res, "matching_result.csv", "text/csv")

                            # 完了処理
                            st.write("---")
                            if st.button("✅ データを履歴に保存してリセット (イベント終了後)"):
                                final_data = st.session_state['matching_results']
                                history_data = final_data[final_data["ステータス"] == "決定"][["生徒氏名", "決定メンター"]]
                                history_data = history_data.rename(columns={"決定メンター": "前回担当メンター"})
                                
                                append_data_to_sheet(history_data, "history")
                                save_data_to_sheet(pd.DataFrame(), "students")
                                save_data_to_sheet(pd.DataFrame(), "mentors")
                                
                                st.session_state['matching_results'] = None
                                set_status(False)
                                st.success("完了しました！初期化してリロードします。")
                                time.sleep(2)
                                st.rerun()

                else:
                    st.session_state['login_attempts'] += 1
                    time.sleep(3)
                    st.warning("パスワードが違います")
                    if 5 - st.session_state['login_attempts'] <= 0:
                        st.rerun()

            except Exception as e:
                st.error(f"システムエラー: {e}")
