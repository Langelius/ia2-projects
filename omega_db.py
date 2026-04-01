"""
omega_db.py
-----------
Module de gestion de la base de données pour le Projet OMEGA.
Contient les modèles SQLAlchemy et les fonctions utilitaires de sécurité.

Tables créées :
    - users            : informations des utilisateurs (nom, email, mot de passe, encodage facial)
    - videos           : métadonnées des vidéos analysées
    - runs             : chaque exécution d'analyse YOLO
    - detection_events : chaque objet détecté par frame
    - count_summaries  : statistiques finales par classe
"""

import os
import json
import hashlib
import binascii
from typing import Optional, List
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
)


# ← Base déclarative moderne (SQLAlchemy 2.x) — remplace declarative_base()
class Base(DeclarativeBase):
    pass


# =============================================================================
# MODÈLES / TABLES
# =============================================================================

class User(Base):
    """Table des utilisateurs de l'application."""
    __tablename__ = "users"

    id            : Mapped[int]           = mapped_column(Integer, primary_key=True)
    username      : Mapped[str]           = mapped_column(String(100), unique=True, nullable=False)
    email         : Mapped[Optional[str]] = mapped_column(String(200), unique=True, nullable=True)   # ← ajouté : requis par le projet
    password_hash : Mapped[str]           = mapped_column(String(255), nullable=False)
    face_data     : Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # ← encodage facial sérialisé en JSON (vecteur 128)
    role          : Mapped[str]           = mapped_column(String(50), default="user")  # ← "admin" ou "user"
    created_at    : Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    # ← Relation vers les runs d'analyse lancés par cet utilisateur
    runs: Mapped[List["Run"]] = relationship("Run", back_populates="user")


class Video(Base):
    """Table des vidéos soumises pour analyse."""
    __tablename__ = "videos"

    id         : Mapped[int]           = mapped_column(Integer, primary_key=True)
    titre      : Mapped[str]           = mapped_column(String(255), nullable=False)
    chemin     : Mapped[str]           = mapped_column(String(500), nullable=False)  # ← chemin local du fichier sauvegardé
    fps        : Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    date_ajout : Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)

    # ← Relation vers les runs associés à cette vidéo
    runs: Mapped[List["Run"]] = relationship("Run", back_populates="video")


class Run(Base):
    """Table d'une exécution d'analyse YOLO sur une vidéo."""
    __tablename__ = "runs"

    id              : Mapped[int]      = mapped_column(Integer, primary_key=True)
    user_id         : Mapped[int]      = mapped_column(Integer, ForeignKey("users.id"), nullable=False)   # ← lié à l'utilisateur
    video_id        : Mapped[int]      = mapped_column(Integer, ForeignKey("videos.id"), nullable=False)  # ← lié à la vidéo
    date_lancement  : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    modele_yolo     : Mapped[str]      = mapped_column(String(100), default="yolov8n.pt")
    seuil_confiance : Mapped[float]    = mapped_column(Float, default=0.5)

    # ← Relations bidirectionnelles
    user             : Mapped["User"]              = relationship("User", back_populates="runs")
    video            : Mapped["Video"]             = relationship("Video", back_populates="runs")
    detection_events : Mapped[List["DetectionEvent"]] = relationship("DetectionEvent", back_populates="run")
    count_summaries  : Mapped[List["CountSummary"]]   = relationship("CountSummary", back_populates="run")


class DetectionEvent(Base):
    """Table de chaque objet détecté dans une frame donnée."""
    __tablename__ = "detection_events"

    id        : Mapped[int]            = mapped_column(Integer, primary_key=True)
    run_id    : Mapped[int]            = mapped_column(Integer, ForeignKey("runs.id"), nullable=False)
    frame     : Mapped[int]            = mapped_column(Integer, nullable=False)  # ← numéro de frame
    track_id  : Mapped[Optional[int]]  = mapped_column(Integer, nullable=True)   # ← ID de tracking multi-objets
    classe    : Mapped[str]            = mapped_column(String(50), nullable=False)
    x1        : Mapped[Optional[float]] = mapped_column(Float)  # ← coordonnées de la boîte englobante
    y1        : Mapped[Optional[float]] = mapped_column(Float)
    x2        : Mapped[Optional[float]] = mapped_column(Float)
    y2        : Mapped[Optional[float]] = mapped_column(Float)
    confiance : Mapped[Optional[float]] = mapped_column(Float)

    run: Mapped["Run"] = relationship("Run", back_populates="detection_events")


class CountSummary(Base):
    """Table des statistiques finales par classe pour un run."""
    __tablename__ = "count_summaries"

    id        : Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id    : Mapped[int] = mapped_column(Integer, ForeignKey("runs.id"), nullable=False)
    classe    : Mapped[str] = mapped_column(String(50), nullable=False)
    direction : Mapped[str] = mapped_column(String(20), default="any")  # ← "north", "south" ou "any"
    total     : Mapped[int] = mapped_column(Integer, default=0)

    run: Mapped["Run"] = relationship("Run", back_populates="count_summaries")


# =============================================================================
# FONCTIONS DE SÉCURITÉ (mots de passe)
# =============================================================================

def hacher_mot_de_passe(mot_de_passe):
    """
    Hache un mot de passe avec PBKDF2-HMAC-SHA256 et un sel aléatoire.
    Retourne une chaîne au format  sel_hex$hash_hex
    """
    sel = os.urandom(16)  # ← sel cryptographique de 16 octets
    hash_pwd = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), sel, 100000)
    return binascii.hexlify(sel).decode() + "$" + binascii.hexlify(hash_pwd).decode()


def verifier_mot_de_passe(mot_de_passe, valeur_stockee):
    """
    Vérifie un mot de passe en clair contre la valeur hachée stockée.
    Retourne True si le mot de passe correspond, False sinon.
    """
    try:
        sel_hex, hash_hex = valeur_stockee.split("$")
        sel = binascii.unhexlify(sel_hex.encode())
        hash_calcule = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), sel, 100000)
        return binascii.hexlify(hash_calcule).decode() == hash_hex  # ← comparaison sécurisée
    except Exception:
        return False  # ← en cas d'erreur de format, on refuse l'accès


# =============================================================================
# INITIALISATION DE LA BASE DE DONNÉES
# =============================================================================

# ← Moteur SQLite local dans le dossier data/
moteur = create_engine("sqlite:///data/omega_system.db")
SessionLocal = sessionmaker(bind=moteur)


def initialiser_base():
    """Crée le dossier data/ et toutes les tables si elles n'existent pas encore."""
    os.makedirs("data", exist_ok=True)  # ← création du dossier de stockage
    Base.metadata.create_all(moteur)    # ← création de toutes les tables déclarées