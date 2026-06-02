-- Corrige grupos G e H que estavam invertidos.
-- Grupo G correto: Belgium, Egypt, Iran, New Zealand
-- Grupo H correto: Spain, Cabo Verde, Saudi Arabia, Uruguay
--
-- Uso (SQLite):  sqlite3 bolao_copa.db < scripts/fix_grupos_g_h.sql
-- Uso (Postgres): psql $DATABASE_URL -f scripts/fix_grupos_g_h.sql

BEGIN;

-- Times que pertencem ao Grupo H (estavam incorretamente no Grupo G)
UPDATE Jogos
SET grupo = 'GRUPO H'
WHERE fase = 'Fase de Grupos'
  AND (
    (LOWER(time_casa) IN ('spain', 'cabo verde', 'saudi arabia', 'uruguay'))
    OR
    (LOWER(time_fora) IN ('spain', 'cabo verde', 'saudi arabia', 'uruguay'))
  );

-- Times que pertencem ao Grupo G (estavam incorretamente no Grupo H)
UPDATE Jogos
SET grupo = 'GRUPO G'
WHERE fase = 'Fase de Grupos'
  AND (
    (LOWER(time_casa) IN ('belgium', 'egypt', 'iran', 'new zealand'))
    OR
    (LOWER(time_fora) IN ('belgium', 'egypt', 'iran', 'new zealand'))
  );

-- Verificacao: deve retornar 6 jogos para cada grupo
SELECT grupo, COUNT(*) AS jogos FROM Jogos
WHERE grupo IN ('GRUPO G', 'GRUPO H')
GROUP BY grupo
ORDER BY grupo;

COMMIT;
