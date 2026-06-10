-- ============================================================
--  iDrugs — Migração: Endereço estruturado + cálculo de frete
--  Adiciona estado / cidade / bairro / regiao em farmacias e clientes
--  Seguro para rodar em banco já existente (idempotente)
-- ============================================================

-- ── FARMÁCIAS ────────────────────────────────────────────────
DO $$
DECLARE cols TEXT[] := ARRAY[
    'estado  VARCHAR(2)',
    'bairro  VARCHAR(100)',
    'regiao  VARCHAR(20)'
];
    col_def  TEXT;
    col_name TEXT;
BEGIN
    FOREACH col_def IN ARRAY cols LOOP
        col_name := split_part(trim(col_def), ' ', 1);
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='farmacias' AND column_name=col_name
        ) THEN
            EXECUTE 'ALTER TABLE farmacias ADD COLUMN ' || col_def;
        END IF;
    END LOOP;
END $$;

-- ── CLIENTES ─────────────────────────────────────────────────
DO $$
DECLARE cols TEXT[] := ARRAY[
    'addr_estado  VARCHAR(2)',
    'addr_cidade  VARCHAR(100)',
    'addr_regiao  VARCHAR(20)'
];
    col_def  TEXT;
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

COMMENT ON COLUMN farmacias.estado IS 'UF (ex: CE). Necessário para cálculo de frete.';
COMMENT ON COLUMN farmacias.bairro IS 'Bairro (apenas Juazeiro do Norte tem catálogo fixo).';
COMMENT ON COLUMN farmacias.regiao IS 'Região do bairro (CENTRAL/NORTE/SUL/OESTE/LESTE) — calculada a partir do bairro.';
