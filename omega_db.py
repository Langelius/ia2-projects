import os
import json
import hashlib
import binascii
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True)
    password_hash = Column(String(255))
    face_data = Column(Text) # Stockage JSON du vecteur 128

class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True)
    video_name = Column(String(255))
    date = Column(DateTime, default=datetime.utcnow)
    summary = Column(Text)

# Fonctions de sécurité
def hash_pwd(password):
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return binascii.hexlify(salt).decode() + "$" + binascii.hexlify(pwd_hash).decode()

def verify_pwd(password, stored_value):
    try:
        salt_hex, hash_hex = stored_value.split("$")
        salt = binascii.unhexlify(salt_hex.encode())
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return binascii.hexlify(pwd_hash).decode() == hash_hex
    except: return False

engine = create_engine("sqlite:///data/omega_system.db")
SessionLocal = sessionmaker(bind=engine)

def setup_database():
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(engine)