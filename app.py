import streamlit as st
import pandas as pd
import datetime
import io
import re

# 1. ページの設定
st.set_page_config(page_title="園児登降園管理アプリ", layout="wide")

# ==========================================
# 🔒 セキュリティ対策：簡易パスワード認証機能
# ==========================================
def check_password():
    """正しいパスワードが入力されたら True を返す"""
    def password_entered():
        if st.session_state["password"] == "nishihara1204":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("パスワードを入力してください", type="password", on_change=password_entered, key="password")
        st.info("※このアプリは関係者以外アクセスできません。")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("パスワードを入力してください", type="password", on_change=password_entered, key="password")
        st.error("❌ パスワードが違います。")
        return False
    else:
        return True

# 日本の祝日（2026年版）簡易リスト
def get_holidays_2026():
    return {
        datetime.date(2026, 1, 1), datetime.date(2026, 1, 2), datetime.date(2026, 1, 3), # 元日・正月休み
        datetime.date(2026, 1, 12), datetime.date(2026, 2, 11), datetime.date(2026, 2, 23),
        datetime.date(2026, 3, 20), datetime.date(2026, 4, 29), datetime.date(2026, 5, 3),
        datetime.date(2026, 5, 4), datetime.date(2026, 5, 5), datetime.date(2026, 5, 6),
        datetime.date(2026, 7, 20), datetime.date(2026, 8, 11), datetime.date(2026, 9, 21),
        datetime.date(2026, 9, 22), datetime.date(2026, 9, 23), datetime.date(2026, 10, 12),
        datetime.date(2026, 11, 3), datetime.date(2026, 11, 23), datetime.date(2026, 12, 23)
    }

# ファイル名から「月」を特定し、平日と土曜日の日数を計算する関数（急な休みにも対応）
def calculate_opening_days(filename, custom_holidays):
    match = re.search(r'(\d+)月', filename)
    if not match:
        return 20, 24, 4
    
    month = int(match.group(1))
    year = 2026
    
    # 標準の祝日に、画面で入力された「急な休み」を合体させる
    holidays = get_holidays_2026()
    if custom_holidays:
        for ch in custom_holidays:
            holidays.add(ch)
    
    weekday_count = 0
    saturday_count = 0
    
    if month == 12:
        next_month = datetime.date(year + 1, 1, 1)
    else:
        next_month = datetime.date(year, month + 1, 1)
    last_day = (next_month - datetime.timedelta(days=1)).day
    
    for day in range(1, last_day + 1):
        d = datetime.date(year, month, day)
        if d in holidays:
            continue
            
        weekday = d.weekday()
        if weekday < 5: # 月〜金
            weekday_count += 1
        elif weekday == 5: # 土
            saturday_count += 1
            
    total_with_sat = weekday_count + saturday_count
    return weekday_count, total_with_sat, month


if check_password():
    if st.sidebar.button("🔒 ログアウト"):
        del st.session_state["password_correct"]
        st.rerun()

    st.title("📛 園児 登降園データ自動集計アプリ")
    st.write("登園時間と降園時間のCSVファイルをアップロードするだけで、日数・登園率・滞在時間を自動計算します。")

    # メイン画面：ファイルアップロード
    col1, col2 = st.columns(2)
    with col1:
        toen_file = st.file_uploader("① 登園時間のCSVファイルを選択", type=["csv"])
    with col2:
        koen_file = st.file_uploader("② 降園時間のCSVファイルを選択", type=["csv"])

    # CSVを安全に読み込むための補助関数
    def load_csv_safely(uploaded_file):
        if uploaded_file is None:
            return None
        encodings = ["utf-8-sig", "shift_jis", "utf-8", "cp932"]
        for enc in encodings:
            try:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding=enc)
                if not df.empty:
                    return df
            except Exception:
                continue
        return None

    # 4. データ処理と集計
    if toen_file and koen_file:
        toen_df = load_csv_safely(toen_file)
        koen_df = load_csv_safely(koen_file)
        
        if toen_df is not None and koen_df is not None:
            
            # --- 📅 開園日数の自動計算と選択機能 ---
            st.sidebar.header("⚙️ 開園日数の設定")
            
            # 📁 ファイル名から数字（月）を仮抽出
            match_m = re.search(r'(\d+)月', toen_file.name)
            current_month = int(match_m.group(1)) if match_m else 4
            
            # 🚨 急な休み（独自の休園日）を入れるカレンダーをサイドバーに設置
            st.sidebar.subheader("臨時休園日の追加")
            custom_holidays = st.sidebar.date_input(
                "急な休み・独自の休園日があれば選択してください（複数選択可）",
                value=[],
                min_value=datetime.date(2026, current_month, 1),
                max_value=datetime.date(2026, current_month, 28 if current_month==2 else 30 if current_month in [4,6,9,11] else 31),
                help="カレンダーから日付を選ぶと、自動計算の開園日数から引かれます。"
            )
            
            # ファイル名と急な休みを考慮して自動計算
            auto_heijitsu, auto_tubo, target_month = calculate_opening_days(toen_file.name, custom_holidays)
            
            st.sidebar.info(f"📁 ファイルから【{target_month}月】のデータと判定しました。")
            
            # ラジオボタンで選択
            day_option = st.sidebar.radio(
                "集計に使う開園日数を選んでください：",
                (f"平日のみ（{auto_heijitsu}日間）", f"土曜日を含む（{auto_tubo}日間）", "手動で入力する")
            )
            
            if "平日のみ" in day_option:
                kaien_days = auto_heijitsu
            elif "土曜日を含む" in day_option:
                kaien_days = auto_tubo
            else:
                kaien_days = st.sidebar.number_input("手動入力（日）", min_value=1, max_value=31, value=20)
                
            st.success(f"両方のファイルが読み込まれました！現在【開園日数：{kaien_days}日】で集計しています。")
            
            # データの整形
            toen_df = toen_df.replace({r'^\s*$': None}, regex=True)
            koen_df = koen_df.replace({r'^\s*$': None}, regex=True)
            
            date_cols = [c for c in toen_df.columns if "日" in c]
            
            if len(date_cols) == 0:
                st.error("CSVファイルから「1日」「2日」などの日付の列が見つかりませんでした。")
            else:
                required_cols = ["児童氏名（漢字）", "児童氏名（カナ）", "生年月日", "クラス年齢", "保育必要量"]
                available_cols = [c for c in required_cols if c in toen_df.columns]
                base_info = toen_df[available_cols].copy()
                
                # --- ① 登園日数・登園率の計算 ---
                attendance_df = base_info.copy()
                attendance_df["開園日数"] = kaien_days
                attendance_df["登園日数"] = toen_df[date_cols].notna().sum(axis=1)
                attendance_df["登園率"] = (attendance_df["登園日数"] / kaien_days).apply(lambda x: f"{x * 100:.1f}%")
                
                # --- ② 滞在時間の計算 ---
                stay_time_df = base_info.copy()
                total_minutes_list = [0] * len(stay_time_df)
                
                for col in date_cols:
                    t_in = pd.to_datetime(toen_df[col], format="%H:%M", errors="coerce")
                    t_out = pd.to_datetime(koen_df[col], format="%H:%M", errors="coerce")
                    diff = t_out - t_in
                    
                    formatted_days = []
                    for i, delta in enumerate(diff):
                        if pd.isna(delta) or delta.total_seconds() < 0:
                            formatted_days.append("")
                        else:
                            minutes = int(delta.total_seconds() // 60)
                            total_minutes_list[i] += minutes
                            
                            hours = minutes // 60
                            mins = minutes % 60
                            formatted_days.append(f"{hours}:{mins:02d}")
                            
                    stay_time_df[col] = formatted_days
                
                total_time_strings = []
                for total_mins in total_minutes_list:
                    if total_mins == 0:
                        total_time_strings.append("0:00")
                    else:
                        hours = total_mins // 60
                        mins = total_mins % 60
                        total_time_strings.append(f"{hours}:{mins:02d}")
                
                stay_time_df.insert(len(available_cols), "総合計時間", total_time_strings)
                
                # --- 5. 画面への結果表示 ---
                tab1, tab2 = st.tabs(["📊 登園日数・登園率", "⏱️ 日別滞在時間"])
                
                with tab1:
                    st.subheader("園児ごとの登園状況")
                    st.dataframe(attendance_df, use_container_width=True)
                    
                with tab2:
                    st.subheader("日別滞在時間（時間:分）")
                    st.write("💡「総合計時間」列に、1ヶ月の合計滞在時間が表示されています。")
                    st.dataframe(stay_time_df, use_container_width=True)
                    
                # --- 6. Excelダウンロード機能 ---
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    attendance_df.to_excel(writer, sheet_name="登園日数・登園率", index=False)
                    stay_time_df.to_excel(writer, sheet_name="日別滞在時間", index=False)
                
                st.sidebar.markdown("---")
                st.sidebar.header("📥 結果をエクスポート")
                st.sidebar.download_button(
                    label="Excelファイルとしてダウンロード",
                    data=buffer.getvalue(),
                    file_name=f"登降園集計結果_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.error("ファイルの読み込みに失敗しました。")
    else:
        st.info("左側のアップロード欄から、CSVファイルをそれぞれ選択してください。")