"""Modelos de domínio usados pelos serviços do SICOSA."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Usuario:
    """Representa um usuário autenticado ou listado pelo sistema."""

    id: int
    full_name: str
    email: str
    is_active: bool = True
    role: Optional[str] = None
    roles: list[str] = field(default_factory=list)

    @classmethod
    def from_auth_rows(cls, rows) -> "Usuario":
        """Cria usuário a partir das linhas retornadas pela consulta de autenticação."""
        first = rows.iloc[0].to_dict()
        return cls(
            id=int(first["id"]),
            full_name=first["full_name"],
            email=first["email"],
            is_active=bool(first["is_active"]),
            roles=rows["role"].dropna().tolist(),
        )

    def as_session_dict(self, role: Optional[str] = None) -> dict:
        """Converte o usuário para o formato gravado na sessão Streamlit."""
        data = {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "is_active": self.is_active,
        }
        if role:
            data["role"] = role
        else:
            data["roles"] = self.roles
        return data


@dataclass
class Ocorrencia:
    """Representa os dados principais de um chamado/ocorrência."""

    requester_id: int
    title: str
    description: str
    department: str
    priority: str
    protocol: Optional[str] = None
    category: Optional[str] = None
    assigned_to: Optional[int] = None
    due_at: Optional[datetime] = None

    @classmethod
    def from_payload(cls, payload: dict, protocol: str, due_at: datetime) -> "Ocorrencia":
        """Cria ocorrência de domínio a partir do payload recebido pela view."""
        return cls(
            protocol=protocol,
            requester_id=int(payload["requester_id"]),
            title=payload["title"],
            description=payload["description"],
            department=payload["department"],
            category=payload.get("category"),
            priority=payload["priority"],
            assigned_to=payload.get("assigned_to"),
            due_at=due_at,
        )


@dataclass
class AtualizacaoOcorrencia:
    """Representa uma interação registrada no histórico de uma ocorrência."""

    occurrence_id: int
    user_id: int
    note: str
    action_type: str = "comentario"
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
