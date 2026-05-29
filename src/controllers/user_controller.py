import pandas as pd
from sqlalchemy import text

from src.db import fetch_scalar, get_engine, run_execute, run_select
from src.security import hash_password


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


def list_user_profile_names(user_id: int) -> list[str]:
    profiles = list_user_profiles(user_id)
    if profiles.empty:
        return []
    return profiles["name"].tolist()


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
