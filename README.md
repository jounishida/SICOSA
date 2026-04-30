# Sistema de Cadastro de Ocorrências do Setor de Apoio

Projeto Streamlit com perfis de **solicitante**, **atendente**, **gestor** e **administrador**, integrado a banco de dados **MySQL**.

## Estrutura

```text
streamlit_ocorrencias/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
└── sql/
    ├── 01_schema.sql
    └── 02_seed.sql
```

## Como iniciar

### 1) Crie e ative um ambiente virtual

**Windows (PowerShell)**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux/macOS**

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Instale as dependências

```bash
pip install -r requirements.txt
```

### 3) Crie o banco e as tabelas

Execute o script de estrutura:

```bash
mysql -u root -p < sql/01_schema.sql
```

Depois carregue a massa inicial:

```bash
mysql -u root -p suporte_ocorrencias < sql/02_seed.sql
```


### 3.1) Migração para múltiplos perfis (quem já tem banco criado)

Se o seu banco já existe com a coluna `users.role`, rode antes:

```bash
mysql -u root -p suporte_ocorrencias < sql/03_migrate_profiles.sql
```

Esse script move os perfis para `user_profiles` e remove `role` da tabela `users`.

### 4) Configure a conexão com o MySQL

Copie o arquivo de exemplo e ajuste a URL:

**Windows (PowerShell)**

```powershell
Copy-Item .env.example .env
```

**Linux/macOS**

```bash
cp .env.example .env
```

Defina a variável `DATABASE_URL` antes de executar o app.

**Windows (PowerShell)**

```powershell
$env:DATABASE_URL="mysql+pymysql://root:1234@localhost:3306/suporte_ocorrencias?charset=utf8mb4"
```

**Linux/macOS**

```bash
export DATABASE_URL="mysql+pymysql://root:1234@localhost:3306/suporte_ocorrencias?charset=utf8mb4"
```

### 5) Rode o projeto

```bash
streamlit run app.py
```

## Usuários de exemplo

Todos usam a senha `Senha@123`.

- `jonathan.nishida@instituicao.br` — solicitante
- `marcos.silva@instituicao.br` — atendente
- `jessica.costa@instituicao.br` — atendente
- `carlos.menezes@instituicao.br` — gestor
- `admin@instituicao.br` — administrador

## O que já está implementado

- Login por perfil
- Dashboard por perfil
- Cadastro de ocorrência
- Consulta e filtros
- Detalhe com histórico
- Atualização de status e comentários
- Upload e download de anexos
- Relatórios gerenciais
- Cadastro e ativação/inativação de usuários
- Logs de auditoria

## Observações

- O app foi organizado como MVP funcional para apresentação acadêmica.
- O armazenamento de anexos está em `LONGBLOB`, adequado para protótipo e volumes moderados.
- Em ambiente produtivo, vale considerar armazenamento externo para arquivos grandes.
