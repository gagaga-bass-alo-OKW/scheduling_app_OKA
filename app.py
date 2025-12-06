import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# ==========================================
# 🛡️ 1. 基本設定・検索除け
# ==========================================
st.set_page_config(page_title="ALOHA面談日程調整", layout="wide")
st.markdown("""<meta name="robots" content="noindex, nofollow">""", unsafe_allow_html=True)

# 画像表示（必要に応じてファイル名を変更してください）
# st.image("logo.png", use_column_width=True) 

# ==========================================
# 📅 2. 時間枠の自動生成
# ==========================================
TIME_SLOTS = []
WEEKDAYS = ["月曜", "火曜", "水曜", "木曜", "金曜"]
WD_START, WD_END = 17, 22
for day in WEEKDAYS:
    for hour in range(WD_START, WD_END):
        TIME_SLOTS.append(f"{day} {hour}:00-{hour+1}:00")

WEEKENDS = ["土曜", "日曜"]
WE_START, WE_END = 10, 23
for day in WEEKENDS:
    for hour in range(WE_START, WE_END):
        TIME_SLOTS.append(f"{day} {hour}:00-{hour+1}:00")

# 曜日ソート用
DAY_ORDER = {"月曜": 0, "火曜": 1, "水曜": 2, "木曜": 3, "金曜": 4, "土曜": 5, "日曜": 6}

# ==========================================
# ☁️ 3. Googleスプレッドシート連携 & 設定管理
# ==========================================
@st.cache_resource
def get_spreadsheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # 🛡️ 鍵データの自動修復ロジック
    # secretsのデータを辞書としてコピーし、改行コード(\n)を正しく置換する
    key_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")

    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_url(st.secrets["spreadsheet_url"])

def load_data_from_sheet(sheet_name):
    try:
        sh = get_spreadsheet()
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

def save_data_to_sheet(df, sheet_name):
    sh = get_spreadsheet()
    worksheet = sh.worksheet(sheet_name)
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

def append_data_to_sheet(df, sheet_name):
    sh = get_spreadsheet()
    worksheet = sh.worksheet(sheet_name)
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

# 現在の状態を読み込む
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
                # 名前入力の空白除去処理
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
            st.write("▼ **面談可能な**時間帯を選択（複数選択可） ※")
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
                        # 上書き保存ロジック
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
            st.write("▼ 対応可能な時間帯を選択 ※")
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

# --- Tab 3: 管理者用 ---
with tab3:
    st.header("🔒 管理者ダッシュボード")

    if 'login_attempts' not in st.session_state:
        st.session_state['login_attempts'] = 0

    if st.session_state['login_attempts'] >= 5:
        st.error("⚠️ ロックされています。解除するにはブラウザを再読み込みしてください。")
    else:
        # パスワード入力フォーム
        password_input = st.text_input("管理者パスワード", type="password")
        
        # ログインボタン または 入力済みエンターで実行
        if st.button("🔑 ログイン") or password_input:
            try:
                # Secretsから取得（ない場合は空文字にする）
                secret_pass = str(st.secrets.get("ADMIN_PASSWORD", ""))
                
                # 空白削除して比較（入力ミス防止）
                input_clean = password_input.strip()
                secret_clean = secret_pass.strip()
                
                if not secret_clean:
                    st.warning("⚠️ システム設定エラー: Secretsにパスワードが設定されていません。")
                
                elif input_clean == secret_clean:
                    st.session_state['login_attempts'] = 0
                    st.success("認証成功")
                    
                    # === 認証成功時の機能 ===
                    st.subheader("📡 公開設定")
                    col_setting1, col_setting2 = st.columns([1, 3])
                    with col_setting1:
                        if is_accepting:
                            if st.button("🔴 受付を停止する"):
                                set_status(False)
                                st.rerun()
                        else:
                            if st.button("🟢 受付を開始する"):
                                set_status(True)
                                st.rerun()
                    with col_setting2:
                        if is_accepting:
                            st.info("現在は「回答受付中」です。")
                        else:
                            st.error("現在は「停止中」です。")
                    st.write("---")

                    # CSVアップロード機能
                    st.subheader("📥 生徒CSV一括登録")
                    with st.expander("CSVアップロード機能を開く"):
                        st.write("Excelなどで作成した生徒名簿を一括で読み込めます。")
                        
                        dummy_data = pd.DataFrame(columns=["生徒氏名", "LINE名", "学校", "学年", "文理", "前回希望", "指名希望", "質問内容", "可能日時"])
                        csv_template = dummy_data.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📄 入力用テンプレート(CSV)をダウンロード",
                            data=csv_template,
                            file_name="student_template.csv",
                            mime="text/csv",
                        )
                        st.info("※「可能日時」は `月曜 17:00-18:00,月曜 18:00-19:00` のようにカンマ区切りで入力してください。")

                        uploaded_file = st.file_uploader("CSVファイルをアップロード", type=["csv"])
                        
                        if uploaded_file is not None:
                            try:
                                df_upload = pd.read_csv(uploaded_file)
                                st.write("▼ 読み込んだデータプレビュー")
                                st.dataframe(df_upload.head())
                                
                                if st.button("💾 この内容で登録/上書きする"):
                                    df_current = load_data_from_sheet("students")
                                    required_cols = ["生徒氏名", "学校", "学年"]
                                    if not all(col in df_upload.columns for col in required_cols):
                                        st.error(f"CSVの列名が正しくありません。テンプレートを使用してください。必須: {required_cols}")
                                    else:
                                        upload_names = df_upload["生徒氏名"].astype(str).str.strip().tolist()
                                        df_upload["生徒氏名"] = df_upload["生徒氏名"].astype(str).str.strip()
                                        
                                        if not df_current.empty:
                                            df_current = df_current[~df_current["生徒氏名"].isin(upload_names)]
                                            df_new = pd.concat([df_current, df_upload], ignore_index=True)
                                        else:
                                            df_new = df_upload
                                        
                                        save_data_to_sheet(df_new, "students")
                                        st.success(f"{len(df_upload)} 件のデータを登録しました！")
                            except Exception as e:
                                st.error(f"エラーが発生しました: {e}")

                    st.write("---")

                    # データ表示
                    if 'matching_results' not in st.session_state:
                        st.session_state['matching_results'] = None
                    if 'managers_results' not in st.session_state:
                        st.session_state['managers_results'] = None

                    df_students = load_data_from_sheet("students")
                    df_mentors = load_data_from_sheet("mentors")
                    df_history = load_data_from_sheet("history")
                    
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.write(f"📋 生徒データ ({len(df_students)}件)")
                        st.dataframe(df_students)
                    with col_b:
                        st.write(f"📋 メンターデータ ({len(df_mentors)}件)")
                        st.dataframe(df_mentors)
                    with col_c:
                        st.write(f"📜 履歴データ ({len(df_history)}件)")
                        st.dataframe(df_history)

                    st.write("---")
                    
                    # 自動マッチングボタン
                    if st.button("🚀 自動マッチングを実行"):
                        if df_students.empty or df_mentors.empty:
                            st.warning("データが不足しています。")
                        else:
                            # 1. マッチング処理
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

                            # 生徒のマッチング
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

                            # 🔄 並び替えロジック
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

                            # --- 🔑 部屋管理者 (Room Manager) 選定 ---
                            managers = []
                            active_days = set()
                            matched_data = df_results[df_results["ステータス"] == "決定"]
                            for dt in matched_data["決定日時"]:
                                active_days.add(dt.split(" ")[0])
                            
                            sorted_days = sorted(list(active_days), key=lambda x: DAY_ORDER.get(x, 99))

                            for day in sorted_days:
                                matched_mentors_today = matched_data[matched_data["決定日時"].str.startswith(day)]["決定メンター"].tolist()
                                available_mentors_today = list(set(mentor_original_availability.get(day, [])))
                                
                                free_mentors = [m for m in available_mentors_today if m not in matched_mentors_today]
                                
                                lonely_mentors = []
                                day_matches = matched_data[matched_data["決定日時"].str.startswith(day)]
                                counts = day_matches["決定日時"].value_counts()
                                for idx, row in day_matches.iterrows():
                                    slot = row["決定日時"]
                                    if counts[slot] == 1:
                                        lonely_mentors.append(row["決定メンター"])

                                selected_manager = "該当なし"
                                note = ""
                                
                                if free_mentors:
                                    selected_manager = free_mentors[0]
                                    note = "条件①: マッチングなし"
                                elif lonely_mentors:
                                    selected_manager = lonely_mentors[0]
                                    note = "条件②: 単独面談"
                                else:
                                    if matched_mentors_today:
                                        selected_manager = matched_mentors_today[0]
                                        note = "条件外: マッチングあり"

                                managers.append({
                                    "曜日": day,
                                    "部屋管理者": selected_manager,
                                    "選出理由": note
                                })
                            
                            st.session_state['managers_results'] = pd.DataFrame(managers)

                    # 結果表示エリア
                    if st.session_state['managers_results'] is not None:
                        st.subheader("🔑 部屋管理者 (各日1名)")
                        st.dataframe(st.session_state['managers_results'])
                        
                    if st.session_state['matching_results'] is not None:
                        df_res = st.session_state['matching_results']
                        st.subheader("✅ マッチング結果")
                        st.dataframe(df_res)
                        
                        csv = df_res.to_csv(index=False).encode('utf-8-sig')
                        st.download_button("📥 結果をCSVでダウンロード", csv, "matching_result.csv", "text/csv")
                        
                        st.write("---")
                        st.warning("⚠️ **イベント終了後の処理**")
                        st.write("全員への連絡が終わったら、以下のボタンを押して次回の準備をしてください。")
                        
                        if st.button("✅ 履歴に保存して、データをリセットする"):
                            history_data = df_res[df_res["ステータス"] == "決定"][["生徒氏名", "前回担当メンター"]]
                            append_data_to_sheet(history_data, "history")
                            save_data_to_sheet(pd.DataFrame(), "students")
                            save_data_to_sheet(pd.DataFrame(), "mentors")
                            st.session_state['matching_results'] = None
                            st.session_state['managers_results'] = None
                            set_status(False) 
                            st.success("リセット完了！自動的に「受付停止」状態にしました。")
                            st.rerun()

                else:
                    # パスワード不一致の処理（ボタン押下時のみ）
                    if password_input:
                        st.session_state['login_attempts'] += 1
                        time.sleep(3)
                        st.warning("パスワードが違います") 
                        
                        attempts_left = 5 - st.session_state['login_attempts']
                        if attempts_left <= 0:
                            st.rerun()

            except Exception as e:
                # 予期せぬエラーは隠して警告のみ
                st.warning("システムエラー: 設定を確認してください")
                # print(e) # 必要ならログに出力
