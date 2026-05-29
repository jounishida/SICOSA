import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from datetime import datetime
from src.config import PRIORITY_OPTIONS, STATUS_OPTIONS
from src.controllers.occurrence_controller import (add_attachment, add_update, close_occurrence,
    create_occurrence, get_active_attendants, get_occurrence_attachments, get_occurrence_by_id,
    get_occurrence_updates, get_occurrences)
from src.controllers.user_controller import list_user_departments
from src.security import validate_files
from src.ui.components import open_detail_button, render_hero, render_occurrences_table, show_db_error


def render_new_occurrence(user: dict):
    render_hero("Abertura de ocorrência", "Registro da demanda com dados mínimos padronizados e anexos de apoio.")
    with st.form("new_occurrence_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Título resumido")
            user_depts = list_user_departments(int(user["id"]))
            dept_options = [""] + user_depts["name"].tolist()
            department = st.selectbox("Setor", dept_options, index=1 if len(dept_options) > 1 else 0)
        with col2:
            priority = st.selectbox("Prioridade", PRIORITY_OPTIONS, index=1)
            st.text_input("Data", value=datetime.now().strftime("%d/%m/%Y"), disabled=True)

        description = st.text_area(
            "Descrição detalhada",
            placeholder="Descreva o problema, o impacto na rotina, o local e qualquer informação relevante.",
            height=180,
        )
        uploaded_files = st.file_uploader(
            "Anexos e evidências",
            accept_multiple_files=True,
            type=None,
        )
        submitted = st.form_submit_button("Enviar ocorrência", use_container_width=True)

        if submitted:
            if not title.strip() or not department.strip() or not description.strip():
                st.error("Preencha título, setor e descrição para registrar a ocorrência.")
            else:
                try:
                    payload = {
                        "requester_id": int(user["id"]),
                        "title": title.strip(),
                        "description": description.strip(),
                        "department": department.strip(),
                        "category": None,
                        "priority": priority,
                        "assigned_to": None,
                    }
                    valid, msg = validate_files(uploaded_files or [])
                    if not valid:
                        st.error(msg)
                        return
                    attachments = [
                        {"file_name": file.name, "mime_type": file.type, "file_data": file.getvalue()}
                        for file in (uploaded_files or [])
                    ]
                    protocol = create_occurrence(payload, attachments)
                    st.success(f"Ocorrência registrada com sucesso. Protocolo: {protocol}")
                except SQLAlchemyError as e:
                    show_db_error(e)


def render_my_occurrences(user: dict):
    render_hero("Consulta de ocorrências", "Pesquise, filtre e acesse o detalhe das ocorrências registradas.")
    c1, c2, c3 = st.columns([1, 1, 2])
    key_scope = f"{user['role']}_{user['id']}"
    status = c1.selectbox("Status", [""] + STATUS_OPTIONS, format_func=lambda x: x or "Todos", key=f"my_occ_status_{key_scope}")
    priority = c2.selectbox("Prioridade", [""] + PRIORITY_OPTIONS, format_func=lambda x: x or "Todas", key=f"my_occ_priority_{key_scope}")
    search = c3.text_input("Pesquisar por protocolo, título ou descrição", key=f"my_occ_search_{key_scope}")

    df = get_occurrences(
        user["role"],
        int(user["id"]),
        filters={"status": status or None, "priority": priority or None, "search": search or None},
    )
    render_occurrences_table(df)
    open_detail_button(df, "solicitante_list")


def render_queue(user: dict):
    render_hero("Fila de atendimento", "Triagem, atualização e acompanhamento operacional das ocorrências.")
    c1, c2, c3 = st.columns([1, 1, 2])
    status = c1.selectbox("Status", [""] + STATUS_OPTIONS, format_func=lambda x: x or "Todos", key="queue_status")
    priority = c2.selectbox("Prioridade", [""] + PRIORITY_OPTIONS, format_func=lambda x: x or "Todas", key="queue_priority")
    search = c3.text_input("Pesquisar por protocolo, título ou descrição", key="queue_search")

    df = get_occurrences(
        user["role"],
        int(user["id"]),
        filters={"status": status or None, "priority": priority or None, "search": search or None},
    )
    render_occurrences_table(df)
    open_detail_button(df, "queue_list")


def render_supervisor_triage(user: dict):
    render_hero("Triagem de tarefas", "Ajuste criticidade e delegue chamados para atendentes.")
    df = get_occurrences("gestor", int(user["id"]))
    render_occurrences_table(df)
    open_detail_button(df, "supervisor_queue")


def render_occurrence_detail(user: dict):
    role = user["role"]
    scope_role = "gestor" if role == "supervisor" else role

    fc1, fc2, fc3 = st.columns([1, 1, 2])
    status = fc1.selectbox("Status", [""] + STATUS_OPTIONS, format_func=lambda x: x or "Todos", key="detail_filter_status")
    priority = fc2.selectbox("Prioridade", [""] + PRIORITY_OPTIONS, format_func=lambda x: x or "Todas", key="detail_filter_priority")
    search = fc3.text_input("Pesquisar por protocolo, título ou descrição", key="detail_filter_search")

    visible = get_occurrences(
        scope_role,
        int(user["id"]),
        filters={"status": status or None, "priority": priority or None, "search": search or None},
    )
    if visible.empty:
        st.warning("Nenhuma ocorrência disponível para os filtros selecionados.")
        return

    options = {f"{row['protocol']} — {row['title']}": int(row['id']) for _, row in visible.iterrows()}
    current_id = st.session_state.get("selected_occurrence_id")
    labels = list(options.keys())
    current_label = labels[0]
    for label, oid in options.items():
        if oid == current_id:
            current_label = label
            break
    selected_label = st.selectbox("Selecionar ocorrência", labels, index=labels.index(current_label), key="detail_picker")
    occurrence_id = options[selected_label]
    st.session_state["selected_occurrence_id"] = occurrence_id

    df = get_occurrence_by_id(int(occurrence_id))
    if df.empty:
        st.error("Ocorrência não encontrada.")
        return

    row = df.iloc[0]
    if user["role"] == "solicitante" and int(row["requester_id"]) != int(user["id"]):
        st.error("Você não possui permissão para visualizar esta ocorrência.")
        return

    render_hero(
        f"Ocorrência {row['protocol']}",
        f"{row['department']} • {row['title']} • Aberta em {pd.to_datetime(row['created_at']).strftime('%d/%m/%Y às %H:%M')}",
    )

    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("### Dados principais")
        st.write(f"**Descrição:** {row['description']}")
        st.write(f"**Solicitante:** {row['requester_name']} ({row['requester_email']})")
        st.write(f"**Responsável:** {row['assigned_to_name']}")
        st.write(f"**Categoria:** {row['category'] or 'Não informada'}")
        if row["closure_notes"]:
            st.write(f"**Solução adotada:** {row['closure_notes']}")
    with c2:
        st.markdown("### Status e classificação")
        st.metric("Status", row["status"])
        st.metric("Prioridade", row["priority"])
        due_label = pd.to_datetime(row["due_at"]).strftime("%d/%m/%Y %H:%M") if pd.notna(row["due_at"]) else "Não definido"
        st.write(f"**SLA estimado:** {due_label}")
        if pd.notna(row["closed_at"]):
            st.write(f"**Encerrada em:** {pd.to_datetime(row['closed_at']).strftime('%d/%m/%Y %H:%M')}")

    st.markdown("### Histórico da ocorrência")
    updates = get_occurrence_updates(int(occurrence_id))
    if updates.empty:
        st.info("Nenhuma atualização registrada.")
    else:
        for _, item in updates.iterrows():
            created = pd.to_datetime(item["created_at"]).strftime("%d/%m/%Y %H:%M")
            st.markdown(
                f"**{created}** — {item['actor_name']} · {item['action_type']}  \n{item['note']}"
            )
            st.divider()

    st.markdown("### Anexos")
    attachments = get_occurrence_attachments(int(occurrence_id))
    if attachments.empty:
        st.caption("Sem anexos para esta ocorrência.")
    else:
        for _, item in attachments.iterrows():
            st.download_button(
                f"Baixar {item['file_name']}",
                data=item["file_data"],
                file_name=item["file_name"],
                mime=item["mime_type"] or "application/octet-stream",
                key=f"download_{item['id']}",
            )

    st.markdown("### Registrar nova interação")
    if user["role"] == "atendente" and (pd.isna(row["assigned_to"]) or row["assigned_to"] != int(user["id"])):
        if st.button("Assumir chamado"):
            add_update(int(occurrence_id), int(user["id"]), "Chamado assumido pelo atendente.", None, int(user["id"]), None)
            st.success("Chamado assumido com sucesso.")
            st.rerun()
    attendants = get_active_attendants()
    attendant_map = {"Manter responsável atual": None}
    attendant_map.update({row["full_name"]: int(row["id"]) for _, row in attendants.iterrows()})

    with st.form("detail_update_form"):
        c1, c2 = st.columns(2)
        note = c1.text_area("Comentário ou atualização", height=120)
        selected_status = c2.selectbox(
            "Novo status",
            ["Sem alteração"] + STATUS_OPTIONS,
            index=0 if role == "solicitante" else 1,
        )
        selected_assignee = st.selectbox("Responsável", list(attendant_map.keys()))
        selected_priority = st.selectbox("Nova criticidade", ["Sem alteração"] + PRIORITY_OPTIONS, index=0)
        new_files = st.file_uploader("Novos anexos", accept_multiple_files=True, key="detail_files")
        submitted = st.form_submit_button("Salvar atualização")
        if submitted:
            if not note.strip() and not new_files and selected_status == "Sem alteração" and selected_assignee == "Manter responsável atual" and selected_priority == "Sem alteração":
                st.error("Informe ao menos um comentário, uma mudança de status, um responsável ou um anexo.")
            else:
                if role == "solicitante":
                    # Solicitante pode comentar e anexar, mas não alterar status/atribuição.
                    selected_status = "Sem alteração"
                    selected_assignee = "Manter responsável atual"
                    selected_priority = "Sem alteração"
                try:
                    add_update(
                        int(occurrence_id),
                        int(user["id"]),
                        note.strip() or "Atualização registrada.",
                        None if selected_status == "Sem alteração" else selected_status,
                        attendant_map[selected_assignee],
                        None if selected_priority == "Sem alteração" else selected_priority,
                    )
                    if new_files:
                        valid, msg = validate_files(new_files)
                        if not valid:
                            st.error(msg)
                            return
                        add_attachment(int(occurrence_id), new_files, int(user["id"]))
                    st.success("Atualização registrada com sucesso.")
                    st.rerun()
                except SQLAlchemyError as e:
                    show_db_error(e)

    if role in {"atendente", "administrador"}:
        st.markdown("### Encerramento")
        with st.form("close_occurrence_form"):
            closure_notes = st.text_area("Solução adotada", height=100)
            close_submitted = st.form_submit_button("Encerrar ocorrência")
            if close_submitted:
                if not closure_notes.strip():
                    st.error("Descreva a solução adotada antes de encerrar a ocorrência.")
                else:
                    try:
                        close_occurrence(int(occurrence_id), int(user["id"]), closure_notes.strip())
                        st.success("Ocorrência encerrada com sucesso.")
                        st.rerun()
                    except SQLAlchemyError as e:
                        show_db_error(e)
