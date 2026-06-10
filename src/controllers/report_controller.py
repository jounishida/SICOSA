"""Controlador de consultas agregadas para dashboards e relatórios."""

from typing import Dict

import pandas as pd

from src.db import fetch_scalar, run_select


def _metrics_for_user(role: str, user_id: int) -> Dict[str, int]:
    """Calcula métricas resumidas de ocorrências conforme perfil."""
    params = {}
    where = ""
    if role == "solicitante":
        where = " WHERE requester_id = :user_id "
        params["user_id"] = user_id

    query = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'Aberta' THEN 1 ELSE 0 END) AS abertas,
            SUM(CASE WHEN status = 'Em atendimento' THEN 1 ELSE 0 END) AS atendimento,
            SUM(CASE WHEN status = 'Pendente' THEN 1 ELSE 0 END) AS pendentes,
            SUM(CASE WHEN status = 'Encerrada' THEN 1 ELSE 0 END) AS encerradas
        FROM occurrences
        {where}
    """
    df = run_select(query, params)
    row = df.iloc[0].fillna(0).to_dict()
    return {k: int(v) for k, v in row.items()}


def _manager_status_summary() -> pd.DataFrame:
    """Agrupa ocorrências por status para dashboard gerencial."""
    return run_select(
        """
        SELECT status, COUNT(*) AS quantidade
        FROM occurrences
        GROUP BY status
        ORDER BY quantidade DESC
        """
    )


def _manager_department_summary() -> pd.DataFrame:
    """Agrupa ocorrências por setor para dashboard gerencial."""
    return run_select(
        """
        SELECT department, COUNT(*) AS quantidade
        FROM occurrences
        GROUP BY department
        ORDER BY quantidade DESC
        LIMIT 10
        """
    )


def _manager_priority_summary() -> pd.DataFrame:
    """Agrupa ocorrências por criticidade para dashboard gerencial."""
    return run_select(
        """
        SELECT priority, COUNT(*) AS quantidade
        FROM occurrences
        GROUP BY priority
        ORDER BY FIELD(priority, 'Crítica','Alta','Média','Baixa')
        """
    )


def _mean_resolution_time_hours() -> float:
    """Calcula tempo médio de resolução em horas."""
    value = fetch_scalar(
        """
        SELECT ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_at, closed_at)) / 60, 2)
        FROM occurrences
        WHERE closed_at IS NOT NULL
        """
    )
    return float(value or 0)


class RelatorioService:
    """Serviço responsável por métricas e agregações gerenciais."""

    def metrics_for_user(self, role: str, user_id: int) -> Dict[str, int]:
        """Calcula métricas resumidas por perfil."""
        return _metrics_for_user(role, user_id)

    def manager_status_summary(self) -> pd.DataFrame:
        """Agrupa ocorrências por status."""
        return _manager_status_summary()

    def manager_department_summary(self) -> pd.DataFrame:
        """Agrupa ocorrências por setor."""
        return _manager_department_summary()

    def manager_priority_summary(self) -> pd.DataFrame:
        """Agrupa ocorrências por criticidade."""
        return _manager_priority_summary()

    def mean_resolution_time_hours(self) -> float:
        """Calcula tempo médio de resolução em horas."""
        return _mean_resolution_time_hours()


relatorio_service = RelatorioService()


def metrics_for_user(role: str, user_id: int) -> Dict[str, int]:
    """Atalho funcional para métricas resumidas por perfil."""
    return relatorio_service.metrics_for_user(role, user_id)


def manager_status_summary() -> pd.DataFrame:
    """Atalho funcional para agrupamento por status."""
    return relatorio_service.manager_status_summary()


def manager_department_summary() -> pd.DataFrame:
    """Atalho funcional para agrupamento por setor."""
    return relatorio_service.manager_department_summary()


def manager_priority_summary() -> pd.DataFrame:
    """Atalho funcional para agrupamento por criticidade."""
    return relatorio_service.manager_priority_summary()


def mean_resolution_time_hours() -> float:
    """Atalho funcional para tempo médio de resolução."""
    return relatorio_service.mean_resolution_time_hours()
