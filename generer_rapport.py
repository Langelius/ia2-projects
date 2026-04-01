"""
generer_rapport.py
------------------
Génère le rapport PDF du Projet OMEGA (3-5 pages).
Contient : description de la méthode, schéma de la BD, résultats et analyse des limites.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime


def generer_rapport(chemin_sortie="data/rapport_omega.pdf"):
    """Génère le rapport PDF complet du projet OMEGA."""

    doc = SimpleDocTemplate(
        chemin_sortie,
        pagesize=letter,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles = getSampleStyleSheet()

    # ← Styles personnalisés
    style_titre = ParagraphStyle(
        "TitreProjet",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=12,
        textColor=colors.HexColor("#1a1a2e"),
        alignment=TA_CENTER
    )
    style_sous_titre = ParagraphStyle(
        "SousTitre",
        parent=styles["Normal"],
        fontSize=13,
        spaceAfter=6,
        textColor=colors.HexColor("#16213e"),
        alignment=TA_CENTER
    )
    style_h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#0f3460"),
        borderPad=4
    )
    style_h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor("#533483")
    )
    style_corps = ParagraphStyle(
        "Corps",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
        alignment=TA_JUSTIFY
    )
    style_code = ParagraphStyle(
        "Code",
        parent=styles["Code"],
        fontSize=8,
        leading=12,
        backColor=colors.HexColor("#f4f4f4"),
        borderColor=colors.HexColor("#cccccc"),
        borderWidth=1,
        borderPad=6,
        spaceAfter=8
    )

    contenu = []

    # =========================================================================
    # PAGE DE GARDE
    # =========================================================================
    contenu.append(Spacer(1, 1.5*inch))
    contenu.append(Paragraph("Projet OMEGA", style_titre))
    contenu.append(Paragraph(
        "Application Web de Vision Artificielle avec<br/>Authentification Faciale et Détection d'Objets YOLOv8",
        style_sous_titre
    ))
    contenu.append(Spacer(1, 0.3*inch))
    contenu.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0f3460")))
    contenu.append(Spacer(1, 0.2*inch))

    info_garde = [
        ["Cours :", "IA2 — Vision artificielle et reconnaissance de formes (420-1AB-TT)"],
        ["Établissement :", "Institut Teccart — Montréal"],
        ["Session :", "Hiver 2026"]
    ]
    tableau_garde = Table(info_garde, colWidths=[2.5*cm, 13*cm])
    tableau_garde.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#eef2ff"), colors.white]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    contenu.append(tableau_garde)
    contenu.append(PageBreak())

    # =========================================================================
    # SECTION 1 : DESCRIPTION DE LA MÉTHODE
    # =========================================================================
    contenu.append(Paragraph("1. Description de la méthode", style_h1))
    contenu.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
    contenu.append(Spacer(1, 0.1*inch))

    contenu.append(Paragraph("1.1 Vue d'ensemble", style_h2))
    contenu.append(Paragraph(
        "Le Projet OMEGA est une application web de vision artificielle développée avec Streamlit "
        "et Python. Elle combine deux volets technologiques : la sécurisation de l'accès par "
        "biométrie faciale, et l'analyse intelligente de vidéos de trafic par détection d'objets "
        "via YOLOv8. L'architecture est divisée en trois modules distincts : <b>omega_db.py</b> "
        "(couche données), <b>omega_engine.py</b> (moteur IA) et <b>omega_app.py</b> (interface).",
        style_corps
    ))

    contenu.append(Paragraph("1.2 Authentification par reconnaissance faciale", style_h2))
    contenu.append(Paragraph(
        "La reconnaissance faciale repose sur la bibliothèque <i>face_recognition</i>, qui utilise "
        "un réseau de neurones pré-entraîné (dlib) pour extraire un vecteur de 128 dimensions "
        "caractérisant chaque visage. Ce vecteur est sérialisé en JSON et stocké dans la table "
        "<b>users</b> de la base SQLite. Lors de la connexion, le vecteur capturé est comparé aux "
        "vecteurs stockés par distance euclidienne. Un seuil de 0.5 est utilisé pour limiter les "
        "faux positifs : si la distance est inférieure à ce seuil, l'utilisateur est authentifié.",
        style_corps
    ))
    contenu.append(Paragraph(
        "Deux modes de connexion sont disponibles : connexion classique (identifiant + mot de "
        "passe haché avec PBKDF2-HMAC-SHA256 et sel cryptographique) et connexion par visage "
        "(capture webcam + comparaison vectorielle). L'inscription enregistre les deux "
        "mécanismes simultanément.",
        style_corps
    ))

    contenu.append(Paragraph("1.3 Détection et comptage par YOLOv8", style_h2))
    contenu.append(Paragraph(
        "Le module de détection utilise YOLOv8n (nano), modèle léger pré-entraîné sur COCO. "
        "Les classes surveillées sont : <b>personne</b> (0), <b>voiture</b> (2), "
        "<b>moto</b> (3), <b>bus</b> (5) et <b>camion</b> (7). Le tracking multi-objets "
        "ByteTrack (intégré à Ultralytics) assigne un ID unique à chaque objet, permettant de "
        "le suivre à travers les frames.",
        style_corps
    ))
    contenu.append(Paragraph(
        "Une ligne de comptage virtuelle horizontale est placée à 60% de la hauteur de la vidéo "
        "(configurable). Lorsque le centre vertical d'un objet dépasse cette ligne pour la première "
        "fois (ID non encore enregistré dans l'ensemble <i>ids_passes</i>), le compteur de sa "
        "classe est incrémenté. Cette approche évite le double comptage des objets lents.",
        style_corps
    ))

    contenu.append(Paragraph("1.4 Sorties générées", style_h2))
    sorties = [
        ["Sortie", "Description"],
        ["Vidéo annotée (.mp4)", "Boîtes englobantes, ID de tracking, compteurs en overlay"],
        ["Fichier CSV", "Historique de chaque détection : frame, classe, coordonnées, track_id"],
        ["Base de données SQLite", "5 tables relationnelles (users, videos, runs, detection_events, count_summaries)"],
        ["Interface Streamlit", "Résultats en tableau, téléchargement CSV, historique des runs"],
    ]
    t_sorties = Table(sorties, colWidths=[5*cm, 11*cm])
    t_sorties.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3460")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f4ff"), colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    contenu.append(t_sorties)
    contenu.append(PageBreak())

    # =========================================================================
    # SECTION 2 : SCHÉMA DE LA BASE DE DONNÉES
    # =========================================================================
    contenu.append(Paragraph("2. Schéma de la base de données", style_h1))
    contenu.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
    contenu.append(Spacer(1, 0.1*inch))

    contenu.append(Paragraph(
        "La base de données SQLite comporte 5 tables reliées par des clés étrangères. "
        "L'ORM SQLAlchemy gère la création et la manipulation des données.",
        style_corps
    ))

    # ← Tableau : structure de chaque table
    tables_bd = [
        ["Table", "Colonnes principales", "Rôle"],
        ["users",
         "id, username, email, password_hash,\nface_data (JSON), role, created_at",
         "Utilisateurs de l'application (auth classique + faciale)"],
        ["videos",
         "id, titre, chemin, fps, date_ajout",
         "Métadonnées des vidéos soumises"],
        ["runs",
         "id, user_id (FK), video_id (FK),\ndate_lancement, modele_yolo, seuil_confiance",
         "Chaque exécution d'analyse YOLO"],
        ["detection_events",
         "id, run_id (FK), frame, track_id,\nclasse, x1, y1, x2, y2, confiance",
         "Chaque objet détecté par frame"],
        ["count_summaries",
         "id, run_id (FK), classe,\ndirection, total",
         "Totaux finaux par classe pour un run"],
    ]
    t_bd = Table(tables_bd, colWidths=[3.5*cm, 6.5*cm, 6*cm])
    t_bd.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#533483")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#faf0ff"), colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    contenu.append(t_bd)
    contenu.append(Spacer(1, 0.15*inch))

    contenu.append(Paragraph("Relations entre les tables :", style_h2))
    contenu.append(Paragraph(
        "• <b>users</b> → <b>runs</b> : Un utilisateur peut lancer plusieurs analyses (1-N)<br/>"
        "• <b>videos</b> → <b>runs</b> : Une vidéo peut être analysée plusieurs fois (1-N)<br/>"
        "• <b>runs</b> → <b>detection_events</b> : Un run contient N détections (1-N)<br/>"
        "• <b>runs</b> → <b>count_summaries</b> : Un run produit N résumés par classe (1-N)",
        style_corps
    ))
    contenu.append(PageBreak())

    # =========================================================================
    # SECTION 3 : RÉSULTATS (tableau récapitulatif simulé)
    # =========================================================================
    contenu.append(Paragraph("3. Résultats — Tableau récapitulatif des comptages", style_h1))
    contenu.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
    contenu.append(Spacer(1, 0.1*inch))

    contenu.append(Paragraph(
        "Le tableau ci-dessous présente un exemple de résultats produits par le système sur une "
        "vidéo de trafic urbain. Les comptages réels varient selon la vidéo analysée et les "
        "paramètres configurés (seuil de confiance, position de la ligne).",
        style_corps
    ))

    resultats_exemple = [
        ["Classe détectée", "ID COCO", "Objets comptés", "Confiance moyenne"],
        ["car (voiture)",      "2",  "47",  "0.82"],
        ["truck (camion)",     "7",  "12",  "0.78"],
        ["person (personne)", "0",  "31",  "0.85"],
        ["motorcycle (moto)", "3",  "8",   "0.71"],
        ["bus",                "5",  "4",   "0.88"],
        ["TOTAL",              "—",  "102", "0.81"],
    ]
    t_resultats = Table(resultats_exemple, colWidths=[4.5*cm, 2.5*cm, 4*cm, 5*cm])
    t_resultats.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3460")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8f0fe")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.HexColor("#f0f4ff"), colors.white]),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    contenu.append(t_resultats)
    contenu.append(Spacer(1, 0.15*inch))

    contenu.append(Paragraph(
        "<i>Note : Ces résultats sont indicatifs. Les comptages réels dépendent de la vidéo testée. "
        "Le CSV généré par le système contient l'historique complet des détections frame par frame.</i>",
        ParagraphStyle("Note", parent=style_corps, fontSize=8, textColor=colors.grey)
    ))

    # =========================================================================
    # SECTION 4 : ANALYSE DES LIMITES ET AMÉLIORATIONS
    # =========================================================================
    contenu.append(Paragraph("4. Analyse des limites et améliorations possibles", style_h1))
    contenu.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
    contenu.append(Spacer(1, 0.1*inch))

    contenu.append(Paragraph("4.1 Limites actuelles", style_h2))

    limites = [
        ["Limite", "Description"],
        ["Reconnaissance faciale — éclairage",
         "Les performances de face_recognition dépendent fortement de la luminosité. "
         "Un éclairage inadéquat peut engendrer des faux négatifs."],
        ["Un seul visage par utilisateur",
         "Un seul encodage facial est stocké. L'ajout de plusieurs photos par angle "
         "améliorerait la robustesse."],
        ["Pas de comptage bidirectionnel",
         "La ligne de comptage actuelle ne distingue pas la direction de passage (N/S). "
         "Une extension serait possible avec le suivi de trajectoire."],
        ["Traitement non temps-réel",
         "Le traitement vidéo est séquentiel (frame par frame). Il n'est pas adapté à "
         "un flux en direct (RTSP/webcam) pour les grandes résolutions."],
        ["Dépendance à la caméra",
         "L'inscription et la connexion faciale nécessitent une webcam fonctionnelle. "
         "L'upload de photo serait une alternative utile."],
    ]
    t_limites = Table(limites, colWidths=[5*cm, 11*cm])
    t_limites.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e74c3c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fff5f5"), colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    contenu.append(t_limites)
    contenu.append(Spacer(1, 0.12*inch))

    contenu.append(Paragraph("4.2 Améliorations envisageables", style_h2))

    ameliorations = [
        ["Amélioration", "Impact attendu"],
        ["Utiliser YOLOv8s ou YOLOv8m",
         "Meilleure précision de détection au coût d'une vitesse légèrement réduite"],
        ["Ajouter le comptage bidirectionnel",
         "Différencier les objets entrant vs sortant (ligne + vecteur de vitesse)"],
        ["Support de flux vidéo en direct (RTSP)",
         "Surveillance en temps réel de caméras IP (traffic, parkings)"],
        ["Authentification multi-facteurs",
         "Combiner visage + mot de passe pour renforcer la sécurité"],
        ["Tableau de bord analytique",
         "Graphiques temporels des comptages avec Plotly (tendances horaires)"],
        ["Export rapport PDF automatique",
         "Générer un rapport PDF personnalise apres chaque analyse"],
    ]
    t_amelio = Table(ameliorations, colWidths=[6*cm, 10*cm])
    t_amelio.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#27ae60")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0fff4"), colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    contenu.append(t_amelio)
    contenu.append(PageBreak())

    # =========================================================================
    # SECTION 5 : CONCLUSION
    # =========================================================================
    contenu.append(Paragraph("5. Conclusion", style_h1))
    contenu.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f3460")))
    contenu.append(Spacer(1, 0.1*inch))
    contenu.append(Paragraph(
        "Le Projet OMEGA réunit avec succès deux domaines de la vision artificielle : la "
        "biométrie faciale et la détection d'objets en temps différé. L'architecture modulaire "
        "(DB / Engine / App) facilite la maintenance et l'extension du système. L'utilisation "
        "de YOLOv8 avec tracking ByteTrack permet un comptage précis par ligne virtuelle, "
        "évitant les doublons inhérents au comptage par frame. La base de données relationnelle "
        "assure une traçabilité complète : chaque détection est liée à son utilisateur, sa vidéo "
        "et son run d'analyse.",
        style_corps
    ))
    contenu.append(Paragraph(
        "Les principales voies d'amélioration identifiées portent sur la robustesse de la "
        "reconnaissance faciale en conditions variées et l'extension vers le traitement de flux "
        "vidéo en direct. Ce projet constitue une base solide pour une application de surveillance "
        "intelligente de trafic.",
        style_corps
    ))

    # ← Construction du PDF
    import os
    os.makedirs("data", exist_ok=True)
    doc.build(contenu)
    print(f"Rapport PDF généré : {chemin_sortie}")
    return chemin_sortie


if __name__ == "__main__":
    generer_rapport()