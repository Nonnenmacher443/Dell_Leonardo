-- =====================================================================
-- Modelagem MySQL: Hotéis de Port Alder (dataset Nice Rooms)
-- =====================================================================
-- Testado em MySQL 8.0 e MariaDB 10.11.
--
-- Decisões de modelagem (normalização):
--  * hotel_id é a chave que liga quase tudo (1 hotel : N linhas nas outras tabelas).
--  * amenities era uma LISTA dentro de um campo (fere a 1ª forma normal).
--    Virou a tabela hotel_comodidades (1 linha por hotel e comodidade).
--  * hotel_name, tier e comp_set se repetiam em mercado_diario e
--    desempenho_semanal; tier se repetia em tipos_quarto. Foram REMOVIDOS
--    dessas tabelas (3ª forma normal) e voltam com JOIN em hoteis.
--  * available_rooms em mercado_diario era cópia de rooms_available: removida.
--  * review_count, lifetime_rating, share_rating_5 e share_rating_1_2 de
--    hotels são calculáveis a partir de avaliacoes: removidos (ver a
--    consulta 0 em consultas_mysql.sql, que os recalcula).
--  * Mantivemos de propósito as métricas já calculadas (occupancy, adr,
--    revpar, rgi...) nas tabelas diária e semanal: são derivadas, mas
--    recalculá-las em toda consulta seria lento e o dataset as valida.
--  * Os nomes das colunas seguem o dataset (em inglês) para facilitar a
--    carga e a conferência com o README. Exceções: `trigger` e `view` são
--    palavras reservadas do SQL e viraram trigger_desc e view_type.
-- =====================================================================

DROP DATABASE IF EXISTS nice_rooms;
CREATE DATABASE nice_rooms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE nice_rooms;

-- ---------------------------------------------------------------------
-- Entidade: hotel
-- ---------------------------------------------------------------------
CREATE TABLE hoteis (
    hotel_id             CHAR(3)       NOT NULL,
    name                 VARCHAR(60)   NOT NULL,
    brand                VARCHAR(60)   NOT NULL,
    tier                 VARCHAR(10)   NOT NULL,
    rooms                INT           NOT NULL,
    opened_year          INT           NOT NULL,
    distance_to_water_km DOUBLE        NOT NULL,
    neighbourhood        VARCHAR(40)   NOT NULL,
    comp_set             VARCHAR(10)   NOT NULL,
    positioning_index    DOUBLE        NOT NULL,
    base_rate            DECIMAL(10,2) NOT NULL,
    city                 VARCHAR(40)   NOT NULL,
    PRIMARY KEY (hotel_id),
    CONSTRAINT ck_hoteis_tier CHECK (tier IN ('luxury','upscale','boutique','midscale','economy')),
    CONSTRAINT ck_hoteis_rooms CHECK (rooms > 0)
);

-- 1 hotel : N comodidades (era a lista "amenities")
CREATE TABLE hotel_comodidades (
    hotel_id   CHAR(3)     NOT NULL,
    comodidade VARCHAR(40) NOT NULL,
    PRIMARY KEY (hotel_id, comodidade),
    CONSTRAINT fk_comod_hotel FOREIGN KEY (hotel_id) REFERENCES hoteis (hotel_id)
);

-- 1 hotel : N tipos de quarto
CREATE TABLE tipos_quarto (
    room_type_id     VARCHAR(10)   NOT NULL,
    hotel_id         CHAR(3)       NOT NULL,
    room_type        VARCHAR(40)   NOT NULL,
    rooms            INT           NOT NULL,
    max_occupancy    INT           NOT NULL,
    size_sqm         INT           NOT NULL,
    rate_premium_pct INT           NOT NULL,
    bar_rate         DECIMAL(10,2) NOT NULL,
    view_type        VARCHAR(20)   NOT NULL,
    PRIMARY KEY (room_type_id),
    CONSTRAINT fk_tipos_hotel FOREIGN KEY (hotel_id) REFERENCES hoteis (hotel_id)
);

-- ---------------------------------------------------------------------
-- 1 hotel : N noites  (chave composta hotel_id + date)
-- ---------------------------------------------------------------------
CREATE TABLE mercado_diario (
    hotel_id               CHAR(3)       NOT NULL,
    date                   DATE          NOT NULL,
    weekday                VARCHAR(10)   NOT NULL,
    month                  TINYINT       NOT NULL,
    year                   SMALLINT      NOT NULL,
    season                 VARCHAR(10)   NOT NULL,
    demand_event           VARCHAR(40)   NULL,      -- NULL = noite comum
    rooms_available        INT           NOT NULL,
    rooms_sold             INT           NOT NULL,
    occupancy              DOUBLE        NOT NULL,
    adr                    DECIMAL(10,2) NOT NULL,
    room_revenue           DECIMAL(12,2) NOT NULL,
    ancillary_revenue      DECIMAL(12,2) NOT NULL,
    commission             DECIMAL(12,2) NOT NULL,
    net_revenue            DECIMAL(12,2) NOT NULL,
    gross_operating_profit DECIMAL(12,2) NOT NULL,
    bookings               INT           NOT NULL,
    cancellations          INT           NOT NULL,
    cancellation_rate      DOUBLE        NOT NULL,
    booking_window_days    DOUBLE        NOT NULL,
    length_of_stay         DOUBLE        NOT NULL,
    revpar                 DOUBLE        NOT NULL,
    trevpar                DOUBLE        NOT NULL,
    revpor                 DOUBLE        NOT NULL,
    net_revpar             DOUBLE        NOT NULL,
    goppar                 DOUBLE        NOT NULL,
    cpor                   DOUBLE        NOT NULL,
    ancillary_capture      DOUBLE        NOT NULL,
    market_occupancy       DOUBLE        NOT NULL,
    market_adr             DOUBLE        NOT NULL,
    demand_index           DOUBLE        NOT NULL,
    otb_occupancy_index    DOUBLE        NOT NULL,
    comp_set_occupancy     DOUBLE        NOT NULL,
    comp_set_adr           DOUBLE        NOT NULL,
    comp_set_revpar        DOUBLE        NOT NULL,
    rgi                    DOUBLE        NOT NULL,
    ari                    DOUBLE        NOT NULL,
    mpi                    DOUBLE        NOT NULL,
    mars_rate              DECIMAL(10,2) NOT NULL,
    mars_band_low          DECIMAL(10,2) NOT NULL,
    mars_band_high         DECIMAL(10,2) NOT NULL,
    rate_position          DOUBLE        NOT NULL,
    rate_gap_pct           DOUBLE        NOT NULL,
    rate_action            VARCHAR(5)    NOT NULL,
    suggested_rate         DECIMAL(10,2) NOT NULL,
    suggested_change_pct   DOUBLE        NOT NULL,
    rate_guardrail         VARCHAR(10)   NOT NULL,
    rate_floor             DECIMAL(10,2) NOT NULL,
    rate_ceiling           DECIMAL(10,2) NOT NULL,
    price_elasticity       DOUBLE        NOT NULL,
    mars_basis             VARCHAR(40)   NOT NULL,
    mars_confidence        DOUBLE        NOT NULL,
    PRIMARY KEY (hotel_id, date),
    CONSTRAINT fk_diario_hotel FOREIGN KEY (hotel_id) REFERENCES hoteis (hotel_id),
    CONSTRAINT ck_diario_vendidos CHECK (rooms_sold <= rooms_available),
    CONSTRAINT ck_diario_acao CHECK (rate_action IN ('raise','hold','lower'))
);

-- ---------------------------------------------------------------------
-- 1 hotel : N semanas  (chave composta hotel_id + week_start)
-- ---------------------------------------------------------------------
CREATE TABLE desempenho_semanal (
    hotel_id               CHAR(3)       NOT NULL,
    week_start             DATE          NOT NULL,
    available_rooms        INT           NOT NULL,
    rooms_sold             INT           NOT NULL,
    bookings               INT           NOT NULL,
    cancellations          INT           NOT NULL,
    occupancy              DOUBLE        NOT NULL,
    adr                    DECIMAL(10,2) NOT NULL,
    revpar                 DOUBLE        NOT NULL,
    room_revenue           DECIMAL(12,2) NOT NULL,
    ancillary_revenue      DECIMAL(12,2) NOT NULL,
    commission             DECIMAL(12,2) NOT NULL,
    net_revenue            DECIMAL(12,2) NOT NULL,
    total_revenue          DECIMAL(12,2) NOT NULL,
    trevpar                DOUBLE        NOT NULL,
    revpor                 DOUBLE        NOT NULL,
    net_revpar             DOUBLE        NOT NULL,
    gross_operating_profit DECIMAL(12,2) NOT NULL,
    goppar                 DOUBLE        NOT NULL,
    cpor                   DOUBLE        NOT NULL,
    length_of_stay         DOUBLE        NOT NULL,
    booking_window_days    DOUBLE        NOT NULL,
    cancellation_rate      DOUBLE        NOT NULL,
    comp_set_occupancy     DOUBLE        NOT NULL,
    comp_set_adr           DOUBLE        NOT NULL,
    comp_set_revpar        DOUBLE        NOT NULL,
    rgi                    DOUBLE        NOT NULL,
    ari                    DOUBLE        NOT NULL,
    mpi                    DOUBLE        NOT NULL,
    ancillary_capture      DOUBLE        NOT NULL,
    demand_event           VARCHAR(40)   NULL,
    event_nights           INT           NOT NULL,
    flow_through           DOUBLE        NULL,      -- NULL no 1º ano
    review_count           INT           NOT NULL,
    mean_rating            DOUBLE        NULL,      -- NULL em semana sem avaliação
    positive_share         DOUBLE        NULL,
    sentiment_index        DOUBLE        NULL,
    response_rate          DOUBLE        NULL,
    PRIMARY KEY (hotel_id, week_start),
    CONSTRAINT fk_semanal_hotel FOREIGN KEY (hotel_id) REFERENCES hoteis (hotel_id)
);

-- 1 semana : 1 decisão (a última semana não tem decisão avaliada)
CREATE TABLE decisoes_preco (
    decision_id          VARCHAR(10)   NOT NULL,
    hotel_id             CHAR(3)       NOT NULL,
    week_start           DATE          NOT NULL,
    action               VARCHAR(5)    NOT NULL,
    current_adr          DECIMAL(10,2) NOT NULL,
    mars_rate            DECIMAL(10,2) NOT NULL,
    rate_position        DOUBLE        NOT NULL,
    rate_gap_pct         DOUBLE        NOT NULL,
    booking_pace_index   DOUBLE        NOT NULL,
    forecast_occupancy   DOUBLE        NOT NULL,
    suggested_rate       DECIMAL(10,2) NOT NULL,
    suggested_change_pct DOUBLE        NOT NULL,
    rate_guardrail       VARCHAR(10)   NOT NULL,
    expected_revpar      DOUBLE        NOT NULL,
    expected_lift_pct    DOUBLE        NOT NULL,
    confidence           DOUBLE        NOT NULL,
    rationale            VARCHAR(100)  NOT NULL,
    cancellation_rate    DOUBLE        NOT NULL,
    demand_event         VARCHAR(40)   NULL,
    realised_occupancy   DOUBLE        NOT NULL,
    realised_adr         DECIMAL(10,2) NOT NULL,
    realised_revpar      DOUBLE        NOT NULL,
    realised_uplift_pct  DOUBLE        NOT NULL,
    outcome              VARCHAR(10)   NOT NULL,
    PRIMARY KEY (decision_id),
    UNIQUE KEY uq_decisao_semana (hotel_id, week_start),
    CONSTRAINT fk_decisao_hotel  FOREIGN KEY (hotel_id) REFERENCES hoteis (hotel_id),
    CONSTRAINT fk_decisao_semana FOREIGN KEY (hotel_id, week_start)
        REFERENCES desempenho_semanal (hotel_id, week_start),
    CONSTRAINT ck_decisao_acao CHECK (action IN ('raise','hold','lower')),
    CONSTRAINT ck_decisao_resultado CHECK (outcome IN ('better','in line','worse'))
);

-- ---------------------------------------------------------------------
-- Avaliações e seus cenários (motivos)
-- ---------------------------------------------------------------------
CREATE TABLE cenarios_avaliacao (
    scenario_id        VARCHAR(20)  NOT NULL,
    label              VARCHAR(60)  NOT NULL,
    share_of_reviews   DOUBLE       NOT NULL,
    rating_band        VARCHAR(20)  NOT NULL,
    trigger_desc       VARCHAR(120) NOT NULL,
    expected_sentiment VARCHAR(20)  NOT NULL,
    recovery_action    VARCHAR(120) NOT NULL,
    PRIMARY KEY (scenario_id)
);

CREATE TABLE avaliacoes (
    review_id       VARCHAR(10)  NOT NULL,
    hotel_id        CHAR(3)      NOT NULL,
    review_date     DATE         NOT NULL,
    stay_date       DATE         NOT NULL,
    week_start      DATE         NOT NULL,
    scenario_id     VARCHAR(20)  NOT NULL,
    rating          TINYINT      NOT NULL,
    title           VARCHAR(100) NOT NULL,
    text            TEXT         NOT NULL,
    channel         VARCHAR(20)  NOT NULL,
    segment         VARCHAR(20)  NOT NULL,
    nights          INT          NOT NULL,
    room_type       VARCHAR(40)  NOT NULL,
    verified_stay   BOOLEAN      NOT NULL,
    cleanliness     TINYINT      NOT NULL,
    comfort         TINYINT      NOT NULL,
    service_score   TINYINT      NOT NULL,
    location_score  TINYINT      NOT NULL,
    value_score     TINYINT      NOT NULL,
    sleep_quality   TINYINT      NOT NULL,
    would_return    BOOLEAN      NOT NULL,
    sentiment       VARCHAR(20)  NOT NULL,
    sentiment_score DOUBLE       NOT NULL,
    lexicon_version VARCHAR(20)  NOT NULL,
    response_text   TEXT         NULL,       -- NULL = hotel não respondeu
    response_hours  DOUBLE       NULL,
    PRIMARY KEY (review_id),
    CONSTRAINT fk_aval_hotel   FOREIGN KEY (hotel_id) REFERENCES hoteis (hotel_id),
    CONSTRAINT fk_aval_cenario FOREIGN KEY (scenario_id) REFERENCES cenarios_avaliacao (scenario_id),
    CONSTRAINT fk_aval_semana  FOREIGN KEY (hotel_id, week_start)
        REFERENCES desempenho_semanal (hotel_id, week_start),
    CONSTRAINT ck_aval_nota CHECK (rating BETWEEN 1 AND 5)
);

-- Índices para as consultas mais usadas
CREATE INDEX ix_diario_data   ON mercado_diario (date);
CREATE INDEX ix_aval_rating   ON avaliacoes (rating);
CREATE INDEX ix_decisao_acao  ON decisoes_preco (action);
