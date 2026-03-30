import streamlit as st
import cv2
import json
from omega_db import setup_database, SessionLocal, User, Analysis, hash_pwd, verify_pwd
from omega_engine import OmegaAI

setup_database()
ai = OmegaAI()

st.set_page_config(page_title="Projet OMEGA", page_icon="🛡️")

if "auth" not in st.session_state:
    st.session_state.auth = False

# --- VUE CONNEXION ---
if not st.session_state.auth:
    st.title("🛡️ Authentification OMEGA")
    choice = st.radio("Mode", ["Connexion Faciale", "Inscription"])

    if choice == "Connexion Faciale":
        if st.button("Scanner Visage"):
            cam = cv2.VideoCapture(0)
            ret, frame = cam.read()
            if ret:
                encoding = ai.get_face_signature(frame)
                if encoding is not None:
                    db = SessionLocal()
                    users = db.query(User).all()
                    # Comparaison
                    for u in users:
                        known = np.array(json.loads(u.face_data))
                        if face_recognition.compare_faces([known], encoding, 0.5)[0]:
                            st.session_state.auth = True
                            st.session_state.user = u.username
                            st.rerun()
                    st.error("Visage non reconnu.")
                    db.close()
            cam.release()

    else:
        name = st.text_input("Nom d'utilisateur")
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("S'inscrire"):
            cam = cv2.VideoCapture(0)
            ret, frame = cam.read()
            if ret:
                enc = ai.get_face_signature(frame)
                if enc is not None:
                    db = SessionLocal()
                    new_u = User(username=name, password_hash=hash_pwd(pwd), face_data=json.dumps(enc.tolist()))
                    db.add(new_u)
                    db.commit()
                    st.success("Compte créé !")
                    db.close()
            cam.release()

# --- VUE ANALYSE ---
else:
    st.sidebar.title(f"👤 {st.session_state.user}")
    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = False
        st.rerun()

    st.header("Analyse de Trafic YOLOv8")
    uploaded = st.file_uploader("Vidéo MP4", type=["mp4"])
    
    if uploaded:
        with open("temp_video.mp4", "wb") as f:
            f.write(uploaded.read())
        
        if st.button("Démarrer le comptage"):
            with st.spinner("Analyse en cours..."):
                results = ai.process_video("temp_video.mp4")
                st.subheader("Résultats du comptage")
                st.table(results)
                
                # Sauvegarde en base
                db = SessionLocal()
                db.add(Analysis(video_name=uploaded.name, summary=json.dumps(results)))
                db.commit()
                db.close()