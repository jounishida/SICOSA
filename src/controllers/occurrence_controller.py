"""Controlador de ocorrências, histórico, anexos e regras de fila."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import text

from src.db import fetch_scalar, get_engine, run_select
from src.models import AtualizacaoOcorrencia, Ocorrencia


# Regras e persistência dos chamados/ocorrências.
def _next_protocol() -> str:
    """Calcula o próximo protocolo anual a partir do maior ID atual."""
    next_id = fetch_scalar("SELECT COALESCE(MAX(id), 0) + 1 FROM occurrences")
    return f"{datetime.now().year}-{int(next_id):04d}"


def _default_due_at(priority: str) -> datetime:
    """Calcula vencimento/SLA inicial com base na criticidade."""
    hours_by_priority = {"Baixa": 48, "Média": 24, "Alta": 8, "Crítica": 4}
    return datetime.now() + timedelta(hours=hours_by_priority.get(priority, 24))


def _create_occurrence(payload: dict, attachments: List[dict]):
    """Cria ocorrência, registra histórico inicial e salva anexos."""
    protocol = _next_protocol()
    due_at = _default_due_at(payload["priority"])
    occurrence = Ocorrencia.from_payload(payload, protocol, due_at)
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO occurrences (
                    protocol, requester_id, title, description, department, category,
                    priority, status, assigned_to, due_at
                ) VALUES (
                    :protocol, :requester_id, :title, :description, :department, :category,
                    :priority, 'Aberta', :assigned_to, :due_at
                )
                """
            ),
            {
                "protocol": occurrence.protocol,
                "requester_id": occurrence.requester_id,
                "title": occurrence.title,
                "description": occurrence.description,
                "department": occurrence.department,
                "category": occurrence.category,
                "priority": occurrence.priority,
                "assigned_to": occurrence.assigned_to,
                "due_at": occurrence.due_at,
            },
        )
        occurrence_id = result.lastrowid
        conn.execute(
            text(
                """
                INSERT INTO occurrence_updates (
                    occurrence_id, user_id, action_type, previous_status, new_status, note
                ) VALUES (
                    :occurrence_id, :user_id, 'criacao', NULL, 'Aberta', :note
                )
                """
            ),
            {
                "occurrence_id": occurrence_id,
                "user_id": occurrence.requester_id,
                "note": "Ocorrência registrada pelo solicitante.",
            },
        )
        for item in attachments:
            conn.execute(
                text(
                    """
                    INSERT INTO occurrence_attachments (
                        occurrence_id, file_name, mime_type, file_data, uploaded_by
                    ) VALUES (
                        :occurrence_id, :file_name, :mime_type, :file_data, :uploaded_by
                    )
                    """
                ),
                {
                    "occurrence_id": occurrence_id,
                    "file_name": item["file_name"],
                    "mime_type": item["mime_type"],
                    "file_data": item["file_data"],
                    "uploaded_by": occurrence.requester_id,
                },
            )
    return occurrence.protocol


def _base_occurrence_query() -> str:
    """Monta SELECT base reutilizado nas consultas de ocorrência."""
    return """
        SELECT
            o.id,
            o.protocol,
            o.title,
            o.department,
            o.category,
            o.priority,
            o.status,
            o.created_at,
            o.updated_at,
            o.closed_at,
            o.description,
            o.closure_notes,
            o.due_at,
            req.full_name AS requester_name,
            req.email AS requester_email,
            COALESCE(ass.full_name, 'Não definido') AS assigned_to_name,
            o.requester_id,
            o.assigned_to
        FROM occurrences o
        INNER JOIN users req ON req.id = o.requester_id
        LEFT JOIN users ass ON ass.id = o.assigned_to
    """


def _get_occurrences(role: str, user_id: int, filters: Optional[Dict] = None) -> pd.DataFrame:
    """Lista ocorrências visíveis por perfil aplicando filtros opcionais."""
    filters = filters or {}
    query = _base_occurrence_query() + " WHERE 1=1 "
    params = {}

    if role == "solicitante":
        query += " AND o.requester_id = :user_id "
        params["user_id"] = user_id
    elif role == "atendente":
        query += """
            AND (
                o.assigned_to = :user_id
                OR o.assigned_to IS NULL
            )
        """
        params["user_id"] = user_id

    if filters.get("status"):
        query += " AND o.status = :status "
        params["status"] = filters["status"]
    if filters.get("priority"):
        query += " AND o.priority = :priority "
        params["priority"] = filters["priority"]
    if filters.get("department"):
        query += " AND o.department LIKE :department "
        params["department"] = f"%{filters['department']}%"
    if filters.get("search"):
        query += " AND (o.protocol LIKE :search OR o.title LIKE :search OR o.description LIKE :search) "
        params["search"] = f"%{filters['search']}%"

    query += " ORDER BY FIELD(o.priority, 'Crítica','Alta','Média','Baixa'), o.created_at DESC "
    return run_select(query, params)


def _get_occurrence_by_id(occurrence_id: int) -> pd.DataFrame:
    """Busca dados completos de uma ocorrência pelo ID."""
    query = _base_occurrence_query() + " WHERE o.id = :occurrence_id LIMIT 1"
    return run_select(query, {"occurrence_id": occurrence_id})


def _get_occurrence_updates(occurrence_id: int) -> pd.DataFrame:
    """Lista histórico de interações de uma ocorrência."""
    return run_select(
        """
        SELECT
            u.created_at,
            usr.full_name AS actor_name,
            u.action_type,
            u.previous_status,
            u.new_status,
            u.note
        FROM occurrence_updates u
        INNER JOIN users usr ON usr.id = u.user_id
        WHERE u.occurrence_id = :occurrence_id
        ORDER BY u.created_at ASC
        """,
        {"occurrence_id": occurrence_id},
    )


def _get_occurrence_attachments(occurrence_id: int) -> pd.DataFrame:
    """Lista anexos vinculados a uma ocorrência."""
    return run_select(
        """
        SELECT id, file_name, mime_type, file_data, uploaded_at
        FROM occurrence_attachments
        WHERE occurrence_id = :occurrence_id
        ORDER BY uploaded_at ASC
        """,
        {"occurrence_id": occurrence_id},
    )


def _get_active_attendants() -> pd.DataFrame:
    """Lista atendentes ativos disponíveis para atribuição."""
    return run_select(
        """
        SELECT DISTINCT u.id, u.full_name
        FROM users u
        WHERE u.is_active = 1
          AND EXISTS (
              SELECT 1
              FROM user_profiles up
              INNER JOIN profiles p ON p.id = up.profile_id
              WHERE up.user_id = u.id
                AND p.name = 'atendente'
          )
        ORDER BY u.full_name
        """
    )


def _add_attachment(occurrence_id: int, uploaded_files: List, user_id: int):
    """Salva novos anexos em ocorrência existente."""
    engine = get_engine()
    with engine.begin() as conn:
        for file in uploaded_files:
            conn.execute(
                text(
                    """
                    INSERT INTO occurrence_attachments (
                        occurrence_id, file_name, mime_type, file_data, uploaded_by
                    ) VALUES (
                        :occurrence_id, :file_name, :mime_type, :file_data, :uploaded_by
                    )
                    """
                ),
                {
                    "occurrence_id": occurrence_id,
                    "file_name": file.name,
                    "mime_type": file.type,
                    "file_data": file.getvalue(),
                    "uploaded_by": user_id,
                },
            )


def _add_update(
    occurrence_id: int,
    user_id: int,
    note: str,
    new_status: Optional[str] = None,
    assigned_to: Optional[int] = None,
    new_priority: Optional[str] = None,
):
    """Registra atualização e aplica status, responsável ou criticidade quando informado."""
    current = _get_occurrence_by_id(occurrence_id)
    if current.empty:
        return
    current_row = current.iloc[0]
    previous_status = current_row["status"]
    status_to_apply = new_status or previous_status
    update = AtualizacaoOcorrencia(
        occurrence_id=occurrence_id,
        user_id=user_id,
        note=note,
        action_type="status" if new_status else "comentario",
        previous_status=previous_status,
        new_status=status_to_apply,
    )

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE occurrences
                SET status = :status,
                    assigned_to = :assigned_to,
                    priority = :priority,
                    updated_at = NOW()
                WHERE id = :occurrence_id
                """
            ),
            {
                "status": status_to_apply,
                "assigned_to": assigned_to if assigned_to not in (None, "") else current_row["assigned_to"],
                "priority": new_priority or current_row["priority"],
                "occurrence_id": occurrence_id,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO occurrence_updates (
                    occurrence_id, user_id, action_type, previous_status, new_status, note
                ) VALUES (
                    :occurrence_id, :user_id, :action_type, :previous_status, :new_status, :note
                )
                """
            ),
            {
                "occurrence_id": update.occurrence_id,
                "user_id": update.user_id,
                "action_type": update.action_type,
                "previous_status": update.previous_status,
                "new_status": update.new_status,
                "note": update.note,
            },
        )


def _close_occurrence(occurrence_id: int, user_id: int, closure_notes: str):
    """Encerra ocorrência e grava justificativa no histórico."""
    current = _get_occurrence_by_id(occurrence_id)
    if current.empty:
        return
    previous_status = current.iloc[0]["status"]
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE occurrences
                SET status = 'Encerrada',
                    closure_notes = :closure_notes,
                    closed_at = NOW(),
                    updated_at = NOW()
                WHERE id = :occurrence_id
                """
            ),
            {"closure_notes": closure_notes, "occurrence_id": occurrence_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO occurrence_updates (
                    occurrence_id, user_id, action_type, previous_status, new_status, note
                ) VALUES (
                    :occurrence_id, :user_id, 'encerramento', :previous_status, 'Encerrada', :note
                )
                """
            ),
            {
                "occurrence_id": occurrence_id,
                "user_id": user_id,
                "previous_status": previous_status,
                "note": closure_notes,
            },
        )


class OcorrenciaService:
    """Serviço que concentra o ciclo de vida das ocorrências."""

    def next_protocol(self) -> str:
        """Calcula o próximo protocolo anual."""
        return _next_protocol()

    def default_due_at(self, priority: str) -> datetime:
        """Calcula o vencimento inicial pela criticidade."""
        return _default_due_at(priority)

    def create_occurrence(self, payload: dict, attachments: List[dict]):
        """Cria uma ocorrência com histórico inicial e anexos."""
        return _create_occurrence(payload, attachments)

    def base_occurrence_query(self) -> str:
        """Retorna o SELECT base de ocorrências."""
        return _base_occurrence_query()

    def get_occurrences(self, role: str, user_id: int, filters: Optional[Dict] = None) -> pd.DataFrame:
        """Lista ocorrências visíveis por perfil."""
        return _get_occurrences(role, user_id, filters)

    def get_occurrence_by_id(self, occurrence_id: int) -> pd.DataFrame:
        """Busca uma ocorrência pelo ID."""
        return _get_occurrence_by_id(occurrence_id)

    def get_occurrence_updates(self, occurrence_id: int) -> pd.DataFrame:
        """Lista o histórico da ocorrência."""
        return _get_occurrence_updates(occurrence_id)

    def get_occurrence_attachments(self, occurrence_id: int) -> pd.DataFrame:
        """Lista anexos da ocorrência."""
        return _get_occurrence_attachments(occurrence_id)

    def get_active_attendants(self) -> pd.DataFrame:
        """Lista atendentes ativos para atribuição."""
        return _get_active_attendants()

    def add_attachment(self, occurrence_id: int, uploaded_files: List, user_id: int):
        """Adiciona anexos à ocorrência."""
        return _add_attachment(occurrence_id, uploaded_files, user_id)

    def add_update(
        self,
        occurrence_id: int,
        user_id: int,
        note: str,
        new_status: Optional[str] = None,
        assigned_to: Optional[int] = None,
        new_priority: Optional[str] = None,
    ):
        """Registra atualização de status, responsável, criticidade ou comentário."""
        return _add_update(occurrence_id, user_id, note, new_status, assigned_to, new_priority)

    def close_occurrence(self, occurrence_id: int, user_id: int, closure_notes: str):
        """Encerra ocorrência com justificativa."""
        return _close_occurrence(occurrence_id, user_id, closure_notes)


ocorrencia_service = OcorrenciaService()


def next_protocol() -> str:
    """Atalho funcional para calcular o próximo protocolo."""
    return ocorrencia_service.next_protocol()


def default_due_at(priority: str) -> datetime:
    """Atalho funcional para calcular vencimento inicial."""
    return ocorrencia_service.default_due_at(priority)


def create_occurrence(payload: dict, attachments: List[dict]):
    """Atalho funcional para criar ocorrência."""
    return ocorrencia_service.create_occurrence(payload, attachments)


def base_occurrence_query() -> str:
    """Atalho funcional para obter o SELECT base."""
    return ocorrencia_service.base_occurrence_query()


def get_occurrences(role: str, user_id: int, filters: Optional[Dict] = None) -> pd.DataFrame:
    """Atalho funcional para listar ocorrências por perfil."""
    return ocorrencia_service.get_occurrences(role, user_id, filters)


def get_occurrence_by_id(occurrence_id: int) -> pd.DataFrame:
    """Atalho funcional para buscar ocorrência por ID."""
    return ocorrencia_service.get_occurrence_by_id(occurrence_id)


def get_occurrence_updates(occurrence_id: int) -> pd.DataFrame:
    """Atalho funcional para listar histórico de ocorrência."""
    return ocorrencia_service.get_occurrence_updates(occurrence_id)


def get_occurrence_attachments(occurrence_id: int) -> pd.DataFrame:
    """Atalho funcional para listar anexos de ocorrência."""
    return ocorrencia_service.get_occurrence_attachments(occurrence_id)


def get_active_attendants() -> pd.DataFrame:
    """Atalho funcional para listar atendentes ativos."""
    return ocorrencia_service.get_active_attendants()


def add_attachment(occurrence_id: int, uploaded_files: List, user_id: int):
    """Atalho funcional para adicionar anexos."""
    return ocorrencia_service.add_attachment(occurrence_id, uploaded_files, user_id)


def add_update(
    occurrence_id: int,
    user_id: int,
    note: str,
    new_status: Optional[str] = None,
    assigned_to: Optional[int] = None,
    new_priority: Optional[str] = None,
):
    """Atalho funcional para registrar atualização de ocorrência."""
    return ocorrencia_service.add_update(occurrence_id, user_id, note, new_status, assigned_to, new_priority)


def close_occurrence(occurrence_id: int, user_id: int, closure_notes: str):
    """Atalho funcional para encerrar ocorrência."""
    return ocorrencia_service.close_occurrence(occurrence_id, user_id, closure_notes)
