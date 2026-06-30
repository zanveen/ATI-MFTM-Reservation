import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from streamlit_calendar import calendar
import datetime
import os
import base64
import time

# --- 설정 및 기초 함수 ---
LOGO_PATH = "ati_logo.png" 
CATEGORIES = ["클리닝", "패킹&출하", "도킹", "RND설치", "작업의뢰", "빌드업", "입고", "VAD", "기타"]

EMOJI_MAP = {
    "클리닝": "🔴", "패킹&출하": "🟠", "도킹": "🟡", 
    "RND설치": "🟢", "작업의뢰": "🔵", "빌드업": "🟣", 
    "입고": "🟤", "VAD": "⚪", "기타": "⚫"
}

def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return ""

def get_color_by_category(category):
    colors = {
        "클리닝": "#FF4B4B", "패킹&출하": "#FF9900", "도킹": "#E6B800", 
        "RND설치": "#2E8B57", "작업의뢰": "#1E90FF", "빌드업": "#4B0082", 
        "입고": "#8D6E63", "VAD": "#00CED1", "기타": "#555555"
    }
    return colors.get(category, "#757575")

st.set_page_config(page_title="제조본부 예약 시스템", layout="wide", page_icon="ati_logo.png")

# 스타일 정의
st.markdown(
    """
    <style>
    .title-wrapper { display: flex; align-items: center; justify-content: flex-start; gap: 20px; margin-bottom: 20px; }
    .logo-img { height: 60px; width: auto; object-fit: contain; }
    .main-title { font-size: 2.5rem; font-weight: bold; margin: 0; }
    .stRadio > div { gap: 15px; } 
    [data-testid="stCheckbox"] { margin-top: -10px !important; margin-bottom: -10px !important; }
    [data-testid="stCheckbox"] p { font-size: 0.85rem !important; }
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.filter-marker) { 
        padding: 0.8rem !important; 
        background-color: #f0f2f6 !important; 
        border-radius: 0.5rem;
    }
    .role-badge {
        display: flex; align-items: center; justify-content: center;
        border: 1px solid rgba(49, 51, 63, 0.2); border-radius: 0.5rem; 
        font-size: 1rem; color: #31333F; background-color: white; 
        height: 42px; width: 100%; font-weight: 400; 
    }
    div[data-testid="stButton"] > button { 
        height: 42px; font-size: 1rem; width: 100%; border: 1px solid rgba(49, 51, 63, 0.2);
    }
    </style>
    """, unsafe_allow_html=True
)

if 'role' not in st.session_state: st.session_state.role = None
# 🚨 스냅샷(복구용) 세션 초기화
if 'db_snapshot' not in st.session_state: st.session_state.db_snapshot = None

# --- 구글 시트 연결 및 데이터 로드 함수 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # ttl=0으로 매번 최신 데이터를 읽어옴
        data = conn.read(ttl="0").dropna(how="all")
        for col in ["분류", "시간구분", "비고"]:
            if col not in data.columns: data[col] = ""
        for col in ["비밀번호", "ID"]:
            if col in data.columns:
                data[col] = data[col].astype(str).apply(lambda x: x[:-2] if x.endswith('.0') else x)
                if col == "비밀번호": data[col] = data[col].apply(lambda x: "0000" if x == "0" else x)
        return data
    except:
        return pd.DataFrame(columns=["신청자", "분류", "설비명 & 작업내용", "날짜", "시간구분", "비고", "비밀번호", "상태", "ID", "등록일시"])

# 🚨 데이터 안전 업데이트 함수 (연속 클릭 오류 방지)
def safe_update(new_df):
    st.session_state.db_snapshot = load_data() # 쓰기 직전 상태를 복구용으로 저장
    conn.update(data=new_df)
    time.sleep(0.5) # 구글 서버 반영 시간 확보
    st.cache_data.clear() # 캐시 강제 삭제
    st.rerun()

df = load_data()

# --- 팝업 (관리자 달력용) ---
@st.dialog("예약 상세 정보")
def show_event_popup(event_data):
    props = event_data.get("extendedProps", {})
    target_id = props.get("id", "")
    
    st.markdown(f"**분류:** {props.get('category', '')}")
    st.markdown(f"**신청자:** {props.get('applicant', '')}")
    st.markdown(f"**설비명 & 작업내용:** {props.get('equip', '')}")
    st.markdown(f"**요청 일정:** {props.get('date', '')} ({props.get('time_type', '')})")
    st.markdown(f"**비고(요청사항):** {props.get('note', '없음')}")
    st.markdown(f"**상태:** {props.get('status', '')}")

    if st.session_state.role == 'admin' and target_id:
        st.divider()
        with st.expander("✏️ 내용 수정"):
            target_idx = df[df['ID'] == target_id].index
            if not target_idx.empty:
                e_row = df.loc[target_idx[0]]
                e_cat = st.selectbox("분류", CATEGORIES, index=CATEGORIES.index(e_row['분류']) if e_row['분류'] in CATEGORIES else 0, key="pop_cat")
                e_eq = st.text_input("작업내용", value=e_row['설비명 & 작업내용'], key="pop_eq")
                e_d = st.date_input("날짜", value=pd.to_datetime(e_row['날짜']), key="pop_d")
                e_t = st.radio("시간구분", ["오전", "오후", "종일"], index=["오전", "오후", "종일"].index(e_row['시간구분']) if e_row['시간구분'] in ["오전", "오후", "종일"] else 0, horizontal=True, key="pop_t")
                e_n = st.text_area("비고", value=e_row.get('비고', ''), key="pop_n")
                if st.button("수정 내용 저장"):
                    df.at[target_idx[0], '분류'] = e_cat
                    df.at[target_idx[0], '설비명 & 작업내용'] = e_eq
                    df.at[target_idx[0], '날짜'] = str(e_d)
                    df.at[target_idx[0], '시간구분'] = e_t
                    df.at[target_idx[0], '비고'] = e_n
                    safe_update(df)

        if st.button("🗑️ 강제 삭제", use_container_width=True):
            new_df = df[df['ID'] != target_id]
            safe_update(new_df)

# --- 로그인 / 헤더 ---
if st.session_state.role is None:
    img_b64 = get_base64_image(LOGO_PATH)
    if img_b64: st.markdown(f'<div class="title-wrapper"><img src="data:image/png;base64,{img_b64}" class="logo-img"><h1 class="main-title">제조본부 예약 시스템</h1></div>', unsafe_allow_html=True)
    else: st.title("제조본부 예약 시스템")
    col_l1, col_l2 = st.columns([1, 2])
    with col_l1:
        login_pw = st.text_input("입장 비밀번호", type="password")
        if st.button("접속하기"):
            if login_pw == "1234": st.session_state.role = 'user'; st.rerun()
            elif login_pw == "ati5344": st.session_state.role = 'admin'; st.rerun()
            else: st.error("비밀번호 불일치")
    st.stop()

col_logo, col_role, col_logout = st.columns([8.2, 0.9, 0.9])
with col_logo:
    img_b64 = get_base64_image(LOGO_PATH)
    st.markdown(f'<div class="title-wrapper"><img src="data:image/png;base64,{img_b64}" class="logo-img" style="height:40px;"><h2 style="margin:0;">제조본부 실시간 예약 현황</h2></div>', unsafe_allow_html=True)
with col_role:
    st.markdown(f'<div class="role-badge">{"관리자" if st.session_state.role == "admin" else "일반"}</div>', unsafe_allow_html=True)
with col_logout:
    if st.button("로그아웃"): st.session_state.role = None; st.rerun()

df['월별'] = pd.to_datetime(df['날짜'], errors='coerce').dt.strftime('%Y-%m')
available_months = sorted(df['월별'].dropna().unique(), reverse=True)

# ==========================================
# 👤 일반 사용자 뷰
# ==========================================
if st.session_state.role == 'user':
    col_form, col_list = st.columns([4, 6])
    with col_form:
        st.subheader("작업 예약 신청")
        with st.form("user_input_form", clear_on_submit=True):
            name = st.text_input("신청자 이름")
            category = st.selectbox("작업 분류", CATEGORIES, format_func=lambda x: f"{EMOJI_MAP.get(x, '')} {x}")
            equip = st.text_input("설비명 & 작업내용")
            date = st.date_input("작업 희망 날짜")
            time_type = st.radio("시간 구분", ["오전", "오후", "종일"], horizontal=True)
            note = st.text_area("비고 (요청사항)")
            res_pw = st.text_input("비밀번호 (수정/삭제용)", type="password")
            if st.form_submit_button("신청하기", type="primary", use_container_width=True):
                if not name or not equip or not res_pw: st.error("필수 항목 입력 누락")
                else:
                    new_row = pd.DataFrame([{"신청자": name, "분류": category, "설비명 & 작업내용": equip, "날짜": str(date), "시간구분": time_type, "비고": note, "비밀번호": str(res_pw), "상태": "대기중", "ID": str(pd.Timestamp.now().strftime("%Y%m%d%H%M%S")), "등록일시": str(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))}])
                    safe_update(pd.concat([df, new_row], ignore_index=True))

    with col_list:
        st.subheader("전체 접수 내역")
        sel_month = st.selectbox("월 선택", ["전체 보기"] + available_months)
        view_df = df if sel_month == "전체 보기" else df[df['월별'] == sel_month]
        t_wait, t_app, t_rej = st.tabs(["대기", "승인", "반려"])
        with t_wait: st.dataframe(view_df[view_df['상태'] == '대기중'][["분류", "설비명 & 작업내용", "신청자", "날짜", "상태"]], hide_index=True, use_container_width=True)
        with t_app: st.dataframe(view_df[view_df['상태'] == '승인완료'][["분류", "설비명 & 작업내용", "신청자", "날짜", "상태"]], hide_index=True, use_container_width=True)
        with t_rej: st.dataframe(view_df[view_df['상태'] == '반려'][["분류", "설비명 & 작업내용", "신청자", "날짜", "상태"]], hide_index=True, use_container_width=True)

# ==========================================
# 👑 관리자 뷰
# ==========================================
elif st.session_state.role == 'admin':
    if "check_all" not in st.session_state:
        st.session_state.check_all = True
        for cat in CATEGORIES: st.session_state[f"chk_{cat}"] = True

    def toggle_all():
        for cat in CATEGORIES: st.session_state[f"chk_{cat}"] = st.session_state.check_all

    col_admin_cal, col_admin_list = st.columns([8, 2])
    
    with col_admin_cal:
        active_filters = [cat for cat in CATEGORIES if st.session_state.get(f"chk_{cat}", False)]
        events = []
        if not df.empty:
            app_df = df[(df["상태"] == "승인완료") & (df['분류'].isin(active_filters))]
            for _, r in app_df.iterrows():
                try:
                    d_str = str(r['날짜'])
                    s_dt = f"{d_str}T09:00:00" if r['시간구분'] == '오전' else (f"{d_str}T13:00:00" if r['시간구분'] == '오후' else f"{d_str}T09:00:00")
                    e_dt = f"{d_str}T13:00:00" if r['시간구분'] == '오전' else (f"{d_str}T18:00:00" if r['시간구분'] == '오후' else f"{d_str}T18:00:00")
                    events.append({"title": f"[{r['분류']}] {r['설비명 & 작업내용']} - {r['신청자']} ({r['시간구분']})", "start": s_dt, "end": e_dt, "color": get_color_by_category(r['분류']), "display": "block", "extendedProps": {"category": str(r['분류']), "applicant": str(r['신청자']), "equip": str(r['설비명 & 작업내용']), "date": d_str, "time_type": str(r['시간구분']), "note": str(r.get('비고', '')), "status": str(r['상태']), "id": str(r['ID'])}})
                except: continue
        res = calendar(events=events, options={"headerToolbar": {"left": "prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek"}, "initialView": "dayGridMonth", "locale": "ko", "height": 750, "displayEventTime": False}, key="admin_cal")
        if res.get("eventClick"): show_event_popup(res["eventClick"]["event"])

    with col_admin_list:
        with st.container(border=True):
            st.markdown('<div class="filter-marker"></div>', unsafe_allow_html=True)
            st.checkbox("☑️ 전체 (ALL)", key="check_all", on_change=toggle_all)
            for i in range(0, len(CATEGORIES), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i+j < len(CATEGORIES):
                        cat = CATEGORIES[i+j]
                        with cols[j]: st.checkbox(f"{EMOJI_MAP.get(cat, '')} {cat}", key=f"chk_{cat}")

        st.write("") 
        st.markdown("##### 예약 통합 관리")
        # 🚨 데이터 복구(Recovery) 탭 추가
        t_wait, t_edit, t_list, t_recovery = st.tabs(["결재", "수정", "내역", "🔄 복구"])
        
        with t_wait:
            wait_df = df[df["상태"] == "대기중"]
            if not wait_df.empty:
                w_sel = st.selectbox("결재 선택", wait_df.apply(lambda x: f"[{x['분류']}] {x['설비명 & 작업내용']} - {x['신청자']}", axis=1).tolist())
                w_id = wait_df.iloc[0]['ID'] # 실제로는 선택한 인덱스에 따라 ID 추출 필요
                # 실제 선택한 항목의 ID 추출 로직
                w_idx = wait_df.apply(lambda x: f"[{x['분류']}] {x['설비명 & 작업내용']} - {x['신청자']}", axis=1).tolist().index(w_sel)
                w_id = wait_df.iloc[w_idx]['ID']
                
                c1, c2, c3 = st.columns(3)
                if c1.button("승인"):
                    df.loc[df['ID'] == w_id, '상태'] = '승인완료'
                    safe_update(df)
                if c2.button("반려"):
                    df.loc[df['ID'] == w_id, '상태'] = '반려'
                    safe_update(df)
                if c3.button("삭제"):
                    safe_update(df[df['ID'] != w_id])
            else: st.success("대기 없음")

        with t_edit:
            a_sel = st.selectbox("수정 선택", df.apply(lambda x: f"[{x['상태']}] {x['설비명 & 작업내용']} - {x['신청자']}", axis=1).tolist())
            a_idx = df.apply(lambda x: f"[{x['상태']}] {x['설비명 & 작업내용']} - {x['신청자']}", axis=1).tolist().index(a_sel)
            a_id = df.iloc[a_idx]['ID']
            with st.expander("내용 수정"):
                row = df.iloc[a_idx]
                nc = st.selectbox("분류 ", CATEGORIES, index=CATEGORIES.index(row['분류']) if row['분류'] in CATEGORIES else 0)
                ne = st.text_input("작업내용 ", value=row['설비명 & 작업내용'])
                nd = st.date_input("날짜 ", value=pd.to_datetime(row['날짜']))
                if st.button("변경 저장"):
                    df.at[a_idx, '분류'] = nc
                    df.at[a_idx, '설비명 & 작업내용'] = ne
                    df.at[a_idx, '날짜'] = str(nd)
                    safe_update(df)

        with t_list:
            adm_month = st.selectbox("조회 월", ["전체 보기"] + available_months)
            st.dataframe(df if adm_month == "전체 보기" else df[df['월별'] == adm_month], hide_index=True)

        # 🚨 [복구 시스템 구현]
        with t_recovery:
            st.warning("데이터 유실 시 직전 상태로 되돌립니다.")
            if st.session_state.db_snapshot is not None:
                st.write("마지막 변경 전 이력 존재")
                if st.button("⏮️ 직전 상태로 복구하기", use_container_width=True):
                    conn.update(data=st.session_state.db_snapshot)
                    st.session_state.db_snapshot = None # 복구 후 스냅샷 초기화
                    st.success("복구가 완료되었습니다!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.info("복구 가능한 스냅샷이 없습니다. (현재 페이지 접속 후 변경 사항이 있어야 생성됨)")
