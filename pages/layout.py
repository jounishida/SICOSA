import streamlit as st

from src.config import ROLE_LABELS
from src.controllers.auth_controller import logout


def render_sidebar(user: dict):
    role = user["role"]
    st.sidebar.title("Navegação")
    st.sidebar.caption(f"Perfil ativo: {ROLE_LABELS[role]}")
    st.sidebar.write(f"**{user['full_name']}**")
    st.sidebar.write(user["email"])

    pages_by_role = {
        "solicitante": ["Dashboard", "Nova ocorrência", "Minhas ocorrências", "Detalhe da ocorrência"],
        "atendente": ["Dashboard", "Fila de atendimento", "Detalhe da ocorrência"],
        "gestor": ["Dashboard", "Relatórios", "Detalhe da ocorrência"],
        "administrador": ["Dashboard", "Usuários", "Setores", "Logs"],
        "supervisor": ["Dashboard", "Triagem", "Detalhe da ocorrência"],
    }

    options = pages_by_role[role]
    current = st.session_state.get("page", options[0])
    if current not in options:
        current = options[0]
    st.session_state["page"] = st.sidebar.radio("Tela", options, index=options.index(current))

    st.sidebar.divider()
    if st.sidebar.button("Sair", use_container_width=True):
        logout()
