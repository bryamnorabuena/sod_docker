import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # /.../utils
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))  # /... (raíz del proyecto)

def load_environment(env: str | None = None):
    """
    Carga variables de entorno desde un .env según el entorno indicado.
    - En Azure (producción), normalmente NO hay .env: se usa App Settings.
    - En local, puedes usar .env.local por conveniencia.
    """
    try:
        from dotenv import load_dotenv, find_dotenv
        
        # Si no viene, intenta leer desde APP_ENV (p. ej., 'local' o 'production')
        env = env or os.getenv("APP_ENV", "").strip().lower()

        # Si no se especifica nada, asume 'local' cuando estás en dev
        if not env:
            env = "local"

        dotenv_path = None
        if env == "local":
            # Busca .env.local primero (en la raíz del proyecto)
            candidate = os.path.join(PROJECT_ROOT, ".env.local")
            if os.path.exists(candidate):
                dotenv_path = candidate
        elif env == "production":
            # Si alguien quiere usar .env.production en su VM/Container propio (no App Service)
            candidate = os.path.join(PROJECT_ROOT, ".env.production")
            if os.path.exists(candidate):
                dotenv_path = candidate
        else:
            # No abortes el arranque: solo advierte (más resiliente en Azure)
            print(f"[ENV] Entorno no reconocido: '{env}'. No se cargarán archivos .env.")
            dotenv_path = None

        # Carga del .env si existe; si no, intenta find_dotenv como fallback
        loaded = False
        if dotenv_path:
            loaded = load_dotenv(dotenv_path=dotenv_path, override=False)
            print(f"[ENV] Cargando variables desde: {dotenv_path} → loaded={loaded}")
        else:
            # Busca cualquier .env en la jerarquía (opcional)
            found = find_dotenv(usecwd=True)
            if found:
                loaded = load_dotenv(found, override=False)
                print(f"[ENV] Cargando variables desde: {found} → loaded={loaded}")
            else:
                print("[ENV] No se encontró archivo .env; se usarán solo variables de entorno del sistema/App Settings.")

        return loaded
    except:
        pass

def get_environment(var: str, default=None):
    return os.getenv(var, default)
