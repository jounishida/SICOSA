"""Concentra a criação da engine e helpers de acesso ao banco de dados."""

from typing import Optional
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

from src.config import DB_URL

@st.cache_resource(show_spinner=False)
def get_engine():
    """Cria e reutiliza a engine SQLAlchemy configurada pela DATABASE_URL."""
    return create_engine(DB_URL, pool_pre_ping=True)


def run_select(query: str, params: Optional[dict] = None) -> pd.DataFrame:
    """Executa consultas SELECT parametrizadas e retorna DataFrame."""
    with get_engine().connect() as conn:
        return pd.read_sql(text(query), conn, params=params or {})


def run_execute(query: str, params: Optional[dict] = None):
    """Executa comandos de escrita dentro de uma transação."""
    with get_engine().begin() as conn:
        conn.execute(text(query), params or {})


def fetch_scalar(query: str, params: Optional[dict] = None):
    """Executa consulta que retorna um único valor escalar."""
    with get_engine().connect() as conn:
        return conn.execute(text(query), params or {}).scalar()
