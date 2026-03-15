import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from streamlit_calendar import calendar
import datetime
import os
import base64

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

# 🚨 업데이트: 8:2 비율에 맞춘 체크박스 압축 및 버튼 쌍둥이 동기화, 특정 박스 회색 칠하기 CSS
st.markdown(
    """
    <style>
    .title-wrapper { display: flex; align-items: center; justify-content: flex-start; gap: 20px; margin-bottom: 20px; }
    .logo-img { height: 60px; width: auto; object-fit: contain; }
    .main-title { font-size: 2.5rem; font-weight: bold; margin: 0; }
    .stRadio > div { gap: 15px; } 
    
    /* 체크박스 글자 크기 및 여백 극한 축소 (좁은 화면 대응) */
    [data-testid="stCheckbox"] p { font-size: 0.6rem !important; }
    [data-testid="stCheckbox"] { margin-top: -10px !important; margin-bottom: -10px !important; }
    
    /* 🚨 마법의 코드: 'filter-marker'를 포함한 컨테이너만 회색으로 칠하기 */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.filter-marker) { 
        padding: 0.8rem !important; 
        background-color: #f0f2f6 !important; 
        border-color: #f0f2f6 !important;
        border-radius: 0.5rem;
    }
    
    /* 🚨 관리자 뱃지와 로그아웃 버튼 100% 쌍둥이 동기화 */
    .role-badge {
        display: flex; align-items: center; justify-content: center;
        border: 1px solid rgba(49, 51, 63, 0.2); border-radius: 0.5rem; 
        font-size: 1rem; color: #31333F; background-color: white; 
        height: 42px; width: 100%; box-sizing: border-box; 
        font-weight: 400; /* 기본 버튼과 같은 폰트 굵기 */
    }
    div[data-testid="stButton"] > button { 
        height: 42px; font-size: 1rem; width: 100%;
        border: 1px solid rgba(49, 51, 63, 0.2);
        padding: 0; margin: 0;
    }
    </style>
    """, unsafe_allow_html=True
)

if 'role' not in st.session_state: st.session_state.role = None

# --- 구글 시트 연결 및 데이터 로드 ---
conn = st.connection("gsheets", type=GSheetsConnection)
try:
    df = conn.read(ttl="0").dropna(how="all")
    for col in ["분류", "시간구분", "비고"]:
        if col not in df.columns: df[col] = ""
    for col in ["비밀번호", "ID"]:
        if col in df.columns:
            df[col] = df[col].astype(str).apply(lambda x: x[:-2] if x.endswith('.0') else x)
            if col == "비밀번호": df[col] = df[col].apply(lambda x: "0000" if x == "0" else x)
except Exception:
    df = pd.DataFrame(columns=["신청자", "분류", "설비명 & 작업내용", "날짜", "시간구분", "비고", "비밀번호", "상태", "ID", "등록일시"])

# --- 팝업 (관리자 달력용) ---
@st.dialog("예약 상세 정보")
def show_event_popup(event_data):
    global df, conn
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
        st.markdown("**관리자 액션**")
        
        with st.expander("이 예약 내용 수정하기"):
            target_idx = df[df['ID'] == target_id].index
            if not target_idx.empty:
                e_row = df.loc[target_idx[0]]
                e_cat = st.selectbox("분류", CATEGORIES, index=CATEGORIES.index(e_row['분류']) if e_row['분류'] in CATEGORIES else 0, key="pop_cat")
                e_eq = st.text_input("작업내용", value=e_row['설비명 & 작업내용'], key="pop_eq")
                e_d = st.date_input("날짜", value=pd.to_datetime(e_row['날짜']), key="pop_d")
                e_t = st.radio("시간구분", ["오전", "오후", "종일"], index=["오전", "오후", "종일"].index(e_row['시간구분']) if e_row['시간구분'] in ["오전", "오후", "종일"] else 0, horizontal=True, key="pop_t")
                e_n = st.text_area("비고", value=e_row.get('비고', ''), key="pop_n")
                
                if st.button("수정 내용 저장", key="pop_save"):
                    df.at[target_idx[0], '분류'] = e_cat
                    df.at[target_idx[0], '설비명 & 작업내용'] = e_eq
                    df.at[target_idx[0], '날짜'] = str(e_d)
                    df.at[target_idx[0], '시간구분'] = e_t
                    df.at[target_idx[0], '비고'] = e_n
                    conn.update(data=df); st.success("수정되었습니다."); st.rerun()

        if st.button("이 예약 강제 삭제하기", use_container_width=True):
            df = df[df['ID'] != target_id]; conn.update(data=df)
            st.success("삭제되었습니다."); st.rerun()

# --- 로그인 화면 ---
if st.session_state.role is None:
    img_b64 = get_base64_image(LOGO_PATH)
    if img_b64: st.markdown(f'<div class="title-wrapper"><img src="data:image/png;base64,{img_b64}" class="logo-img"><h1 class="main-title">제조본부 예약 시스템</h1></div>', unsafe_allow_html=True)
    else: st.title("제조본부 예약 시스템")
    
    col_l1, col_l2 = st.columns([1, 2])
    with col_l1:
        st.subheader("로그인")
        login_pw = st.text_input("입장 비밀번호를 입력하세요", type="password")
        if st.button("접속하기", use_container_width=True):
            if login_pw == "1234":
                st.session_state.role = 'user'; st.rerun()
            elif login_pw == "ati5344":
                st.session_state.role = 'admin'; st.rerun()
            else: st.error("비밀번호가 일치하지 않습니다.")
    st.stop()

# --- 헤더 ---
col_logo, col_role, col_logout = st.columns([8.2, 0.9, 0.9])

with col_logo:
    img_b64 = get_base64_image(LOGO_PATH)
    if img_b64: st.markdown(f'<div class="title-wrapper"><img src="data:image/png;base64,{img_b64}" class="logo-img" style="height:40px;"><h2 style="margin:0;">제조본부 실시간 예약 현황</h2></div>', unsafe_allow_html=True)
    else: st.header(f"제조본부 실시간 예약 현황")

with col_role:
    # 🚨 업데이트: 이모티콘 제거 및 텍스트만 깔끔하게 표시
    role_text = "관리자" if st.session_state.role == "admin" else "일반"
    st.markdown(f'<div class="role-badge">{role_text}</div>', unsafe_allow_html=True)

with col_logout:
    if st.button("로그아웃", use_container_width=True): st.session_state.role = None; st.rerun()

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
            name = st.text_input("신청자 이름", placeholder="예: 신아테크")
            category = st.selectbox("작업 분류", CATEGORIES, format_func=lambda x: f"{EMOJI_MAP.get(x, '')} {x}")
            equip = st.text_input("설비명 & 작업내용", placeholder="예: 대덕 PINE2S 빌드업")
            date = st.date_input("작업 희망 날짜")
            time_type = st.radio("시간 구분", ["오전", "오후", "종일"], horizontal=True)
            note = st.text_area("비고 (요청사항)", placeholder="예: 오후 3시까지 완료 희망합니다.")
            res_pw = st.text_input("예약 비밀번호 (수정/삭제용)", type="password")
            
            if st.form_submit_button("신청하기", type="primary", use_container_width=True):
                if not name or not equip or not res_pw: st.error("신청자, 작업내용, 비밀번호는 필수입니다.")
                else:
                    new_data = pd.DataFrame([{
                        "신청자": name, "분류": category, "설비명 & 작업내용": equip, 
                        "날짜": str(date), "시간구분": time_type, "비고": note, 
                        "비밀번호": str(res_pw), "상태": "대기중", 
                        "ID": str(pd.Timestamp.now().strftime("%Y%m%d%H%M%S")),
                        "등록일시": str(pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
                    }])
                    conn.update(data=pd.concat([df, new_data], ignore_index=True))
                    st.success("✅ 신청이 완료되었습니다. 관리자 승인을 대기합니다."); st.rerun()

    with col_list:
        st.subheader("전체 접수 내역")
        selected_month = st.selectbox("조회할 월 선택", ["전체 보기"] + available_months, key="user_month")
        view_df = df.copy()
        if selected_month != "전체 보기": view_df = view_df[view_df['월별'] == selected_month]
        
        if view_df.empty:
            st.info("해당 월에 접수된 내역이 없습니다.")
        else:
            t_wait, t_app, t_rej = st.tabs(["승인 대기", "승인 완료", "반려됨"])
            disp_cols = ["분류", "설비명 & 작업내용", "신청자", "날짜", "시간구분", "상태"]
            
            with t_wait: st.dataframe(view_df[view_df['상태'] == '대기중'][disp_cols], hide_index=True, use_container_width=True)
            with t_app: st.dataframe(view_df[view_df['상태'] == '승인완료'][disp_cols], hide_index=True, use_container_width=True)
            with t_rej: st.dataframe(view_df[view_df['상태'] == '반려'][disp_cols], hide_index=True, use_container_width=True)
            
            st.divider()
            st.subheader("내 예약 수정 및 삭제")
            my_opts = view_df.apply(lambda x: f"[{x['분류']}] {x['설비명 & 작업내용']} | {x['날짜']} ({x['상태']})", axis=1).tolist()
            if my_opts:
                sel_opt = st.selectbox("수정/삭제할 예약 선택", my_opts)
                sel_idx = my_opts.index(sel_opt)
                target_row = view_df.iloc[sel_idx]
                target_id = target_row['ID']
                
                auth_pw = st.text_input("해당 예약의 비밀번호 입력", type="password", key="user_auth_pw")
                
                with st.expander("일정 세부 내용 수정하기"):
                    e_cat = st.selectbox("분류", CATEGORIES, index=CATEGORIES.index(target_row['분류']) if target_row['분류'] in CATEGORIES else 0, format_func=lambda x: f"{EMOJI_MAP.get(x, '')} {x}")
                    e_eq = st.text_input("작업내용", value=target_row['설비명 & 작업내용'])
                    e_d = st.date_input("날짜", value=pd.to_datetime(target_row['날짜']))
                    e_t = st.radio("시간구분", ["오전", "오후", "종일"], index=["오전", "오후", "종일"].index(target_row['시간구분']) if target_row['시간구분'] in ["오전", "오후", "종일"] else 0, horizontal=True)
                    e_n = st.text_area("비고", value=target_row.get('비고', ''))
                    
                    if st.button("변경 내용 저장"):
                        if auth_pw == str(target_row['비밀번호']):
                            df_idx = df[df['ID'] == target_id].index[0]
                            df.at[df_idx, '분류'] = e_cat
                            df.at[df_idx, '설비명 & 작업내용'] = e_eq
                            df.at[df_idx, '날짜'] = str(e_d)
                            df.at[df_idx, '시간구분'] = e_t
                            df.at[df_idx, '비고'] = e_n
                            conn.update(data=df); st.success("수정되었습니다."); st.rerun()
                        else: st.error("비밀번호가 틀립니다.")
                
                if st.button("이 예약 삭제하기"):
                    if auth_pw == str(target_row['비밀번호']):
                        df = df[df['ID'] != target_id]; conn.update(data=df); st.success("삭제되었습니다."); st.rerun()
                    else: st.error("비밀번호가 틀립니다.")

# ==========================================
# 👑 관리자 뷰
# ==========================================
elif st.session_state.role == 'admin':
    
    if "check_all" not in st.session_state:
        st.session_state.check_all = True
        for cat in CATEGORIES:
            st.session_state[f"chk_{cat}"] = True

    def toggle_all():
        val = st.session_state.check_all
        for cat in CATEGORIES:
            st.session_state[f"chk_{cat}"] = val

    def toggle_one():
        st.session_state.check_all = all(st.session_state.get(f"chk_{c}", False) for c in CATEGORIES)

    # 🚨 업데이트: 비율 8:2로 과감한 화면 분할
    col_admin_cal, col_admin_list = st.columns([8, 2])
    
    # 📌 [좌측 영역] 달력 전용 (80% 차지)
    with col_admin_cal:
        events = []
        active_filters = [cat for cat in CATEGORIES if st.session_state.get(f"chk_{cat}", False)]
        
        if not df.empty:
            app_df = df[(df["상태"] == "승인완료") & (df['분류'].isin(active_filters))]
            for _, r in app_df.iterrows():
                try:
                    d_str = str(r['날짜'])
                    if r['시간구분'] == '오전': s_dt, e_dt = f"{d_str}T09:00:00", f"{d_str}T13:00:00"
                    elif r['시간구분'] == '오후': s_dt, e_dt = f"{d_str}T13:00:00", f"{d_str}T18:00:00"
                    else: s_dt, e_dt = f"{d_str}T09:00:00", f"{d_str}T18:00:00"
                    
                    events.append({
                        "title": f"[{r['분류']}] {r['설비명 & 작업내용']} - {r['신청자']}", 
                        "start": s_dt, "end": e_dt, 
                        "color": get_color_by_category(r['분류']), 
                        "display": "block", 
                        "extendedProps": {
                            "category": str(r['분류']), "applicant": str(r['신청자']), 
                            "equip": str(r['설비명 & 작업내용']), "date": d_str, 
                            "time_type": str(r['시간구분']), "note": str(r.get('비고', '')),
                            "status": str(r['상태']), "id": str(r['ID']) 
                        }
                    })
                except: continue
                
        res = calendar(events=events, options={"headerToolbar": {"left": "prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek"}, "initialView": "dayGridMonth", "locale": "ko", "height": 750}, key="admin_cal")
        if res.get("eventClick"): show_event_popup(res["eventClick"]["event"])

    # 📌 [우측 영역] 필터 박스 및 예약 통합 관리 (20% 차지)
    with col_admin_list:
        
        # 🚨 업데이트: filter-marker 클래스를 심어서 이 박스만 회색으로 칠함
        with st.container(border=True):
            st.markdown('<div class="filter-marker"></div>', unsafe_allow_html=True)
            st.checkbox("☑️ 전체 (ALL)", key="check_all", on_change=toggle_all)
            
            # 🚨 업데이트: 전체선택 제외하고 순서대로 3열씩 딱 맞게 배열
            for i in range(0, len(CATEGORIES), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(CATEGORIES):
                        cat = CATEGORIES[i + j]
                        with cols[j]:
                            st.checkbox(f"{EMOJI_MAP.get(cat, '')} {cat}", key=f"chk_{cat}", on_change=toggle_one)

        st.write("") 
        
        st.markdown("##### 예약 통합 관리")
        t_wait, t_edit, t_list = st.tabs(["결재 대기", "일정 수정", "월별 내역"])
        
        with t_wait:
            wait_df = df[df["상태"] == "대기중"]
            if not wait_df.empty:
                w_opts = wait_df.apply(lambda x: f"[{x['분류']}] {x['설비명 & 작업내용']} | {x['날짜']} - {x['신청자']}", axis=1).tolist()
                w_sel = st.selectbox("결재할 항목 선택", w_opts)
                w_idx = w_opts.index(w_sel)
                w_id = wait_df.iloc[w_idx]['ID']
                w_note = wait_df.iloc[w_idx].get('비고', '')
                if w_note: st.info(f"신청자 비고: {w_note}")
                
                c1, c2, c3 = st.columns(3)
                if c1.button("승인", use_container_width=True):
                    df.loc[df['ID'] == w_id, '상태'] = '승인완료'; conn.update(data=df); st.rerun()
                if c2.button("반려", use_container_width=True):
                    df.loc[df['ID'] == w_id, '상태'] = '반려'; conn.update(data=df); st.rerun()
                if c3.button("삭제", use_container_width=True):
                    df = df[df['ID'] != w_id]; conn.update(data=df); st.rerun()
            else: st.success("현재 대기 중인 항목이 없습니다.")

        with t_edit:
            admin_opts = df.apply(lambda x: f"[{x['상태']}] {x['설비명 & 작업내용']} | {x['날짜']} - {x['신청자']}", axis=1).tolist()
            if admin_opts:
                a_sel = st.selectbox("수정할 예약 전체 목록 (비밀번호 불필요)", admin_opts)
                a_idx = admin_opts.index(a_sel)
                a_row = df.iloc[a_idx]
                a_id = a_row['ID']
                
                with st.expander("세부 내용 수정", expanded=True):
                    a_cat = st.selectbox("분류", CATEGORIES, index=CATEGORIES.index(a_row['분류']) if a_row['분류'] in CATEGORIES else 0, format_func=lambda x: f"{EMOJI_MAP.get(x, '')} {x}", key="admin_edit_cat")
                    a_eq = st.text_input("작업내용", value=a_row['설비명 & 작업내용'], key="admin_edit_eq")
                    a_d = st.date_input("날짜", value=pd.to_datetime(a_row['날짜']), key="admin_edit_d")
                    a_t = st.radio("시간구분", ["오전", "오후", "종일"], index=["오전", "오후", "종일"].index(a_row['시간구분']) if a_row['시간구분'] in ["오전", "오후", "종일"] else 0, horizontal=True, key="admin_edit_t")
                    a_n = st.text_area("비고", value=a_row.get('비고', ''), key="admin_edit_n")
                    
                    if st.button("관리자 권한으로 변경 내용 저장"):
                        df_idx = df[df['ID'] == a_id].index[0]
                        df.at[df_idx, '분류'] = a_cat
                        df.at[df_idx, '설비명 & 작업내용'] = a_eq
                        df.at[df_idx, '날짜'] = str(a_d)
                        df.at[df_idx, '시간구분'] = a_t
                        df.at[df_idx, '비고'] = a_n
                        conn.update(data=df); st.success("수정되었습니다."); st.rerun()

        with t_list:
            admin_month = st.selectbox("조회할 월(Month) 선택", ["전체 보기"] + available_months, key="admin_month")
            view_df = df.copy()
            if admin_month != "전체 보기": view_df = view_df[view_df['월별'] == admin_month]
            
            disp_cols_admin = ["등록일시", "분류", "설비명 & 작업내용", "신청자", "날짜", "상태"]
            st.dataframe(view_df[disp_cols_admin], hide_index=True, use_container_width=True, height=450)
