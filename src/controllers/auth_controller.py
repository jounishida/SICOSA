"""Controlador de autenticação e encerramento de sessão."""

from typing import Optional

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.db import run_execute, run_select
from src.models import Usuario
from src.security import hash_password
from src.ui.components import show_db_error


class AuthService:
    """Serviço responsável por validar credenciais e perfis permitidos."""

    def authenticate_credentials(self, email: str, password: str) -> Optional[dict]:
        """Valida usuário e senha e retorna os perfis permitidos para seleção posterior."""
        query = """
            SELECT DISTINCT u.id, u.full_name, u.email, u.is_active, p.id AS profile_id, p.name AS role
            FROM users u
            INNER JOIN user_profiles up ON up.user_id = u.id
            INNER JOIN profiles p ON p.id = up.profile_id
            WHERE u.email = :email
              AND u.password_hash = :password_hash
              AND u.is_active = 1
            ORDER BY p.id
        """
        params = {"email": email.strip().lower(), "password_hash": hash_password(password)}
        try:
            df = run_select(query, params)
            if df.empty:
                return None
            usuario = Usuario.from_auth_rows(df)
            run_execute("UPDATE users SET last_login = NOW() WHERE id = :id", {"id": usuario.id})
            return usuario.as_session_dict()
        except SQLAlchemyError as e:
            show_db_error(e)
            return None

    def authenticate_user(self, email: str, password: str, role: str) -> Optional[dict]:
        """Autentica usuário por e-mail/senha e confirma se o perfil solicitado é permitido."""
        authenticated = self.authenticate_credentials(email, password)
        if not authenticated or role not in authenticated["roles"]:
            return None
        return {k: v for k, v in authenticated.items() if k != "roles"} | {"role": role}


auth_service = AuthService()


def authenticate_credentials(email: str, password: str) -> Optional[dict]:
    """Atalho funcional para validar credenciais via AuthService."""
    return auth_service.authenticate_credentials(email, password)


def authenticate_user(email: str, password: str, role: str) -> Optional[dict]:
    """Atalho funcional para autenticar usuário em um perfil via AuthService."""
    return auth_service.authenticate_user(email, password, role)


def logout():
    """Limpa os dados de sessão e retorna para a tela de login."""
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.session_state["page"] = "Dashboard"
    st.session_state["selected_occurrence_id"] = None
    st.session_state["pending_login_user"] = None
    st.rerun()
