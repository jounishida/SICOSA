CREATE DATABASE IF NOT EXISTS suporte_ocorrencias
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE suporte_ocorrencias;

DROP TABLE IF EXISTS occurrence_attachments;
DROP TABLE IF EXISTS occurrence_updates;
DROP TABLE IF EXISTS occurrences;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash CHAR(64) NOT NULL,
    role ENUM('solicitante', 'atendente', 'gestor', 'administrador') NOT NULL,
    department VARCHAR(100) NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login DATETIME NULL
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
    CONSTRAINT fk_occurrence_assigned_to FOREIGN KEY (assigned_to) REFERENCES users(id),
    INDEX idx_occurrences_status (status),
    INDEX idx_occurrences_priority (priority),
    INDEX idx_occurrences_requester (requester_id),
    INDEX idx_occurrences_assigned_to (assigned_to),
    INDEX idx_occurrences_department (department)
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
    CONSTRAINT fk_update_user FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_updates_occurrence (occurrence_id),
    INDEX idx_updates_created_at (created_at)
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
    CONSTRAINT fk_attachment_user FOREIGN KEY (uploaded_by) REFERENCES users(id),
    INDEX idx_attachments_occurrence (occurrence_id)
) ENGINE=InnoDB;
