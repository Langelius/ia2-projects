"""
generer_rapport.py
------------------
Génère le rapport PDF du Projet OMEGA (5 pages).
Format A4, marges 2 cm, zone utile = 17 cm.

RÈGLE CRITIQUE : chaque cellule de tableau est un Paragraph, jamais une str brute.
Cela garantit le retour à la ligne automatique et évite tout débordement de contenu.
"""

import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)

# ← Largeur utilisable sur A4 avec marges de 2 cm de chaque côté
LARGEUR_UTILE = 17 * cm


# =============================================================================
# HELPERS
# =============================================================================

def _styles():
    """Initialise et retourne tous les styles typographiques du rapport."""
    base = getSampleStyleSheet()

    # ← Style pour cellule d'en-tête de tableau (fond coloré, texte blanc)
    entete = ParagraphStyle(
        "CellEntete", parent=base["Normal"],
        fontSize=8, leading=11,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        wordWrap="CJK"  # ← active le retour à la ligne automatique
    )
    # ← Style pour cellule de corps de tableau
    cellule = ParagraphStyle(
        "CellCorps", parent=base["Normal"],
        fontSize=8, leading=11,
        textColor=colors.HexColor("#222222"),
        fontName="Helvetica",
        wordWrap="CJK"  # ← active le retour à la ligne automatique
    )
    # ← Style pour cellule de corps gras (ligne TOTAL, colonne clé)
    cellule_bold = ParagraphStyle(
        "CellBold", parent=base["Normal"],
        fontSize=8, leading=11,
        textColor=colors.HexColor("#222222"),
        fontName="Helvetica-Bold",
        wordWrap="CJK"
    )

    autres = {
        "titre":      ParagraphStyle("Titre",     parent=base["Title"],   fontSize=24, spaceAfter=10,
                                     textColor=colors.HexColor("#0f3460"), alignment=TA_CENTER),
        "sous_titre": ParagraphStyle("SousTitre", parent=base["Normal"],  fontSize=12, spaceAfter=4,
                                     leading=16,  textColor=colors.HexColor("#16213e"), alignment=TA_CENTER),
        "garde":      ParagraphStyle("Garde",     parent=base["Normal"],  fontSize=10, leading=14,
                                     textColor=colors.HexColor("#333333"), alignment=TA_LEFT),
        "h1":         ParagraphStyle("H1",        parent=base["Heading1"],fontSize=13, spaceBefore=14,
                                     spaceAfter=6,textColor=colors.HexColor("#0f3460"), borderPad=0),
        "h2":         ParagraphStyle("H2",        parent=base["Heading2"],fontSize=11, spaceBefore=8,
                                     spaceAfter=4,textColor=colors.HexColor("#533483")),
        "corps":      ParagraphStyle("Corps",     parent=base["Normal"],  fontSize=9,  leading=13,
                                     spaceAfter=5,alignment=TA_JUSTIFY),
        "note":       ParagraphStyle("Note",      parent=base["Normal"],  fontSize=7.5,leading=11,
                                     spaceAfter=4,textColor=colors.grey,  alignment=TA_JUSTIFY),
        "puce":       ParagraphStyle("Puce",      parent=base["Normal"],  fontSize=9,  leading=13,
                                     spaceAfter=3,leftIndent=12,          alignment=TA_JUSTIFY),
    }
    return entete, cellule, cellule_bold, autres


def _tableau(lignes, col_widths, couleur_entete,
             s_entete, s_corps, s_corps_bold=None,
             lignes_totaux=None):
    """
    Construit un Table ReportLab dont CHAQUE cellule est un Paragraph.
    Paramètres :
        lignes        : liste de listes de str (ligne 0 = en-tête)
        col_widths    : liste de largeurs en points (doit sommer à LARGEUR_UTILE)
        couleur_entete: HexColor pour le fond de l'en-tête
        s_entete      : style Paragraph pour l'en-tête
        s_corps       : style Paragraph pour le corps
        s_corps_bold  : style Paragraph pour les lignes spéciales (ex. TOTAL)
        lignes_totaux : indices des lignes à mettre en gras + fond bleu clair
    """
    lignes_totaux = lignes_totaux or []

    # ← Conversion de toutes les cellules en Paragraph
    data = []
    for i, ligne in enumerate(lignes):
        if i == 0:
            # ← En-tête : fond coloré, texte blanc
            data.append([Paragraph(str(cel), s_entete) for cel in ligne])
        elif i in lignes_totaux and s_corps_bold:
            # ← Ligne spéciale (TOTAL) : gras
            data.append([Paragraph(str(cel), s_corps_bold) for cel in ligne])
        else:
            data.append([Paragraph(str(cel), s_corps) for cel in ligne])

    t = Table(data, colWidths=col_widths, repeatRows=1)  # ← repeatRows répète l'en-tête si saut de page

    style = TableStyle([
        # En-tête
        ("BACKGROUND",    (0, 0), (-1,  0), couleur_entete),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#f5f5f5"), colors.white]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("BOX",           (0, 0), (-1, -1), 0.8, couleur_entete),
        # Alignement et espacement — identiques pour toutes les cellules
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ])

    # ← Fond bleu clair pour les lignes de total
    for idx in lignes_totaux:
        style.add("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#e8f0fe"))

    t.setStyle(style)
    return t


# =============================================================================
# FONCTION PRINCIPALE
# =============================================================================

def generer_rapport(
    chemin_sortie="data/rapport_omega.pdf",
    donnees_reelles=None,   # ← liste de dicts issus de l'historique Streamlit
    nom_video=None,         # ← nom de la vidéo analysée
    date_analyse=None,      # ← date du run
    modele=None,            # ← nom du modèle YOLO utilisé
    seuil=None,             # ← seuil de confiance utilisé
    run_id=None             # ← identifiant du run
):
    """
    Génère le rapport PDF du projet OMEGA.
    Si donnees_reelles est fourni, la section résultats utilise les vraies données
    du run sélectionné au lieu des valeurs indicatives.
    """

    os.makedirs("data", exist_ok=True)

    doc = SimpleDocTemplate(
        chemin_sortie,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm,   bottomMargin=2*cm,
        title="Rapport Projet OMEGA",
        author="Teccart IA2 H2026"
    )

    s_ent, s_cel, s_cel_b, S = _styles()  # ← S = dict des autres styles

    c = []  # ← liste du contenu (flowables)

    # =========================================================================
    # PAGE DE GARDE
    # =========================================================================
    c.append(Spacer(1, 3*cm))

    bloc_titre = Table(
        [[Paragraph("Projet OMEGA", S["titre"])],
         [Paragraph("Application Web de Vision Artificielle<br/>"
                    "Authentification Faciale et Detection d'Objets avec YOLOv8",
                    S["sous_titre"])]],
        colWidths=[LARGEUR_UTILE]
    )
    bloc_titre.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#eef2ff")),
        ("BOX",           (0, 0), (-1, -1), 2, colors.HexColor("#0f3460")),
        ("TOPPADDING",    (0, 0), (-1, -1), 20),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
    ]))
    c.append(bloc_titre)
    c.append(Spacer(1, 1.2*cm))

    # ← Tableau page de garde : toutes les cellules sont des Paragraph  (4 + 13 = 17 cm)
    garde_data = [
        [Paragraph("<b>Cours :</b>",          S["garde"]),
         Paragraph("IA2 - Vision artificielle et reconnaissance de formes (420-1AB-TT)", S["garde"])],
        [Paragraph("<b>Etablissement :</b>",  S["garde"]),
         Paragraph("Institut Teccart - Montreal", S["garde"])],
        [Paragraph("<b>Session :</b>",        S["garde"]),
         Paragraph("Hiver 2026", S["garde"])],
        [Paragraph("<b>Date :</b>",           S["garde"]),
         Paragraph(datetime.now().strftime("%d %B %Y"), S["garde"])],
    ]
    t_garde = Table(garde_data, colWidths=[4*cm, 13*cm])
    t_garde.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [colors.HexColor("#f0f4ff"), colors.white]),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("BOX",           (0, 0), (-1, -1), 0.8, colors.HexColor("#0f3460")),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, colors.HexColor("#cccccc")),
    ]))
    c.append(t_garde)
    c.append(PageBreak())

    # =========================================================================
    # SECTION 1 - DESCRIPTION DE LA MÉTHODE
    # =========================================================================
    c.append(Paragraph("1. Description de la methode", S["h1"]))
    c.append(HRFlowable(width=LARGEUR_UTILE, thickness=1.5,
                        color=colors.HexColor("#0f3460"), spaceAfter=6))

    c.append(Paragraph("1.1 Vue d'ensemble", S["h2"]))
    c.append(Paragraph(
        "Le Projet OMEGA est une application web de vision artificielle developpee avec "
        "Streamlit et Python. Elle combine deux volets : la securisation de l'acces par "
        "biometrie faciale, et l'analyse intelligente de videos de trafic par detection "
        "d'objets via YOLOv8. L'architecture est divisee en trois modules : "
        "<b>omega_db.py</b> (couche donnees), <b>omega_engine.py</b> (moteur IA) "
        "et <b>omega_app.py</b> (interface Streamlit).", S["corps"]))

    c.append(Paragraph("1.2 Authentification", S["h2"]))
    c.append(Paragraph("Deux modes de connexion sont disponibles :", S["corps"]))
    c.append(Paragraph(
        "• <b>Classique :</b> identifiant + mot de passe hache avec PBKDF2-HMAC-SHA256 "
        "et sel aleatoire de 16 octets.", S["puce"]))
    c.append(Paragraph(
        "• <b>Faciale :</b> capture webcam, extraction d'un vecteur de 128 dimensions "
        "via face_recognition (reseau dlib), comparaison par distance euclidienne (seuil 0.5).",
        S["puce"]))

    c.append(Paragraph("1.3 Detection et comptage par YOLOv8", S["h2"]))
    c.append(Paragraph(
        "Le module de detection utilise YOLOv8n (nano), pre-entraine sur COCO. "
        "Le tracking ByteTrack assigne un ID unique a chaque objet. "
        "Une ligne de comptage virtuelle horizontale (configurable) "
        "incremente le compteur d'une classe des que le centre d'un objet la franchit, "
        "en evitant les doublons grace a un ensemble d'IDs deja comptes.", S["corps"]))

    c.append(Paragraph("1.4 Sorties generees", S["h2"]))
    # ← (5 + 12 = 17 cm)
    c.append(_tableau(
        [["Sortie",               "Description"],
         ["Video annotee (.mp4)", "Boites englobantes, ID de tracking, compteurs en overlay"],
         ["Fichier CSV",          "Historique de chaque detection : frame, classe, coords, track_id"],
         ["Base SQLite",          "5 tables relationnelles (users, videos, runs, detection_events, count_summaries)"],
         ["Interface Streamlit",  "Resultats en tableau, telechargement CSV, historique des runs"]],
        [5*cm, 12*cm], colors.HexColor("#0f3460"), s_ent, s_cel
    ))
    c.append(PageBreak())

    # =========================================================================
    # SECTION 2 - SCHÉMA DE LA BASE DE DONNÉES
    # =========================================================================
    c.append(Paragraph("2. Schema de la base de donnees", S["h1"]))
    c.append(HRFlowable(width=LARGEUR_UTILE, thickness=1.5,
                        color=colors.HexColor("#0f3460"), spaceAfter=6))
    c.append(Paragraph(
        "La base SQLite comporte 5 tables reliees par cles etrangeres. "
        "L'ORM SQLAlchemy 2.x gere la creation et la manipulation des donnees.", S["corps"]))

    # ← (3.5 + 5.5 + 8 = 17 cm)
    c.append(_tableau(
        [["Table",             "Colonnes principales",
                               "Role"],
         ["users",             "id, username, email, password_hash, face_data, role, created_at",
                               "Comptes utilisateurs (auth classique + faciale)"],
         ["videos",            "id, titre, chemin, fps, date_ajout",
                               "Metadonnees des videos soumises"],
         ["runs",              "id, user_id (FK), video_id (FK), date_lancement, modele_yolo, seuil_confiance",
                               "Chaque execution d'analyse YOLO"],
         ["detection_events",  "id, run_id (FK), frame, track_id, classe, x1, y1, x2, y2, confiance",
                               "Chaque objet detecte par frame"],
         ["count_summaries",   "id, run_id (FK), classe, direction, total",
                               "Totaux finaux par classe et direction"]],
        [3.5*cm, 5.5*cm, 8*cm], colors.HexColor("#533483"), s_ent, s_cel
    ))
    c.append(Spacer(1, 0.4*cm))

    c.append(KeepTogether([
        Paragraph("Relations entre les tables :", S["h2"]),
        Paragraph("• <b>users</b> (1) -> (N) <b>runs</b> : un utilisateur lance plusieurs analyses", S["puce"]),
        Paragraph("• <b>videos</b> (1) -> (N) <b>runs</b> : une video peut etre analysee plusieurs fois", S["puce"]),
        Paragraph("• <b>runs</b> (1) -> (N) <b>detection_events</b> : un run contient N detections", S["puce"]),
        Paragraph("• <b>runs</b> (1) -> (N) <b>count_summaries</b> : un run produit N resumes par classe", S["puce"]),
    ]))
    c.append(PageBreak())

    # =========================================================================
    # SECTION 3 - RÉSULTATS
    # =========================================================================
    c.append(Paragraph("3. Resultats - Tableau recapitulatif des comptages", S["h1"]))
    c.append(HRFlowable(width=LARGEUR_UTILE, thickness=1.5,
                        color=colors.HexColor("#0f3460"), spaceAfter=6))

    if donnees_reelles and run_id:
        # ← Contexte du run
        ctx = []
        if nom_video:    ctx.append(f"Video : <b>{nom_video}</b>")
        if date_analyse: ctx.append(f"Date : <b>{date_analyse}</b>")
        if modele:       ctx.append(f"Modele : <b>{modele}</b>")
        if seuil is not None: ctx.append(f"Seuil : <b>{seuil}</b>")
        if ctx:
            c.append(Paragraph("  |  ".join(ctx), S["corps"]))
        c.append(Paragraph(f"Resultats reels du Run #{run_id} issus de la base de donnees.",
                           S["corps"]))
        c.append(Spacer(1, 0.2*cm))

        # ← Construction des lignes depuis les données réelles
        lignes = [["Classe", "ID COCO", "Objets comptes", "Detections totales", "Confiance moy."]]
        total_obj = total_det = 0
        for row in donnees_reelles:
            lignes.append([
                str(row.get("Classe", "-")),
                str(row.get("ID COCO", "-")),
                str(row.get("Objets comptés", 0)),
                str(row.get("Détections totales", 0)),
                str(row.get("Confiance moyenne", "-")),
            ])
            total_obj += int(row.get("Objets comptés", 0))
            total_det += int(row.get("Détections totales", 0))
        lignes.append(["TOTAL", "-", str(total_obj), str(total_det), "-"])

        # ← (4 + 2.5 + 3 + 4 + 3.5 = 17 cm)
        c.append(_tableau(lignes, [4*cm, 2.5*cm, 3*cm, 4*cm, 3.5*cm],
                          colors.HexColor("#0f3460"), s_ent, s_cel, s_cel_b,
                          lignes_totaux=[len(lignes) - 1]))
        c.append(Spacer(1, 0.2*cm))
        c.append(Paragraph(
            f"<i>Donnees reelles extraites de la base omega_system.db - Run #{run_id}.</i>",
            S["note"]))

    else:
        # ← Données indicatives
        c.append(Paragraph(
            "Le tableau ci-dessous presente un exemple de resultats indicatifs. "
            "Generez le rapport depuis la page Historique de l'application pour obtenir "
            "les vraies donnees d'un run.", S["corps"]))
        c.append(Spacer(1, 0.2*cm))

        lignes_ind = [
            ["Classe",             "ID COCO", "Objets comptes", "Detections totales", "Confiance moy."],
            ["car (voiture)",      "2",       "47",             "312",                "0.82"],
            ["truck (camion)",     "7",       "12",             "89",                 "0.78"],
            ["person (personne)", "0",       "31",             "210",                "0.85"],
            ["motorcycle (moto)", "3",       "8",              "54",                 "0.71"],
            ["bus",                "5",       "4",              "28",                 "0.88"],
            ["TOTAL",              "-",       "102",            "693",                "0.81"],
        ]
        # ← (4 + 2.5 + 3 + 4 + 3.5 = 17 cm)
        c.append(_tableau(lignes_ind, [4*cm, 2.5*cm, 3*cm, 4*cm, 3.5*cm],
                          colors.HexColor("#0f3460"), s_ent, s_cel, s_cel_b,
                          lignes_totaux=[len(lignes_ind) - 1]))
        c.append(Spacer(1, 0.2*cm))
        c.append(Paragraph(
            "<i>Note : resultats indicatifs sur une video de test.</i>", S["note"]))

    c.append(Spacer(1, 0.5*cm))

    # =========================================================================
    # SECTION 4 - LIMITES ET AMÉLIORATIONS
    # =========================================================================
    c.append(Paragraph("4. Analyse des limites et ameliorations", S["h1"]))
    c.append(HRFlowable(width=LARGEUR_UTILE, thickness=1.5,
                        color=colors.HexColor("#0f3460"), spaceAfter=6))

    c.append(Paragraph("4.1 Limites actuelles", S["h2"]))
    # ← (5 + 12 = 17 cm)
    c.append(_tableau(
        [["Limite",                        "Description"],
         ["Eclairage variable",             "Les performances de face_recognition dependent fortement de la luminosite. Un eclairage inadapte provoque des faux negatifs."],
         ["Un seul encodage par compte",    "Un seul vecteur facial stocke par utilisateur. Plusieurs angles de prise de vue amelioreraient la robustesse de la reconnaissance."],
         ["Pas de comptage bidirectionnel", "La ligne de comptage ne distingue pas la direction de passage (Nord/Sud). Une extension est possible avec le suivi de trajectoire."],
         ["Traitement non temps-reel",      "L'analyse est sequentielle frame par frame. Elle n'est pas adaptee aux flux video en direct (RTSP) pour les hautes resolutions."],
         ["Camera obligatoire",             "L'inscription faciale necessite une webcam fonctionnelle. L'upload d'une photo serait une alternative utile."]],
        [5*cm, 12*cm], colors.HexColor("#c0392b"), s_ent, s_cel
    ))
    c.append(Spacer(1, 0.4*cm))

    c.append(Paragraph("4.2 Ameliorations envisageables", S["h2"]))
    # ← (6 + 11 = 17 cm)
    c.append(_tableau(
        [["Amelioration",                   "Impact attendu"],
         ["Utiliser YOLOv8s ou YOLOv8m",    "Meilleure precision de detection, au cout d'une vitesse legerement reduite."],
         ["Comptage bidirectionnel",         "Differencier les objets entrant vs sortant grace au suivi du vecteur de deplacement."],
         ["Flux video en direct (RTSP)",     "Permettre la surveillance en temps reel de cameras IP (intersections, parkings)."],
         ["Authentification multi-facteurs", "Combiner visage + mot de passe pour renforcer la securite des acces."],
         ["Tableau de bord analytique",      "Ajouter des graphiques Plotly des comptages dans le temps (tendances horaires et journalieres)."]],
        [6*cm, 11*cm], colors.HexColor("#27ae60"), s_ent, s_cel
    ))
    c.append(PageBreak())

    # =========================================================================
    # SECTION 5 - CONCLUSION
    # =========================================================================
    c.append(Paragraph("5. Conclusion", S["h1"]))
    c.append(HRFlowable(width=LARGEUR_UTILE, thickness=1.5,
                        color=colors.HexColor("#0f3460"), spaceAfter=6))
    c.append(Paragraph(
        "Le Projet OMEGA reunit avec succes deux domaines de la vision artificielle : "
        "la biometrie faciale et la detection d'objets en video differee. "
        "L'architecture modulaire (DB / Engine / App) facilite la maintenance et l'extension "
        "du systeme. L'utilisation de YOLOv8 avec tracking ByteTrack permet un comptage "
        "precis par ligne virtuelle, eliminant les doublons inherents a un comptage brut "
        "par frame. La base de donnees relationnelle assure une tracabilite complete : "
        "chaque detection est liee a son utilisateur, sa video et son execution d'analyse.",
        S["corps"]))
    c.append(Spacer(1, 0.2*cm))
    c.append(Paragraph(
        "Les principales voies d'amelioration portent sur la robustesse de la reconnaissance "
        "faciale en conditions variees et l'extension vers le traitement de flux video en direct. "
        "Ce projet constitue une base solide pour une application de surveillance intelligente "
        "de trafic, extensible vers la gestion de stationnements ou la surveillance d'intersections.",
        S["corps"]))

    # ← Construction finale du PDF
    doc.build(c)
    print(f"Rapport PDF genere : {chemin_sortie}")
    return chemin_sortie


if __name__ == "__main__":
    generer_rapport()