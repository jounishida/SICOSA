"""Componentes reutilizáveis de interface e fallbacks de renderização."""

from typing import Dict

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError


def show_db_error(error: Exception):
    """Exibe erro de banco de forma padronizada na interface."""
    st.error(
        "Não foi possível acessar o banco de dados. Verifique a variável DATABASE_URL e rode os scripts SQL antes de iniciar o app."
    )
    st.code(str(error))


def _is_grid_dependency_error(error: Exception) -> bool:
    """Identifica falhas conhecidas de pyarrow/numpy na renderização."""
    message = str(error).lower()
    cause = getattr(error, "__cause__", None)
    context = getattr(error, "__context__", None)
    return (
        "pyarrow" in message
        or "numpy.core.multiarray" in message
        or "multiarray failed to import" in message
        or isinstance(error, ImportError)
        or isinstance(cause, ImportError)
        or isinstance(context, ImportError)
    )


def _render_html_table(df: pd.DataFrame):
    """Renderiza tabela HTML simplificada como fallback seguro."""
    st.markdown(
        """
        <style>
        .fallback-table-wrapper {overflow-x: auto; width: 100%;}
        .fallback-table-wrapper table {border-collapse: collapse; width: 100%; font-size: 0.9rem;}
        .fallback-table-wrapper th, .fallback-table-wrapper td {
            border: 1px solid #334155;
            padding: 0.45rem 0.55rem;
            text-align: left;
            vertical-align: top;
        }
        .fallback-table-wrapper th {background: #0f172a; color: #f8fafc;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div class='fallback-table-wrapper'>{df.to_html(index=False)}</div>",
        unsafe_allow_html=True,
    )


def safe_dataframe(df: pd.DataFrame, **kwargs):
    """Tenta renderizar DataFrame avançado e cai para HTML quando necessário."""
    try:
        st.dataframe(df, **kwargs)
    except Exception as exc:
        if _is_grid_dependency_error(exc):
            _render_html_table(df)
        else:
            raise


def safe_chart(chart_func, data, empty_message: str = "Sem dados para exibir."):
    """Renderiza gráficos com tratamento para dados vazios ou dependências quebradas."""
    if data is None or getattr(data, "empty", False):
        st.info(empty_message)
        return
    try:
        chart_func(data)
    except Exception as exc:
        if _is_grid_dependency_error(exc):
            _render_html_table(data.reset_index() if hasattr(data, "reset_index") else data)
        else:
            raise


def render_hero(title: str, subtitle: str):
    """Renderiza cabeçalho visual padrão da página."""
    st.markdown(
        f"""
        <div class='hero'>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_cards(metrics: Dict[str, int]):
    """Renderiza cartões de métricas na largura disponível."""
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", metrics.get("total", 0))
    c2.metric("Abertas", metrics.get("abertas", 0))
    c3.metric("Em atendimento", metrics.get("atendimento", 0))
    c4.metric("Pendentes", metrics.get("pendentes", 0))
    c5.metric("Encerradas", metrics.get("encerradas", 0))


def open_detail_button(df: pd.DataFrame, key_prefix: str):
    """Permite selecionar ocorrência da tabela e abrir detalhe."""
    if df.empty:
        st.info("Nenhuma ocorrência encontrada para os filtros selecionados.")
        return

    options = {f"{row['protocol']} — {row['title']}": int(row['id']) for _, row in df.iterrows()}
    selected = st.selectbox("Abrir ocorrência", list(options.keys()), key=f"{key_prefix}_select")
    if st.button("Ver detalhe", key=f"{key_prefix}_button"):
        st.session_state["selected_occurrence_id"] = options[selected]
        st.session_state["page"] = "Detalhe da ocorrência"
        st.rerun()


def render_occurrences_table(df: pd.DataFrame, height: int = 350):
    """Renderiza tabela padronizada de ocorrências."""
    if df.empty:
        st.info("Nenhuma ocorrência encontrada.")
        return

    display_df = df[[
        "protocol", "title", "department", "priority", "status", "requester_name", "assigned_to_name", "created_at"
    ]].copy()
    display_df.columns = [
        "Protocolo", "Título", "Setor", "Prioridade", "Status", "Solicitante", "Responsável", "Criada em"
    ]
    safe_dataframe(display_df, use_container_width=True, hide_index=True, height=height)
