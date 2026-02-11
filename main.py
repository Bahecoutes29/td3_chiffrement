import os
import sys
import json
import platform
import subprocess
from datetime import datetime
from getpass import getpass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives import constant_time

from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64
import paramiko
from tqdm import tqdm
import secrets

KEY_DIR = "./keys"

# ===============================
# PARTIE A – DEPENDENCIES
# ===============================
def verif_dependance():
    print("Vérification des dépendances...")

    if sys.version_info < (3, 8):
        print("Python 3.8+ requis.")
        sys.exit(1)

    try:
        import cryptography
        import paramiko
        print("✓ Toutes les dépendances sont installées.")
    except ImportError:
        print("Dépendances manquantes. Installation...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])


# ===============================
# PARTIE C – GENERATION CLE
# ===============================
def generate_key(algo, length):
    if algo == "AES":
        return secrets.token_bytes(length // 8)

    elif algo == "PBKDF2":
        password = getpass("Mot de passe maître : ").encode()
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=length // 8,
            salt=salt,
            iterations=390000,
        )
        return kdf.derive(password)

    else:
        raise ValueError("Algorithme non supporté.")


def save_key(key):
    os.makedirs(KEY_DIR, exist_ok=True)

    filename = f"key_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = os.path.join(KEY_DIR, filename)

    with open(path, "w") as f:
        json.dump({"key": base64.b64encode(key).decode()}, f)

    os.chmod(path, 0o600)
    print(f"✓ Clé sauvegardée : {path}")
    return path


# ===============================
# PARTIE D – SFTP
# ===============================
def send_sftp(local_path):
    host = input("Host : ")
    username = input("Username : ")
    password = getpass("Password : ")
    remote_path = input("Remote path : ")

    try:
        transport = paramiko.Transport((host, 22))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)

        sftp.put(local_path, remote_path)
        sftp.close()
        transport.close()
        print("✓ Transfert réussi.")
    except Exception as e:
        print(f"Erreur SFTP : {e}")


# ===============================
# PARTIE E – CHIFFREMENT LAB ONLY
# ===============================
def encrypt_file(filepath, key):
    with open(filepath, "rb") as f:
        data = f.read()

    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()

    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()

    encrypted = encryptor.update(padded_data) + encryptor.finalize()

    with open(filepath, "wb") as f:
        f.write(iv + encrypted)


def select_directories():
    print("[1] Fichier unique")
    print("[2] Dossier complet")
    choice = input("Choix : ")

    if choice == "1":
        return [input("Chemin fichier : ")]

    elif choice == "2":
        folder = input("Chemin dossier : ")
        files = []
        for root, _, filenames in os.walk(folder):
            for file in filenames:
                files.append(os.path.join(root, file))
        return files

    return []


# ===============================
# PETIT KIFF - Déchiffrement FICHIER
# ===============================

def decrypt_file(filepath, key):
    with open(filepath, "rb") as f:
        blob = f.read()

    if len(blob) < 16:
        print(f"⚠️ Fichier trop court / invalide : {filepath}")
        return

    iv = blob[:16]
    ciphertext = blob[16:]

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()

    padded_plain = decryptor.update(ciphertext) + decryptor.finalize()

    unpadder = padding.PKCS7(128).unpadder()
    try:
        plain = unpadder.update(padded_plain) + unpadder.finalize()
    except ValueError:
        print(f"✗ Padding invalide (mauvaise clé ? fichier non chiffré ?) : {filepath}")
        return

    with open(filepath, "wb") as f:
        f.write(plain)



# ===============================
# MENU PRINCIPAL
# ===============================
def main():
    while True:
        print("""
==============================
Système de Chiffrement - TP3
==============================
1. Générer une clé
2. Envoyer une clé via SFTP
3. Chiffrer fichiers
4. Déchiffrer fichiers
5. Vérifier dépendances
6. Quitter
""")

        choice = input("Choix : ")

        if choice == "1":
            algo = input("Algorithme (AES/PBKDF2) : ")
            length = int(input("Longueur (128/192/256) : "))
            key = generate_key(algo, length)
            save_key(key)

        elif choice == "2":
            path = input("Chemin clé locale : ")
            send_sftp(path)

        elif choice == "3":
            key_path = input("Chemin clé : ")
            with open(key_path) as f:
                key = base64.b64decode(json.load(f)["key"])

            files = select_directories()

            print(f"Chiffrement de {len(files)} fichiers...")
            for file in tqdm(files):
                encrypt_file(file, key)

            print("✓ Terminé.")

        elif choice == "4":
            key_path = input("Chemin clé : ")
            with open(key_path) as f:
                key = base64.b64decode(json.load(f)["key"])

            files = select_directories()

            print(f"Déchiffrement de {len(files)} fichiers...")
            for file in tqdm(files):
                decrypt_file(file, key)

            print("✓ Terminé.")
            

        elif choice == "5":
            verif_dependance()

        elif choice == "6":
            break

        else:
            print("Merci d'entrer un chiffre entre 1 et 6")


if __name__ == "__main__":
    main()