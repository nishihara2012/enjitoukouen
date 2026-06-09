import streamlit as st
import pandas as pd
import datetime
import io

# 1. ページの設定
st.set_page_config(page_title="園児登降園管理アプリ", layout="wide")

# ==========================================
# 🔒 セキュリティ対策：簡易パスワード認証機能
# ==========================================
def check_password():
    """正しいパスワードが入力されたら True を返す"""
    def password_entered():
        """入力されたパスワードが正しいかチェック"""
        # 園で決めたパスワードを設定（例: "enmu2026"）
        if st.session_state["password"] == "enmu2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # セキュリティのため入力欄から消す
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # まだパスワードを入力していない状態
        st.text_input(
            "パスワードを入力してください", type="password", on_change=password_entered, key="password"
        )
        st.info("※このアプリは関係者以外アクセスできません。")
        return False
    elif not st.session_state["password_correct"]:
        # パスワードが間違っている状態
        st.text_input(
            "パスワードを入力してください", type="password", on_change=password_entered, key="password"
        )
        st.error("❌ パスワードが違います。")
        return False
    else:
        # パスワードが合っている状態
        return True

# パスワードチェックが通った場合のみ、以下の本編アプリを動かす
if check_password():

    # ログアウトボタンを右上に配置（安全のため）
    if st.sidebar.button("🔒 ログアウト"):
        del st.session_state["password_correct"]
        st.rerun()

    st.title("📛 園児 登降園データ自動集計アプリ")
    st.write("登園時間と降園時間のCSVファイルをアップロードするだけで、日数・登園率・滞在時間を自動計算します。")

    # 2. サイドバーの設定（条件入力）
    st.sidebar.header("⚙️ 設定")
    kaien_days = st.sidebar.number_input("今月の総開園日数（日）", min_value=1, max_value=31, value=20)

    # 3. メイン画面：ファイルアップロード
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
            st.success("両方のファイルが読み込まれました！集計中...")
            
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
                
                # 総合計時間を分単位で蓄積するためのリスト
                total_minutes_list = [0] * len(stay_time_df)
                
                for col in date_cols:
                    t_in = pd.to_datetime(toen_df[col], format="%H:%M", errors="coerce")
                    t_out = pd.to_datetime(koen_df[col], format="%H:%M", errors="coerce")
                    diff = t_out - t_in
                    
                    # 各日の時間を「H:MM」形式の文字列にしつつ、合計用の分を計算
                    formatted_days = []
                    for i, delta in enumerate(diff):
                        if pd.isna(delta) or delta.total_seconds() < 0:
                            formatted_days.append("")
                        else:
                            minutes = int(delta.total_seconds() // 60)
                            total_minutes_list[i] += minutes # 総合計用に分を足す
                            
                            hours = minutes // 60
                            mins = minutes % 60
                            formatted_days.append(f"{hours}:{mins:02d}")
                            
                    stay_time_df[col] = formatted_days
                
                # 蓄積した合計分数を「〇時間〇分」の文字にして、表の左側（基本情報の直後）に差し込む
                total_time_strings = []
                for total_mins in total_minutes_list:
                    if total_mins == 0:
                        total_time_strings.append("0:00")
                    else:
                        hours = total_mins // 60
                        mins = total_mins % 60
                        total_time_strings.append(f"{hours}:{mins:02d}")
                
                # 「総合計時間」という列名で、基本情報のすぐ後ろに挿入
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