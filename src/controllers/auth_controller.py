"""Controlador de autenticação e encerramento de sessão."""

from typing import Optional

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.db import run_execute, run_select
from src.security import hash_password
from src.ui.components import show_db_error


def authenticate_user(email: str, password: str, role: str) -> Optional[dict]:
    """Autentica usuário por e-mail, senha e perfil solicitado."""
    query = """
        SELECT DISTINCT u.id, u.full_name, u.email, p.name AS role, u.is_active
        FROM users u
        INNER JOIN user_profiles up ON up.user_id = u.id
        INNER JOIN profiles p ON p.id = up.profile_id
        WHERE u.email = :email
          AND p.name = :role
          AND u.password_hash = :password_hash
          AND u.is_active = 1
        LIMIT 1
    """
    params = {"email": email.strip().lower(), "role": role, "password_hash": hash_password(password)}
    try:
        df = run_select(query, params)
        if df.empty:
            return None
        user = df.iloc[0].to_dict()
        run_execute("UPDATE users SET last_login = NOW() WHERE id = :id", {"id": int(user["id"])})
        return user
    except SQLAlchemyError as e:
        show_db_error(e)
        return None


def logout():
    """Limpa os dados de sessão e retorna para a tela de login."""
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.session_state["page"] = "Dashboard"
    st.session_state["selected_occurrence_id"] = None
    st.rerun()
