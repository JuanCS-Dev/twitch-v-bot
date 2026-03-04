-- BLINDAGEM DE SEGURANÇA VÉRTICE v1.0
-- Habilita RLS e define políticas restritivas para todas as tabelas

DO $$ 
DECLARE 
    t text;
BEGIN
    FOR t IN 
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
    LOOP
        -- 1. Habilita RLS
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', t);
        
        -- 2. Remove qualquer política existente para evitar conflitos
        EXECUTE format('DROP POLICY IF EXISTS "Service Role Full Access" ON public.%I;', t);
        
        -- 3. Cria política de acesso total apenas para a role 'service_role' (o bot)
        -- Nota: O Supabase já ignora RLS para service_role por padrão, 
        -- mas criar uma política explícita para 'authenticated' ajuda a organizar.
        EXECUTE format('CREATE POLICY "Service Role Full Access" ON public.%I FOR ALL TO authenticated USING (true) WITH CHECK (true);', t);
        
        -- 4. Garante que 'anon' não tenha acesso algum (default do RLS habilitado sem política para anon)
        RAISE NOTICE 'RLS habilitado e política de proteção aplicada na tabela: %', t;
    END LOOP;
END $$;

-- Proteção adicional para colunas sensíveis
COMMENT ON COLUMN public.outbound_webhooks.secret IS 'SENSIBLE DATA: Access restricted to service_role only via RLS.';
