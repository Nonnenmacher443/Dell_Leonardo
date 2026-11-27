-- =====================================================================
-- Consultas de negócio: Hotéis de Port Alder (MySQL 8 / MariaDB 10.11)
-- Rode depois de carregar_mysql.py. No Workbench: abra este arquivo e
-- execute uma consulta por vez (Ctrl+Enter com o cursor nela).
-- =====================================================================
USE nice_rooms;

-- ---------------------------------------------------------------------
-- A. Verificação de integridade: registros que apontam para hotel,
--    cenário ou semana inexistente. Resultado esperado: tudo 0.
--    (As FOREIGN KEYs já impedem isso; aqui fica a prova.)
-- ---------------------------------------------------------------------
SELECT 'mercado_diario sem hotel' AS verificacao, COUNT(*) AS orfaos
  FROM mercado_diario d LEFT JOIN hoteis h ON h.hotel_id = d.hotel_id WHERE h.hotel_id IS NULL
UNION ALL
SELECT 'decisoes_preco sem hotel', COUNT(*)
  FROM decisoes_preco d LEFT JOIN hoteis h ON h.hotel_id = d.hotel_id WHERE h.hotel_id IS NULL
UNION ALL
SELECT 'avaliacoes sem hotel', COUNT(*)
  FROM avaliacoes a LEFT JOIN hoteis h ON h.hotel_id = a.hotel_id WHERE h.hotel_id IS NULL
UNION ALL
SELECT 'avaliacoes sem cenario', COUNT(*)
  FROM avaliacoes a LEFT JOIN cenarios_avaliacao c ON c.scenario_id = a.scenario_id WHERE c.scenario_id IS NULL
UNION ALL
SELECT 'avaliacoes sem semana', COUNT(*)
  FROM avaliacoes a LEFT JOIN desempenho_semanal s
    ON s.hotel_id = a.hotel_id AND s.week_start = a.week_start WHERE s.hotel_id IS NULL;

-- ---------------------------------------------------------------------
-- 0. Recalcular as colunas que tiramos de hoteis (normalização):
--    quantidade de avaliações, nota média e % de 5 e de 1–2 estrelas.
-- ---------------------------------------------------------------------
SELECT h.hotel_id, h.name,
       COUNT(*)                                   AS review_count,
       ROUND(AVG(a.rating), 3)                    AS lifetime_rating,
       ROUND(AVG(a.rating = 5), 4)                AS share_rating_5,
       ROUND(AVG(a.rating <= 2), 4)               AS share_rating_1_2
  FROM hoteis h
  JOIN avaliacoes a ON a.hotel_id = h.hotel_id
 GROUP BY h.hotel_id, h.name
 ORDER BY h.hotel_id;

-- ---------------------------------------------------------------------
-- 1. Ranking dos hotéis por receita total em cada ano
--    receita total = receita de quartos + receitas extras (ancillary)
-- ---------------------------------------------------------------------
SELECT d.year,
       RANK() OVER (PARTITION BY d.year ORDER BY SUM(d.room_revenue + d.ancillary_revenue) DESC) AS posicao,
       h.name, h.tier,
       ROUND(SUM(d.room_revenue + d.ancillary_revenue), 0) AS receita_total
  FROM mercado_diario d
  JOIN hoteis h ON h.hotel_id = d.hotel_id
 GROUP BY d.year, h.hotel_id, h.name, h.tier
 ORDER BY d.year, posicao;

-- ---------------------------------------------------------------------
-- 2. Ocupação e diária média por tier e estação
--    Ponderadas: ocupação = vendidos / disponíveis; ADR = receita / vendidos
--    (média de médias daria peso igual a hotéis de tamanhos diferentes)
-- ---------------------------------------------------------------------
SELECT h.tier, d.season,
       ROUND(SUM(d.rooms_sold) / SUM(d.rooms_available) * 100, 1) AS ocupacao_pct,
       ROUND(SUM(d.room_revenue) / SUM(d.rooms_sold), 2)          AS adr_medio
  FROM mercado_diario d
  JOIN hoteis h ON h.hotel_id = d.hotel_id
 GROUP BY h.tier, d.season
 ORDER BY FIELD(h.tier, 'luxury','upscale','boutique','midscale','economy'),
          FIELD(d.season, 'winter','spring','summer','autumn');

-- ---------------------------------------------------------------------
-- 3. Hotéis com MAIS DE 30% de avaliações de 1 ou 2 estrelas
-- ---------------------------------------------------------------------
SELECT h.name, h.tier,
       COUNT(*)                              AS avaliacoes,
       SUM(a.rating <= 2)                    AS ruins,
       ROUND(AVG(a.rating <= 2) * 100, 1)    AS pct_ruins
  FROM avaliacoes a
  JOIN hoteis h ON h.hotel_id = a.hotel_id
 GROUP BY h.hotel_id, h.name, h.tier
HAVING AVG(a.rating <= 2) > 0.30
 ORDER BY pct_ruins DESC;

-- ---------------------------------------------------------------------
-- 4. Para cada cenário: quantas avaliações, nota média e ação recomendada
--    (junção avaliacoes x cenarios_avaliacao)
-- ---------------------------------------------------------------------
SELECT c.scenario_id, c.label,
       COUNT(a.review_id)          AS avaliacoes,
       ROUND(AVG(a.rating), 2)     AS nota_media,
       c.recovery_action
  FROM cenarios_avaliacao c
  LEFT JOIN avaliacoes a ON a.scenario_id = c.scenario_id
 GROUP BY c.scenario_id, c.label, c.recovery_action
 ORDER BY avaliacoes DESC;

-- ---------------------------------------------------------------------
-- 5. Para cada tipo de decisão de preço: proporção de resultados
--    "better" (melhor), "in line" (estável) e "worse" (pior) na semana seguinte
-- ---------------------------------------------------------------------
SELECT action,
       COUNT(*)                                       AS semanas,
       ROUND(AVG(outcome = 'better')  * 100, 1)       AS pct_melhor,
       ROUND(AVG(outcome = 'in line') * 100, 1)       AS pct_estavel,
       ROUND(AVG(outcome = 'worse')   * 100, 1)       AS pct_pior,
       ROUND(AVG(realised_uplift_pct), 2)             AS variacao_media_revpar_pct
  FROM decisoes_preco
 GROUP BY action
 ORDER BY FIELD(action, 'raise','hold','lower');

-- ---------------------------------------------------------------------
-- 6. % de avaliações respondidas por faixa de nota e tempo médio de resposta
-- ---------------------------------------------------------------------
SELECT CASE WHEN rating <= 2 THEN '1-2 estrelas'
            WHEN rating = 3  THEN '3 estrelas'
            ELSE '4-5 estrelas' END                      AS faixa,
       COUNT(*)                                          AS avaliacoes,
       ROUND(AVG(response_hours IS NOT NULL) * 100, 1)   AS pct_respondidas,
       ROUND(AVG(response_hours), 1)                     AS horas_medias_resposta
  FROM avaliacoes
 GROUP BY faixa
 ORDER BY faixa;

-- ---------------------------------------------------------------------
-- 7. (Nossa pergunta) Quais hotéis cobram, em média, mais de 2% longe da
--    diária adequada (MARS), e quantas noites ficaram fora da faixa ±6%?
--    Usa junção, agrupamento e filtro de grupos (HAVING).
--    ADR e MARS ponderados pelos quartos vendidos.
-- ---------------------------------------------------------------------
SELECT h.name, h.tier,
       ROUND(SUM(d.room_revenue) / SUM(d.rooms_sold), 2)               AS adr_cobrado,
       ROUND(SUM(d.mars_rate * d.rooms_sold) / SUM(d.rooms_sold), 2)   AS mars_adequado,
       ROUND((SUM(d.room_revenue) / SUM(d.mars_rate * d.rooms_sold) - 1) * 100, 1) AS diferenca_pct,
       SUM(d.adr < d.mars_band_low)                                    AS noites_abaixo_faixa,
       SUM(d.adr > d.mars_band_high)                                   AS noites_acima_faixa,
       ROUND(SUM(d.rooms_sold) / SUM(d.comp_set_occupancy * d.rooms_available) * 100, 1) AS mpi
  FROM mercado_diario d
  JOIN hoteis h ON h.hotel_id = d.hotel_id
 GROUP BY h.hotel_id, h.name, h.tier
HAVING ABS(SUM(d.room_revenue) / SUM(d.mars_rate * d.rooms_sold) - 1) > 0.02
 ORDER BY diferenca_pct;

-- ---------------------------------------------------------------------
-- 8. Tabela de preço de referência: MARS médio por hotel e estação.
--    (MySQL não tem a função MEDIAN(); o Python usa a mediana.)
-- ---------------------------------------------------------------------
SELECT h.name,
       ROUND(AVG(CASE WHEN d.season = 'winter' THEN d.mars_rate END), 0) AS inverno,
       ROUND(AVG(CASE WHEN d.season = 'spring' THEN d.mars_rate END), 0) AS primavera,
       ROUND(AVG(CASE WHEN d.season = 'summer' THEN d.mars_rate END), 0) AS verao,
       ROUND(AVG(CASE WHEN d.season = 'autumn' THEN d.mars_rate END), 0) AS outono
  FROM mercado_diario d
  JOIN hoteis h ON h.hotel_id = d.hotel_id
 GROUP BY h.hotel_id, h.name
 ORDER BY h.name;

-- ---------------------------------------------------------------------
-- 9. Quantos hotéis têm restaurante? (tabela hotel_comodidades)
-- ---------------------------------------------------------------------
SELECT COUNT(DISTINCT hotel_id) AS hoteis_com_restaurante
  FROM hotel_comodidades
 WHERE comodidade LIKE '%restaurant%';
