import pandas as pd
import streamlit as st

from src.config import ROLE_LABELS
from src.controllers.occurrence_controller import get_occurrences
from src.controllers.report_controller import (manager_department_summary, manager_priority_summary,
    manager_status_summary, mean_resolution_time_hours, metrics_for_user)
from src.controllers.user_controller import list_users
from src.db import fetch_scalar
from src.ui.components import metric_cards, open_detail_button, render_hero, render_occurrences_table, safe_chart, safe_dataframe


def render_solicitante_dashboard(user: dict):
    render_hero("Painel do solicitante", "Acompanhe suas ocorrências, o histórico e o andamento das demandas.")
    metric_cards(metrics_for_user(user["role"], int(user["id"])))
    df = get_occurrences(user["role"], int(user["id"]))

    st.markdown("### Minhas ocorrências")
    render_occurrences_table(df)
    open_detail_button(df, "solicitante_dashboard")


def render_atendente_dashboard(user: dict):
    render_hero("Painel do atendente", "Visão operacional das ocorrências para triagem, atualização e conclusão dos atendimentos.")
    metrics = metrics_for_user("gestor", int(user["id"]))
    metric_cards(metrics)
    df = get_occurrences("atendente", int(user["id"]))
    col1, col2 = st.columns([1.3, 1])
    with col1:
        st.markdown("### Fila priorizada")
        render_occurrences_table(df.head(10), height=330)
        open_detail_button(df, "atendente_dashboard")
    with col2:
        st.markdown("### Resumo operacional")
        critical = int((df["priority"] == "Crítica").sum()) if not df.empty else 0
        assigned_to_me = int((df["assigned_to"] == int(user["id"])).sum()) if not df.empty else 0
        st.markdown(f"- {len(df)} ocorrências visíveis na fila")
        st.markdown(f"- {critical} ocorrências críticas")
        st.markdown(f"- {assigned_to_me} atribuídas a você")
        st.markdown("- Histórico completo preservado para auditoria e rastreabilidade")


def render_supervisor_dashboard(user: dict):
    render_hero("Painel do supervisor", "Triagem das ocorrências: priorização e delegação para atendentes.")
    df = get_occurrences("gestor", int(user["id"]))
    metric_cards(metrics_for_user("gestor", int(user["id"])))
    st.markdown("### Ocorrências para triagem")
    render_occurrences_table(df.head(20))
    open_detail_button(df, "supervisor_dashboard")


def render_manager_dashboard(user: dict):
    render_hero("Relatórios e indicadores", "Painel gerencial para análise de volume, tempos de resposta e recorrências.")
    metrics = metrics_for_user("gestor", int(user["id"]))
    metric_cards(metrics)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Ocorrências por status")
        status_df = manager_status_summary().set_index("status")
        safe_chart(st.bar_chart, status_df, "Sem ocorrências por status para exibir.")
    with c2:
        st.markdown("### Ocorrências por prioridade")
        prio_df = manager_priority_summary().set_index("priority")
        safe_chart(st.bar_chart, prio_df, "Sem ocorrências por prioridade para exibir.")

    st.markdown("### Leituras rápidas do painel")
    st.markdown(f"- Tempo médio de resolução: **{mean_resolution_time_hours():.2f} horas**")
    top_departments = manager_department_summary()
    if not top_departments.empty:
        st.markdown(
            f"- Setor mais demandante: **{top_departments.iloc[0]['department']}** com **{int(top_departments.iloc[0]['quantidade'])}** ocorrências"
        )
    df = get_occurrences("gestor", int(user["id"]))
    open_detail_button(df, "manager_dashboard")


def render_admin_dashboard(user: dict):
    render_hero("Administração do sistema", "Gestão de perfis de acesso, usuários, trilha de auditoria e sustentação do sistema.")
    total_users = fetch_scalar("SELECT COUNT(*) FROM users") or 0
    active_users = fetch_scalar("SELECT COUNT(*) FROM users WHERE is_active = 1") or 0
    last_backup_label = "Procedimento manual/documentado"

    c1, c2, c3 = st.columns(3)
    c1.metric("Usuários cadastrados", int(total_users))
    c2.metric("Usuários ativos", int(active_users))
    c3.metric("Backup", last_backup_label)

    st.markdown("### Perfis ativos")
    users_df = list_users()
    if not users_df.empty:
        role_rows = []
        for _, r in users_df.iterrows():
            for rr in (r["roles"] or "").split(","):
                rr = rr.strip()
                if rr:
                    role_rows.append(rr)
        grouped = pd.DataFrame({"role": role_rows}).groupby("role").size().reset_index(name="quantidade") if role_rows else pd.DataFrame(columns=["role","quantidade"])
        grouped["role"] = grouped["role"].map(lambda x: ROLE_LABELS.get(x, x))
        safe_dataframe(grouped.rename(columns={"role": "Perfil", "quantidade": "Quantidade"}), hide_index=True, use_container_width=True)
