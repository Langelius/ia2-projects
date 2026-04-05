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
from sqlalchemy import func

from omega_db import (
    initialiser_base, SessionLocal,
    User, Video, Run, CountSummary, DetectionEvent,
    hacher_mot_de_passe, verifier_mot_de_passe
)
from omega_engine import OmegaAI
from generer_rapport import generer_rapport

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

        col1, col2, col3 = st.columns(3)
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
        with col3:
            pas_frames = st.select_slider(
                "Analyser 1 frame sur :",
                options=[1, 2, 3, 5, 10],
                value=2,
                help="Plus la valeur est grande, plus l'analyse est rapide (mais moins précise)."
            )  # ← sous-échantillonnage : 1=toutes les frames, 2=une sur deux, etc.

        if fichier_video is not None:
            # ← Sauvegarde temporaire de la vidéo uploadée
            chemin_temp = f"data/temp_{fichier_video.name}"
            with open(chemin_temp, "wb") as f:
                f.write(fichier_video.read())

            if st.button("▶️ Démarrer l'analyse"):

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

                # ← Éléments de progression affichés en temps réel
                barre  = st.progress(0, text="Initialisation...")
                statut = st.empty()  # ← zone de texte mise à jour à chaque frame

                def maj_progression(frame_actuelle, total_frames):
                    """Callback appelé par traiter_video() à chaque frame traitée."""
                    if total_frames > 0:
                        pct = frame_actuelle / total_frames
                        barre.progress(
                            min(pct, 1.0),
                            text=f"Frame {frame_actuelle} / {total_frames} — {pct*100:.1f}%"
                        )
                        statut.caption(
                            f"⏱ Traitement en cours... "
                            f"({frame_actuelle} frames analysées sur {total_frames})"
                        )

                # ← Lancement de l'analyse avec callback de progression
                resultats = moteur.traiter_video(
                    chemin_temp, run_id, ratio_ligne,
                    pas_frames=pas_frames,
                    callback_progression=maj_progression
                )

                # ← Nettoyage des éléments de progression
                barre.empty()
                statut.empty()

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

        # ← Dictionnaire ID COCO par classe (constantes du modèle COCO)
        ID_COCO = {
            "person":     0,
            "car":        2,
            "motorcycle": 3,
            "bus":        5,
            "truck":      7,
        }

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
                titre_expander = (
                    f"Run #{run.id} — "
                    f"{run.date_lancement.strftime('%Y-%m-%d %H:%M')} — "
                    f"{run.video.titre}"
                )
                with st.expander(titre_expander):
                    st.markdown(f"**Modèle :** {run.modele_yolo} | **Seuil :** {run.seuil_confiance}")
                    st.divider()

                    # ← Calcul de la confiance moyenne par classe depuis detection_events
                    stats_confiance = (
                        session.query(
                            DetectionEvent.classe,
                            func.avg(DetectionEvent.confiance).label("conf_moy"),
                            func.count(DetectionEvent.id).label("nb_detections")
                        )
                        .filter(DetectionEvent.run_id == run.id)
                        .group_by(DetectionEvent.classe)
                        .all()
                    )

                    # ← Dictionnaire classe → (conf_moy, nb_detections) pour croisement
                    conf_par_classe = {
                        row.classe: (round(float(row.conf_moy), 3), int(row.nb_detections))
                        for row in stats_confiance
                        if row.conf_moy is not None
                    }

                    # ← Résumés de comptage (totaux par classe)
                    resumes = (
                        session.query(CountSummary)
                        .filter_by(run_id=run.id)
                        .all()
                    )

                    classes_detectees = [r for r in resumes if r.total > 0]

                    if classes_detectees:
                        # ← Construction du tableau enrichi
                        tableau = []
                        for r in classes_detectees:
                            conf_moy, nb_det = conf_par_classe.get(r.classe, (None, 0))
                            tableau.append({
                                "Classe":            r.classe,
                                "ID COCO":           ID_COCO.get(r.classe, "—"),
                                "Objets comptés":    r.total,
                                "Détections totales": nb_det,
                                "Confiance moyenne": f"{conf_moy:.3f}" if conf_moy else "—",
                            })

                        st.dataframe(
                            tableau,
                            use_container_width=True,
                            hide_index=True
                        )

                        # ← Bouton pour générer le rapport PDF avec les vraies données de ce run
                        chemin_rapport = f"data/rapport_run_{run.id}.pdf"
                        if st.button(f"📄 Générer le rapport PDF (Run #{run.id})", key=f"rapport_{run.id}"):
                            with st.spinner("Génération du rapport..."):
                                generer_rapport(
                                    chemin_sortie=chemin_rapport,
                                    donnees_reelles=tableau,
                                    nom_video=run.video.titre,
                                    date_analyse=run.date_lancement.strftime("%Y-%m-%d %H:%M"),
                                    modele=run.modele_yolo,
                                    seuil=run.seuil_confiance,
                                    run_id=run.id
                                )
                            with open(chemin_rapport, "rb") as f:
                                st.download_button(
                                    label="⬇️ Télécharger le rapport PDF",
                                    data=f.read(),
                                    file_name=f"rapport_omega_run{run.id}.pdf",
                                    mime="application/pdf",
                                    key=f"dl_rapport_{run.id}"
                                )
                    else:
                        st.markdown("*Aucun objet détecté lors de cette analyse.*")

        session.close()