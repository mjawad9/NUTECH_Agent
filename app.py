def student_login():
    if st.button("← Back to home"):
        go(None)
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.markdown(f"<div style='text-align:center'>{logo_html(80)}</div>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align:center;color:{NAVY}'>Student Login</h2>", unsafe_allow_html=True)
        with st.form("login"):
            nutech_id = st.text_input("NUTECH ID", placeholder="e.g. NU-2022-001")
            access_code = st.text_input("Access Code", type="password")
            ok = st.form_submit_button("Login", use_container_width=True, type="primary")
        if ok:
            student = authenticate(nutech_id, access_code)
            if student:
                st.session_state.student = student
                go("student")
            else:
                st.error("Invalid NUTECH ID or access code.")
