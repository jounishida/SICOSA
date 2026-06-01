USE suporte_ocorrencias;

CREATE TABLE IF NOT EXISTS profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name ENUM('solicitante', 'atendente', 'gestor', 'administrador') NOT NULL UNIQUE,
    label VARCHAR(40) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INT NOT NULL,
    profile_id INT NOT NULL,
    PRIMARY KEY (user_id, profile_id),
    CONSTRAINT fk_user_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_user_profiles_profile FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

INSERT IGNORE INTO profiles (name, label) VALUES
('solicitante', 'Solicitante'),
('atendente', 'Atendente'),
('gestor', 'Gestor'),
('administrador', 'Administrador');

SET @has_role_col = (
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'users'
      AND column_name = 'role'
);

SET @sql_backfill = IF(
    @has_role_col > 0,
    'INSERT IGNORE INTO user_profiles (user_id, profile_id) SELECT u.id, p.id FROM users u INNER JOIN profiles p ON p.name = u.role',
    'SELECT 1'
);
PREPARE stmt_backfill FROM @sql_backfill;
EXECUTE stmt_backfill;
DEALLOCATE PREPARE stmt_backfill;

SET @sql_drop_role = IF(
    @has_role_col > 0,
    'ALTER TABLE users DROP COLUMN role',
    'SELECT 1'
);
PREPARE stmt_drop_role FROM @sql_drop_role;
EXECUTE stmt_drop_role;
DEALLOCATE PREPARE stmt_drop_role;
