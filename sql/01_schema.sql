CREATE DATABASE IF NOT EXISTS suporte_ocorrencias
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE suporte_ocorrencias;

DROP TABLE IF EXISTS occurrence_attachments;
DROP TABLE IF EXISTS occurrence_updates;
DROP TABLE IF EXISTS occurrences;
DROP TABLE IF EXISTS user_departments;
DROP TABLE IF EXISTS departments;
DROP TABLE IF EXISTS user_profiles;
DROP TABLE IF EXISTS profiles;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash CHAR(64) NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login DATETIME NULL
) ENGINE=InnoDB;

CREATE TABLE profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name ENUM('solicitante', 'atendente', 'gestor', 'administrador') NOT NULL UNIQUE,
    label VARCHAR(40) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE departments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE user_profiles (
    user_id INT NOT NULL,
    profile_id INT NOT NULL,
    PRIMARY KEY (user_id, profile_id),
    CONSTRAINT fk_user_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_profiles_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE user_departments (
    user_id INT NOT NULL,
    department_id INT NOT NULL,
    PRIMARY KEY (user_id, department_id),
    CONSTRAINT fk_user_departments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_departments_department FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE occurrences (
    id INT AUTO_INCREMENT PRIMARY KEY,
    protocol VARCHAR(20) NOT NULL UNIQUE,
    requester_id INT NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    department VARCHAR(100) NOT NULL,
    category VARCHAR(100) NULL,
    priority ENUM('Baixa', 'Média', 'Alta', 'Crítica') NOT NULL DEFAULT 'Média',
    status ENUM('Aberta', 'Em atendimento', 'Pendente', 'Encerrada') NOT NULL DEFAULT 'Aberta',
    assigned_to INT NULL,
    due_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    closed_at DATETIME NULL,
    closure_notes TEXT NULL,
    CONSTRAINT fk_occurrence_requester FOREIGN KEY (requester_id) REFERENCES users(id),
    CONSTRAINT fk_occurrence_assigned_to FOREIGN KEY (assigned_to) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE occurrence_updates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    occurrence_id INT NOT NULL,
    user_id INT NOT NULL,
    action_type ENUM('criacao', 'comentario', 'status', 'encerramento') NOT NULL,
    previous_status ENUM('Aberta', 'Em atendimento', 'Pendente', 'Encerrada') NULL,
    new_status ENUM('Aberta', 'Em atendimento', 'Pendente', 'Encerrada') NULL,
    note TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_update_occurrence FOREIGN KEY (occurrence_id) REFERENCES occurrences(id) ON DELETE CASCADE,
    CONSTRAINT fk_update_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE occurrence_attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    occurrence_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(120) NULL,
    file_data LONGBLOB NOT NULL,
    uploaded_by INT NOT NULL,
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_attachment_occurrence FOREIGN KEY (occurrence_id) REFERENCES occurrences(id) ON DELETE CASCADE,
    CONSTRAINT fk_attachment_user FOREIGN KEY (uploaded_by) REFERENCES users(id)
) ENGINE=InnoDB;
