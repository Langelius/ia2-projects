"""
omega_app.py
------------
Application principale Streamlit pour le Projet OMEGA.
Gère l'authentification (classique + faciale) et le module d'analyse vidéo YOLO.

Lancement : streamlit run omega_app.py
"""

import streamlit as st
import cv2
import json
import numpy as np
import face_recognition

from omega_db import (
    initialiser_base, SessionLocal,
    User, Video, Run, CountSummary,
    hacher_mot_de_passe, verifier_mot_de_passe
)
from omega_engine import OmegaAI

# ← Initialisation de la base de données au démarrage de l'application
initialiser_base()

# ← Chargement unique du moteur IA (évite de recharger YOLO à chaque interaction)
@st.cache_resource
def charger_moteur():
    return OmegaAI()

moteur = charger_moteur()

# ← Configuration de la page Streamlit
st.set_page_config(
    page_title="Projet OMEGA",
    page_icon="🛡️",
    layout="wide"
)

# ← Initialisation de l'état de session (connexion)
if "authentifie" not in st.session_state:
    st.session_state.authentifie = False
if "utilisateur" not in st.session_state:
    st.session_state.utilisateur = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None


# =============================================================================
# FONCTIONS UTILITAIRES D'AUTHENTIFICATION
# =============================================================================

def connecter_par_mot_de_passe(nom, mot_de_passe):
    """
    Vérifie les identifiants classiques (nom + mot de passe).
    Met à jour la session si la connexion réussit.
    Retourne un message d'erreur ou None si succès.
    """
    session = SessionLocal()
    utilisateur = session.query(User).filter_by(username=nom).first()
    session.close()

    if utilisateur is None:
        return "Utilisateur introuvable."  # ← nom inexistant

    if not verifier_mot_de_passe(mot_de_passe, utilisateur.password_hash):
        return "Mot de passe incorrect."  # ← mauvais mot de passe

    # ← Connexion réussie : mise à jour de la session Streamlit
    st.session_state.authentifie = True
    st.session_state.utilisateur = utilisateur.username
    st.session_state.user_id = utilisateur.id
    return None


def connecter_par_visage(image):
    """
    Authentifie un utilisateur par reconnaissance faciale.
    Retourne un message d'erreur ou None si succès.
    """
    encodage = moteur.obtenir_encodage_facial(image)

    if encodage is None:
        return "Aucun visage détecté. Assurez-vous d'être bien cadré."

    # ← Comparaison avec tous les visages enregistrés dans la base
    session = SessionLocal()
    utilisateurs = session.query(User).filter(User.face_data.isnot(None)).all()
    session.close()

    for u in utilisateurs:
        if u.face_data is None:
            continue  # ← sécurité : ignorer les utilisateurs sans encodage facial
        visage_connu = np.array(json.loads(str(u.face_data)))  # ← str() : évite l'erreur de typage Column[str] vs str
        if moteur.comparer_visage(encodage, visage_connu, seuil=0.5):
            # ← Visage reconnu : connexion réussie
            st.session_state.authentifie = True
            st.session_state.utilisateur = u.username
            st.session_state.user_id = u.id
            return None

    return "Visage non reconnu dans la base de données."  # ← aucune correspondance trouvée


def inscrire_utilisateur(nom, email, mot_de_passe, image):
    """
    Crée un nouveau compte utilisateur avec son encodage facial.
    Retourne un message de succès ou d'erreur.
    """
    if not nom or not mot_de_passe:
        return False, "Le nom d'utilisateur et le mot de passe sont obligatoires."

    encodage = moteur.obtenir_encodage_facial(image)
    if encodage is None:
        return False, "Aucun visage détecté. Veuillez prendre une photo claire."

    session = SessionLocal()
    try:
        # ← Vérification que le nom n'est pas déjà utilisé
        existant = session.query(User).filter_by(username=nom).first()
        if existant:
            return False, f"Le nom d'utilisateur '{nom}' est déjà pris."

        # ← Création du nouvel utilisateur
        nouvel_utilisateur = User(
            username=nom,
            email=email if email else None,
            password_hash=hacher_mot_de_passe(mot_de_passe),
            face_data=json.dumps(encodage.tolist())  # ← sérialisation du vecteur en JSON
        )
        session.add(nouvel_utilisateur)
        session.commit()
        return True, f"Compte '{nom}' créé avec succès !"

    except Exception as e:
        session.rollback()
        return False, f"Erreur lors de la création du compte : {e}"
    finally:
        session.close()


# =============================================================================
# VUE : AUTHENTIFICATION (non connecté)
# =============================================================================

if not st.session_state.authentifie:
    st.title("🛡️ Système OMEGA — Authentification")
    st.markdown("---")

    # ← Onglets pour les différents modes
    onglet_connexion, onglet_facial, onglet_inscription = st.tabs([
        "🔑 Connexion classique",
        "📷 Connexion faciale",
        "📝 Inscription"
    ])

    # ------------------------------------------------------------------
    # ONGLET 1 : Connexion classique (nom + mot de passe)
    # ------------------------------------------------------------------
    with onglet_connexion:
        st.subheader("Connexion par identifiants")
        nom_saisi    = st.text_input("Nom d'utilisateur", key="login_nom")
        mdp_saisi    = st.text_input("Mot de passe", type="password", key="login_mdp")

        if st.button("Se connecter", key="btn_connexion"):
            if nom_saisi and mdp_saisi:
                erreur = connecter_par_mot_de_passe(nom_saisi, mdp_saisi)
                if erreur:
                    st.error(erreur)
                else:
                    st.success("Connexion réussie !")
                    st.rerun()  # ← rafraîchissement pour afficher la vue analyse
            else:
                st.warning("Veuillez remplir tous les champs.")

    # ------------------------------------------------------------------
    # ONGLET 2 : Connexion par reconnaissance faciale
    # ------------------------------------------------------------------
    with onglet_facial:
        st.subheader("Connexion par reconnaissance faciale")
        st.info("Cliquez sur le bouton pour capturer votre visage via la webcam.")

        if st.button("📷 Scanner mon visage", key="btn_facial"):
            with st.spinner("Capture en cours..."):
                image_capturee = moteur.capturer_image_webcam(index_camera=0)

            if image_capturee is None:
                st.error("Impossible d'accéder à la caméra.")
            else:
                # ← Affichage de la photo capturée pour confirmation
                image_rgb = cv2.cvtColor(image_capturee, cv2.COLOR_BGR2RGB)
                st.image(image_rgb, caption="Photo capturée", width=300)

                erreur = connecter_par_visage(image_capturee)
                if erreur:
                    st.error(erreur)
                else:
                    st.success("Visage reconnu ! Connexion réussie.")
                    st.rerun()  # ← rafraîchissement vers la vue analyse

    # ------------------------------------------------------------------
    # ONGLET 3 : Inscription (nouveau compte)
    # ------------------------------------------------------------------
    with onglet_inscription:
        st.subheader("Créer un nouveau compte")
        nouveau_nom   = st.text_input("Nom d'utilisateur", key="reg_nom")
        nouveau_email = st.text_input("Courriel (optionnel)", key="reg_email")
        nouveau_mdp   = st.text_input("Mot de passe", type="password", key="reg_mdp")
        confirmer_mdp = st.text_input("Confirmer le mot de passe", type="password", key="reg_confirm")

        st.info("Lors de l'inscription, votre visage sera capturé pour activer l'authentification faciale.")

        if st.button("S'inscrire", key="btn_inscription"):
            if nouveau_mdp != confirmer_mdp:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                with st.spinner("Capture du visage..."):
                    image_inscription = moteur.capturer_image_webcam(index_camera=0)

                if image_inscription is None:
                    st.error("Impossible d'accéder à la caméra pour la photo.")
                else:
                    image_rgb = cv2.cvtColor(image_inscription, cv2.COLOR_BGR2RGB)
                    st.image(image_rgb, caption="Votre photo d'inscription", width=300)

                    succes, message = inscrire_utilisateur(
                        nouveau_nom, nouveau_email, nouveau_mdp, image_inscription
                    )
                    if succes:
                        st.success(message)
                    else:
                        st.error(message)


# =============================================================================
# VUE : ANALYSE VIDÉO (utilisateur connecté)
# =============================================================================

else:
    # ← Barre latérale : informations utilisateur et déconnexion
    st.sidebar.title(f"👤 {st.session_state.utilisateur}")
    st.sidebar.markdown("---")

    if st.sidebar.button("🚪 Déconnexion"):
        st.session_state.authentifie = False
        st.session_state.utilisateur = None
        st.session_state.user_id = None
        st.rerun()  # ← retour à la vue de connexion

    # ← Navigation dans la barre latérale
    page = st.sidebar.radio("Navigation", ["Analyse vidéo", "Historique"])

    # ------------------------------------------------------------------
    # PAGE 1 : Analyse vidéo
    # ------------------------------------------------------------------
    if page == "Analyse vidéo":
        st.header("🎥 Analyse de Trafic — YOLOv8")
        st.markdown("Chargez une vidéo MP4 pour lancer la détection et le comptage d'objets.")

        fichier_video = st.file_uploader("Sélectionner une vidéo MP4", type=["mp4"])

        col1, col2 = st.columns(2)
        with col1:
            ratio_ligne = st.slider(
                "Position de la ligne de comptage (%)",
                min_value=10, max_value=90, value=60
            ) / 100  # ← conversion en ratio décimal
        with col2:
            seuil_conf = st.slider(
                "Seuil de confiance YOLO",
                min_value=0.1, max_value=0.9, value=0.5, step=0.05
            )

        if fichier_video is not None:
            # ← Sauvegarde temporaire de la vidéo uploadée
            chemin_temp = f"data/temp_{fichier_video.name}"
            with open(chemin_temp, "wb") as f:
                f.write(fichier_video.read())

            if st.button("▶️ Démarrer l'analyse"):
                with st.spinner("Analyse en cours... Cela peut prendre quelques minutes."):

                    # ← Mise à jour du seuil de confiance du moteur
                    moteur.seuil_confiance = seuil_conf

                    # ← Enregistrement de la vidéo dans la base
                    session = SessionLocal()
                    nouvelle_video = Video(
                        titre=fichier_video.name,
                        chemin=chemin_temp,
                        fps=0  # ← sera mis à jour après analyse
                    )
                    session.add(nouvelle_video)
                    session.commit()
                    video_id = nouvelle_video.id

                    # ← Création du run d'analyse
                    run = Run(
                        user_id=st.session_state.user_id,
                        video_id=video_id,
                        modele_yolo="yolov8n.pt",
                        seuil_confiance=seuil_conf
                    )
                    session.add(run)
                    session.commit()
                    run_id = run.id
                    session.close()

                    # ← Lancement de l'analyse (détection + comptage + CSV)
                    resultats = moteur.traiter_video(chemin_temp, run_id, ratio_ligne)

                if resultats:
                    st.success("Analyse terminée !")
                    st.subheader("Résultats du comptage")

                    # ← Tableau des résultats
                    donnees_tableau = [
                        {"Classe": k, "Objets comptés": v}
                        for k, v in resultats["compteurs"].items()
                        if v > 0  # ← n'afficher que les classes détectées
                    ]
                    if donnees_tableau:
                        st.table(donnees_tableau)
                    else:
                        st.info("Aucun objet cible détecté dans cette vidéo.")

                    # ← Informations sur les fichiers générés
                    st.markdown("**Fichiers générés :**")
                    st.markdown(f"- Vidéo annotée : `{resultats['chemin_annote']}`")
                    st.markdown(f"- Fichier CSV : `{resultats['chemin_csv']}`")
                    st.markdown(f"- Frames analysées : {resultats['nb_frames']}")

                    # ← Bouton de téléchargement du CSV
                    with open(resultats["chemin_csv"], "r", encoding="utf-8") as f:
                        st.download_button(
                            label="⬇️ Télécharger le CSV des détections",
                            data=f.read(),
                            file_name=f"detections_run{run_id}.csv",
                            mime="text/csv"
                        )

                    # ← Mise à jour du FPS dans la base
                    session = SessionLocal()
                    video_enr = session.get(Video, video_id)
                    if video_enr:
                        video_enr.fps = resultats["fps"]
                        session.commit()
                    session.close()

    # ------------------------------------------------------------------
    # PAGE 2 : Historique des analyses
    # ------------------------------------------------------------------
    elif page == "Historique":
        st.header("📋 Historique de mes analyses")

        session = SessionLocal()
        runs = (
            session.query(Run)
            .filter_by(user_id=st.session_state.user_id)
            .order_by(Run.date_lancement.desc())
            .all()
        )

        if not runs:
            st.info("Aucune analyse effectuée pour l'instant.")
        else:
            for run in runs:
                with st.expander(f"Run #{run.id} — {run.date_lancement.strftime('%Y-%m-%d %H:%M')} — {run.video.titre}"):
                    st.markdown(f"**Modèle :** {run.modele_yolo}")
                    st.markdown(f"**Seuil de confiance :** {run.seuil_confiance}")

                    # ← Récupération des résumés de comptage pour ce run
                    resumés = session.query(CountSummary).filter_by(run_id=run.id).all()
                    if resumés:
                        st.table([
                            {"Classe": r.classe, "Objets comptés": r.total}
                            for r in resumés if r.total > 0
                        ])
                    else:
                        st.markdown("*Pas encore de résultats enregistrés.*")

        session.close()