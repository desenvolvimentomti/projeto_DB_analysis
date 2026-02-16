from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os

class Settings(BaseSettings):
    # Google Cloud & Earth Engine
    # O Pydantic buscará automaticamente essas chaves no seu arquivo .env
    gee_service_account_json_path: str = Field(validation_alias="GEE_SERVICE_ACCOUNT_JSON_PATH")
    gcp_bucket_name: str = Field(validation_alias="GCP_BUCKET_NAME")
    
    # Configurações do FastAPI
    app_name: str = "Plataforma de Análise Climática MFLAB"
    debug_mode: bool = False

    # Configuração para carregar o arquivo .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def get_credentials_path(self):
        """Retorna o caminho absoluto do JSON de credenciais"""
        return os.path.abspath(self.gee_service_account_json_path)

# Instância global para ser usada em todo o projeto
settings = Settings()