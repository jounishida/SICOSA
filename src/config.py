import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:1234@localhost:3306/suporte_ocorrencias?charset=utf8mb4",
)
APP_NAME = "Sistema de Cadastro de Ocorrências do Setor de Apoio"
STATUS_OPTIONS = ["Aberta", "Em atendimento", "Pendente", "Encerrada"]
PRIORITY_OPTIONS = ["Baixa", "Média", "Alta", "Crítica"]
ROLE_LABELS = {
    "solicitante": "Solicitante",
    "atendente": "Atendente",
    "gestor": "Gestor",
    "administrador": "Administrador",
    "supervisor": "Supervisor",
}
ALLOWED_MIME_TYPES = {
    "image/png", "image/jpeg", "application/pdf", "text/plain",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
