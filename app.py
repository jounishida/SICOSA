import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from pages.admin import render_admin_departments, render_admin_logs, render_admin_users
from pages.dashboards import (
    render_admin_dashboard,
    render_atendente_dashboard,
    render_manager_dashboard,
    render_solicitante_dashboard,
    render_supervisor_dashboard,
)
from pages.layout import render_sidebar
from pages.login import render_login
from pages.occurrences import (
    render_my_occurrences,
    render_new_occurrence,
    render_occurrence_detail,
    render_queue,
    render_supervisor_triage,
)
from pages.reports import render_reports
from src.ui.components import show_db_error


def configure_app():
    st.set_page_config(
        page_title="Sistema de Cadastro de Ocorrências",
        page_icon="🛠️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
        .hero {
            background: linear-gradient(135deg, #0b1020 0%, #1e3a8a 55%, #06b6d4 100%);
            color: white;
            padding: 1.6rem 1.8rem;
            border-radius: 18px;
            margin-bottom: 1rem;
        }
        .hero h1 {margin: 0 0 .4rem 0; font-size: 2rem;}
        .hero p {margin: 0; opacity: .92;}
        .card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 1rem 1rem .8rem 1rem;
            min-height: 120px;
        }
        .small-muted {color: #64748b; font-size: .92rem;}
        .section-title {margin-top: .6rem; margin-bottom: .4rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state():
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("page", "Dashboard")
    st.session_state.setdefault("selected_occurrence_id", None)


def render_current_page(user: dict):
    render_sidebar(user)
    page = st.session_state.get("page", "Dashboard")
    role = user["role"]

    routes = {
        "solicitante": {
            "Dashboard": render_solicitante_dashboard,
            "Nova ocorrência": render_new_occurrence,
            "Minhas ocorrências": render_my_occurrences,
            "Detalhe da ocorrência": render_occurrence_detail,
        },
        "atendente": {
            "Dashboard": render_atendente_dashboard,
            "Fila de atendimento": render_queue,
            "Detalhe da ocorrência": render_occurrence_detail,
        },
        "gestor": {
            "Dashboard": render_manager_dashboard,
            "Relatórios": render_reports,
            "Detalhe da ocorrência": render_occurrence_detail,
        },
        "supervisor": {
            "Dashboard": render_supervisor_dashboard,
            "Triagem": render_supervisor_triage,
            "Detalhe da ocorrência": render_occurrence_detail,
        },
        "administrador": {
            "Dashboard": render_admin_dashboard,
            "Usuários": lambda _user: render_admin_users(),
            "Setores": lambda _user: render_admin_departments(),
            "Logs": lambda _user: render_admin_logs(),
        },
    }

    handler = routes.get(role, {}).get(page)
    if handler is None:
        st.error("Perfil ou página sem rota configurada.")
        return
    handler(user)


def main():
    configure_app()
    init_state()

    user = st.session_state.get("user")
    if not st.session_state.get("authenticated") or not user:
        render_login()
        return

    render_current_page(user)


if __name__ == "__main__":
    try:
        main()
    except SQLAlchemyError as e:
        show_db_error(e)
