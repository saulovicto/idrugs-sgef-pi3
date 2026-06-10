-- ============================================================
--  SGEF – Sistema de Gestão de Entregas para Farmácias
--  Script SQL para criação das tabelas no PostgreSQL
--  Banco: sgef_db
-- ============================================================
-- CREATE DATABASE sgef_db ENCODING 'UTF8';

-- ──────────────────────────────────────────────────────────
-- FUNÇÕES DE VALIDAÇÃO
-- ──────────────────────────────────────────────────────────

-- Valida CPF (algoritmo oficial — Lei nº 9.454/97)
CREATE OR REPLACE FUNCTION validar_cpf(cpf TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    c     TEXT;    soma INTEGER;    resto INTEGER;    i INTEGER;
BEGIN
    c := REGEXP_REPLACE(cpf, '[.\-]', '', 'g');
    IF LENGTH(c) <> 11 OR c !~ '^[0-9]+$' THEN RETURN FALSE; END IF;
    IF c = REPEAT(SUBSTRING(c, 1, 1), 11) THEN RETURN FALSE; END IF;
    soma := 0;
    FOR i IN 1..9 LOOP soma := soma + CAST(SUBSTRING(c,i,1) AS INTEGER) * (11-i); END LOOP;
    resto := (soma * 10) % 11;
    IF resto IN (10,11) THEN resto := 0; END IF;
    IF resto <> CAST(SUBSTRING(c,10,1) AS INTEGER) THEN RETURN FALSE; END IF;
    soma := 0;
    FOR i IN 1..10 LOOP soma := soma + CAST(SUBSTRING(c,i,1) AS INTEGER) * (12-i); END LOOP;
    resto := (soma * 10) % 11;
    IF resto IN (10,11) THEN resto := 0; END IF;
    IF resto <> CAST(SUBSTRING(c,11,1) AS INTEGER) THEN RETURN FALSE; END IF;
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION validar_cpf IS
    'Valida CPF conforme algoritmo oficial (Lei nº 9.454/97). Aceita 00000000000 ou 000.000.000-00.';


-- Valida CNPJ (algoritmo oficial — Receita Federal)
CREATE OR REPLACE FUNCTION validar_cnpj(cnpj TEXT)
RETURNS BOOLEAN AS $$
DECLARE
    c      TEXT;
    soma   INTEGER;
    resto  INTEGER;
    d1     INTEGER;
    d2     INTEGER;
    i      INTEGER;
    p1     INTEGER[] := ARRAY[5,4,3,2,9,8,7,6,5,4,3,2];
    p2     INTEGER[] := ARRAY[6,5,4,3,2,9,8,7,6,5,4,3,2];
BEGIN
    -- Remove pontuação: pontos, barras, hífens
    c := REGEXP_REPLACE(cnpj, '[.\-/]', '', 'g');

    -- Deve ter exatamente 14 dígitos numéricos
    IF LENGTH(c) <> 14 OR c !~ '^[0-9]+$' THEN
        RETURN FALSE;
    END IF;

    -- Rejeita sequências repetidas (00000000000000, 11111111111111, etc.)
    IF c = REPEAT(SUBSTRING(c, 1, 1), 14) THEN
        RETURN FALSE;
    END IF;

    -- 1º dígito verificador
    soma := 0;
    FOR i IN 1..12 LOOP
        soma := soma + CAST(SUBSTRING(c, i, 1) AS INTEGER) * p1[i];
    END LOOP;
    resto := soma % 11;
    d1 := CASE WHEN resto < 2 THEN 0 ELSE 11 - resto END;

    IF CAST(SUBSTRING(c, 13, 1) AS INTEGER) <> d1 THEN
        RETURN FALSE;
    END IF;

    -- 2º dígito verificador
    soma := 0;
    FOR i IN 1..13 LOOP
        soma := soma + CAST(SUBSTRING(c, i, 1) AS INTEGER) * p2[i];
    END LOOP;
    resto := soma % 11;
    d2 := CASE WHEN resto < 2 THEN 0 ELSE 11 - resto END;

    RETURN CAST(SUBSTRING(c, 14, 1) AS INTEGER) = d2;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

COMMENT ON FUNCTION validar_cnpj IS
    'Valida CNPJ conforme algoritmo oficial da Receita Federal. '
    'Aceita 00000000000000 ou 00.000.000/0000-00. '
    'Rejeita sequências repetidas e dígitos verificadores incorretos.';


-- ──────────────────────────────────────────────────────────
-- 1. FARMACIAS
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS farmacias (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(150) NOT NULL,

    -- CNPJ: armazenado no formato 00.000.000/0000-00 e validado pelo algoritmo oficial
    cnpj        VARCHAR(18)  NOT NULL UNIQUE
                    CHECK (validar_cnpj(cnpj)),

    email       VARCHAR(150) NOT NULL UNIQUE
                    CHECK (email ~* '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$'),

    senha_hash  VARCHAR(256),                   -- hash bcrypt do colaborador
    telefone    VARCHAR(20),
    endereco    VARCHAR(255),
    cidade      VARCHAR(100),
    ativo       BOOLEAN      NOT NULL DEFAULT TRUE,
    criado_em   TIMESTAMP    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  farmacias            IS 'Farmácias cadastradas na plataforma';
COMMENT ON COLUMN farmacias.cnpj       IS 'CNPJ no formato 00.000.000/0000-00 — validado pelo algoritmo da Receita Federal';
COMMENT ON COLUMN farmacias.senha_hash IS 'Hash bcrypt da senha do colaborador/farmacêutico';


-- ──────────────────────────────────────────────────────────
-- 2. CLIENTES
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clientes (
    id           SERIAL PRIMARY KEY,
    nome         VARCHAR(150) NOT NULL,
    email        VARCHAR(150) NOT NULL UNIQUE
                     CHECK (email ~* '^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$'),
    cpf          VARCHAR(14)  NOT NULL UNIQUE
                     CHECK (validar_cpf(cpf)),
    senha_hash   VARCHAR(256) NOT NULL,
    telefone     VARCHAR(20),
    endereco     VARCHAR(255),
    addr_rua     VARCHAR(150),
    addr_num     VARCHAR(20),
    addr_bairro  VARCHAR(100),
    addr_cep     VARCHAR(10),
    addr_ref     VARCHAR(200),
    ativo        BOOLEAN      NOT NULL DEFAULT TRUE,
    criado_em    TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- Migração segura: adiciona colunas novas em bancos existentes
DO $$
DECLARE cols TEXT[] := ARRAY[
    'telefone    VARCHAR(20)',
    'endereco    VARCHAR(255)',
    'addr_rua    VARCHAR(150)',
    'addr_num    VARCHAR(20)',
    'addr_bairro VARCHAR(100)',
    'addr_cep    VARCHAR(10)',
    'addr_ref    VARCHAR(200)'
];
    col_def TEXT;
    col_name TEXT;
BEGIN
    FOREACH col_def IN ARRAY cols LOOP
        col_name := split_part(trim(col_def), ' ', 1);
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='clientes' AND column_name=col_name
        ) THEN
            EXECUTE 'ALTER TABLE clientes ADD COLUMN ' || col_def;
        END IF;
    END LOOP;
END $$;

COMMENT ON TABLE  clientes       IS 'Clientes cadastrados no aplicativo';
COMMENT ON COLUMN clientes.cpf   IS 'CPF no formato 000.000.000-00; validado pelo algoritmo oficial';


-- ──────────────────────────────────────────────────────────
-- 3. PRODUTOS
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS produtos (
    id           SERIAL PRIMARY KEY,
    farmacia_id  INTEGER       NOT NULL REFERENCES farmacias(id) ON DELETE CASCADE,
    nome         VARCHAR(200)  NOT NULL,
    descricao    TEXT,
    preco        NUMERIC(10,2) NOT NULL CHECK (preco >= 0),
    estoque      INTEGER       NOT NULL DEFAULT 0 CHECK (estoque >= 0),
    categoria    VARCHAR(100),
    imagem_url   VARCHAR(500),
    ativo        BOOLEAN       NOT NULL DEFAULT TRUE,
    criado_em    TIMESTAMP     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  produtos           IS 'Produtos disponíveis em cada farmácia';
COMMENT ON COLUMN produtos.estoque   IS 'Quantidade disponível; não pode ser negativa';
COMMENT ON COLUMN produtos.ativo     IS 'Permite inativar sem remover do banco';


-- ──────────────────────────────────────────────────────────
-- 4. PEDIDOS
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pedidos (
    id           SERIAL PRIMARY KEY,
    cliente_id   INTEGER       NOT NULL REFERENCES clientes(id)  ON DELETE RESTRICT,
    farmacia_id  INTEGER       NOT NULL REFERENCES farmacias(id) ON DELETE RESTRICT,
    status       VARCHAR(50)   NOT NULL DEFAULT 'pendente'
                     CHECK (status IN ('pendente','confirmado','em_entrega','entregue','cancelado')),
    total        NUMERIC(10,2) CHECK (total >= 0),
    forma_pagto  VARCHAR(50),
    criado_em    TIMESTAMP     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  pedidos        IS 'Pedidos realizados pelos clientes';
COMMENT ON COLUMN pedidos.status IS 'Ciclo: pendente → confirmado → em_entrega → entregue | cancelado';


-- ──────────────────────────────────────────────────────────
-- 5. ITENS_PEDIDO
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS itens_pedido (
    id           SERIAL PRIMARY KEY,
    pedido_id    INTEGER       NOT NULL REFERENCES pedidos(id)  ON DELETE CASCADE,
    produto_id   INTEGER       NOT NULL REFERENCES produtos(id) ON DELETE RESTRICT,
    quantidade   INTEGER       NOT NULL CHECK (quantidade > 0),
    preco_unit   NUMERIC(10,2) NOT NULL CHECK (preco_unit >= 0)
);

COMMENT ON TABLE  itens_pedido            IS 'Itens individuais de cada pedido';
COMMENT ON COLUMN itens_pedido.preco_unit IS 'Preço no momento da compra (snapshot)';


-- ──────────────────────────────────────────────────────────
-- 6. CODIGOS_VERIFICACAO
-- ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS codigos_verificacao (
    id        SERIAL PRIMARY KEY,
    email     VARCHAR(150) NOT NULL,
    codigo    VARCHAR(6)   NOT NULL,
    usado     BOOLEAN      NOT NULL DEFAULT FALSE,
    expira_em TIMESTAMP    NOT NULL,
    criado_em TIMESTAMP    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE codigos_verificacao IS
    'Códigos OTP de 6 dígitos para verificação de e-mail e recuperação de senha';


-- ──────────────────────────────────────────────────────────
-- ÍNDICES
-- ──────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_clientes_email    ON clientes(email);
CREATE INDEX IF NOT EXISTS idx_clientes_cpf      ON clientes(cpf);
CREATE INDEX IF NOT EXISTS idx_farmacias_cnpj    ON farmacias(cnpj);
CREATE INDEX IF NOT EXISTS idx_farmacias_email   ON farmacias(email);
CREATE INDEX IF NOT EXISTS idx_produtos_farmacia ON produtos(farmacia_id);
CREATE INDEX IF NOT EXISTS idx_produtos_ativo    ON produtos(ativo);
CREATE INDEX IF NOT EXISTS idx_pedidos_cliente   ON pedidos(cliente_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_farmacia  ON pedidos(farmacia_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_status    ON pedidos(status);
CREATE INDEX IF NOT EXISTS idx_codigos_email     ON codigos_verificacao(email);
CREATE INDEX IF NOT EXISTS idx_itens_pedido      ON itens_pedido(pedido_id);


-- ──────────────────────────────────────────────────────────
-- DADOS DE EXEMPLO (seed)
-- Senhas placeholder — use POST /api/seed para gerar os hashes bcrypt corretos.
-- ──────────────────────────────────────────────────────────

INSERT INTO farmacias (nome, cnpj, email, senha_hash, telefone, endereco, cidade)
VALUES ('iDrugs Farmácia', '12.345.678/0001-99', 'contato@idrugs.com.br',
        '$2b$12$placeholder_use_api_seed', '(85) 99999-0000', 'Av. Beira Mar, 100', 'Fortaleza')
ON CONFLICT DO NOTHING;

INSERT INTO farmacias (nome, cnpj, email, senha_hash, telefone, endereco, cidade)
VALUES ('FarmaVida', '98.765.432/0001-11', 'contato@farmavida.com.br',
        '$2b$12$placeholder_use_api_seed', '(85) 88888-1111', 'Rua dos Jangadeiros, 55', 'Fortaleza')
ON CONFLICT DO NOTHING;

INSERT INTO farmacias (nome, cnpj, email, senha_hash, telefone, endereco, cidade)
VALUES ('Drogaria Saúde+', '11.222.333/0001-44', 'contato@saude.com.br',
        '$2b$12$placeholder_use_api_seed', '(85) 77777-2222', 'Av. Washington Soares, 200', 'Fortaleza')
ON CONFLICT DO NOTHING;

INSERT INTO produtos (farmacia_id, nome, descricao, preco, estoque, categoria)
SELECT f.id, p.nome, p.descricao, p.preco, p.estoque, p.categoria
FROM farmacias f,
     (VALUES
        ('Dipirona 500mg',    'Cxa 10comp',    6.49, 50, 'Analgésico'),
        ('Paracetamol 500mg', 'Cxa 20comp',    9.89, 80, 'Analgésico'),
        ('Ibuprofeno 400mg',  'Cxa 12comp',   12.89, 40, 'Anti-inflamatório'),
        ('Amoxicilina 500mg', 'Cxa 21cap',    24.90, 30, 'Antibiótico'),
        ('Ambroxol',          'Frasco 120ml', 18.50, 25, 'Expectorante')
     ) AS p(nome, descricao, preco, estoque, categoria)
WHERE f.cnpj = '12.345.678/0001-99'
ON CONFLICT DO NOTHING;

INSERT INTO produtos (farmacia_id, nome, descricao, preco, estoque, categoria)
SELECT f.id, p.nome, p.descricao, p.preco, p.estoque, p.categoria
FROM farmacias f,
     (VALUES
        ('Vitamina C',      'Tubo 50comp', 14.90, 60, 'Suplemento'),
        ('Loratadina 10mg', 'Cxa 12comp',   8.50, 45, 'Antialérgico'),
        ('Omeprazol 20mg',  'Cxa 28cap',   22.00, 35, 'Gastro')
     ) AS p(nome, descricao, preco, estoque, categoria)
WHERE f.cnpj = '98.765.432/0001-11'
ON CONFLICT DO NOTHING;

INSERT INTO produtos (farmacia_id, nome, descricao, preco, estoque, categoria)
SELECT f.id, p.nome, p.descricao, p.preco, p.estoque, p.categoria
FROM farmacias f,
     (VALUES
        ('Buscopan Simples', 'Cxa 10comp',  11.90, 55, 'Espasmolítico'),
        ('Rivotril 2mg',     'Cxa 30comp',  35.00, 15, 'Ansiolítico')
     ) AS p(nome, descricao, preco, estoque, categoria)
WHERE f.cnpj = '11.222.333/0001-44'
ON CONFLICT DO NOTHING;


-- ──────────────────────────────────────────────────────────
-- TESTES DA VALIDAÇÃO DE CNPJ
-- ──────────────────────────────────────────────────────────
-- SELECT validar_cnpj('11.222.333/0001-44');   -- TRUE  (Drogaria Saúde+)
-- SELECT validar_cnpj('12.345.678/0001-99');   -- TRUE  (iDrugs)
-- SELECT validar_cnpj('00.000.000/0000-00');   -- FALSE (sequência repetida)
-- SELECT validar_cnpj('11.111.111/1111-11');   -- FALSE (sequência repetida)
-- SELECT validar_cnpj('12.345.678/0001-00');   -- FALSE (dígitos errados)
-- SELECT validar_cnpj('abc');                  -- FALSE (não numérico)

-- ──────────────────────────────────────────────────────────
-- TESTES DA VALIDAÇÃO DE CPF
-- ──────────────────────────────────────────────────────────
-- SELECT validar_cpf('529.982.247-25');  -- TRUE
-- SELECT validar_cpf('111.111.111-11');  -- FALSE
-- SELECT validar_cpf('000.000.000-00');  -- FALSE

-- ──────────────────────────────────────────────────────────
-- INICIALIZAÇÃO
-- ──────────────────────────────────────────────────────────
-- 1. psql -U postgres -d sgef_db -f schema.sql
-- 2. python app.py
-- 3. curl -X POST http://localhost:5000/api/seed
--
-- Login de demonstração (após seed):
--   contato@idrugs.com.br      | senha: 123456
--   contato@farmavida.com.br   | senha: 123456
--   contato@saude.com.br       | senha: 123456
-- ──────────────────────────────────────────────────────────
