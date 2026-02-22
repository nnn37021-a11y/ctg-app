import streamlit as st
import pandas as pd
import numpy as np
import re
from collections import Counter
import matplotlib.pyplot as plt
import matplotlib
import matplotlib.font_manager as fm

# フォント設定（Mac/Windows/Linux対応）
_jp_fonts = ["Hiragino Sans", "Hiragino Kaku Gothic Pro", "AppleGothic",
             "MS Gothic", "Yu Gothic", "IPAexGothic", "DejaVu Sans"]
_available = [f.name for f in fm.fontManager.ttflist]
for _font in _jp_fonts:
    if _font in _available:
        matplotlib.rcParams['font.family'] = _font
        break
matplotlib.rcParams["axes.unicode_minus"] = False #追加
st.set_page_config(page_title="臨床試験エクスプローラー", page_icon="🔬", layout="wide")

# =====================================================
# パスワード認証
# =====================================================
PASSWORD = "knot2000"

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown("## 🔬 臨床試験エクスプローラー")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔒 ログイン")
        pw = st.text_input("パスワードを入力してください", type="password", key="pw_input")
        if st.button("ログイン", use_container_width=True, type="primary"):
            if pw == PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが違います")
    return False

if not check_password():
    st.stop()

# =====================================================
# データ読み込み
# =====================================================
@st.cache_data
def load_data():
    df = pd.read_csv("ctg-studies-5.csv")
    df["Start Year"] = pd.to_datetime(df["Start Date"], errors="coerce").dt.year
    df["Start DT"] = pd.to_datetime(df["Start Date"], errors="coerce")
    df["End DT"] = pd.to_datetime(df["Completion Date"], errors="coerce")
    df["Duration (months)"] = ((df["End DT"] - df["Start DT"]).dt.days / 30.44).round(1)

    def extract_countries(loc):
        if pd.isna(loc): return []
        parts = loc.split("|")
        result = []
        for p in parts:
            segs = p.split(",")
            if len(segs) >= 2:
                result.append(segs[-1].strip())
        return result

    df["Countries"] = df["Locations"].apply(extract_countries)
    df["Country Count"] = df["Countries"].apply(len)
    df["Randomized"] = df["Study Design"].str.contains("RANDOMIZED", na=False)

    def get_masking(sd):
        if pd.isna(sd): return "不明"
        m = re.search(r"Masking:\s*([^|]+)", sd)
        return m.group(1).strip() if m else "不明"
    df["Masking"] = df["Study Design"].apply(get_masking)
    return df

df = load_data()

status_ja = {
    "COMPLETED": "完了", "UNKNOWN": "不明", "RECRUITING": "募集中",
    "ACTIVE_NOT_RECRUITING": "進行中（募集終了）", "TERMINATED": "中止",
    "NOT_YET_RECRUITING": "未開始", "WITHDRAWN": "撤回",
}

# =====================================================
# サイドバー
# =====================================================
st.sidebar.markdown("### 🔬 臨床試験エクスプローラー")
page = st.sidebar.radio(
    "ページ選択",
    ["🔍 検索・フィルタリング", "📊 ダッシュボード", "📋 試験詳細ビュー", "🎯 結果予測"]
)
st.sidebar.markdown("---")
st.sidebar.caption(f"データ件数: **{len(df):,} 件**")
if st.sidebar.button("🔓 ログアウト"):
    st.session_state.authenticated = False
    st.rerun()

# =====================================================
# PAGE 1: 検索・フィルタリング
# =====================================================
if page == "🔍 検索・フィルタリング":
    st.title("🔍 臨床試験 検索・フィルタリング")

    c1, c2, c3 = st.columns(3)
    with c1:
        status_opts = ["すべて"] + sorted(df["Study Status"].dropna().unique().tolist())
        status = st.selectbox("ステータス", status_opts,
            format_func=lambda x: status_ja.get(x, x) if x != "すべて" else "すべて")
    with c2:
        funder_opts = ["すべて"] + sorted(df["Funder Type"].dropna().unique().tolist())
        funder = st.selectbox("資金提供者", funder_opts)
    with c3:
        result_opts = ["すべて", "YES（公開済み）", "NO（未公開）"]
        result_f = st.selectbox("結果公開", result_opts)

    keyword = st.text_input("🔎 キーワード検索（タイトル・概要）")
    enroll_min, enroll_max = st.slider(
        "登録患者数",
        int(df["Enrollment"].min()), int(df["Enrollment"].max()),
        (int(df["Enrollment"].min()), int(df["Enrollment"].max()))
    )

    filtered = df.copy()
    if status != "すべて":
        filtered = filtered[filtered["Study Status"] == status]
    if funder != "すべて":
        filtered = filtered[filtered["Funder Type"] == funder]
    if result_f == "YES（公開済み）":
        filtered = filtered[filtered["Study Results"] == "YES"]
    elif result_f == "NO（未公開）":
        filtered = filtered[filtered["Study Results"] == "NO"]
    if keyword:
        mask = (
            filtered["Study Title"].str.contains(keyword, case=False, na=False) |
            filtered["Brief Summary"].str.contains(keyword, case=False, na=False)
        )
        filtered = filtered[mask]
    filtered = filtered[
        (filtered["Enrollment"] >= enroll_min) &
        (filtered["Enrollment"] <= enroll_max)
    ]

    st.markdown(f"**該当件数: {len(filtered):,} 件**")
    show_cols = ["NCT Number", "Study Title", "Study Status", "Study Results", "Enrollment", "Sponsor", "Start Date"]
    display = filtered[show_cols].copy()
    display["Study Status"] = display["Study Status"].map(status_ja).fillna(display["Study Status"])
    display.columns = ["NCT番号", "試験タイトル", "ステータス", "結果公開", "患者数", "スポンサー", "開始日"]
    st.dataframe(display.reset_index(drop=True), use_container_width=True, height=450)
    csv = filtered[show_cols].to_csv(index=False, encoding="utf-8-sig")
    st.download_button("📥 CSVダウンロード", csv, "filtered_trials.csv", "text/csv")

# =====================================================
# PAGE 2: ダッシュボード
# =====================================================
elif page == "📊 ダッシュボード":
    st.title("📊 ダッシュボード")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("総試験数", f"{len(df):,}")
    k2.metric("完了済み", f"{(df['Study Status']=='COMPLETED').sum():,}")
    k3.metric("結果公開済み", f"{(df['Study Results']=='YES').sum():,}")
    k4.metric("平均登録患者数", f"{int(df['Enrollment'].mean()):,}")

    st.markdown("---")
    r1c1, r1c2 = st.columns(2)

    with r1c1:
        st.subheader("試験ステータス分布")
        sc = df["Study Status"].value_counts()
        sc.index = [status_ja.get(i, i) for i in sc.index]
        colors = ["#e11d48","#f97316","#eab308","#22c55e","#3b82f6","#8b5cf6","#6b7280"]
        fig, ax = plt.subplots(figsize=(5, 4))
        wedges, texts, autotexts = ax.pie(
            sc.values, labels=sc.index, autopct="%1.1f%%",
            colors=colors[:len(sc)], startangle=90)
        for t in texts: t.set_fontsize(8)
        for t in autotexts: t.set_fontsize(7)
        plt.tight_layout()
        st.pyplot(fig); plt.close()

    with r1c2:
        st.subheader("年別試験開始数")
        yc = df["Start Year"].dropna().astype(int).value_counts().sort_index()
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.bar(yc.index, yc.values, color="#e11d48", edgecolor="white")
        ax.set_xlabel("Year"); ax.set_ylabel("件数")
        ax.tick_params(axis="x", rotation=45)
        plt.tight_layout()
        st.pyplot(fig); plt.close()

    r2c1, r2c2 = st.columns(2)

    with r2c1:
        st.subheader("国別試験数 Top 10")
        all_c = []
        for cl in df["Countries"]: all_c.extend(cl)
        cc = Counter(all_c).most_common(10)
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.barh([c[0] for c in cc][::-1], [c[1] for c in cc][::-1], color="#3b82f6")
        ax.set_xlabel("件数")
        plt.tight_layout()
        st.pyplot(fig); plt.close()

    with r2c2:
        st.subheader("資金提供者タイプ")
        fc = df["Funder Type"].value_counts()
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.bar(fc.index, fc.values, color="#8b5cf6", edgecolor="white")
        ax.set_ylabel("件数"); ax.tick_params(axis="x", rotation=20)
        plt.tight_layout()
        st.pyplot(fig); plt.close()

    st.markdown("---")
    st.subheader("登録患者数の分布")
    fig, ax = plt.subplots(figsize=(10, 3))
    ed = df["Enrollment"].dropna()
    ed = ed[ed < ed.quantile(0.95)]
    ax.hist(ed, bins=40, color="#22c55e", edgecolor="white")
    ax.set_xlabel("登録患者数"); ax.set_ylabel("件数")
    plt.tight_layout()
    st.pyplot(fig); plt.close()

# =====================================================
# PAGE 3: 試験詳細ビュー
# =====================================================
elif page == "📋 試験詳細ビュー":
    st.title("📋 試験詳細ビュー")

    selected_nct = st.selectbox(
        "試験を選択してください",
        df["NCT Number"].tolist(),
        format_func=lambda x: f"{x}｜{df[df['NCT Number']==x]['Study Title'].values[0][:55]}..."
    )

    if selected_nct:
        row = df[df["NCT Number"] == selected_nct].iloc[0]
        st.markdown(f"## {row['Study Title']}")
        st.markdown(f"🔗 [ClinicalTrials.govで開く]({row['Study URL']})")
        st.markdown("---")

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("ステータス", status_ja.get(row["Study Status"], row["Study Status"]))
        k2.metric("登録患者数", f"{row['Enrollment']:,}")
        k3.metric("結果公開", row["Study Results"])
        k4.metric("フェーズ", row["Phases"])

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("📌 基本情報")
            st.markdown(f"**NCT番号:** {row['NCT Number']}")
            st.markdown(f"**スポンサー:** {row['Sponsor']}")
            st.markdown(f"**資金提供者:** {row['Funder Type']}")
            st.markdown(f"**開始日:** {row['Start Date']}")
            st.markdown(f"**完了日:** {row['Completion Date']}")
            dur = row['Duration (months)']
            if not pd.isna(dur):
                st.markdown(f"**試験期間:** 約 {dur:.0f} ヶ月")
            st.markdown(f"**無作為化:** {'あり' if row['Randomized'] else 'なし'}")
            st.markdown(f"**マスキング:** {row['Masking']}")
        with c2:
            st.subheader("🏥 試験設計")
            st.markdown(f"**対象疾患:** {row['Conditions']}")
            st.markdown(f"**対象者:** {row['Age']} / {row['Sex']}")
            if not pd.isna(row.get('Collaborators')):
                st.markdown(f"**共同研究機関:** {row['Collaborators']}")
            st.markdown(f"**参加国数:** {row['Country Count']} カ国")

        st.markdown("---")
        st.subheader("📝 試験概要")
        st.info(row["Brief Summary"])
        st.subheader("🎯 主要評価項目")
        st.write(row["Primary Outcome Measures"])
        if not pd.isna(row.get("Secondary Outcome Measures")):
            st.subheader("📊 副次評価項目")
            st.write(row["Secondary Outcome Measures"])
        st.subheader("💉 介入方法")
        st.write(row["Interventions"])

# =====================================================
# PAGE 4: 結果予測
# =====================================================
elif page == "🎯 結果予測":
    st.title("🎯 試験結果公開予測（機械学習）")
    st.caption("Study Results（結果公開済みか）をLightGBMで予測します")

    @st.cache_resource
    def train_model():
        import lightgbm as lgb
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import roc_auc_score, accuracy_score
        from sklearn.preprocessing import LabelEncoder

        df2 = df.copy()
        df2["target"] = (df2["Study Results"] == "YES").astype(int)
        df2["log_enrollment"] = np.log1p(df2["Enrollment"])
        df2["duration"] = df2["Duration (months)"].fillna(df2["Duration (months)"].median())
        df2["country_count"] = df2["Country Count"]
        df2["has_collaborator"] = df2["Collaborators"].notna().astype(int)
        df2["start_year"] = df2["Start Year"].fillna(2015)

        cat_features = ["Study Status", "Funder Type", "Phases", "Randomized"]
        le_dict = {}
        for col in cat_features:
            le = LabelEncoder()
            df2[col + "_enc"] = le.fit_transform(df2[col].astype(str))
            le_dict[col] = le

        feature_cols = ["log_enrollment", "duration", "country_count",
                        "has_collaborator", "start_year"] + [c + "_enc" for c in cat_features]
        X = df2[feature_cols]
        y = df2["target"]
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)
        model = lgb.LGBMClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            num_leaves=15, class_weight="balanced", random_state=42, verbose=-1)
        model.fit(X_train, y_train)
        y_prob = model.predict_proba(X_test)[:, 1]
        y_pred = model.predict(X_test)
        metrics = {
            "auc": roc_auc_score(y_test, y_prob),
            "accuracy": accuracy_score(y_test, y_pred),
        }
        return model, feature_cols, le_dict, metrics

    with st.spinner("モデルを学習中..."):
        model, feature_cols, le_dict, metrics = train_model()

    c1, c2 = st.columns(2)
    c1.metric("AUC", f"{metrics['auc']:.4f}")
    c2.metric("Accuracy", f"{metrics['accuracy']:.4f}")
    st.info("⚠️ データが401件と少ないため、精度は参考値です。")

    st.markdown("---")
    st.subheader("個別予測")
    col1, col2 = st.columns(2)
    with col1:
        enrollment = st.number_input("登録患者数", 10, 10000, 200)
        duration = st.number_input("試験期間（月）", 1, 200, 48)
        country_count = st.slider("参加国数", 1, 50, 5)
        has_collab = st.selectbox("共同研究機関", [1, 0], format_func=lambda x: "あり" if x else "なし")
        start_year = st.slider("開始年", 2000, 2025, 2015)
    with col2:
        status = st.selectbox("ステータス", df["Study Status"].dropna().unique().tolist(),
            format_func=lambda x: status_ja.get(x, x))
        funder = st.selectbox("資金提供者", df["Funder Type"].dropna().unique().tolist())
        phase = st.selectbox("フェーズ", df["Phases"].dropna().unique().tolist())
        randomized = st.selectbox("無作為化", [True, False], format_func=lambda x: "あり" if x else "なし")

    if st.button("🎯 予測する", type="primary", use_container_width=True):
        input_dict = {
            "log_enrollment": np.log1p(enrollment),
            "duration": duration,
            "country_count": country_count,
            "has_collaborator": has_collab,
            "start_year": start_year,
            "Study Status_enc": le_dict["Study Status"].transform([status])[0] if status in le_dict["Study Status"].classes_ else 0,
            "Funder Type_enc": le_dict["Funder Type"].transform([funder])[0] if funder in le_dict["Funder Type"].classes_ else 0,
            "Phases_enc": le_dict["Phases"].transform([phase])[0] if phase in le_dict["Phases"].classes_ else 0,
            "Randomized_enc": le_dict["Randomized"].transform([str(randomized)])[0] if str(randomized) in le_dict["Randomized"].classes_ else 0,
        }
        input_df = pd.DataFrame([input_dict])
        prob = model.predict_proba(input_df)[0][1]
        if prob >= 0.5:
            st.success(f"✅ 結果が公開される可能性が高い（{prob*100:.1f}%）")
        else:
            st.warning(f"⚠️ 結果が未公開のままになる可能性が高い（{prob*100:.1f}%）")
        st.progress(float(prob))

    st.markdown("---")
    st.subheader("特徴量の重要度")
    imp = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=True)
    feat_labels = {
        "log_enrollment": "登録患者数（対数）", "duration": "試験期間（月）",
        "country_count": "参加国数", "has_collaborator": "共同研究機関あり",
        "start_year": "開始年", "Study Status_enc": "ステータス",
        "Funder Type_enc": "資金提供者", "Phases_enc": "フェーズ", "Randomized_enc": "無作為化",
    }
    imp.index = [feat_labels.get(i, i) for i in imp.index]
    fig, ax = plt.subplots(figsize=(8, 4))
    imp.plot(kind="barh", ax=ax, color="#e11d48")
    ax.set_xlabel("重要度")
    plt.tight_layout()
    st.pyplot(fig); plt.close()
