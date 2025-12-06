import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 🛡️ 1. 基本設定・検索除け
# ==========================================
st.set_page_config(page_title="ALOHA面談日程調整ツール", layout="wide")

# 検索エンジンにインデックスさせない設定 (noindex)
st.markdown("""
    <meta name="robots" content="noindex, nofollow">
""", unsafe_allow_html=True)

# ==========================================
# 📅 2. 時間枠の自動生成（平日・休日対応）
# ==========================================
TIME_SLOTS = []

# 平日（月〜金）：17:00 〜 22:00（終了）
WEEKDAYS = ["月曜", "火曜", "水曜", "木曜", "金曜"]
WD_START = 17
WD_END = 22 # 21:00-22:00が最終枠

for day in WEEKDAYS:
    for hour in range(WD_START, WD_END):
        TIME_SLOTS.append(f"{day} {hour}:00-{hour+1}:00")

# 土日（土・日）：10:00 〜 23:00（終了）
WEEKENDS = ["土曜", "日曜"]
WE_START = 10
WE_END = 23 # 22:00-23:00が最終枠

for day in WEEKENDS:
    for hour in range(WE_START, WE_END):
        TIME_SLOTS.append(f"{day} {hour}:00-{hour+1}:00")

# ==========================================
# ☁️ 3. Googleスプレッドシート連携
# ==========================================
@st.cache_resource
def get_spreadsheet():
    # secrets.toml から認証情報を読み込む
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
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
    # カラム名とデータを書き込む
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# ==========================================
# 🖥️ 4. アプリ画面構成
# ==========================================
st.title("📅 面談日程調整＆マッチングツール")

tab1, tab2, tab3 = st.tabs(["🏫 生徒用入力", "🎓 大学生用入力", "⚙️ 管理者専用"])

# --- Tab 1: 生徒用 ---
with tab1:
    st.header("中高生用：希望調査")
    
    # LINE追加への誘導
    st.info("まだ登録していない場合は、以下のリンクから公式LINEを追加してください。")
    # ※以下のURLをあなたの公式LINEのURLに書き換えてください
    st.markdown("### [👉 公式LINEを追加する](https://lin.ee/fhVvKJa)")
    
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
        st.subheader("東大生の希望（氏名のみ）　※〇〇な人という場合は、下の自由記述欄へ！")
        
        # 前回希望：チェックボックスからラジオボタンに変更（必須化のため）
        s_want_prev = st.radio("前回の担当者と同じ人を希望しますか？ ※", ["希望する", "希望しない"], index=None, horizontal=True)
        
        s_request_mentor = st.text_input("その他、担当してほしい東大生がいれば名前を書いてください")

        st.write("---")
        # 当日聞きたいこと
        s_questions = st.text_area("当日聞きたいことや相談したいことがあれば自由に書いてください")
        
        st.write("▼ **面談可能な**時間帯を選択（複数選択可） ※")
        s_available = st.multiselect("面談可能日時", TIME_SLOTS)

        if st.form_submit_button("送信"):
            # 必須項目のチェックリスト
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
                    "前回希望": "あり" if s_want_prev == "希望する" else "なし",
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

# --- Tab 2: 大学生用 ---
with tab2:
    st.header("大学生用：空きコマ登録")
    st.write("ご協力ありがとうございます。自身の属性と空き時間を入力してください。")
    
    with st.form("mentor_form"):
        m_name = st.text_input("氏名（大学生） ※")
        
        # 文理選択（複数回答可）
        st.write("▼ 受験時の文理を選択してください（両方対応可能な場合は複数選択可） ※")
        m_stream = st.multiselect("文理選択", ["文系", "理系"])
        
        st.write("---")
        st.write("▼ 対応可能な時間帯を選択 ※")
        m_available = st.multiselect("対応可能日時", TIME_SLOTS)
        
        if st.form_submit_button("登録"):
            if m_name and m_available and m_stream:
                df_m = load_data_from_sheet("mentors")
                
                new_row = {
                    "メンター氏名": m_name,
                    "文理": ",".join(m_stream), # リストを文字列にして保存
                    "可能日時": ",".join(m_available)
                }
                
                if not df_m.empty and "メンター氏名" in df_m.columns:
                    df_m = df_m[df_m["メンター氏名"] != m_name]
                    df_m = pd.concat([df_m, pd.DataFrame([new_row])], ignore_index=True)
                else:
                    df_m = pd.DataFrame([new_row])
                
                save_data_to_sheet(df_m, "mentors")
                st.success(f"登録しました！ありがとうございます、{m_name}さん。")
            else:
                st.error("「氏名」「文理」「日時」はすべて必須です。")

# --- Tab 3: 管理者用 ---
with tab3:
    st.header("🔒 管理者ダッシュボード")
    
    # パスワード認証
    password = st.text_input("管理者パスワード", type="password")
    
    # Secretsからパスワードを取得
    if password == st.secrets["ADMIN_PASSWORD"]:
        st.success("認証成功")
        
        # データ読み込み
        df_students = load_data_from_sheet("students")
        df_mentors = load_data_from_sheet("mentors")
        df_history = load_data_from_sheet("history")
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.write("📋 生徒データ")
            st.dataframe(df_students)
        with col_b:
            st.write("📋 メンターデータ")
            st.dataframe(df_mentors)
        with col_c:
            st.write("📜 履歴データ")
            st.dataframe(df_history)

        st.write("---")
        if st.button("🚀 自動マッチングを実行"):
            if df_students.empty or df_mentors.empty:
                st.error("データが不足しています。")
            else:
                results = []
                mentor_schedule = {} 
                mentor_streams = {}  
                
                # メンターデータの展開
                for _, row in df_mentors.iterrows():
                    m_name = row["メンター氏名"]
                    slots = set(row["可能日時"].split(",")) if row["可能日時"] else set()
                    mentor_schedule[m_name] = slots
                    
                    streams = row["文理"].split(",") if "文理" in row and row["文理"] else []
                    mentor_streams[m_name] = streams

                # 生徒ごとのマッチング処理
                for _, s_row in df_students.iterrows():
                    s_name = s_row["生徒氏名"]
                    s_stream = s_row["文理"] # 生徒の文理
                    s_slots = set(s_row["可能日時"].split(",")) if s_row["可能日時"] else set()
                    want_prev = (s_row["前回希望"] == "あり")
                    
                    # 履歴確認
                    prev_mentor = None
                    if not df_history.empty and "生徒氏名" in df_history.columns:
                        hist = df_history[df_history["生徒氏名"] == s_name]
                        if not hist.empty:
                            prev_mentor = hist.iloc[0]["前回担当メンター"]

                    assigned_mentor = None
                    assigned_slot = None
                    
                    # 候補者リスト作成
                    candidates = list(mentor_schedule.keys())
                    
                    # 前回希望があれば優先的に先頭へ
                    if want_prev and prev_mentor in candidates:
                        candidates.remove(prev_mentor)
                        candidates.insert(0, prev_mentor)

                    # メンターを一人ずつチェック
                    for m_name in candidates:
                        # --- 文理チェック ---
                        m_streams_list = mentor_streams.get(m_name, [])
                        
                        # 生徒が「未定」以外で、メンターがその属性を持っていないならスキップ
                        if s_stream != "未定" and s_stream not in m_streams_list:
                            continue 
                        # ------------------

                        # 時間の共通部分を探す
                        common = s_slots.intersection(mentor_schedule[m_name])
                        if common:
                            slot = list(common)[0] # 最初の候補を採用
                            assigned_mentor = m_name
                            assigned_slot = slot
                            mentor_schedule[m_name].remove(slot) # 枠を消費
                            break
                    
                    results.append({
                        "生徒氏名": s_name,
                        "決定メンター": assigned_mentor,
                        "決定日時": assigned_slot,
                        "ステータス": "決定" if assigned_mentor else "未定",
                        "学校": s_row["学校"],
                        "生徒文理": s_stream,
                        "メンター文理": ",".join(mentor_streams.get(assigned_mentor, [])) if assigned_mentor else ""
                    })

                df_res = pd.DataFrame(results)
                st.dataframe(df_res)
                
                csv = df_res.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 結果をCSVでダウンロード", csv, "matching_result.csv", "text/csv")
    
    elif password:
        st.error("パスワードが違います")
