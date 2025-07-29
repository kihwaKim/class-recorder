import streamlit as st
from firebase_admin import credentials, firestore, initialize_app, storage
import firebase_admin
import pandas as pd
import uuid
from datetime import datetime
import os, json



# Firebase 초기화 (한 번만 수행)
if not firebase_admin._apps:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
    cred = credentials.Certificate(firebase_key)
    initialize_app(cred, {
        'storageBucket': 'class-recoder-ca0ea.firebasestorage.app'
    })

db = firestore.client()
bucket = storage.bucket()

st.set_page_config(page_title="학사 관리 시스템", layout="wide")

menu = st.sidebar.selectbox("메뉴", [
    "교과 관리", "수업 등록", "학생 등록", "진도 등록",
    "진도 조회", "출결 등록", "출결 조회"
])

if menu == "교과 관리":
    st.header("📘 교과 관리")

    with st.form("add_course"):
        col1, col2, col3 = st.columns(3)
        with col1:
            course_name = st.text_input("교과명")
        with col2:
            year = st.selectbox("학년도", [str(y) for y in range(2020, 2031)])
        with col3:
            semester = st.selectbox("학기", ["1학기", "2학기"])
        file = st.file_uploader("수업 및 평가 계획서 (PDF, 최대 10MB)", type=["pdf"])
        submitted = st.form_submit_button("교과 등록")

        if submitted:
            if not course_name or not file:
                st.warning("모든 정보를 입력해주세요.")
            elif file.size > 10 * 1024 * 1024:
                st.error("파일 크기는 최대 10MB입니다.")
            else:
                blob = bucket.blob(f"course_plans/{uuid.uuid4()}.pdf")
                blob.upload_from_file(file, content_type='application/pdf')
                blob.make_public()
                db.collection("courses").add({
                    "course_name": course_name,
                    "year": year,
                    "semester": semester,
                    "pdf_url": blob.public_url,
                    "created_at": datetime.now()
                })
                st.success("교과가 등록되었습니다.")

    st.subheader("📖 등록된 교과 목록")
    search = st.text_input("교과명 검색")
    courses = db.collection("courses").stream()
    rows = []
    for doc in courses:
        data = doc.to_dict()
        if search.lower() in data["course_name"].lower():
            rows.append({
                "교과명": data["course_name"],
                "학년도": data["year"],
                "학기": data["semester"],
                "PDF 링크": data["pdf_url"]
            })
    if rows:
        st.dataframe(pd.DataFrame(rows))
    else:
        st.info("검색된 교과가 없습니다.")

elif menu == "수업 등록":
    st.header("📗 수업 등록")
    courses = db.collection("courses").stream()
    course_map = {f"{c.to_dict()['course_name']} ({c.to_dict()['year']} {c.to_dict()['semester']})": c.id for c in courses}
    course_choice = st.selectbox("교과 선택", list(course_map.keys()))
    class_name = st.text_input("학반")
    weekday = st.selectbox("요일", ["월", "화", "수", "목", "금"])
    period = st.number_input("교시", min_value=1, max_value=10, step=1)
    if st.button("수업 등록"):
        db.collection("classes").add({
            "course_id": course_map[course_choice],
            "class_name": class_name,
            "weekday": weekday,
            "period": period,
            "created_at": datetime.now()
        })
        st.success("수업이 등록되었습니다.")

elif menu == "학생 등록":
    st.header("👨‍🎓 학생 등록")
    class_docs = db.collection("classes").stream()
    class_map = {doc.id: doc.to_dict() for doc in class_docs}
    class_choices = [f"{v['class_name']} ({v['weekday']} {v['period']}교시)" for v in class_map.values()]
    selected_class = st.selectbox("수업 선택", class_choices)
    selected_class_id = list(class_map.keys())[class_choices.index(selected_class)]

    st.subheader("CSV 파일 업로드")
    file = st.file_uploader("CSV 업로드 (학번, 이름 열 포함)", type=["csv"])
    if file:
        df = pd.read_csv(file)
        for _, row in df.iterrows():
            db.collection("students").add({
                "class_id": selected_class_id,
                "student_id": str(row["학번"]),
                "name": row["이름"]
            })
        st.success("CSV에서 학생이 등록되었습니다.")

    st.subheader("직접 입력")
    sid = st.text_input("학번")
    sname = st.text_input("이름")
    if st.button("학생 추가"):
        db.collection("students").add({
            "class_id": selected_class_id,
            "student_id": sid,
            "name": sname
        })
        st.success("학생이 추가되었습니다.")

elif menu == "진도 등록":
    st.header("📒 진도 등록")
    classes = db.collection("classes").stream()
    class_map = {f"{doc.to_dict()['class_name']} ({doc.to_dict()['weekday']} {doc.to_dict()['period']}교시)": doc.id for doc in classes}
    selected = st.selectbox("수업 선택", list(class_map.keys()))
    date = st.date_input("일자")
    period = st.number_input("교시", min_value=1, max_value=10)
    content = st.text_area("진도 내용")
    note = st.text_area("특기사항")
    if st.button("기록"):
        db.collection("progress").add({
            "class_id": class_map[selected],
            "date": str(date),
            "period": period,
            "content": content,
            "note": note
        })
        st.success("진도가 기록되었습니다.")

elif menu == "진도 조회":
    st.header("📔 진도 조회")
    date = st.date_input("조회할 날짜")
    progress = db.collection("progress").where("date", "==", str(date)).stream()
    rows = []
    for doc in progress:
        d = doc.to_dict()
        rows.append(d)
    if rows:
        st.dataframe(pd.DataFrame(rows))
    else:
        st.info("기록된 진도가 없습니다.")

elif menu == "출결 등록":
    st.header("✅ 출결 등록")
    classes = db.collection("classes").stream()
    class_map = {f"{c.to_dict()['class_name']} ({c.to_dict()['weekday']} {c.to_dict()['period']}교시)": c.id for c in classes}
    selected_class = st.selectbox("수업 선택", list(class_map.keys()))
    date = st.date_input("일자")
    students = db.collection("students").where("class_id", "==", class_map[selected_class]).stream()
    for student in students:
        s = student.to_dict()
        col1, col2, col3 = st.columns([2, 2, 6])
        with col1:
            st.markdown(f"**{s['student_id']} {s['name']}**")
        with col2:
            status = st.selectbox(
                f"출결 상태 ({s['student_id']})",
                ["출석", "지각", "조퇴", "결석"],
                key=s['student_id']
            )
        with col3:
            remark = st.text_input(f"특기사항 ({s['student_id']})", key=f"note_{s['student_id']}")
        if st.button(f"저장 ({s['student_id']})"):
            db.collection("attendance").add({
                "class_id": class_map[selected_class],
                "student_id": s['student_id'],
                "date": str(date),
                "status": status,
                "note": remark
            })
            st.success(f"{s['student_id']} 저장 완료")

elif menu == "출결 조회":
    st.header("📋 출결 조회")
    date = st.date_input("조회 날짜")
    records = db.collection("attendance").where("date", "==", str(date)).stream()
    rows = []
    for doc in records:
        d = doc.to_dict()
        rows.append(d)
    if rows:
        st.dataframe(pd.DataFrame(rows))
    else:
        st.info("해당 날짜에 출결 정보가 없습니다.")
