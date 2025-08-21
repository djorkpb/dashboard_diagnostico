import streamlit as st
import pandas as pd
import plotly.express as px
# Importa a função do novo arquivo de conector
from db_connector_diagnostico import carregar_dados_do_banco

# --- Configurações da Página ---
st.set_page_config(
    page_title="Dashboard de Análise de OS",
    page_icon="🛠️",
    layout="wide"
)

# --- Funções Auxiliares ---
@st.cache_data
def convert_df_to_csv(df):
    """Converte um DataFrame para CSV para download."""
    df_export = df.rename(columns={
        'Matrícula': 'imov_id', 
        'Localidade': 'loca_id',
        'Data de Geração': 'data_geracao',
        'Data de Conclusão': 'data_conclusao',
        'Tipo de Serviço': 'tipo_servico',
        'Status': 'status_os',
        'Descrição do Serviço': 'descricao_servico',
        'Motivo do Encerramento': 'motivo_encerramento'
    })
    return df_export.to_csv(index=False).encode('utf-8-sig')

# --- Carregamento dos Dados ---
df_original = carregar_dados_do_banco()

# --- Título e Descrição ---
st.title("🛠️ Dashboard de Análise de Ordens de Serviço")
st.markdown("Análise de OS de Diagnóstico, Sondagem e Supressão.")

# --- Sidebar de Filtros ---
st.sidebar.header("Filtros Interativos")

if df_original.empty:
    st.warning("Não foi possível carregar os dados. Verifique a conexão com o banco de dados.")
else:
    # Renomeia as colunas para exibição no dashboard
    df_original.rename(columns={
        'imov_id': 'Matrícula', 
        'loca_id': 'Localidade',
        'data_geracao': 'Data de Geração',
        'data_conclusao': 'Data de Conclusão',
        'tipo_servico': 'Tipo de Serviço',
        'status_os': 'Status',
        'descricao_servico': 'Descrição do Serviço',
        'motivo_encerramento': 'Motivo do Encerramento'
    }, inplace=True)

    # Filtro por Localidade
    localidades = sorted(df_original['Localidade'].unique())
    localidade_selecionada = st.sidebar.multiselect(
        'Selecione a Localidade:',
        options=localidades,
        default=localidades,
        placeholder="Selecione uma ou mais localidades"
    )

    # Filtro por Período (Data de Geração)
    data_min = df_original['Data de Geração'].min().date()
    data_max = df_original['Data de Geração'].max().date()
    periodo_selecionado = st.sidebar.date_input(
        'Selecione o Período de Geração:',
        value=(data_min, data_max),
        min_value=data_min,
        max_value=data_max
    )

    # --- Aplicação dos Filtros ---
    df_filtrado = df_original[
        (df_original['Localidade'].isin(localidade_selecionada)) &
        (df_original['Data de Geração'].dt.date >= periodo_selecionado[0]) &
        (df_original['Data de Geração'].dt.date <= periodo_selecionado[1])
    ]

    # --- Métricas Principais (KPIs) ---
    st.subheader("Visão Geral do Período Selecionado")
    
    total_geradas = df_filtrado.shape[0]
    # CORREÇÃO: Atualiza o status para 'Conclusão do Serviço'
    total_concluidas = df_filtrado[df_filtrado['Status'] == 'Conclusão do Serviço'].shape[0]
    taxa_conclusao = (total_concluidas / total_geradas) * 100 if total_geradas > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de OS Geradas", f"{total_geradas:,}".replace(",", "."))
    # CORREÇÃO: Atualiza o label da métrica
    col2.metric("Total de OS Concluídas", f"{total_concluidas:,}".replace(",", "."))
    col3.metric("Taxa de Conclusão", f"{taxa_conclusao:.2f}%")
    
    st.divider()

    # --- Gráficos Interativos ---
    st.subheader("Análises Visuais")

    # --- CORREÇÃO: Define um mapa de cores padrão para os status ---
    color_map = {
        'Pendente': 'lightblue',
        'Cancelada': 'red',
        'Conclusão do Serviço': '#0047AB', # Azul Cobalto
        'EXECUTADA': 'darkslateblue',
        'GERADA': 'grey'
        # Adicione outros status e cores que possam vir do banco
    }

    # Gráfico 1: Volume de OS por Tipo e Status
    df_grafico_status = df_filtrado.groupby(['Tipo de Serviço', 'Status']).size().reset_index(name='Quantidade')

    # Calcula os totais por tipo de serviço para as anotações
    df_totais = df_filtrado.groupby('Tipo de Serviço').size().reset_index(name='Total')

    fig_tipo_os = px.bar(
        df_grafico_status,
        x='Tipo de Serviço',
        y='Quantidade',
        color='Status',
        title='Volume de OS por Tipo e Status',
        labels={'Quantidade': 'Quantidade de OS', 'Tipo de Serviço': 'Tipo de Serviço'},
        barmode='stack', # Altera para 'stack' para melhor visualização de parte-todo
        color_discrete_map=color_map # Aplica o mapa de cores
    )

    # Adiciona o valor de cada segmento dentro da barra
    fig_tipo_os.update_traces(texttemplate='%{y}', textposition='inside')

    # Adiciona anotações com o total em cima de cada barra empilhada
    annotations = []
    for _, row in df_totais.iterrows():
        annotations.append(
            dict(
                x=row['Tipo de Serviço'],
                y=row['Total'],
                text=f"<b>{row['Total']}</b>", # Texto da anotação (total)
                showarrow=False,
                yshift=10, # Deslocamento vertical para ficar acima da barra
                font=dict(size=14, color="black")
            )
        )

    fig_tipo_os.update_layout(
        legend_title_text='Status da OS',
        annotations=annotations,
        # Aumenta a margem superior para garantir que o total seja visível
        margin=dict(t=100)
    )
    st.plotly_chart(fig_tipo_os, use_container_width=True)


    # --- Gráfico 2: Análise Mensal Detalhada ---
    st.subheader("Análise Mensal Detalhada")
    df_grafico_mensal = df_filtrado.copy()
    df_grafico_mensal['Mês de Geração'] = df_grafico_mensal['Data de Geração'].dt.strftime('%m/%Y')
    
    # Ordena os meses cronologicamente para o filtro
    meses_disponiveis = sorted(
        df_grafico_mensal['Mês de Geração'].unique(),
        key=lambda x: pd.to_datetime(x, format='%m/%Y')
    )

    # Filtro para selecionar os meses a serem exibidos no gráfico
    meses_selecionados = st.multiselect(
        'Selecione os meses para análise:',
        options=meses_disponiveis,
        default=meses_disponiveis,
        placeholder="Selecione um ou mais meses"
    )

    if meses_selecionados:
        df_grafico_filtrado_mensal = df_grafico_mensal[df_grafico_mensal['Mês de Geração'].isin(meses_selecionados)]
        
        df_plot_mensal = df_grafico_filtrado_mensal.groupby(['Mês de Geração', 'Tipo de Serviço', 'Status']).size().reset_index(name='Quantidade')
        
        # Calcula os totais para as anotações no gráfico facetado
        df_totais_mensal = df_grafico_filtrado_mensal.groupby(['Mês de Geração', 'Tipo de Serviço']).size().reset_index(name='Total')

        fig_detalhe_mensal = px.bar(
            df_plot_mensal,
            x='Tipo de Serviço',
            y='Quantidade',
            color='Status',
            facet_col='Mês de Geração',
            facet_col_wrap=4, # Quebra a linha a cada 4 meses para não ficar muito largo
            title='Análise Mensal de OS por Tipo e Status',
            labels={'Quantidade': 'Quantidade de OS', 'Tipo de Serviço': ''},
            barmode='stack',
            color_discrete_map=color_map # Aplica o mapa de cores
        )
        
        # Adiciona os valores de cada segmento dentro das barras
        fig_detalhe_mensal.update_traces(texttemplate='%{y}', textposition='inside')

        # Adiciona anotações com o total em cima de cada barra empilhada
        for i, mes in enumerate(meses_selecionados):
            df_totais_mes = df_totais_mensal[df_totais_mensal['Mês de Geração'] == mes]
            
            # Constrói a referência do eixo para cada subplot
            subplot_num_str = str(i + 1) if i > 0 else ""
            xref = f'x{subplot_num_str}'
            yref = f'y{subplot_num_str}'
            
            for _, row in df_totais_mes.iterrows():
                fig_detalhe_mensal.add_annotation(
                    x=row['Tipo de Serviço'],
                    y=row['Total'],
                    text=f"<b>{row['Total']}</b>",
                    showarrow=False,
                    yshift=5,
                    font=dict(size=12, color="black"),
                    xref=xref,
                    yref=yref
                )

        fig_detalhe_mensal.update_layout(
            legend_title_text='Status da OS',
            margin=dict(t=100) # Aumenta a margem para os totais
        )
        # Renomeia os títulos dos subplots para remover "Mês de Geração="
        fig_detalhe_mensal.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]) if 'Mês de Geração' in a.text else ())
        fig_detalhe_mensal.update_yaxes(matches=None, title_text="") # Permite eixos Y independentes e remove títulos
        fig_detalhe_mensal.update_xaxes(title_text="") # Remove títulos do eixo X
        st.plotly_chart(fig_detalhe_mensal, use_container_width=True)
    else:
        st.info("Selecione pelo menos um mês para visualizar a análise detalhada.")


    st.divider()

    # --- Botão para Exibir/Ocultar Tabela de Dados ---
    if 'show_details' not in st.session_state:
        st.session_state.show_details = False

    if st.button('Mostrar/Ocultar Dados Detalhados'):
        st.session_state.show_details = not st.session_state.show_details

    if st.session_state.show_details:
        st.subheader("Dados Detalhados")
        
        with st.spinner('Carregando dados detalhados...'):
            st.dataframe(df_filtrado.style.format({
                'Data de Geração': '{:%d/%m/%Y %H:%M}',
                'Data de Conclusão': lambda x: f'{x:%d/%m/%Y %H:%M}' if pd.notna(x) else 'N/A'
            }))

            csv = convert_df_to_csv(df_filtrado)
            st.download_button(
                label="📥 Download de TODOS os dados filtrados em CSV",
                data=csv,
                file_name='dados_os_diagnostico.csv',
                mime='text/csv',
            )
