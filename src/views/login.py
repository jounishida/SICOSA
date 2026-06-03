"""View de autenticação do sistema."""

import streamlit as st

from src.config import APP_NAME, ROLE_LABELS
from src.controllers.auth_controller import authenticate_credentials
from src.ui.components import render_hero


def _complete_login(user: dict, role: str):
    """Finaliza a autenticação armazenando usuário e perfil ativo na sessão."""
    st.session_state["authenticated"] = True
    st.session_state["user"] = {k: v for k, v in user.items() if k != "roles"} | {"role": role}
    st.session_state["pending_login_user"] = None
    st.session_state["page"] = "Dashboard"
    st.rerun()


def render_login():
    """Renderiza login em duas etapas: credenciais e, se necessário, seleção de perfil permitido."""
    render_hero(
        APP_NAME,
        "Acesso inicial para solicitantes, atendentes, gestores e administradores.",
    )
    col1, col2 = st.columns([1.15, 0.85], gap="large")
    with col1:
        st.markdown(
            """
            ### Controle centralizado das demandas internas
            Uma entrada simples para registrar, acompanhar e gerenciar ocorrências do setor de apoio.

            **Perfis contemplados**
            - Solicitante
            - Atendente
            - Gestor
            - Supervisor
            - Administrador
            """
        )
    with col2:
        pending_user = st.session_state.get("pending_login_user")
        if pending_user:
            roles = pending_user.get("roles", [])
            with st.form("profile_selection_form"):
                st.subheader("Selecionar perfil")
                st.caption("Escolha um dos perfis que seu usuário tem permissão para acessar.")
                selected_role = st.selectbox("Perfil", roles, format_func=lambda x: ROLE_LABELS.get(x, x))
                submitted = st.form_submit_button("Acessar perfil", use_container_width=True)
                if submitted:
                    _complete_login(pending_user, selected_role)
            if st.button("Voltar para login", use_container_width=True):
                st.session_state["pending_login_user"] = None
                st.rerun()
            return

        with st.form("login_form"):
            st.subheader("Acessar plataforma")
            email = st.text_input("Usuário", placeholder="nome.sobrenome@instituicao.br")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            if submitted:
                user = authenticate_credentials(email, password)
                if not user:
                    st.error("Credenciais inválidas ou usuário inativo.")
                    return
                roles = user.get("roles", [])
                if len(roles) == 1:
                    _complete_login(user, roles[0])
                elif len(roles) > 1:
                    st.session_state["pending_login_user"] = user
                    st.rerun()
                else:
                    st.error("Usuário sem perfil de acesso vinculado.")
