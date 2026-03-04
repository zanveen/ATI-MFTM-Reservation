import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from streamlit_calendar import calendar
import datetime
from datetime import timedelta
import requests
import os
import base64

# --- 설정 및 보안 ---
LOGO_PATH = "ati_logo.png" 

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# 이름별 고유 색상을 반환하는 함수
def get_color_by_name(name):
    # '신아테크'는 ATI의 아이덴티티를 담은 Red 계열로 고정
    if name == "신아테크":
        return "#D32F2F" # ATI Red
    
    # 그 외 이름들은 7가지 팔레트에서 자동으로 배정
    color_palette = [
        "#1E88E5", "#43A047", "#FB8C00", "#8E24AA", 
        "#00ACC1", "#3949AB", "#5D4037" 
    ]
    idx = sum(ord(char) for char in name) % len(color_palette)
    return color_palette[idx]

st.set_page_config(
    page_title="제조본부 예약 시스템", 
    layout="wide",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "🚜"
)

# UI 스타일 정의 (로그인창 너비 제한 포함)
st.markdown(
    """
    <style>
    .title-wrapper { display: flex; align-items: center; justify-content: flex-start; gap: 20px; margin-bottom: 30px; }
    .logo-img { height: 60px; width: auto; object-fit: contain; }
    .main-title { font-size: 2.5rem; font-weight: bold; margin: 0; }
    .stTextInput { max-width: 400px; }
    div.stButton > button { max-width: 400px; }
    .block-container { padding-top: 3rem; }
    </style>
    """,
    unsafe_allow_html=True
)

if 'auth' not in st.session_state: st.session_state.auth = False
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False

# --- 진입 화면 ---
if not st.session_state.auth:
    if os.path.exists(LOGO_PATH):
        img_base64 = get_base64_image(LOGO_PATH)
        st.markdown(f'<div class="title-wrapper"><img src="data:image/png;base64,{img_base64}" class="logo-img"><h1 class="main-title">제조본부 예약 시스템</h1></div>', unsafe_allow_html=True)
    else: st.title("제조본부 예약 시스템")
    
    login_pw = st.text_input("입장 비밀번호를 입력하세요", type="password")
    if st.button("입장하기"):
        if login_pw == "1234":
            st.session_state.auth = True
            st.rerun()
        else: st.error("암호가 틀렸습니다.")
    st.stop()

# --- 구글 시트 연결 ---
conn = st.connection("gsheets", type=GSheetsConnection)
try:
    df = conn.read(ttl="0")
    df = df.dropna(how="all")
    for col in ["비밀번호", "ID"]:
        if col in df.columns:
            df[col] = df[col].astype(str).apply(lambda x: x[:-2] if x.endswith('.0') else x)
            if col == "비밀번호":
                df[col] = df[col].apply(lambda x: "0000" if x == "0" else x)
    if "시간" in df.columns:
        df["시간"] = df["시간"].astype(str).apply(lambda x: f"0{x}" if len(x.split(':')[0]) == 1 else x)
except Exception as e:
    df = pd.DataFrame(columns=["신청자", "설비명 & 작업내용", "날짜", "시간", "소요시간", "비밀번호", "상태", "ID"])

# --- 중복 체크 함수 ---
def check_overlap(new_date, new_time, new_duration_str, current_df, ignore_id=None):
    start_dt = datetime.datetime.combine(new_date, new_time)
    dur_h = int(new_duration_str[0]) if new_duration_str[0].isdigit() else 1
    end_dt = start_dt + timedelta(hours=dur_h)
    approved_df = current_df[current_df["상태"] == "승인완료"]
    if ignore_id: approved_df = approved_df[approved_df["ID"] != ignore_id]
    for _, row in approved_df.iterrows():
        exist_start = datetime.datetime.strptime(f"{row['날짜']} {row['시간']}", "%Y-%m-%d %H:%M")
        e_dur_h = int(row['소요시간'][0]) if row['소요시간'][0].isdigit() else 1
        exist_end = exist_start + timedelta(hours=e_dur_h)
        if (start_dt < exist_end) and (end_dt > exist_start):
            return True, f"⚠️ 중복 일정 발견: [{row['설비명 & 작업내용']}] {row['시간']} ~ {exist_end.strftime('%H:%M')}"
    return False, ""

# --- 🚨 업데이트 1: 팝업 함수 (달력 내 관리자 수정/삭제 기능) ---
@st.dialog("📅 예약 상세 정보")
def show_event_popup(event_data):
    global df, conn # 데이터 수정을 위해 전역 변수 선언
    props = event_data.get("extendedProps", {})
    target_id = props.get("id", "")
    
    st.markdown(f"**🏢 신청자:** {props.get('applicant', '')}")
    st.markdown(f"**🚜 설비명 & 작업내용:** {props.get('equip', '')}")
    st.markdown(f"**⏰ 예약 일시:** {event_data.get('start', '').replace('T', ' ')}")
    st.markdown(f"**⏳ 소요 시간:** {props.get('duration', '')}")
    st.markdown(f"**✅ 상태:** {props.get('status', '')}")

    # 관리자 메뉴에 로그인되어 있을 때만 아래 기능이 활성화됩니다!
    if st.session_state.admin_auth and target_id:
        st.divider()
        st.markdown("🛠️ **관리자 빠른 달력 관리**")
        
        # 삭제 기능
        if st.button("🗑️ 이 예약 강제 삭제하기", type="primary", use_container_width=True):
            df = df[df['ID'] != target_id]
            conn.update(data=df)
            st.success("예약이 완전히 삭제되었습니다."); st.rerun()
            
        # 수정 기능
        with st.expander("✏️ 세부 일정 직접 수정"):
            target_idx = df[df['ID'] == target_id].index
            if not target_idx.empty:
                e_row = df.loc[target_idx[0]]
                new_eq = st.text_input("설비명 & 작업내용 수정", value=e_row['설비명 & 작업내용'], key="pop_eq")
                c_date, c_time = st.columns(2)
                new_d = c_date.date_input("날짜", value=pd.to_datetime(e_row['날짜']), key="pop_d")
                h, m = map(int, str(e_row['시간']).split(':'))
                new_t = c_time.time_input("시간", value=datetime.time(h, m), step=1800, key="pop_t")
                dur_opts = ["1시간", "2시간", "3시간", "4시간", "5시간 이상"]
                cur_dur = e_row['소요시간'] if e_row['소요시간'] in dur_opts else "1시간"
                new_dur = st.selectbox("소요시간", dur_opts, index=dur_opts.index(cur_dur), key="pop_dur")
                
                if st.button("💾 달력 변경 내용 저장", key="pop_save"):
                    is_ov, m_ov = check_overlap(new_d, new_t, new_dur, df, ignore_id=target_id)
                    if is_ov: st.error(m_ov)
                    else:
                        df.at[target_idx[0], '설비명 & 작업내용'] = new_eq
                        df.at[target_idx[0], '날짜'] = str(new_d)
                        df.at[target_idx[0], '시간'] = str(new_t)[:5]
                        df.at[target_idx[0], '소요시간'] = new_dur
                        conn.update(data=df)
                        st.success("달력 수정이 완료되었습니다!"); st.rerun()

# --- 메인 UI 상단 ---
if os.path.exists(LOGO_PATH):
    img_base64_main = get_base64_image(LOGO_PATH)
    st.markdown(f'<div class="title-wrapper"><img src="data:image/png;base64,{img_base64_main}" class="logo-img" style="height:50px;"><h2 style="margin:0;">제조본부 실시간 예약 현황</h2></div>', unsafe_allow_html=True)
else: st.header("제조본부 실시간 예약 현황")

col_left, col_right = st.columns([7, 3])

# 📌 우측 영역
with col_right:
    st.subheader("📝 예약 등록")
    with st.form("input_form", clear_on_submit=True):
        name = st.text_input("신청자 이름", value="신아테크")
        equip = st.text_input("설비명 & 작업내용", placeholder="예: SGM #1 등")
        date = st.date_input("예약 날짜")
        time = st.time_input("작업 예정 시간", value=datetime.time(10, 0), step=1800) 
        duration = st.selectbox("예상 소요 시간", ["1시간", "2시간", "3시간", "4시간", "5시간 이상"])
        res_pw = st.text_input("비밀번호(취소용)", type="password")
        if st.form_submit_button("예약 신청하기"):
            is_overlap, msg = check_overlap(date, time, duration, df)
            if not equip or not res_pw: st.error("내용을 입력하세요!")
            elif is_overlap: st.error(msg)
            else:
                new_data = pd.DataFrame([{"신청자": name, "설비명 & 작업내용": equip, "날짜": str(date), "시간": str(time)[:5], "소요시간": duration, "비밀번호": str(res_pw), "상태": "대기중", "ID": str(pd.Timestamp.now().strftime("%Y%m%d%H%M%S"))}])
                conn.update(data=pd.concat([df, new_data], ignore_index=True))
                st.success("신청 완료!"); st.rerun()

    st.divider()
    st.subheader("📋 현재 예약 대기 현황")
    p_df = df[df["상태"].isin(["대기중", "반려"])] if not df.empty else pd.DataFrame()
    if not p_df.empty:
        d_df = p_df[['상태', '날짜', '시간', '신청자', '설비명 & 작업내용']].copy()
        d_df['상태'] = d_df['상태'].replace({'대기중': '⏳ 대기', '반려': '❌ 반려'})
        st.dataframe(d_df, use_container_width=True, hide_index=True)
        cancel_opts = p_df.apply(lambda x: f"[{x['설비명 & 작업내용']}] {x['날짜']} {x['시간']} | {x['신청자']}", axis=1).tolist()
        c_sel = st.selectbox("취소/삭제 대상 선택", cancel_opts, label_visibility="collapsed")
        c_idx = cancel_opts.index(c_sel)
        t_pw = str(p_df.iloc[c_idx]['비밀번호']).strip()
        cpw = st.text_input("예약 비밀번호 입력", type="password", key="cpw")
        if st.button("삭제하기"):
            if str(cpw).strip() == t_pw:
                df = df[df['ID'] != p_df.iloc[c_idx]['ID']]
                conn.update(data=df); st.rerun()
            else: st.error("비밀번호가 틀립니다.")
    else: st.info("대기 중인 내역이 없습니다.")

    st.divider()
    st.subheader("🔑 관리자 메뉴")
    if not st.session_state.admin_auth:
        admin_pw_input = st.text_input("관리자 암호", type="password", label_visibility="collapsed")
        if st.button("관리자 로그인"):
            if admin_pw_input == "ati5344":
                st.session_state.admin_auth = True
                st.rerun()
            else: st.error("비밀번호 틀림")
    else:
        if st.button("로그아웃"): st.session_state.admin_auth = False; st.rerun()
        tab1, tab2 = st.tabs(["🆕 승인 및 관리", "✏️ 수정"])
        with tab1:
            a_p_df = df[df["상태"] == "대기중"]
            if not a_p_df.empty:
                a_opts = a_p_df.apply(lambda x: f"[{x['설비명 & 작업내용']}] {x['날짜']} {x['신청자']}", axis=1).tolist()
                a_sel = st.selectbox("승인 대상 선택", a_opts)
                a_idx = a_opts.index(a_sel)
                a_id = a_p_df.iloc[a_idx]['ID']
                row = a_p_df.iloc[a_idx]
                r_date = datetime.datetime.strptime(row['날짜'], "%Y-%m-%d").date()
                r_time = datetime.datetime.strptime(row['시간'], "%H:%M").time()
                is_overlap, msg = check_overlap(r_date, r_time, row['소요시간'], df)
                if is_overlap: st.warning(f"참고: {msg}")
                
                # --- 🚨 업데이트 2: 관리자 메뉴에 삭제 버튼 추가 ---
                c1, c2, c3 = st.columns(3)
                if c1.button("✅ 승인", use_container_width=True):
                    df.loc[df['ID'] == a_id, '상태'] = '승인완료'; conn.update(data=df); st.rerun()
                if c2.button("❌ 반려", use_container_width=True):
                    df.loc[df['ID'] == a_id, '상태'] = '반려'; conn.update(data=df); st.rerun()
                if c3.button("🗑️ 삭제", use_container_width=True):
                    df = df[df['ID'] != a_id]; conn.update(data=df); st.rerun()
            else: st.info("대기 건 없음")
            
        with tab2:
            today = datetime.date.today()
            this_monday = today - timedelta(days=today.weekday())
            a_list = df[(df["상태"] == "승인완료") & (pd.to_datetime(df["날짜"]).dt.date >= this_monday)]
            if not a_list.empty:
                e_opts = a_list.apply(lambda x: f"[{x['설비명 & 작업내용']}] {x['날짜']} {x['신청자']}", axis=1).tolist()
                e_sel = st.selectbox("수정 대상 선택", e_opts)
                e_row = a_list.iloc[e_opts.index(e_sel)]
                with st.expander("📝 상세 일정 변경", expanded=True):
                    new_eq = st.text_input("설비명 & 작업내용 수정", value=e_row['설비명 & 작업내용'])
                    c_date, c_time = st.columns(2)
                    new_d = c_date.date_input("날짜", value=pd.to_datetime(e_row['날짜']))
                    h, m = map(int, e_row['시간'].split(':'))
                    new_t = c_time.time_input("시간", value=datetime.time(h, m), step=1800)
                    new_dur = st.selectbox("소요시간", ["1시간", "2시간", "3시간", "4시간", "5시간 이상"], index=["1시간", "2시간", "3시간", "4시간", "5시간 이상"].index(e_row['소요시간']) if e_row['소요시간'] in ["1시간", "2시간", "3시간", "4시간", "5시간 이상"] else 0)
                    
                    if st.button("💾 모든 변경 내용 저장"):
                        is_ov, m_ov = check_overlap(new_d, new_t, new_dur, df, ignore_id=e_row['ID'])
                        if is_ov: st.error(m_ov)
                        else:
                            idx = df[df['ID'] == e_row['ID']].index[0]
                            df.at[idx, '설비명 & 작업내용'] = new_eq
                            df.at[idx, '날짜'] = str(new_d)
                            df.at[idx, '시간'] = str(new_t)[:5]
                            df.at[idx, '소요시간'] = new_dur
                            conn.update(data=df); st.success("수정 완료!"); st.rerun()
                    
                    # 관리자 메뉴(수정 탭) 하단에도 일정 삭제 버튼 추가
                    if st.button("🗑️ 이 예약 강제 삭제하기"):
                        df = df[df['ID'] != e_row['ID']]; conn.update(data=df); st.rerun()
            else: st.info("수정 가능한 일정이 없습니다.")

# 📌 좌측 영역 (달력)
with col_left:
    st.subheader("📅 예약 현황 달력")
    events = []
    if not df.empty:
        app_df = df[df["상태"] == "승인완료"]
        for _, r in app_df.iterrows():
            try:
                start_dt = datetime.datetime.strptime(f"{r['날짜']} {r['시간']}", "%Y-%m-%d %H:%M")
                dur_h = int(r['소요시간'][0]) if r['소요시간'][0].isdigit() else 1
                end_dt = start_dt + timedelta(hours=dur_h)
                
                applicant_name = str(r['신청자'])
                event_color = get_color_by_name(applicant_name)
                
                events.append({
                    "title": f"[{r['설비명 & 작업내용']}] {applicant_name}", 
                    "start": start_dt.strftime("%Y-%m-%dT%H:%M"), 
                    "end": end_dt.strftime("%Y-%m-%dT%H:%M"), 
                    "color": event_color, 
                    "extendedProps": {
                        "applicant": applicant_name, 
                        "equip": str(r['설비명 & 작업내용']), 
                        "duration": str(r['소요시간']), 
                        "status": str(r['상태']),
                        # --- 🚨 업데이트 3: 달력 팝업에 고유 ID 전달 ---
                        "id": str(r['ID']) 
                    }
                })
            except: continue
    res = calendar(events=events, options={"headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"}, "initialView": "dayGridMonth", "locale": "ko", "slotMinTime": "06:00:00", "slotMaxTime": "22:00:00"})
    if res.get("eventClick"): show_event_popup(res["eventClick"]["event"])
