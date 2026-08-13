import re
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="사카타코리아 - LOT재고상세현황", layout="wide"
)

st.title("🌱 SAKATA KOREA 스마트 LOT 재고통합 시스템")

uploaded_file = st.file_uploader(
    "📁 ERP 엑셀 파일(.xlsx)을 업로드하세요", type=["xlsx", "xls"]
)

if uploaded_file:
    df = pd.read_excel(uploaded_file, header=1)


    def clean_spec(spec):
        if pd.isna(spec):
            return ""
        return re.sub(r"\s+\d+/\d+$", "", str(spec).strip())


    # 컬럼 자동 매핑
    def get_col(possible_names, default_idx):
        for name in possible_names:
            if name in df.columns:
                return name
        if len(df.columns) > default_idx:
            return df.columns[default_idx]
        return None


    col_item = get_col(["NM_ITEM", "품목명", "품명"], 1)
    col_spec = get_col(["STND_ITEM", "규격"], 2)
    col_lot = get_col(["NO_LOT", "LOT번호", "Lot번호"], 5)
    col_sl = get_col(["NM_SL", "창고명"], 6)
    col_qty = get_col(["재고량"], 9)
    col_loc = get_col(["CD_MNG4", "위치"], 10)
    col_clean = get_col(["CD_MNG5", "정선내역"], 12)
    col_proc = get_col(["CD_MNG6", "가공내역"], 13)
    col_mng = get_col(["CD_MNG8", "재고명세"], 14)
    col_note = get_col(["CD_MNG10", "특이사항"], 15)
    col_mng13 = get_col(["CD_MNG13", "관리항목13", "생산년도"], 16)
    col_mng14 = get_col(["CD_MNG14", "관리항목14", "발아"], 17)
    col_mng15 = get_col(["CD_MNG15", "관리항목15", "순도"], 18)

    df["재고명세_그룹키"] = df[col_mng].apply(clean_spec) if col_mng else ""

    group_cols = [col_item, col_lot, "재고명세_그룹키"]
    agg_dict = {col_qty: "sum"}

    other_cols = [
        col_spec,
        col_sl,
        col_loc,
        col_clean,
        col_proc,
        col_note,
        col_mng13,
        col_mng14,
        col_mng15,
    ]
    for c in other_cols:
        if c and c in df.columns and c not in group_cols:
            agg_dict[c] = "first"

    grouped = df.groupby(group_cols, as_index=False).agg(agg_dict)

    # 컬럼명 변경
    rename_dict = {
        col_item: "품명",
        col_spec: "규격",
        col_lot: "Lot번호",
        col_sl: "창고명",
        col_qty: "재고량(kg)",
        col_loc: "위치",
        col_clean: "정선내역",
        col_proc: "가공내역",
        "재고명세_그룹키": "재고명세",
        col_note: "특이사항",
        col_mng13: "생산년도",
        col_mng14: "발아",
        col_mng15: "순도",
    }
    grouped = grouped.rename(columns=rename_dict)

    # 필터 검색 영역
    col1, col2 = st.columns(2)
    with col1:
        search_item = st.text_input("🔍 품명 검색")
    with col2:
        search_lot = st.text_input("🔍 Lot번호 검색")

    filtered_df = grouped.copy()
    if search_item:
        filtered_df = filtered_df[
            filtered_df["품명"].str.contains(search_item, case=False, na=False)
        ]
    if search_lot:
        filtered_df = filtered_df[
            filtered_df["Lot번호"].str.contains(
                search_lot, case=False, na=False
            )
        ]

    st.write(f"총 **{len(filtered_df)}**건의 데이터가 조회되었습니다.")
    st.dataframe(filtered_df, use_container_width=True, height=600)