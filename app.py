import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🛡️ 検索エンジン回避設定 (noindex)
# ==========================================
# これを書くことで、Googleなどの検索エンジンに「このページを登録しないで」と伝えます
st.markdown("""
    <meta name="robots" content="noindex, nofollow">
""", unsafe_allow_html=True)

# --- 設定と接続 ---
st.set_page_config(page_title="面談日程調整ツール", layout="wide")

# スプレッドシートへの接続関数（キャッシュして高速化）
@st.cache_resource
def get_spreadsheet():
    # secretsから認証情報を取得
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open_by_url(st.secrets["spreadsheet_url"])

# データの読み込み関数
def load_data_from_sheet(sheet_name):
    try:
        sh = get_spreadsheet()
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame() # エラー時は空のDFを返す

# データの保存関数（全書き換え方式：シンプルさ優先）
def save_data_to_sheet(df, sheet_name):
    sh = get_spreadsheet()
    worksheet = sh.worksheet(sheet_name)
    worksheet.clear() # 一旦クリア
    # ヘッダーとデータを書き込む
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# 定数：面談可能な時間枠
# --- 時間枠の自動生成（平日と土日で時間を変える） ---
TIME_SLOTS = []

# 1. 平日（月〜金）の設定
# ※ここは必要に応じて数字を変えてください（例: 17時から22時まで）
WEEKDAYS = ["月曜", "火曜", "水曜", "木曜", "金曜"]
WD_START = 20  # 平日の開始時間
WD_END = 23    # 平日の終了時間（22にすると 21:00-22:00 が最終枠）

for day in WEEKDAYS:
    for hour in range(WD_START, WD_END):
        TIME_SLOTS.append(f"{day} {hour}:00-{hour+1}:00")

# 2. 土日の設定（10時から23時まで）
WEEKENDS = ["土曜", "日曜"]
WE_START = 10  # 土日の開始時間
WE_END = 23    # 土日の終了時間（23にすると 22:00-23:00 が最終枠）

for day in WEEKENDS:
    for hour in range(WE_START, WE_END):
        TIME_SLOTS.append(f"{day} {hour}:00-{hour+1}:00")

st.title("📅 面談日程調整＆マッチングツール (Cloud版)")

# タブ設定
tab1, tab2, tab3 = st.tabs(["🏫 生徒用入力", "🎓 大学生用入力", "⚙️ 管理者・マッチング"])

# --- Tab 1: 生徒用 ---
with tab1:
    st.header("中高生用：希望調査")
    
    # ③ LINE追加への誘導
    st.info("まだ登録していない場合は、以下のリンクから公式LINEを追加してください。")
    # ※URLを書き換えてください
    st.markdown("### [👉 公式LINEを追加する](https://line.me/R/ti/p/@YOUR_LINE_ID)")
    
    st.write("---")
    st.write("以下のフォームに入力してください。※印は必須項目です")

    with st.form("student_form"):
        col1, col2 = st.columns(2)
        with col1:
            s_name = st.text_input("氏名（本名） ※")
            s_line_name = st.text_input("公式LINEでのあなたの名前（表示名） ※")
            s_school = st.text_input("学校名 ※")
        with col2:
            # index=None にすることで、最初は「未選択」状態にします
            s_grade = st.selectbox("学年 ※", ["中1", "中2", "中3", "高1", "高2", "高3"], index=None, placeholder="選択してください")
            s_stream = st.radio("文理選択 ※", ["文系", "理系", "未定"], index=None)
        
        st.write("---")
        st.subheader("メンターの希望")
        
        # ① 前回希望：チェックボックスからラジオボタンに変更（必須化のため）
        s_want_prev = st.radio("前回の担当者と同じ人を希望しますか？ ※", ["希望する", "希望しない"], index=None, horizontal=True)
        
        s_request_mentor = st.text_input("その他、担当してほしい東大生がいれば名前を書いてください")

        st.write("---")
        # ② 当日聞きたいこと
        s_questions = st.text_area("当日聞きたいことや相談したいことがあれば自由に書いてください")
        
        st.write("▼ **面談可能な**時間帯を選択（複数選択可） ※")
        s_available = st.multiselect("面談可能日時", TIME_SLOTS)

        if st.form_submit_button("送信"):
            # 必須項目のチェックリスト
            # ここに並べた変数が「空っぽ（未入力）」だったらエラーにします
            required_fields = {
                "氏名": s_name,
                "LINE名": s_line_name,
                "学校名": s_school,
                "学年": s_grade,
                "文理選択": s_stream,
                "前回希望の有無": s_want_prev,
                "面談可能日時": s_available
            }
            
            # 未入力があるかチェック
            missing_fields = [k for k, v in required_fields.items() if not v]
            
            if missing_fields:
                # エラー表示：何が足りないか具体的に教える
                st.error(f"以下の必須項目が入力されていません： {', '.join(missing_fields)}")
            else:
                # すべて入力されていたら保存処理へ
                df_s = load_data_from_sheet("students")
                
                new_row = {
                    "生徒氏名": s_name,
                    "LINE名": s_line_name,
                    "学校": s_school,
                    "学年": s_grade,
                    "文理": s_stream,
                    "前回希望": "あり" if s_want_prev == "希望する" else "なし", # ラジオボタンの値に合わせて調整
                    "指名希望": s_request_mentor,
                    "質問内容": s_questions,
                    "可能日時": ",".join(s_available)
                }
                
                if not df_s.empty and "生徒氏名" in df_s.columns:
                    df_s = df_s[df_s["生徒氏名"] != s_name]
                    df_s = pd.concat([df_s, pd.DataFrame([new_row])], ignore_index=True)
                else:
                    df_s = pd.DataFrame([new_row])
                
                save_data_to_sheet(df_s, "students")
                st.success(f"保存しました！ありがとうございます、{s_name}さん。")

# ==========================================
# Tab 2: 大学生用入力フォーム
# ==========================================
with tab2:
    st.header("大学生用：空きコマ登録フォーム")
    with st.form("mentor_form"):
        m_name = st.text_input("氏名（大学生）")
        st.write("▼ 対応可能な時間帯にチェックを入れてください")
        m_available = st.multiselect("対応可能日時", TIME_SLOTS)

        submitted_m = st.form_submit_button("登録")

        if submitted_m:
            if m_name and m_available:
                df_m = load_data_from_sheet("mentors")

                new_row = {
                    "メンター氏名": m_name,
                    "可能日時": ",".join(m_available)
                }

                if df_m.empty:
                    df_m = pd.DataFrame([new_row])
                else:
                    df_m = df_m[df_m["メンター氏名"] != m_name]
                    df_m = pd.concat([df_m, pd.DataFrame([new_row])], ignore_index=True)

                save_data_to_sheet(df_m, "mentors")
                st.success(f"{m_name} さんの予定をクラウドに登録しました！")
            else:
                st.error("氏名と日時を入力してください。")

# ==========================================
# Tab 3: 管理者・マッチング実行（セキュリティ保護）
# ==========================================
with tab3:
    st.header("管理者ダッシュボード")

    # Secretsからパスワードを取得
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

    password = st.text_input("管理者パスワードを入力してください", type="password")

    if password == ADMIN_PASSWORD:
        st.success("認証成功")

        col_a, col_b, col_c = st.columns(3)

        # データの読み込み
        df_students = load_data_from_sheet("students")
        df_mentors = load_data_from_sheet("mentors")
        df_history = load_data_from_sheet("history")

        with col_a:
            st.write("📋 登録生徒")
            st.dataframe(df_students)
        with col_b:
            st.write("📋 登録メンター")
            st.dataframe(df_mentors)
        with col_c:
            st.write("📜 履歴データ")
            st.dataframe(df_history)

        st.write("---")
        if st.button("🚀 自動マッチングを実行する"):
            if df_students.empty or df_mentors.empty:
                st.error("データが不足しています。")
            else:
                results = []
                mentor_schedule = {}

                # メンターデータの整形
                for index, row in df_mentors.iterrows():
                    slots = set(row["可能日時"].split(",")) if isinstance(row["可能日時"], str) else set()
                    mentor_schedule[row["メンター氏名"]] = slots

                # マッチング処理
                for index, s_row in df_students.iterrows():
                    s_name = s_row["生徒氏名"]
                    s_slots = set(s_row["可能日時"].split(",")) if isinstance(s_row["可能日時"], str) else set()
                    want_prev = (s_row["前回希望"] == "あり")

                    # 履歴検索
                    prev_mentor = None
                    if not df_history.empty and "生徒氏名" in df_history.columns:
                         hist_row = df_history[df_history["生徒氏名"] == s_name]
                         if not hist_row.empty:
                             prev_mentor = hist_row.iloc[0]["前回担当メンター"]

                    assigned_mentor = None
                    assigned_slot = None

                    candidate_mentors = list(mentor_schedule.keys())
                    # 前回希望の優先処理
                    if want_prev and prev_mentor in candidate_mentors:
                        candidate_mentors.remove(prev_mentor)
                        candidate_mentors.insert(0, prev_mentor)

                    for m_name in candidate_mentors:
                        m_slots = mentor_schedule[m_name]
                        common_slots = s_slots.intersection(m_slots)
                        if common_slots:
                            slot = list(common_slots)[0]
                            assigned_mentor = m_name
                            assigned_slot = slot
                            mentor_schedule[m_name].remove(slot)
                            break

                    results.append({
                        "生徒氏名": s_name,
                        "決定メンター": assigned_mentor,
                        "決定日時": assigned_slot,
                        "ステータス": "決定" if assigned_mentor else "未定",
                        "学校": s_row["学校"]
                    })

                df_results = pd.DataFrame(results)
                st.success("マッチング完了！")
                st.dataframe(df_results)

                csv = df_results.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 結果CSVダウンロード", csv, "matching_result.csv", "text/csv")

    elif password != "":
        st.error("パスワードが違います")
