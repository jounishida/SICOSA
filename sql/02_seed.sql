USE suporte_ocorrencias;

-- Senha padrão para todos os usuários abaixo: Senha@123
-- Hash SHA-256: a2ca37fe6fdc490b8f7ce841e1701a169d2b1697c6b5b5c63f94abb8f9b6d6dd

INSERT INTO users (id, full_name, email, password_hash, is_active) VALUES
(1, 'Jonathan Ken Nishida', 'jonathan.nishida', 'a2ca37fe6fdc490b8f7ce841e1701a169d2b1697c6b5b5c63f94abb8f9b6d6dd', 1),
(2, 'Marcos Silva', 'marcos.silva', 'a2ca37fe6fdc490b8f7ce841e1701a169d2b1697c6b5b5c63f94abb8f9b6d6dd', 1),
(3, 'Jéssica Costa', 'jessica.costa', 'a2ca37fe6fdc490b8f7ce841e1701a169d2b1697c6b5b5c63f94abb8f9b6d6dd', 1),
(4, 'Carlos Menezes', 'carlos.menezes', 'a2ca37fe6fdc490b8f7ce841e1701a169d2b1697c6b5b5c63f94abb8f9b6d6dd', 1),
(5, 'Administrador do Sistema', 'admin', 'a2ca37fe6fdc490b8f7ce841e1701a169d2b1697c6b5b5c63f94abb8f9b6d6dd', 1);




INSERT INTO departments (id, name) VALUES
(1, 'Almoxarifado'),
(2, 'Setor de Apoio'),
(3, 'Gestão'),
(4, 'TI'),
(5, 'Jurídico'),
(6, 'Financeiro'),
(7, 'Recursos Humanos'),
(8, 'Compras'),
(9, 'Comercial'),
(10, 'Operações');

INSERT INTO user_departments (user_id, department_id) VALUES
(1, 1),
(2, 2),
(3, 2),
(4, 3),
(5, 4),
(4, 5);

INSERT INTO profiles (id, name, label) VALUES
(1, 'solicitante', 'Solicitante'),
(2, 'atendente', 'Atendente'),
(3, 'gestor', 'Gestor'),
(4, 'administrador', 'Administrador'),
(5, 'supervisor', 'Supervisor');

INSERT IGNORE INTO user_profiles (user_id, profile_id) VALUES
(1, 1),
(1, 2),
(1, 3),
(1, 4),
(1, 5),
(2, 2),
(3, 2),
(4, 3),
(4, 5),
(5, 4);

INSERT INTO occurrences (
    id, protocol, requester_id, title, description, department, category,
    priority, status, assigned_to, due_at, created_at, updated_at, closed_at, closure_notes
) VALUES
(1, '2026-0001', 1, 'Falta de materiais para manutenção preventiva', 'Itens críticos do estoque não foram repostos e a manutenção preventiva pode atrasar.', 'Almoxarifado', 'Materiais', 'Alta', 'Em atendimento', 2, DATE_ADD(NOW(), INTERVAL 8 HOUR), DATE_SUB(NOW(), INTERVAL 6 HOUR), DATE_SUB(NOW(), INTERVAL 30 MINUTE), NULL, NULL),
(2, '2026-0002', 1, 'Impressora sem conexão com a rede', 'Equipamento do setor administrativo não imprime após queda da conexão local.', 'Suporte Administrativo', 'Equipamentos', 'Crítica', 'Pendente', 3, DATE_ADD(NOW(), INTERVAL 4 HOUR), DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_SUB(NOW(), INTERVAL 3 HOUR), NULL, NULL),
(3, '2026-0003', 1, 'Troca de luminária no corredor B', 'Luminária apagada desde a semana passada, afetando iluminação do corredor.', 'Serviços Gerais', 'Infraestrutura', 'Média', 'Encerrada', 2, DATE_SUB(NOW(), INTERVAL 20 HOUR), DATE_SUB(NOW(), INTERVAL 3 DAY), DATE_SUB(NOW(), INTERVAL 1 DAY), DATE_SUB(NOW(), INTERVAL 1 DAY), 'Lâmpada substituída e circuito revisado.');

INSERT INTO occurrence_updates (occurrence_id, user_id, action_type, previous_status, new_status, note, created_at) VALUES
(1, 1, 'criacao', NULL, 'Aberta', 'Ocorrência registrada pelo solicitante.', DATE_SUB(NOW(), INTERVAL 6 HOUR)),
(1, 2, 'status', 'Aberta', 'Em atendimento', 'Triagem realizada e fornecedor acionado.', DATE_SUB(NOW(), INTERVAL 5 HOUR)),
(2, 1, 'criacao', NULL, 'Aberta', 'Ocorrência registrada pelo solicitante.', DATE_SUB(NOW(), INTERVAL 1 DAY)),
(2, 3, 'status', 'Aberta', 'Pendente', 'Aguardando liberação de acesso ao equipamento para atendimento.', DATE_SUB(NOW(), INTERVAL 3 HOUR)),
(3, 1, 'criacao', NULL, 'Aberta', 'Ocorrência registrada pelo solicitante.', DATE_SUB(NOW(), INTERVAL 3 DAY)),
(3, 2, 'status', 'Aberta', 'Em atendimento', 'Equipe elétrica designada para o local.', DATE_SUB(NOW(), INTERVAL 2 DAY)),
(3, 2, 'encerramento', 'Em atendimento', 'Encerrada', 'Luminária substituída e funcionamento validado.', DATE_SUB(NOW(), INTERVAL 1 DAY));
