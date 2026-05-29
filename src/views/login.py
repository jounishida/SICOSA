import streamlit as st

from src.config import APP_NAME, ROLE_LABELS
from src.controllers.auth_controller import authenticate_user
from src.ui.components import render_hero


def render_login():
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
        st.info("Usuários de exemplo no banco de dados usam a senha: **Senha@123**")
    with col2:
        with st.form("login_form"):
            st.subheader("Acessar plataforma")
            email = st.text_input("Usuário", placeholder="nome.sobrenome@instituicao.br")
            password = st.text_input("Senha", type="password")
            role = st.selectbox("Perfil", list(ROLE_LABELS.keys()), format_func=lambda x: ROLE_LABELS[x])
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            if submitted:
                user = authenticate_user(email, password, role)
                if user:
                    st.session_state["authenticated"] = True
                    st.session_state["user"] = user
                    st.session_state["page"] = "Dashboard"
                    st.rerun()
                else:
                    st.error("Credenciais inválidas ou perfil incompatível.")
