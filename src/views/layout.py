"""View de layout lateral, troca de perfil e navegação por perfil."""

import streamlit as st

from src.config import APP_NAME, ROLE_LABELS
from src.controllers.auth_controller import logout
from src.controllers.user_controller import list_user_profile_names


PAGES_BY_ROLE = {
    "solicitante": ["Dashboard", "Nova ocorrência", "Minhas ocorrências", "Detalhe da ocorrência"],
    "atendente": ["Dashboard", "Fila de atendimento", "Detalhe da ocorrência"],
    "gestor": ["Dashboard", "Relatórios", "Detalhe da ocorrência"],
    "administrador": ["Dashboard", "Usuários", "Setores", "Logs"],
    "supervisor": ["Dashboard", "Triagem", "Detalhe da ocorrência"],
}


def _change_profile(user: dict, role: str):
    """Troca perfil ativo do usuário e reinicia navegação."""
    st.session_state["user"] = {**user, "role": role}
    st.session_state["page"] = "Dashboard"
    st.session_state["selected_occurrence_id"] = None
    st.rerun()


def render_profile_switcher(user: dict):
    """Renderiza seletor de perfis disponíveis na sidebar."""
    role = user["role"]
    available_roles = list_user_profile_names(int(user["id"])) or [role]
    st.sidebar.caption("Perfil ativo")

    with st.sidebar.popover(ROLE_LABELS.get(role, role), use_container_width=True):
        st.caption("Selecione outro perfil disponível para este usuário.")
        for available_role in available_roles:
            label = ROLE_LABELS.get(available_role, available_role)
            disabled = available_role == role
            if st.button(label, key=f"switch_role_{available_role}", disabled=disabled, use_container_width=True):
                _change_profile(user, available_role)


def render_sidebar(user: dict):
    """Renderiza identidade do usuário, menu e botão sair."""
    role = user["role"]
    st.sidebar.title(APP_NAME)
    st.sidebar.write(f"**{user['full_name']}**")
    st.sidebar.write(user["email"])
    render_profile_switcher(user)

    st.sidebar.divider()
    st.sidebar.title("Navegação")

    options = PAGES_BY_ROLE[role]
    current = st.session_state.get("page", options[0])
    if current not in options:
        current = options[0]
    st.session_state["page"] = st.sidebar.radio("Tela", options, index=options.index(current))

    st.sidebar.divider()
    if st.sidebar.button("Sair", use_container_width=True):
        logout()
