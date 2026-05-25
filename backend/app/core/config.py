"""
Configuración de la aplicación.

Lee los parámetros de conexión a la base de datos desde variables de entorno
(fichero .env), de modo que la contraseña NUNCA aparezca en el código fuente ni
se suba al repositorio. El fichero .env está excluido en .gitignore.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()  # carga las variables del fichero .env si existe


class Settings:
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "optilog")

    @property
    def database_url(self) -> str:
        return (f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}")


settings = Settings()
