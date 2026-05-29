from typing import Dict

import pandas as pd

from src.db import fetch_scalar, run_select


def metrics_for_user(role: str, user_id: int) -> Dict[str, int]:
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


def manager_status_summary() -> pd.DataFrame:
    return run_select(
        """
        SELECT status, COUNT(*) AS quantidade
        FROM occurrences
        GROUP BY status
        ORDER BY quantidade DESC
        """
    )


def manager_department_summary() -> pd.DataFrame:
    return run_select(
        """
        SELECT department, COUNT(*) AS quantidade
        FROM occurrences
        GROUP BY department
        ORDER BY quantidade DESC
        LIMIT 10
        """
    )


def manager_priority_summary() -> pd.DataFrame:
    return run_select(
        """
        SELECT priority, COUNT(*) AS quantidade
        FROM occurrences
        GROUP BY priority
        ORDER BY FIELD(priority, 'Crítica','Alta','Média','Baixa')
        """
    )


def mean_resolution_time_hours() -> float:
    value = fetch_scalar(
        """
        SELECT ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_at, closed_at)) / 60, 2)
        FROM occurrences
        WHERE closed_at IS NOT NULL
        """
    )
    return float(value or 0)
