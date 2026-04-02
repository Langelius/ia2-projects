"""
omega_engine.py
---------------
Moteur de vision artificielle pour le Projet OMEGA.
Gère deux fonctionnalités principales :
    1. Reconnaissance faciale (encodage + comparaison)
    2. Détection, suivi et comptage d'objets par YOLOv8

Style inspiré des fichiers de cours (Cours9-yolo.py / Cours9-yolo-Advanced.py).
"""

import cv2
import csv
import json
import numpy as np
import face_recognition
from datetime import datetime
from ultralytics import YOLO

from omega_db import SessionLocal, DetectionEvent, CountSummary


# =============================================================================
# CLASSE PRINCIPALE DU MOTEUR IA
# =============================================================================

class OmegaAI:
    """
    Moteur d'intelligence artificielle du système OMEGA.
    Encapsule la détection YOLO et la reconnaissance faciale.
    """

    def __init__(self, chemin_modele="models/yolov8n.pt", seuil_confiance=0.5):
        # ← Chargement du modèle YOLOv8 (téléchargement automatique si absent)
        self.modele = YOLO(chemin_modele)
        self.seuil_confiance = seuil_confiance

        # ← Classes d'objets surveillées (indices COCO)
        # 0=person, 2=car, 3=motorcycle, 5=bus, 7=truck
        self.classes_cibles = {
            0: "person",
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck"
        }

        # ← Couleurs d'annotation par classe (BGR)
        self.couleurs_classes = {
            "person":     (0, 255, 0),    # vert
            "car":        (255, 0, 0),    # bleu
            "motorcycle": (0, 165, 255),  # orange
            "bus":        (0, 0, 255),    # rouge
            "truck":      (128, 0, 128),  # violet
        }

    # -------------------------------------------------------------------------
    # RECONNAISSANCE FACIALE
    # -------------------------------------------------------------------------

    def obtenir_encodage_facial(self, image):
        """
        Extrait le vecteur d'encodage facial (128 dimensions) depuis une image.
        Retourne le vecteur numpy ou None si aucun visage détecté.
        """
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  # ← conversion BGR → RGB requis par face_recognition
        encodages = face_recognition.face_encodings(image_rgb)
        return encodages[0] if encodages else None  # ← retourne le premier visage trouvé


    def comparer_visage(self, encodage_inconnu, encodage_connu, seuil=0.5):
        """
        Compare un visage inconnu avec un encodage stocké.
        Utilise la distance euclidienne avec un seuil configurable.
        Retourne True si les visages correspondent.
        """
        distance = face_recognition.face_distance([encodage_connu], encodage_inconnu)[0]
        return distance < seuil  # ← plus la distance est faible, plus les visages sont similaires


    def capturer_image_webcam(self, index_camera=0):
        """
        Capture une seule image depuis la webcam.
        Retourne l'image (numpy array) ou None en cas d'échec.
        """
        camera = cv2.VideoCapture(index_camera)  # ← ouverture de la caméra
        if not camera.isOpened():
            return None

        reponse, image = camera.read()  # ← capture d'une frame
        camera.release()               # ← bonne pratique : libérer la caméra immédiatement

        return image if reponse else None  # ← retourne l'image seulement si la lecture a réussi


    # -------------------------------------------------------------------------
    # TRAITEMENT VIDÉO (YOLO + COMPTAGE)
    # -------------------------------------------------------------------------

    def traiter_video(self, chemin_video, run_id, ratio_ligne=0.6,
                      pas_frames=1, callback_progression=None):
        """
        Analyse complète d'une vidéo : détection, suivi et comptage par ligne virtuelle.

        Paramètres :
            chemin_video          (str)      : chemin vers le fichier MP4
            run_id                (int)      : identifiant du run pour la base de données
            ratio_ligne           (float)    : position de la ligne de comptage (0.0 à 1.0)
            pas_frames            (int)      : analyser 1 frame sur N (1 = toutes, 2 = une sur deux…)
            callback_progression  (callable) : fonction appelée à chaque frame avec (frame_actuelle, total_frames)
        """
        capture = cv2.VideoCapture(chemin_video)  # ← ouverture de la vidéo

        if not capture.isOpened():
            print("Erreur : impossible d'ouvrir la vidéo")
            return None

        # ← Récupération des propriétés de la vidéo
        largeur      = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        hauteur      = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps          = capture.get(cv2.CAP_PROP_FPS)
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))  # ← nombre total de frames

        # ← Position Y de la ligne de comptage virtuelle
        ligne_y = int(hauteur * ratio_ligne)

        # ← Préparation de la vidéo de sortie annotée
        chemin_sortie = chemin_video.replace(".mp4", "_annote.mp4")
        encodeur = cv2.VideoWriter.fourcc(*"mp4v")  # ← API correcte pour les stubs opencv
        sortie   = cv2.VideoWriter(chemin_sortie, encodeur, fps, (largeur, hauteur))

        # ← Initialisation des compteurs
        compteurs  = {nom: 0 for nom in self.classes_cibles.values()}
        ids_passes = set()  # ← ensemble des IDs ayant déjà traversé la ligne
        evenements = []     # ← liste des détections pour la base de données + CSV

        numero_frame = 0

        while capture.isOpened():
            reponse, image = capture.read()  # ← lecture frame par frame
            if not reponse:
                break  # ← fin de la vidéo

            numero_frame += 1

            # ← Notification de la progression au callback (Streamlit ou autre)
            if callback_progression is not None:
                callback_progression(numero_frame, total_frames)

            # ← Sous-échantillonnage : écrire la frame dans la sortie mais sauter l'inférence YOLO
            if numero_frame % pas_frames != 0:
                sortie.write(image)  # ← on conserve la frame dans la vidéo sans l'annoter
                continue

            # ← Dessin de la ligne de comptage virtuelle (rouge)
            cv2.line(image, (0, ligne_y), (largeur, ligne_y), (0, 0, 255), 2)

            # ← Tracking YOLO avec ByteTrack (persist=True pour conserver les IDs entre frames)
            resultats = self.modele.track(
                image,
                persist=True,
                verbose=False,
                conf=self.seuil_confiance
            )

            # ← Extraction du bloc boxes dans une variable locale pour satisfaire Pyright
            boxes_result = resultats[0].boxes
            if boxes_result is not None and boxes_result.id is not None:

                def _vers_numpy(valeur):
                    """Convertit un Tensor PyTorch ou un ndarray numpy en ndarray numpy."""
                    if hasattr(valeur, "cpu"):
                        return valeur.cpu().numpy()  # ← cas Tensor PyTorch
                    return np.array(valeur)           # ← cas ndarray ou autre

                boites     = _vers_numpy(boxes_result.xyxy)           # ← (x1, y1, x2, y2)
                ids        = _vers_numpy(boxes_result.id).astype(int)  # ← IDs entiers
                classes    = _vers_numpy(boxes_result.cls).astype(int) # ← classes entières
                confiances = _vers_numpy(boxes_result.conf)            # ← scores de confiance

                for boite, obj_id, cls, conf in zip(boites, ids, classes, confiances):
                    # ← Vérification si la classe est dans notre liste de surveillance
                    if cls not in self.classes_cibles:
                        continue

                    nom_classe = self.classes_cibles[cls]
                    x1, y1, x2, y2 = int(boite[0]), int(boite[1]), int(boite[2]), int(boite[3])
                    centre_y = int((y1 + y2) / 2)  # ← centre vertical de la boîte

                    # ← Logique de comptage : incrémente si le centre dépasse la ligne et ID non encore compté
                    if centre_y > ligne_y and obj_id not in ids_passes:
                        compteurs[nom_classe] += 1
                        ids_passes.add(obj_id)

                    # ← Annotation de la boîte sur la frame
                    couleur = self.couleurs_classes.get(nom_classe, (255, 255, 255))
                    cv2.rectangle(image, (x1, y1), (x2, y2), couleur, 2)
                    cv2.putText(
                        image,
                        f"{nom_classe} ID:{obj_id}",
                        (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, couleur, 2
                    )

                    # ← Enregistrement de l'événement pour la DB et le CSV
                    evenements.append({
                        "run_id":   run_id,
                        "frame":    numero_frame,
                        "track_id": obj_id,
                        "classe":   nom_classe,
                        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                        "confiance": round(float(conf), 3)
                    })

            # ← Affichage des compteurs en overlay sur chaque frame
            self._afficher_compteurs_overlay(image, compteurs)

            sortie.write(image)  # ← écriture de la frame annotée dans la vidéo de sortie

        # ← Libération des ressources
        capture.release()
        sortie.release()

        # ← Sauvegarde des événements en base de données
        self._sauvegarder_evenements(evenements, run_id, compteurs)

        # ← Export CSV des détections
        chemin_csv = chemin_video.replace(".mp4", "_detections.csv")
        self._exporter_csv(evenements, chemin_csv)

        return {
            "compteurs":       compteurs,
            "chemin_annote":   chemin_sortie,
            "chemin_csv":      chemin_csv,
            "nb_frames":       numero_frame,
            "fps":             fps
        }


    def _afficher_compteurs_overlay(self, image, compteurs):
        """
        Affiche les compteurs par classe en haut à gauche de la frame.
        Même style que les fichiers de cours (putText blanc sur fond sombre).
        """
        hauteur_ligne = 25
        y_depart = 30

        # ← Fond semi-transparent pour la lisibilité
        overlay = image.copy()
        cv2.rectangle(overlay, (5, 5), (200, y_depart + len(compteurs) * hauteur_ligne), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, image, 0.5, 0, image)  # ← fusion avec transparence

        for i, (classe, total) in enumerate(compteurs.items()):
            cv2.putText(
                image,
                f"{classe}: {total}",
                (10, y_depart + i * hauteur_ligne),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                self.couleurs_classes.get(classe, (255, 255, 255)), 2
            )


    def _sauvegarder_evenements(self, evenements, run_id, compteurs):
        """
        Insère les événements de détection et les résumés de comptage dans la base.
        """
        session = SessionLocal()
        try:
            # ← Insertion des événements de détection (par batch pour les performances)
            for ev in evenements:
                session.add(DetectionEvent(
                    run_id=ev["run_id"],
                    frame=ev["frame"],
                    track_id=ev["track_id"],
                    classe=ev["classe"],
                    x1=ev["x1"], y1=ev["y1"], x2=ev["x2"], y2=ev["y2"],
                    confiance=ev["confiance"]
                ))

            # ← Insertion des totaux finaux par classe
            for classe, total in compteurs.items():
                session.add(CountSummary(
                    run_id=run_id,
                    classe=classe,
                    direction="any",
                    total=total
                ))

            session.commit()  # ← validation de la transaction
        except Exception as e:
            session.rollback()  # ← annulation en cas d'erreur
            print(f"Erreur lors de la sauvegarde en base : {e}")
        finally:
            session.close()


    def _exporter_csv(self, evenements, chemin_csv):
        """
        Exporte l'historique complet des détections dans un fichier CSV.
        """
        if not evenements:
            return

        champs = ["run_id", "frame", "track_id", "classe", "x1", "y1", "x2", "y2", "confiance"]

        with open(chemin_csv, "w", newline="", encoding="utf-8") as fichier_csv:
            writer = csv.DictWriter(fichier_csv, fieldnames=champs)
            writer.writeheader()         # ← écriture de l'en-tête
            writer.writerows(evenements) # ← écriture de toutes les lignes

        print(f"CSV exporté : {chemin_csv}")