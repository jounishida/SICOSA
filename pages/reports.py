import streamlit as st

from src.controllers.occurrence_controller import get_occurrences
from src.controllers.report_controller import manager_department_summary, manager_status_summary
from src.ui.components import open_detail_button, render_hero, render_occurrences_table, safe_dataframe


def render_reports(user: dict):
    render_hero("Painel gerencial consolidado", "Resumo visual do volume de ocorrências, recorrências e tempos médios de atendimento.")
    c1, c2 = st.columns(2)
    with c1:
        departments = manager_department_summary()
        st.markdown("### Ocorrências por setor")
        if not departments.empty:
            safe_dataframe(departments.rename(columns={"department": "Setor", "quantidade": "Ocorrências"}), hide_index=True, use_container_width=True)
    with c2:
        status_df = manager_status_summary()
        st.markdown("### Distribuição por status")
        if not status_df.empty:
            safe_dataframe(status_df.rename(columns={"status": "Status", "quantidade": "Ocorrências"}), hide_index=True, use_container_width=True)

    st.markdown("### Detalhamento")
    df = get_occurrences("gestor", int(user["id"]))
    render_occurrences_table(df)
    open_detail_button(df, "manager_report")
