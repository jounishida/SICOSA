import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()


st.set_page_config(
    page_title="Sistema de Cadastro de Ocorrências",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================
# Configuração e utilitários
# =========================
DB_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:1234@localhost:3306/suporte_ocorrencias?charset=utf8mb4",
)
APP_NAME = "Sistema de Cadastro de Ocorrências do Setor de Apoio"
STATUS_OPTIONS = ["Aberta", "Em atendimento", "Pendente", "Encerrada"]
PRIORITY_OPTIONS = ["Baixa", "Média", "Alta", "Crítica"]
ROLE_LABELS = {
    "solicitante": "Solicitante",
    "atendente": "Atendente",
    "gestor": "Gestor",
    "administrador": "Administrador",
}


st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    .hero {
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
        color: white;
        padding: 1.6rem 1.8rem;
        border-radius: 18px;
        margin-bottom: 1rem;
    }
    .hero h1 {margin: 0 0 .4rem 0; font-size: 2rem;}
    .hero p {margin: 0; opacity: .92;}
    .card {
        background: #f8fafc;
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


@st.cache_resource(show_spinner=False)
def get_engine():
    return create_engine(DB_URL, pool_pre_ping=True)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def show_db_error(error: Exception):
    st.error(
        "Não foi possível acessar o banco de dados. Verifique a variável DATABASE_URL e rode os scripts SQL antes de iniciar o app."
    )
    st.code(str(error))


def run_select(query: str, params: Optional[dict] = None) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(query), conn, params=params or {})


def run_execute(query: str, params: Optional[dict] = None):
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(query), params or {})


def fetch_scalar(query: str, params: Optional[dict] = None):
    engine = get_engine()
    with engine.connect() as conn:
        return conn.execute(text(query), params or {}).scalar()


# =========================
# Estado da sessão
# =========================
def init_state():
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("page", "Dashboard")
    st.session_state.setdefault("selected_occurrence_id", None)


init_state()


# =========================
# Acesso e perfis
# =========================
def authenticate_user(email: str, password: str, role: str) -> Optional[dict]:
    query = """
        SELECT id, full_name, email, role, department, is_active
        FROM users
        WHERE email = :email
          AND role = :role
          AND password_hash = :password_hash
          AND is_active = 1
        LIMIT 1
    """
    params = {"email": email.strip().lower(), "role": role, "password_hash": hash_password(password)}
    try:
        df = run_select(query, params)
        if df.empty:
            return None
        user = df.iloc[0].to_dict()
        run_execute("UPDATE users SET last_login = NOW() WHERE id = :id", {"id": int(user["id"])})
        return user
    except SQLAlchemyError as e:
        show_db_error(e)
        return None


def logout():
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.session_state["page"] = "Dashboard"
    st.session_state["selected_occurrence_id"] = None
    st.rerun()


# =========================
# Banco de dados
# =========================
def next_protocol() -> str:
    next_id = fetch_scalar("SELECT COALESCE(MAX(id), 0) + 1 FROM occurrences")
    return f"{datetime.now().year}-{int(next_id):04d}"


def default_due_at(priority: str) -> datetime:
    hours_by_priority = {"Baixa": 48, "Média": 24, "Alta": 8, "Crítica": 4}
    return datetime.now() + timedelta(hours=hours_by_priority.get(priority, 24))


def create_occurrence(payload: dict, attachments: List[dict]):
    protocol = next_protocol()
    due_at = default_due_at(payload["priority"])
    insert_occurrence = """
        INSERT INTO occurrences (
            protocol, requester_id, title, description, department, category,
            priority, status, assigned_to, due_at
        ) VALUES (
            :protocol, :requester_id, :title, :description, :department, :category,
            :priority, 'Aberta', :assigned_to, :due_at
        )
    """
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(insert_occurrence),
            {
                "protocol": protocol,
                "requester_id": payload["requester_id"],
                "title": payload["title"],
                "description": payload["description"],
                "department": payload["department"],
                "category": payload["category"],
                "priority": payload["priority"],
                "assigned_to": payload.get("assigned_to"),
                "due_at": due_at,
            },
        )
        occurrence_id = result.lastrowid
        conn.execute(
            text(
                """
                INSERT INTO occurrence_updates (
                    occurrence_id, user_id, action_type, previous_status, new_status, note
                ) VALUES (
                    :occurrence_id, :user_id, 'criacao', NULL, 'Aberta', :note
                )
                """
            ),
            {
                "occurrence_id": occurrence_id,
                "user_id": payload["requester_id"],
                "note": "Ocorrência registrada pelo solicitante.",
            },
        )

        for item in attachments:
            conn.execute(
                text(
                    """
                    INSERT INTO occurrence_attachments (
                        occurrence_id, file_name, mime_type, file_data, uploaded_by
                    ) VALUES (
                        :occurrence_id, :file_name, :mime_type, :file_data, :uploaded_by
                    )
                    """
                ),
                {
                    "occurrence_id": occurrence_id,
                    "file_name": item["file_name"],
                    "mime_type": item["mime_type"],
                    "file_data": item["file_data"],
                    "uploaded_by": payload["requester_id"],
                },
            )
    return protocol


def base_occurrence_query() -> str:
    return """
        SELECT
            o.id,
            o.protocol,
            o.title,
            o.department,
            o.category,
            o.priority,
            o.status,
            o.created_at,
            o.updated_at,
            o.closed_at,
            o.description,
            o.closure_notes,
            o.due_at,
            req.full_name AS requester_name,
            req.email AS requester_email,
            COALESCE(ass.full_name, 'Não definido') AS assigned_to_name,
            o.requester_id,
            o.assigned_to
        FROM occurrences o
        INNER JOIN users req ON req.id = o.requester_id
        LEFT JOIN users ass ON ass.id = o.assigned_to
    """


def get_occurrences(role: str, user_id: int, filters: Optional[Dict] = None) -> pd.DataFrame:
    filters = filters or {}
    query = base_occurrence_query() + " WHERE 1=1 "
    params = {}

    if role == "solicitante":
        query += " AND o.requester_id = :user_id "
        params["user_id"] = user_id

    if filters.get("status"):
        query += " AND o.status = :status "
        params["status"] = filters["status"]
    if filters.get("priority"):
        query += " AND o.priority = :priority "
        params["priority"] = filters["priority"]
    if filters.get("department"):
        query += " AND o.department LIKE :department "
        params["department"] = f"%{filters['department']}%"
    if filters.get("search"):
        query += " AND (o.protocol LIKE :search OR o.title LIKE :search OR o.description LIKE :search) "
        params["search"] = f"%{filters['search']}%"

    query += " ORDER BY FIELD(o.priority, 'Crítica','Alta','Média','Baixa'), o.created_at DESC "
    return run_select(query, params)


def get_occurrence_by_id(occurrence_id: int) -> pd.DataFrame:
    query = base_occurrence_query() + " WHERE o.id = :occurrence_id LIMIT 1"
    return run_select(query, {"occurrence_id": occurrence_id})


def get_occurrence_updates(occurrence_id: int) -> pd.DataFrame:
    query = """
        SELECT
            u.created_at,
            usr.full_name AS actor_name,
            u.action_type,
            u.previous_status,
            u.new_status,
            u.note
        FROM occurrence_updates u
        INNER JOIN users usr ON usr.id = u.user_id
        WHERE u.occurrence_id = :occurrence_id
        ORDER BY u.created_at ASC
    """
    return run_select(query, {"occurrence_id": occurrence_id})


def get_occurrence_attachments(occurrence_id: int) -> pd.DataFrame:
    query = """
        SELECT id, file_name, mime_type, file_data, uploaded_at
        FROM occurrence_attachments
        WHERE occurrence_id = :occurrence_id
        ORDER BY uploaded_at ASC
    """
    return run_select(query, {"occurrence_id": occurrence_id})


def get_active_attendants() -> pd.DataFrame:
    return run_select(
        """
        SELECT id, full_name
        FROM users
        WHERE role = 'atendente' AND is_active = 1
        ORDER BY full_name
        """
    )


def add_attachment(occurrence_id: int, uploaded_files: List, user_id: int):
    engine = get_engine()
    with engine.begin() as conn:
        for file in uploaded_files:
            conn.execute(
                text(
                    """
                    INSERT INTO occurrence_attachments (
                        occurrence_id, file_name, mime_type, file_data, uploaded_by
                    ) VALUES (
                        :occurrence_id, :file_name, :mime_type, :file_data, :uploaded_by
                    )
                    """
                ),
                {
                    "occurrence_id": occurrence_id,
                    "file_name": file.name,
                    "mime_type": file.type,
                    "file_data": file.getvalue(),
                    "uploaded_by": user_id,
                },
            )


def add_update(occurrence_id: int, user_id: int, note: str, new_status: Optional[str] = None, assigned_to: Optional[int] = None):
    current = get_occurrence_by_id(occurrence_id)
    if current.empty:
        return
    current_row = current.iloc[0]
    previous_status = current_row["status"]
    status_to_apply = new_status or previous_status

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE occurrences
                SET status = :status,
                    assigned_to = :assigned_to,
                    updated_at = NOW()
                WHERE id = :occurrence_id
                """
            ),
            {
                "status": status_to_apply,
                "assigned_to": assigned_to if assigned_to not in (None, "") else current_row["assigned_to"],
                "occurrence_id": occurrence_id,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO occurrence_updates (
                    occurrence_id, user_id, action_type, previous_status, new_status, note
                ) VALUES (
                    :occurrence_id, :user_id, :action_type, :previous_status, :new_status, :note
                )
                """
            ),
            {
                "occurrence_id": occurrence_id,
                "user_id": user_id,
                "action_type": "status" if new_status else "comentario",
                "previous_status": previous_status,
                "new_status": status_to_apply,
                "note": note,
            },
        )


def close_occurrence(occurrence_id: int, user_id: int, closure_notes: str):
    current = get_occurrence_by_id(occurrence_id)
    if current.empty:
        return
    previous_status = current.iloc[0]["status"]
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE occurrences
                SET status = 'Encerrada',
                    closure_notes = :closure_notes,
                    closed_at = NOW(),
                    updated_at = NOW()
                WHERE id = :occurrence_id
                """
            ),
            {"closure_notes": closure_notes, "occurrence_id": occurrence_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO occurrence_updates (
                    occurrence_id, user_id, action_type, previous_status, new_status, note
                ) VALUES (
                    :occurrence_id, :user_id, 'encerramento', :previous_status, 'Encerrada', :note
                )
                """
            ),
            {
                "occurrence_id": occurrence_id,
                "user_id": user_id,
                "previous_status": previous_status,
                "note": closure_notes,
            },
        )


def metrics_for_user(role: str, user_id: int) -> Dict[str, int]:
    params = {}
    where = ""
    if role == "solicitante":
        where = " WHERE requester_id = :user_id "
        params["user_id"] = user_id

    query = f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'Aberta' THEN 1 ELSE 0 END) AS abertas,
            SUM(CASE WHEN status = 'Em atendimento' THEN 1 ELSE 0 END) AS atendimento,
            SUM(CASE WHEN status = 'Pendente' THEN 1 ELSE 0 END) AS pendentes,
            SUM(CASE WHEN status = 'Encerrada' THEN 1 ELSE 0 END) AS encerradas
        FROM occurrences
        {where}
    """
    df = run_select(query, params)
    row = df.iloc[0].fillna(0).to_dict()
    return {k: int(v) for k, v in row.items()}


def manager_status_summary() -> pd.DataFrame:
    return run_select(
        """
        SELECT status, COUNT(*) AS quantidade
        FROM occurrences
        GROUP BY status
        ORDER BY quantidade DESC
        """
    )


def manager_department_summary() -> pd.DataFrame:
    return run_select(
        """
        SELECT department, COUNT(*) AS quantidade
        FROM occurrences
        GROUP BY department
        ORDER BY quantidade DESC
        LIMIT 10
        """
    )


def manager_priority_summary() -> pd.DataFrame:
    return run_select(
        """
        SELECT priority, COUNT(*) AS quantidade
        FROM occurrences
        GROUP BY priority
        ORDER BY FIELD(priority, 'Crítica','Alta','Média','Baixa')
        """
    )


def mean_resolution_time_hours() -> float:
    value = fetch_scalar(
        """
        SELECT ROUND(AVG(TIMESTAMPDIFF(MINUTE, created_at, closed_at)) / 60, 2)
        FROM occurrences
        WHERE closed_at IS NOT NULL
        """
    )
    return float(value or 0)


def list_users() -> pd.DataFrame:
    return run_select(
        """
        SELECT id, full_name, email, role, department, is_active, created_at, last_login
        FROM users
        ORDER BY full_name
        """
    )


def create_user(payload: dict):
    run_execute(
        """
        INSERT INTO users (full_name, email, password_hash, role, department, is_active)
        VALUES (:full_name, :email, :password_hash, :role, :department, 1)
        """,
        {
            "full_name": payload["full_name"],
            "email": payload["email"].strip().lower(),
            "password_hash": hash_password(payload["password"]),
            "role": payload["role"],
            "department": payload["department"],
        },
    )


def toggle_user_status(user_id: int, is_active: bool):
    run_execute(
        "UPDATE users SET is_active = :is_active, updated_at = NOW() WHERE id = :user_id",
        {"is_active": 0 if is_active else 1, "user_id": user_id},
    )


# =========================
# Componentes de interface
# =========================
def render_hero(title: str, subtitle: str):
    st.markdown(
        f"""
        <div class='hero'>
            <h1>{title}</h1>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_cards(metrics: Dict[str, int]):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", metrics.get("total", 0))
    c2.metric("Abertas", metrics.get("abertas", 0))
    c3.metric("Em atendimento", metrics.get("atendimento", 0))
    c4.metric("Pendentes", metrics.get("pendentes", 0))
    c5.metric("Encerradas", metrics.get("encerradas", 0))


def open_detail_button(df: pd.DataFrame, key_prefix: str):
    if df.empty:
        st.info("Nenhuma ocorrência encontrada para os filtros selecionados.")
        return

    options = {f"{row['protocol']} — {row['title']}": int(row['id']) for _, row in df.iterrows()}
    selected = st.selectbox("Abrir ocorrência", list(options.keys()), key=f"{key_prefix}_select")
    if st.button("Ver detalhe", key=f"{key_prefix}_button"):
        st.session_state["selected_occurrence_id"] = options[selected]
        st.session_state["page"] = "Detalhe da ocorrência"
        st.rerun()


def render_occurrences_table(df: pd.DataFrame, height: int = 350):
    if df.empty:
        st.info("Nenhuma ocorrência encontrada.")
        return

    display_df = df[[
        "protocol", "title", "department", "priority", "status", "requester_name", "assigned_to_name", "created_at"
    ]].copy()
    display_df.columns = [
        "Protocolo", "Título", "Setor", "Prioridade", "Status", "Solicitante", "Responsável", "Criada em"
    ]
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=height)


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


# =========================
# Telas por perfil
# =========================
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
        "administrador": ["Dashboard", "Usuários", "Logs", "Detalhe da ocorrência"],
    }

    options = pages_by_role[role]
    current = st.session_state.get("page", options[0])
    if current not in options:
        current = options[0]
    st.session_state["page"] = st.sidebar.radio("Tela", options, index=options.index(current))

    st.sidebar.divider()
    if st.sidebar.button("Sair", use_container_width=True):
        logout()


def render_solicitante_dashboard(user: dict):
    render_hero("Painel do solicitante", "Acompanhe suas ocorrências, o histórico e o andamento das demandas.")
    metric_cards(metrics_for_user(user["role"], int(user["id"])))
    df = get_occurrences(user["role"], int(user["id"]))

    st.markdown("### Minhas ocorrências")
    render_occurrences_table(df)
    open_detail_button(df, "solicitante_dashboard")


def render_new_occurrence(user: dict):
    render_hero("Abertura de ocorrência", "Registro da demanda com dados mínimos padronizados e anexos de apoio.")
    attendants = get_active_attendants()
    attendant_options = {"Definição na triagem": None}
    attendant_options.update({row["full_name"]: int(row["id"]) for _, row in attendants.iterrows()})

    with st.form("new_occurrence_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Título resumido")
            department = st.text_input("Setor", value=user.get("department") or "")
            category = st.text_input("Categoria", placeholder="Ex.: Infraestrutura, Materiais, Suporte")
        with col2:
            priority = st.selectbox("Prioridade", PRIORITY_OPTIONS, index=1)
            assigned_label = st.selectbox("Responsável inicial", list(attendant_options.keys()))
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
                        "category": category.strip() or None,
                        "priority": priority,
                        "assigned_to": attendant_options[assigned_label],
                    }
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
    status = c1.selectbox("Status", [""] + STATUS_OPTIONS, format_func=lambda x: x or "Todos")
    priority = c2.selectbox("Prioridade", [""] + PRIORITY_OPTIONS, format_func=lambda x: x or "Todas")
    search = c3.text_input("Pesquisar por protocolo, título ou descrição")

    df = get_occurrences(
        user["role"],
        int(user["id"]),
        filters={"status": status or None, "priority": priority or None, "search": search or None},
    )
    render_occurrences_table(df)
    open_detail_button(df, "solicitante_list")


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


def render_manager_dashboard(user: dict):
    render_hero("Relatórios e indicadores", "Painel gerencial para análise de volume, tempos de resposta e recorrências.")
    metrics = metrics_for_user("gestor", int(user["id"]))
    metric_cards(metrics)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Ocorrências por status")
        status_df = manager_status_summary().set_index("status")
        if not status_df.empty:
            st.bar_chart(status_df)
    with c2:
        st.markdown("### Ocorrências por prioridade")
        prio_df = manager_priority_summary().set_index("priority")
        if not prio_df.empty:
            st.bar_chart(prio_df)

    st.markdown("### Leituras rápidas do painel")
    st.markdown(f"- Tempo médio de resolução: **{mean_resolution_time_hours():.2f} horas**")
    top_departments = manager_department_summary()
    if not top_departments.empty:
        st.markdown(
            f"- Setor mais demandante: **{top_departments.iloc[0]['department']}** com **{int(top_departments.iloc[0]['quantidade'])}** ocorrências"
        )
    df = get_occurrences("gestor", int(user["id"]))
    open_detail_button(df, "manager_dashboard")


def render_reports(user: dict):
    render_hero("Painel gerencial consolidado", "Resumo visual do volume de ocorrências, recorrências e tempos médios de atendimento.")
    c1, c2 = st.columns(2)
    with c1:
        departments = manager_department_summary()
        st.markdown("### Ocorrências por setor")
        if not departments.empty:
            st.dataframe(departments.rename(columns={"department": "Setor", "quantidade": "Ocorrências"}), hide_index=True, use_container_width=True)
    with c2:
        status_df = manager_status_summary()
        st.markdown("### Distribuição por status")
        if not status_df.empty:
            st.dataframe(status_df.rename(columns={"status": "Status", "quantidade": "Ocorrências"}), hide_index=True, use_container_width=True)

    st.markdown("### Detalhamento")
    df = get_occurrences("gestor", int(user["id"]))
    render_occurrences_table(df)
    open_detail_button(df, "manager_report")


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
        grouped = users_df.groupby("role").size().reset_index(name="quantidade")
        grouped["role"] = grouped["role"].map(ROLE_LABELS)
        st.dataframe(grouped.rename(columns={"role": "Perfil", "quantidade": "Quantidade"}), hide_index=True, use_container_width=True)


def render_admin_users():
    render_hero("Gestão de usuários", "Criação de perfis, ativação e inativação de acessos do sistema.")
    st.markdown("### Novo usuário")
    with st.form("new_user_form"):
        c1, c2 = st.columns(2)
        full_name = c1.text_input("Nome completo")
        email = c2.text_input("E-mail")
        c3, c4, c5 = st.columns(3)
        role = c3.selectbox("Perfil", list(ROLE_LABELS.keys()), format_func=lambda x: ROLE_LABELS[x])
        department = c4.text_input("Setor")
        password = c5.text_input("Senha inicial", type="password", value="Senha@123")
        submitted = st.form_submit_button("Criar usuário")
        if submitted:
            if not full_name.strip() or not email.strip() or not password.strip():
                st.error("Preencha nome, e-mail e senha para criar o usuário.")
            else:
                try:
                    create_user({
                        "full_name": full_name,
                        "email": email,
                        "password": password,
                        "role": role,
                        "department": department,
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
    display_df["role"] = display_df["role"].map(ROLE_LABELS)
    display_df["is_active"] = display_df["is_active"].map({1: "Ativo", 0: "Inativo"})
    display_df.columns = ["ID", "Nome", "E-mail", "Perfil", "Setor", "Status", "Criado em", "Último acesso"]
    st.dataframe(display_df, hide_index=True, use_container_width=True, height=380)

    user_options = {f"{row['full_name']} — {ROLE_LABELS[row['role']]}": (int(row['id']), bool(row['is_active'])) for _, row in users.iterrows()}
    selected = st.selectbox("Alterar status de usuário", list(user_options.keys()))
    if st.button("Ativar/Inativar usuário"):
        user_id, is_active = user_options[selected]
        toggle_user_status(user_id, is_active)
        st.success("Status do usuário atualizado.")
        st.rerun()


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
        st.dataframe(logs, hide_index=True, use_container_width=True, height=420)


def render_occurrence_detail(user: dict):
    occurrence_id = st.session_state.get("selected_occurrence_id")
    if not occurrence_id:
        st.warning("Selecione uma ocorrência em uma das telas anteriores para ver o detalhe.")
        return

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
    role = user["role"]
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
        new_files = st.file_uploader("Novos anexos", accept_multiple_files=True, key="detail_files")
        submitted = st.form_submit_button("Salvar atualização")
        if submitted:
            if not note.strip() and not new_files and selected_status == "Sem alteração" and selected_assignee == "Manter responsável atual":
                st.error("Informe ao menos um comentário, uma mudança de status, um responsável ou um anexo.")
            else:
                if role == "solicitante":
                    # Solicitante pode comentar e anexar, mas não alterar status/atribuição.
                    selected_status = "Sem alteração"
                    selected_assignee = "Manter responsável atual"
                try:
                    add_update(
                        int(occurrence_id),
                        int(user["id"]),
                        note.strip() or "Atualização registrada.",
                        None if selected_status == "Sem alteração" else selected_status,
                        attendant_map[selected_assignee],
                    )
                    if new_files:
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


# =========================
# Fluxo principal
# =========================
def main():
    user = st.session_state.get("user")
    if not st.session_state.get("authenticated") or not user:
        render_login()
        return

    render_sidebar(user)
    page = st.session_state.get("page", "Dashboard")

    role = user["role"]
    if role == "solicitante":
        if page == "Dashboard":
            render_solicitante_dashboard(user)
        elif page == "Nova ocorrência":
            render_new_occurrence(user)
        elif page == "Minhas ocorrências":
            render_my_occurrences(user)
        else:
            render_occurrence_detail(user)
    elif role == "atendente":
        if page == "Dashboard":
            render_atendente_dashboard(user)
        elif page == "Fila de atendimento":
            render_queue(user)
        else:
            render_occurrence_detail(user)
    elif role == "gestor":
        if page == "Dashboard":
            render_manager_dashboard(user)
        elif page == "Relatórios":
            render_reports(user)
        else:
            render_occurrence_detail(user)
    elif role == "administrador":
        if page == "Dashboard":
            render_admin_dashboard(user)
        elif page == "Usuários":
            render_admin_users()
        elif page == "Logs":
            render_admin_logs()
        else:
            render_occurrence_detail(user)


if __name__ == "__main__":
    try:
        main()
    except SQLAlchemyError as e:
        show_db_error(e)
