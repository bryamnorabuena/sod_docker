# security.py
import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica bcrypt $2y$ sin límite de 72 bytes usando la librería bcrypt nativa.
    """
    try:
        # Compatibilidad: bcrypt de Python NO acepta $2y$, lo cambiamos por $2b$
        fixed_hash = hashed_password.replace("$2y$", "$2b$")

        # Convertir strings a bytes
        plain_bytes = plain_password.encode("utf-8")
        hash_bytes = fixed_hash.encode("utf-8")

        # checkpw NO lanza error si la pass es larga (a diferencia de passlib)
        return bcrypt.checkpw(plain_bytes, hash_bytes)
    except Exception as e:
        print("verify_password error:", e)
        return False

def hash_password_bcrypt(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()
