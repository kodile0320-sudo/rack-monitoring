import datetime
import os
import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="창고 랙 스마트 모니터링", layout="wide")
st.title("📦 창고 랙 스마트 모니터링 대시보드")

# 📌 깃허브에 업로드된 inventory.xlsx 파일 자동 로드 (없을 경우 업로더 제공)
EXCEL_FILE_PATH = "inventory.xlsx"

df = None
if os.path.exists(EXCEL_FILE_PATH):
  df = pd.read_excel(EXCEL_FILE_PATH)
else:
  uploaded_file = st.file_uploader(
      "엑셀 파일(.xlsx)을 업로드하세요", type=["xlsx", "xls"]
  )
  if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

if df is not None:
  current_year = datetime.datetime.now().year

  # 'G024-3' 형태의 연속 위치 코드 분할
  expanded_rows = []
  for idx, row in df.iterrows():
    loc_code = str(row.get("위치코드", "")).strip()

    if not loc_code or loc_code == "nan":
      continue

    pattern = r"^([A-Za-z])(\d{2})(\d{1,2})(?:-(\d+))?$"
    match = re.match(pattern, loc_code)

    if match:
      col = match.group(1).upper()
      bay = int(match.group(2))
      start_lvl = int(match.group(3))
      count = int(match.group(4)) if match.group(4) else 1

      for offset in range(count):
        new_row = row.to_dict()
        new_row["열"] = col
        new_row["베이"] = bay
        new_row["단"] = start_lvl + offset
        new_row["생성위치"] = f"{col}{bay:02d}{start_lvl + offset}"
        expanded_rows.append(new_row)
    else:
      expanded_rows.append(row.to_dict())

  raw_df = pd.DataFrame(expanded_rows)

  if raw_df.empty:
    st.error("엑셀 파일에 유효한 위치코드 데이터가 없습니다.")
  else:
    # 5년 이상 노후 품목 계산
    raw_df["경과년수"] = current_year - pd.to_numeric(
        raw_df.get("생산년도", current_year), errors="coerce"
    )
    raw_df["노후여부"] = raw_df["경과년수"] >= 5

    # Lot 컬럼 통일
    if "Lot" not in raw_df.columns and "Lot번호" in raw_df.columns:
      raw_df["Lot"] = raw_df["Lot번호"]
    elif "Lot" not in raw_df.columns:
      raw_df["Lot"] = "-"

    # 상단 컨트롤 (열 선택 및 Lot 검색)
    c1, c2 = st.columns([1, 2])
    with c1:
      valid_cols = sorted(
          [
              str(c).upper()
              for c in raw_df["열"].dropna().unique()
              if str(c) != ""
          ]
      )
      selected_col = st.selectbox("📍 도식화할 열 선택:", valid_cols)

    with c2:
      search_lot = st.text_input(
          "🔍 Lot 번호 검색 (입력 시 해당 위치가 강조됩니다):", ""
      ).strip()

    col_df = raw_df[raw_df["열"] == selected_col]

    # 열별 랙 규격 설정
    max_bay_dict = {
        "A": 10,
        "B": 12,
        "C": 14,
        "D": 16,
        "E": 16,
        "F": 16,
        "G": 16,
        "H": 16,
    }
    max_bay = max_bay_dict.get(
        selected_col, int(col_df["베이"].max()) if not col_df.empty else 16
    )
    max_lvl = 12 if selected_col == "A" else 6

    # 열별 전체 슬롯 및 사용율 계산
    total_capacity = 0
    occupied_count = 0

    grid_rows = []
    for lvl in range(1, max_lvl + 1):
      for bay in range(1, max_bay + 1):
        if selected_col == "A" and bay >= 5 and lvl > 6:
          continue

        total_capacity += 1
        loc_id = f"{selected_col}{bay:02d}{lvl}"
        matched_items = col_df[
            (col_df["베이"] == bay) & (col_df["단"] == lvl)
        ]

        if not matched_items.empty:
          occupied_count += 1
          cnt = len(matched_items)

          raw_name = str(matched_items.iloc[0].get("품목명", "-"))
          clean_name = raw_name.replace(" ", "")
          short_item = clean_name[:3] if len(clean_name) >= 3 else clean_name

          if cnt > 1:
            short_label = f"{short_item} 외{cnt-1}"
          else:
            short_label = short_item

          has_old = matched_items["노후여부"].any()
          has_lot_match = False
          if search_lot:
            has_lot_match = matched_items["Lot"].astype(str).str.contains(
                search_lot, case=False
            ).any()

          if has_lot_match:
            bg_color = "#F97316"
            short_label = f"🎯{short_label}"
          elif has_old:
            bg_color = "#FECACA"
            short_label = f"⚠️{short_label}"
          elif cnt > 1:
            bg_color = "#BAE6FD"
            short_label = f"📦{short_label}"
          else:
            bg_color = "#E2E8F0"

          grid_rows.append({
              "베이": bay,
              "단": lvl,
              "생성위치": loc_id,
              "표시문구": short_label,
              "색상": bg_color,
          })
        else:
          grid_rows.append({
              "베이": bay,
              "단": lvl,
              "생성위치": loc_id,
              "표시문구": "-",
              "색상": "#F1F5F9",
          })

    usage_rate = (
        (occupied_count / total_capacity * 100) if total_capacity > 0 else 0
    )
    empty_count = total_capacity - occupied_count

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"📊 {selected_col}열 현재 적재율", f"{usage_rate:.1f}%")
    m2.metric("📦 총 보관 용량", f"{total_capacity}칸")
    m3.metric("✅ 적재 중", f"{occupied_count}칸")
    m4.metric("⬜ 빈 공간", f"{empty_count}칸")

    st.divider()

    grid_df = pd.DataFrame(grid_rows)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=grid_df["베이"],
            y=grid_df["단"],
            mode="markers+text",
            marker=dict(
                size=36 if max_bay > 12 else 42,
                symbol="square",
                color=grid_df["색상"],
                line=dict(width=1.5, color="#94A3B8"),
            ),
            text=grid_df["표시문구"],
            textposition="middle center",
            textfont=dict(size=10, color="#1E293B"),
            customdata=grid_df["생성위치"],
            hovertemplate=(
                "<b>위치: %{customdata}</b><br>내용: %{text}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"🧱 {selected_col}열 랙 배치도 (마우스로 원하는 랙 칸을 직접 누르세요)",
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(1, max_bay + 1)),
            ticktext=[f"{b}베이" for b in range(1, max_bay + 1)],
            range=[0.3, max_bay + 0.7],
            fixedrange=True,
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(1, max_lvl + 1)),
            ticktext=[f"{l}단" for l in range(1, max_lvl + 1)],
            range=[0.3, max_lvl + 0.7],
            fixedrange=True,
        ),
        height=420 if max_lvl == 6 else 650,
        margin=dict(l=20, r=20, t=50, b=20),
        plot_bgcolor="#FFFFFF",
        clickmode="event+select",
    )

    st.subheader(f"🧱 {selected_col}열 배치도")

    chart_event = st.plotly_chart(
        fig,
        use_container_width=True,
        selection_mode="points",
        on_select="rerun",
        key=f"rack_chart_{selected_col}",
    )

    if "selected_loc" not in st.session_state or not st.session_state[
        "selected_loc"
    ].startswith(selected_col):
      st.session_state["selected_loc"] = f"{selected_col}011"

    if (
        chart_event
        and "selection" in chart_event
        and chart_event["selection"].get("points")
    ):
      pt = chart_event["selection"]["points"][0]
      cd = pt.get("customdata")
      if cd:
        clicked_loc = cd[0] if isinstance(cd, list) else str(cd)
        st.session_state["selected_loc"] = clicked_loc

    current_loc = st.session_state["selected_loc"]

    st.divider()

    st.subheader(f"📋 선택된 랙 위치: [{current_loc}] 상세 품목 목록")

    detail_items = col_df[col_df["생성위치"] == current_loc][
        ["생성위치", "품목명", "Lot", "생산년도", "경과년수", "노후여부"]
    ]

    if detail_items.empty:
      st.info(
          f"💡 **{current_loc}** 위치는 현재 **[빈 공간]**입니다. 위 배치도에서"
          " 다른 사각형 칸을 누르면 즉시 변경됩니다."
      )
    else:

      def highlight_old_rows(row):
        if row.get("노후여부", False):
          return ["background-color: #FFC7CE; color: #9C0006;"] * len(row)
        return [""] * len(row)

      st.dataframe(
          detail_items.style.apply(highlight_old_rows, axis=1),
          use_container_width=True,
      )
