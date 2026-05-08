import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.config import APP_NAME, PRIORITY_OPTIONS, ROLE_LABELS, STATUS_OPTIONS
from src.security import hash_password, valid_email, valid_password_strength, validate_files
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


@st.cache_resource(show_spinner=False)
def get_engine():
    return create_engine(DB_URL, pool_pre_ping=True)


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
        SELECT DISTINCT u.id, u.full_name, u.email, p.name AS role, u.is_active
        FROM users u
        INNER JOIN user_profiles up ON up.user_id = u.id
        INNER JOIN profiles p ON p.id = up.profile_id
        WHERE u.email = :email
          AND p.name = :role
          AND u.password_hash = :password_hash
          AND u.is_active = 1
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
                "priority": new_priority or current_row["priority"],
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
                    "priority": new_priority or current_row["priority"],
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
    elif role == "atendente":
        query += """
            AND EXISTS (
                SELECT 1
                FROM user_departments ud
                INNER JOIN departments d ON d.id = ud.department_id
                WHERE ud.user_id = :user_id
                  AND d.name = o.department
            )
        """
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
        SELECT DISTINCT u.id, u.full_name
        FROM users u
        WHERE u.is_active = 1
          AND EXISTS (
              SELECT 1
              FROM user_profiles up
              INNER JOIN profiles p ON p.id = up.profile_id
              WHERE up.user_id = u.id
                AND p.name = 'atendente'
          )
        ORDER BY u.full_name
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
                    "priority": new_priority or current_row["priority"],
                "occurrence_id": occurrence_id,
                    "file_name": file.name,
                    "mime_type": file.type,
                    "file_data": file.getvalue(),
                    "uploaded_by": user_id,
                },
            )


def add_update(occurrence_id: int, user_id: int, note: str, new_status: Optional[str] = None, assigned_to: Optional[int] = None, new_priority: Optional[str] = None):
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
                    priority = :priority,
                    updated_at = NOW()
                WHERE id = :occurrence_id
                """
            ),
            {
                "status": status_to_apply,
                "assigned_to": assigned_to if assigned_to not in (None, "") else current_row["assigned_to"],
                "priority": new_priority or current_row["priority"],
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
                "priority": new_priority or current_row["priority"],
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
                "priority": new_priority or current_row["priority"],
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
        SELECT
            u.id,
            u.full_name,
            u.email,
            GROUP_CONCAT(DISTINCT p.name ORDER BY p.name SEPARATOR ',') AS roles,
            GROUP_CONCAT(DISTINCT d.name ORDER BY d.name SEPARATOR ',') AS departments,
            u.is_active,
            u.created_at,
            u.last_login
        FROM users u
        LEFT JOIN user_profiles up ON up.user_id = u.id
        LEFT JOIN profiles p ON p.id = up.profile_id
        LEFT JOIN user_departments ud ON ud.user_id = u.id
        LEFT JOIN departments d ON d.id = ud.department_id
        GROUP BY u.id, u.full_name, u.email, u.is_active, u.created_at, u.last_login
        ORDER BY u.full_name
        """
    )


def create_user(payload: dict):
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text("""
            INSERT INTO users (full_name, email, password_hash, is_active)
            VALUES (:full_name, :email, :password_hash, 1)
            """),
            {
                "full_name": payload["full_name"],
                "email": payload["email"].strip().lower(),
                "password_hash": hash_password(payload["password"]),
                            },
        )
        user_id = result.lastrowid
        conn.execute(
            text("""
            INSERT INTO user_profiles (user_id, profile_id)
            SELECT :user_id, id FROM profiles WHERE name = :role
            """),
            {"user_id": user_id, "role": payload["role"]},
        )






def list_profiles() -> pd.DataFrame:
    return run_select("SELECT id, name, label FROM profiles ORDER BY id")


def list_user_profiles(user_id: int) -> pd.DataFrame:
    return run_select("""
        SELECT p.id, p.name, p.label
        FROM user_profiles up
        INNER JOIN profiles p ON p.id = up.profile_id
        WHERE up.user_id = :user_id
        ORDER BY p.id
    """, {"user_id": user_id})


def assign_user_profile(user_id: int, profile_id: int):
    run_execute("INSERT IGNORE INTO user_profiles (user_id, profile_id) VALUES (:user_id, :profile_id)", {"user_id": user_id, "profile_id": profile_id})


def remove_user_profile(user_id: int, profile_id: int):
    qty = fetch_scalar("SELECT COUNT(*) FROM user_profiles WHERE user_id = :user_id", {"user_id": user_id}) or 0
    if int(qty) <= 1:
        raise ValueError("O usuário deve possuir ao menos um perfil.")
    run_execute("DELETE FROM user_profiles WHERE user_id = :user_id AND profile_id = :profile_id", {"user_id": user_id, "profile_id": profile_id})

def list_departments() -> pd.DataFrame:
    return run_select("SELECT id, name FROM departments ORDER BY name")


def list_user_departments(user_id: int) -> pd.DataFrame:
    return run_select("""
        SELECT d.id, d.name
        FROM user_departments ud
        INNER JOIN departments d ON d.id = ud.department_id
        WHERE ud.user_id = :user_id
        ORDER BY d.name
    """, {"user_id": user_id})


def assign_user_department(user_id: int, department_id: int):
    run_execute("INSERT IGNORE INTO user_departments (user_id, department_id) VALUES (:user_id, :department_id)", {"user_id": user_id, "department_id": department_id})


def remove_user_department(user_id: int, department_id: int):
    run_execute("DELETE FROM user_departments WHERE user_id = :user_id AND department_id = :department_id", {"user_id": user_id, "department_id": department_id})


def create_department(name: str):
    run_execute("INSERT INTO departments (name) VALUES (:name)", {"name": name.strip()})


def delete_department(department_id: int):
    linked = fetch_scalar("SELECT COUNT(*) FROM user_departments WHERE department_id = :id", {"id": department_id}) or 0
    if int(linked) > 0:
        raise ValueError("Não é possível excluir setor vinculado a usuários.")
    run_execute("DELETE FROM departments WHERE id = :id", {"id": department_id})

def toggle_user_status(user_id: int, is_active: bool):
    run_execute(
        "UPDATE users SET is_active = :is_active, updated_at = NOW() WHERE id = :user_id",
        {"is_active": 0 if is_active else 1, "user_id": user_id},
    )


# =========================
# Componentes de interface
# =========================


def safe_dataframe(df: pd.DataFrame, **kwargs):
    try:
        st.dataframe(df, **kwargs)
    except Exception as exc:
        message = str(exc).lower()
        if (
            "pyarrow" in message
            or "numpy.core.multiarray" in message
            or isinstance(exc, ImportError)
            or isinstance(getattr(exc, "__cause__", None), ImportError)
        ):
            st.warning("Ambiente sem compatibilidade com pyarrow/numpy para grid avançada. Exibindo tabela simplificada.")
            st.table(df)
        else:
            raise

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
    safe_dataframe(display_df, use_container_width=True, hide_index=True, height=height)


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


def render_solicitante_dashboard(user: dict):
    render_hero("Painel do solicitante", "Acompanhe suas ocorrências, o histórico e o andamento das demandas.")
    metric_cards(metrics_for_user(user["role"], int(user["id"])))
    df = get_occurrences(user["role"], int(user["id"]))

    st.markdown("### Minhas ocorrências")
    render_occurrences_table(df)
    open_detail_button(df, "solicitante_dashboard")


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
    status = c1.selectbox("Status", [""] + STATUS_OPTIONS, format_func=lambda x: x or "Todos", key=f"my_occ_status_{user["role"]}_{user["id"]}")
    priority = c2.selectbox("Prioridade", [""] + PRIORITY_OPTIONS, format_func=lambda x: x or "Todas", key=f"my_occ_priority_{user["role"]}_{user["id"]}")
    search = c3.text_input("Pesquisar por protocolo, título ou descrição", key=f"my_occ_search_{user["role"]}_{user["id"]}")

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




def render_supervisor_dashboard(user: dict):
    render_hero("Painel do supervisor", "Triagem das ocorrências: priorização e delegação para atendentes.")
    df = get_occurrences("gestor", int(user["id"]))
    metric_cards(metrics_for_user("gestor", int(user["id"])))
    st.markdown("### Ocorrências para triagem")
    render_occurrences_table(df.head(20))
    open_detail_button(df, "supervisor_dashboard")


def render_supervisor_triage(user: dict):
    render_hero("Triagem de tarefas", "Ajuste criticidade e delegue chamados para atendentes.")
    df = get_occurrences("gestor", int(user["id"]))
    render_occurrences_table(df)
    open_detail_button(df, "supervisor_queue")

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
    elif role == "supervisor":
        if page == "Dashboard":
            render_supervisor_dashboard(user)
        elif page == "Triagem":
            render_supervisor_triage(user)
        else:
            render_occurrence_detail(user)
    elif role == "administrador":
        if page == "Dashboard":
            render_admin_dashboard(user)
        elif page == "Usuários":
            render_admin_users()
        elif page == "Setores":
            render_admin_departments()
        else:
            render_admin_logs()


if __name__ == "__main__":
    try:
        main()
    except SQLAlchemyError as e:
        show_db_error(e)
