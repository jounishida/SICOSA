import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.config import ROLE_LABELS
from src.controllers.user_controller import (assign_user_department, assign_user_profile, create_department,
    create_user, delete_department, list_departments, list_profiles, list_user_profiles, list_users,
    remove_user_profile, toggle_user_status)
from src.db import run_select
from src.security import valid_email, valid_password_strength
from src.ui.components import render_hero, safe_dataframe, show_db_error


def render_admin_users():
    render_hero("Gestão de usuários", "Criação de perfis, ativação e inativação de acessos do sistema.")
    st.markdown("### Novo usuário")
    with st.form("new_user_form"):
        c1, c2 = st.columns(2)
        full_name = c1.text_input("Nome completo")
        email = c2.text_input("E-mail")
        c3, c4 = st.columns(2)
        role = c3.selectbox("Perfil", list(ROLE_LABELS.keys()), format_func=lambda x: ROLE_LABELS[x])
        password = c4.text_input("Senha inicial", type="password", value="Senha@123")
        submitted = st.form_submit_button("Criar usuário")
        if submitted:
            if not full_name.strip() or not email.strip() or not password.strip():
                st.error("Preencha nome, e-mail e senha para criar o usuário.")
            else:
                if not valid_email(email):
                    st.error("Informe um e-mail válido.")
                    return
                if not valid_password_strength(password):
                    st.error("Senha fraca. Use ao menos 8 caracteres, 1 maiúscula e 1 número.")
                    return
                try:
                    create_user({
                        "full_name": full_name,
                        "email": email,
                        "password": password,
                        "role": role,
                    })
                    st.success("Usuário criado com sucesso.")
                except SQLAlchemyError as e:
                    show_db_error(e)

    st.markdown("### Usuários cadastrados")
    users = list_users()
    if users.empty:
        st.info("Nenhum usuário cadastrado.")
        return
    display_df = users.copy()
    display_df["roles"] = display_df["roles"].fillna("").apply(lambda x: ", ".join(ROLE_LABELS.get(i.strip(), i.strip()) for i in x.split(",") if i.strip()))
    display_df["is_active"] = display_df["is_active"].map({1: "Ativo", 0: "Inativo"})
    display_df.columns = ["ID", "Nome", "E-mail", "Perfis", "Setores", "Status", "Criado em", "Último acesso"]
    safe_dataframe(display_df, hide_index=True, use_container_width=True, height=380)

    user_options = {f"{row['full_name']} — {row['roles'] or 'Sem perfil'}": (int(row['id']), bool(row['is_active'])) for _, row in users.iterrows()}

    st.markdown("### Permissões de perfil por usuário")
    selected_user_label = st.selectbox("Selecionar usuário", list(user_options.keys()), key="profile_user_sel")
    selected_user_id = user_options[selected_user_label][0]
    all_profiles = list_profiles()
    current_profiles = list_user_profiles(selected_user_id)

    colp1, colp2 = st.columns(2)
    with colp1:
        add_map = {row['label']: int(row['id']) for _, row in all_profiles.iterrows()}
        add_choice = st.selectbox("Adicionar perfil", list(add_map.keys()), key="add_profile_sel")
        if st.button("Adicionar permissão"):
            assign_user_profile(selected_user_id, add_map[add_choice])
            st.success("Permissão adicionada.")
            st.rerun()
    with colp2:
        if current_profiles.empty:
            st.info("Usuário sem perfis cadastrados.")
        else:
            rem_map = {row['label']: int(row['id']) for _, row in current_profiles.iterrows()}
            rem_choice = st.selectbox("Remover perfil", list(rem_map.keys()), key="rem_profile_sel")
            if st.button("Remover permissão"):
                try:
                    remove_user_profile(selected_user_id, rem_map[rem_choice])
                    st.success("Permissão removida.")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    selected = st.selectbox("Alterar status de usuário", list(user_options.keys()))
    if st.button("Ativar/Inativar usuário"):
        user_id, is_active = user_options[selected]
        toggle_user_status(user_id, is_active)
        st.success("Status do usuário atualizado.")
        st.rerun()


def render_admin_departments():
    render_hero("Gestão de setores", "Criação, exclusão e vínculo de setores aos usuários.")
    with st.form("create_department_form"):
        name = st.text_input("Novo setor")
        if st.form_submit_button("Criar setor"):
            if name.strip():
                create_department(name)
                st.success("Setor criado.")
                st.rerun()
    departments = list_departments()
    users = list_users()
    if not departments.empty:
        dep_map = {row["name"]: int(row["id"]) for _, row in departments.iterrows()}
        dep_sel = st.selectbox("Excluir setor", list(dep_map.keys()))
        if st.button("Excluir setor"):
            try:
                delete_department(dep_map[dep_sel])
                st.success("Setor removido.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    st.markdown("### Vincular setor a usuário")
    if not users.empty and not departments.empty:
        user_map = {f"{r['full_name']} ({r['email']})": int(r['id']) for _, r in users.iterrows()}
        dep_map = {row["name"]: int(row["id"]) for _, row in departments.iterrows()}
        c1, c2 = st.columns(2)
        us = c1.selectbox("Usuário", list(user_map.keys()))
        dp = c2.selectbox("Setor", list(dep_map.keys()))
        if st.button("Vincular setor"):
            assign_user_department(user_map[us], dep_map[dp])
            st.success("Setor vinculado.")


def render_admin_logs():
    render_hero("Logs e trilha de auditoria", "Acompanhamento das alterações realizadas nas ocorrências do sistema.")
    logs = run_select(
        """
        SELECT
            ou.created_at,
            o.protocol,
            u.full_name,
            ou.action_type,
            ou.previous_status,
            ou.new_status,
            ou.note
        FROM occurrence_updates ou
        INNER JOIN occurrences o ON o.id = ou.occurrence_id
        INNER JOIN users u ON u.id = ou.user_id
        ORDER BY ou.created_at DESC
        LIMIT 300
        """
    )
    if logs.empty:
        st.info("Nenhum log encontrado.")
    else:
        logs.columns = ["Data", "Protocolo", "Usuário", "Ação", "Status anterior", "Novo status", "Observação"]
        safe_dataframe(logs, hide_index=True, use_container_width=True, height=420)
