CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS tipos_banco (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS scripts_sql (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    tipo_banco TEXT NOT NULL,
    descricao TEXT NOT NULL,
    codigo_sql TEXT NOT NULL,
    observacoes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS correcoes_n2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    sistema TEXT NOT NULL,
    erro TEXT NOT NULL,
    causa TEXT NOT NULL,
    correcao TEXT NOT NULL,
    categoria TEXT NOT NULL,
    criticidade TEXT NOT NULL CHECK (criticidade IN ('Baixa', 'Média', 'Alta')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS anexos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_origem TEXT NOT NULL,
    origem_id INTEGER NOT NULL,
    nome_arquivo TEXT NOT NULL,
    caminho_arquivo TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_scripts_sql_busca ON scripts_sql (titulo, tipo_banco, deleted_at);
CREATE INDEX IF NOT EXISTS idx_correcoes_n2_busca ON correcoes_n2 (titulo, sistema, categoria, criticidade, deleted_at);
CREATE INDEX IF NOT EXISTS idx_anexos_origem ON anexos (tipo_origem, origem_id, deleted_at);
