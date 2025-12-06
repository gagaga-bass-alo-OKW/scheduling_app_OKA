import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import io

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
WD_START, WD_END = 17, 22
for day in WEEKDAYS:
    for hour in range(WD_START, WD_END):
        TIME_SLOTS.append(f"{day} {hour}:00-{hour+1}:00")

WEEKENDS = ["土曜", "日曜"]
WE_START, WE_END = 10, 23
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
        password_input = st.text_input("管理者パスワード", type="password")
        
        if st.button("🔑 ログイン") or password_input:
            try:
                secret_pass = str(st.secrets.get("ADMIN_PASSWORD", ""))
                input_clean = password_input.strip()
                secret_clean = secret_pass.strip()
                
                if not secret_clean:
                    st.warning("⚠️ システム設定エラー: Secretsにパスワードが設定されていません。")
                
                elif input_clean == secret_clean:
                    st.session_state['login_attempts'] = 0
                    st.success("認証成功")
                    
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

                    col_csv1, col_csv2 = st.columns(2)
                    
                    # 生徒CSV
                    with col_csv1:
                        st.subheader("📥 生徒CSV登録")
                        with st.expander("生徒CSV機能"):
                            dummy_s = pd.DataFrame(columns=["生徒氏名", "LINE名", "学校", "学年", "文理", "前回希望", "指名希望", "質問内容", "可能日時"])
                            csv_template_s = dummy_s.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📄 生徒用テンプレート", csv_template_s, "student_template.csv", "text/csv")
                            
                            uploaded_file_s = st.file_uploader("生徒CSVをアップロード", type=["csv"], key="s_up")
                            if uploaded_file_s:
                                try:
                                    df_upload = pd.read_csv(uploaded_file_s)
                                    df_upload = df_upload.fillna("")
                                    if st.button("💾 生徒データを登録", key="s_btn"):
                                        df_current = load_data_from_sheet("students")
                                        required = ["生徒氏名", "学校", "学年"]
                                        if not all(col in df_upload.columns for col in required):
                                            st.error(f"列名エラー。必須: {required}")
                                        else:
                                            names = df_upload["生徒氏名"].astype(str).str.strip().tolist()
                                            df_upload["生徒氏名"] = df_upload["生徒氏名"].astype(str).str.strip()
                                            if not df_current.empty:
                                                df_current = df_current[~df_current["生徒氏名"].isin(names)]
                                                df_new = pd.concat([df_current, df_upload], ignore_index=True)
                                            else:
                                                df_new = df_upload
                                            save_data_to_sheet(df_new, "students")
                                            st.success(f"{len(df_upload)} 件登録しました！")
                                except Exception as e:
                                    st.error(f"エラー: {e}")

                    # メンターCSV
                    with col_csv2:
                        st.subheader("📥 メンターCSV登録")
                        with st.expander("メンターCSV機能"):
                            dummy_m = pd.DataFrame(columns=["メンター氏名", "文理", "可能日時"])
                            csv_template_m = dummy_m.to_csv(index=False).encode('utf-8-sig')
                            st.download_button("📄 メンター用テンプレート", csv_template_m, "mentor_template.csv", "text/csv")

                            uploaded_file_m = st.file_uploader("メンターCSVをアップロード", type=["csv"], key="m_up")
                            if uploaded_file_m:
                                try:
                                    df_upload_m = pd.read_csv(uploaded_file_m)
                                    df_upload_m = df_upload_m.fillna("")
                                    if st.button("💾 メンターデータを登録", key="m_btn"):
                                        df_current_m = load_data_from_sheet("mentors")
                                        required_m = ["メンター氏名", "文理", "可能日時"]
                                        if not all(col in df_upload_m.columns for col in required_m):
                                            st.error(f"列名エラー。必須: {required_m}")
                                        else:
                                            names_m = df_upload_m["メンター氏名"].astype(str).str.strip().tolist()
                                            df_upload_m["メンター氏名"] = df_upload_m["メンター氏名"].astype(str).str.strip()
                                            if not df_current_m.empty:
                                                df_current_m = df_current_m[~df_current_m["メンター氏名"].isin(names_m)]
                                                df_new_m = pd.concat([df_current_m, df_upload_m], ignore_index=True)
                                            else:
                                                df_new_m = df_upload_m
                                            save_data_to_sheet(df_new_m, "mentors")
                                            st.success(f"{len(df_upload_m)} 件登録しました！")
                                except Exception as e:
                                    st.error(f"エラー: {e}")

                    st.write("---")

                    # テストデータ生成
                    st.subheader("🧪 テストデータ生成")
                    with st.expander("動作確認用のダミーデータをダウンロード"):
                        st.write("以下のボタンを押すと、架空の「生徒40名」「メンター10名」のCSVファイルをダウンロードできます。")
                        
                        test_students_csv = """生徒氏名,LINE名,学校,学年,文理,前回希望,指名希望,質問内容,可能日時
佐藤 一郎,Sato1,〇〇高校,高1,文系,なし,,部活との両立,"月曜 17:00-18:00,月曜 18:00-19:00"
鈴木 次郎,Jiro_S,〇〇高校,高2,理系,なし,,理系の進路,"火曜 18:00-19:00,水曜 17:00-18:00"
高橋 花子,Hana_T,△△中学,中3,未定,なし,,受験勉強,"水曜 19:00-20:00,木曜 17:00-18:00"
田中 美咲,Misaki,△△中学,中2,未定,なし,,英語苦手,"金曜 17:00-18:00,土曜 10:00-11:00"
伊藤 健太,Kenta_I,□□高校,高3,理系,なし,東大 太郎,物理の勉強法,"土曜 13:00-14:00,日曜 14:00-15:00"
渡辺 翔太,Shota_W,〇〇高校,高1,文系,あり,,世界史,"日曜 15:00-16:00,月曜 19:00-20:00"
山本 真由,Mayu_Y,□□高校,高2,文系,なし,,古文,"月曜 17:00-18:00,火曜 18:00-19:00"
中村 拓海,Takumi,△△中学,中1,未定,なし,,,"水曜 17:00-18:00,木曜 18:00-19:00"
小林 さくら,Sakura,〇〇高校,高3,理系,あり,,化学,"金曜 19:00-20:00,土曜 11:00-12:00"
加藤 陽菜,Hina,□□高校,高2,理系,なし,,数III,"土曜 14:00-15:00,日曜 16:00-17:00"
吉田 蓮,Ren_Y,〇〇高校,高1,文系,なし,,現代文,"日曜 10:00-11:00,月曜 18:00-19:00"
山田 結衣,Yui_Y,△△中学,中3,文系,なし,,志望校,"月曜 19:00-20:00,火曜 17:00-18:00"
佐々木 陸,Riku_S,□□高校,高2,理系,なし,,生物,"水曜 18:00-19:00,木曜 19:00-20:00"
山口 葵,Aoi_Y,〇〇高校,高3,文系,あり,,英語長文,"金曜 17:00-18:00,土曜 15:00-16:00"
松本 蒼太,Sota_M,△△中学,中2,未定,なし,,,"土曜 16:00-17:00,日曜 11:00-12:00"
井上 凛,Rin_I,□□高校,高1,理系,なし,,数学IA,"日曜 13:00-14:00,月曜 17:00-18:00"
木村 湊,Minato,〇〇高校,高2,文系,なし,,日本史,"月曜 18:00-19:00,火曜 19:00-20:00"
林 陽向,Hinata,△△中学,中3,理系,なし,,理科実験,"水曜 17:00-18:00,木曜 18:00-19:00"
清水 結菜,Yuina,□□高校,高3,文系,なし,,小論文,"金曜 18:00-19:00,土曜 12:00-13:00"
山崎 樹,Itsuki,〇〇高校,高1,理系,なし,,プログラミング,"土曜 17:00-18:00,日曜 15:00-16:00"
池田 杏,An_I,△△中学,中1,未定,なし,,,"日曜 16:00-17:00,月曜 19:00-20:00"
橋本 瑛太,Eita,□□高校,高2,文系,なし,,漢文,"月曜 17:00-18:00,火曜 18:00-19:00"
阿部 紬,Tsumugi,〇〇高校,高3,理系,あり,,物理,"水曜 19:00-20:00,木曜 17:00-18:00"
石川 颯太,Sota_I,△△中学,中2,未定,なし,,,"金曜 19:00-20:00,土曜 10:00-11:00"
中島 詩,Uta_N,□□高校,高1,文系,なし,,英単語,"土曜 13:00-14:00,日曜 14:00-15:00"
前田 暖,Dan_M,〇〇高校,高2,理系,なし,,模試復習,"日曜 10:00-11:00,月曜 18:00-19:00"
藤田 咲良,Sakura_F,△△中学,中3,文系,なし,,英検,"月曜 19:00-20:00,火曜 17:00-18:00"
後藤 大和,Yamato,□□高校,高3,理系,なし,,共通テスト,"水曜 18:00-19:00,木曜 19:00-20:00"
小川 芽依,Mei_O,〇〇高校,高1,文系,なし,,留学,"金曜 17:00-18:00,土曜 15:00-16:00"
村上 悠,Yu_M,△△中学,中2,未定,なし,,,"土曜 16:00-17:00,日曜 11:00-12:00"
岡田 奏,Kanade,□□高校,高2,理系,なし,,数B,"日曜 13:00-14:00,月曜 17:00-18:00"
長谷川 澪,Mio_H,〇〇高校,高3,文系,あり,,過去問,"月曜 18:00-19:00,火曜 19:00-20:00"
近藤 律,Ritsu,△△中学,中3,理系,なし,,高校数学,"水曜 17:00-18:00,木曜 18:00-19:00"
石井 凪,Nagi_I,□□高校,高1,文系,なし,,読書,"金曜 18:00-19:00,土曜 12:00-13:00"
斉藤 仁,Jin_S,〇〇高校,高2,理系,なし,,有機化学,"土曜 17:00-18:00,日曜 15:00-16:00"
坂本 琴音,Kotone,△△中学,中1,未定,なし,,,"日曜 16:00-17:00,月曜 19:00-20:00"
遠藤 晴,Haru_E,□□高校,高3,文系,なし,,リスニング,"月曜 17:00-18:00,火曜 18:00-19:00"
青木 朔,Saku_A,〇〇高校,高2,理系,あり,,力学,"水曜 19:00-20:00,木曜 17:00-18:00"
藤井 あかり,Akari,△△中学,中2,未定,なし,,,"金曜 19:00-20:00,土曜 10:00-11:00"
西村 賢人,Kento,□□高校,高1,文系,なし,,現代社会,"土曜 13:00-14:00,日曜 14:00-15:00"
"""
                        
                        test_mentors_csv = """メンター氏名,文理,可能日時
東大 太郎,理系,"月曜 17:00-18:00,月曜 18:00-19:00,土曜 13:00-14:00"
東大 次郎,文系,"火曜 18:00-19:00,水曜 17:00-18:00,日曜 14:00-15:00"
東大 花子,文系,"水曜 19:00-20:00,木曜 17:00-18:00,金曜 17:00-18:00"
東大 美咲,理系,"金曜 17:00-18:00,土曜 10:00-11:00,土曜 11:00-12:00"
東大 健太,"文系,理系","土曜 13:00-14:00,日曜 14:00-15:00,日曜 15:00-16:00"
東大 翔太,文系,"日曜 15:00-16:00,月曜 19:00-20:00,月曜 17:00-18:00"
東大 真由,理系,"月曜 17:00-18:00,火曜 18:00-19:00,火曜 19:00-20:00"
東大 拓海,"文系,理系","水曜 17:00-18:00,木曜 18:00-19:00,金曜 18:00-19:00"
東大 さくら,文系,"金曜 19:00-20:00,土曜 11:00-12:00,土曜 12:00-13:00"
東大 陽菜,理系,"土曜 14:00-15:00,日曜 16:00-17:00,日曜 10:00-11:00"
"""
                        df_test_s = pd.read_csv(io.StringIO(test_students_csv))
                        csv_test_s = df_test_s.to_csv(index=False).encode('utf-8-sig')
                        st.download_button("📥 生徒40名データDL", csv_test_s, "test_students_40.csv", "text/csv")

                        df_test_m = pd.read_csv(io.StringIO(test_mentors_csv))
                        csv_test_m = df_test_m.to_csv(index=False).encode('utf-8-sig')
                        st.download_button("📥 大学生10名データDL", csv_test_m, "test_mentors_10.csv", "text/csv")

                    st.write("---")

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
                    if st.button("🚀 自動マッチングを実行"):
                        if df_students.empty or df_mentors.empty:
                            st.warning("データが不足しています。")
                        else:
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
                            df_results = df_results.fillna("")

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
                        
                        # --- ボタン分割 (履歴保存 / リセット) ---
                        col_op1, col_op2 = st.columns(2)
                        
                        with col_op1:
                            if st.button("💾 マッチング結果を履歴に保存"):
                                # "決定"ステータスのものだけ履歴に追加
                                history_data = df_res[df_res["ステータス"] == "決定"][["生徒氏名", "前回担当メンター", "決定日時"]]
                                append_data_to_sheet(history_data, "history")
                                st.success("✅ マッチング結果を「履歴」シートに保存しました！")

                        with col_op2:
                            if st.button("🗑️ データをリセットして受付停止"):
                                # データを空にする
                                save_data_to_sheet(pd.DataFrame(), "students")
                                save_data_to_sheet(pd.DataFrame(), "mentors")
                                # セッションステートをクリア
                                st.session_state['matching_results'] = None
                                st.session_state['managers_results'] = None
                                # 受付停止
                                set_status(False) 
                                st.success("🧹 データをリセットし、受付を停止しました。")
                                time.sleep(1) # メッセージを読めるように少し待つ
                                st.rerun()

                else:
                    if password_input:
                        st.session_state['login_attempts'] += 1
                        time.sleep(3)
                        st.warning("パスワードが違います") 
                        attempts_left = 5 - st.session_state['login_attempts']
                        if attempts_left <= 0:
                            st.rerun()

            except Exception as e:
                st.warning("システムエラー: 設定を確認してください")
