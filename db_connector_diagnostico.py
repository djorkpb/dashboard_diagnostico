import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# --- CONFIGURAÇÃO SEGURA DAS CREDENCIAIS ---
DB_USER = st.secrets.get("DB_USER", os.environ.get("DB_USER"))
DB_PASSWORD = st.secrets.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))
DB_HOST = st.secrets.get("DB_HOST", os.environ.get("DB_HOST"))
DB_PORT = st.secrets.get("DB_PORT", os.environ.get("DB_PORT", "5432"))
DB_NAME = st.secrets.get("DB_NAME", os.environ.get("DB_NAME"))

# Monta a string de conexão para o PostgreSQL
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

@st.cache_data(ttl=600)
def carregar_dados_do_banco():
    """
    Conecta ao banco de dados PostgreSQL e executa a consulta para obter os dados
    de Ordens de Serviço de Diagnóstico, Sondagem e Supressão.
    """
    # --- CONSULTA SQL ATUALIZADA ---
    query = text("""
    WITH Parametros AS (
        -- ÚNICO LOCAL PARA ALTERAR A DATA DE REFERÊNCIA INICIAL
        SELECT '2025-06-01'::timestamp AS data_inicial
    )
    SELECT
        os.orse_id,
        os.imov_id,
        i.loca_id,
        os.orse_tmgeracao AS data_geracao,
        os.orse_tmencerramento AS data_conclusao,
        -- Categoriza o tipo de serviço principal
        CASE
            WHEN os.svtp_id = 718 THEN 'Diagnóstico'
            WHEN os.svtp_id IN (719, 720, 803) THEN 'Sondagem'
            WHEN os.svtp_id IN (33, 82, 32, 804, 811, 810, 36, 726, 807) THEN 'Supressão'
            ELSE 'Outro'
        END AS tipo_servico,
        -- CORREÇÃO: Lógica de status customizada
        CASE
            WHEN os.orse_cdsituacao = 1 THEN 'Pendente'
            WHEN os.amen_id = 2 THEN 'Conclusão do Serviço'
            WHEN os.amen_id IS NOT NULL AND os.amen_id <> 2 THEN 'Cancelada'
            ELSE oss.osst_dssituacao
        END AS status_os,
        st.svtp_dsservicotipo AS descricao_servico,
        -- NOVO CAMPO: Adiciona o motivo do encerramento
        me.amen_dsmotivoencerramento AS motivo_encerramento
    FROM
        atendimentopublico.ordem_servico os
    JOIN
        cadastro.imovel i ON os.imov_id = i.imov_id
    JOIN
        atendimentopublico.servico_tipo st ON os.svtp_id = st.svtp_id
    -- CORREÇÃO: Adiciona JOIN para a tabela de situação da OS
    JOIN
        atendimentopublico.ordem_servico_situacao oss ON os.orse_cdsituacao = oss.osst_id
    -- NOVO JOIN: Adiciona LEFT JOIN para o motivo do encerramento (pode ser nulo)
    LEFT JOIN
        atendimentopublico.atend_motivo_encmt me ON os.amen_id = me.amen_id
    CROSS JOIN
        Parametros
    WHERE
        os.svtp_id IN (
            718, -- Diagnóstico
            719, 720, 803, -- Sondagem
            33, 82, 32, 804, 811, 810, 36, 726, 807 -- Supressão
        )
        AND os.orse_tmgeracao >= Parametros.data_inicial
        AND os.orse_tmgeracao <= NOW();
    """)

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        
        # Converte as colunas de data para o tipo datetime do pandas
        df['data_geracao'] = pd.to_datetime(df['data_geracao'])
        df['data_conclusao'] = pd.to_datetime(df['data_conclusao'])
        
        return df
    except SQLAlchemyError as e:
        st.error(f"Erro ao conectar ou consultar o banco de dados: {e}")
        return pd.DataFrame()
