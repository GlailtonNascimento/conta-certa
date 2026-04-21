
# ============================================
# CONTA CERTA - SISTEMA DE CONCILIAÇÃO FINANCEIRA
# Versão Robusta com melhorias de UX e performance
# ============================================

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import base64
import re
import warnings
from io import BytesIO
import chardet

warnings.filterwarnings("ignore")

# ============================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================
st.set_page_config(
    page_title="Conta Certa - Conciliação Financeira",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================
# 1. FUNÇÃO ÚNICA DE CARREGAMENTO (Centralizada)
# ============================================

def carregar_arquivo(arquivo, tipo_arquivo="desconhecido"):
    """Função única para carregar qualquer arquivo (CSV/Excel)"""
    try:
        nome = arquivo.name.lower()
        
        # Detecta se é CSV
        if nome.endswith('.csv'):
            # Detecta encoding automaticamente
            raw_data = arquivo.read()
            resultado_encoding = chardet.detect(raw_data)
            encoding = resultado_encoding['encoding'] if resultado_encoding else 'utf-8'
            arquivo.seek(0)
            
            # Tenta diferentes separadores automaticamente
            try:
                # Primeiro tenta com detecção automática
                df = pd.read_csv(arquivo, encoding=encoding, engine='python', sep=None)
            except:
                arquivo.seek(0)
                # Tenta ponto e vírgula
                df = pd.read_csv(arquivo, encoding=encoding, sep=';')
        else:
            # Arquivo Excel
            df = pd.read_excel(arquivo)
        
        return df, None
        
    except Exception as e:
        return None, str(e)

# ============================================
# 2. PARSING MONETÁRIO VETORIZADO (Otimizado)
# ============================================

def parse_monetario_vetorizado(serie):
    """Versão otimizada para processar valores monetários em massa"""
    def converter(valor):
        if pd.isna(valor):
            return 0.0
        if isinstance(valor, (int, float)):
            return float(valor)
        texto = str(valor).strip()
        if not texto:
            return 0.0
        texto = texto.replace("R$", "").replace("$", "").replace(" ", "")
        texto = texto.replace(".", "").replace(",", ".")
        try:
            return float(texto)
        except:
            return 0.0
    
    return serie.apply(converter)

def padronizar_colunas(df):
    """Padroniza colunas com tratamento robusto"""
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    
    # Mapeamento de colunas
    mapeamento = {
        'valor total': 'valor', 'vlr': 'valor', 'total': 'valor',
        'pdv': 'terminal', 'caixa': 'terminal',
        'data': 'data', 'dt': 'data', 'date': 'data'
    }
    
    for col_antigo, col_novo in mapeamento.items():
        if col_antigo in df.columns:
            df = df.rename(columns={col_antigo: col_novo})
    
    # Detecta coluna de valor automaticamente
    if 'valor' not in df.columns:
        for col in df.columns:
            if 'valor' in col or 'total' in col:
                df = df.rename(columns={col: 'valor'})
                break
    
    # Aplica parsing monetário otimizado
    if 'valor' in df.columns:
        with st.spinner("🔄 Processando valores..."):
            df['valor'] = parse_monetario_vetorizado(df['valor'])
    else:
        df['valor'] = 0.0
    
    # Padroniza terminal
    if 'terminal' not in df.columns:
        df['terminal'] = 'GERAL'
    else:
        df['terminal'] = df['terminal'].fillna('GERAL').astype(str)
    
    # Padroniza data
    if 'data' in df.columns:
        df['data'] = pd.to_datetime(df['data'], errors='coerce', dayfirst=True)
    
    return df

# ============================================
# 3. FUNÇÕES DE CONCILIAÇÃO (Lógica intacta)
# ============================================

def conciliar(siac_df, operadora_df):
    """Compara SIAC com Operadora e encontra divergências"""
    if siac_df is None or operadora_df is None:
        return pd.DataFrame()
    
    siac_total = siac_df.groupby('terminal')['valor'].sum().reset_index()
    siac_total.columns = ['terminal', 'valor_siac']
    
    oper_total = operadora_df.groupby('terminal')['valor'].sum().reset_index()
    oper_total.columns = ['terminal', 'valor_operadora']
    
    merged = pd.merge(siac_total, oper_total, on='terminal', how='outer').fillna(0)
    merged['diferenca'] = merged['valor_siac'] - merged['valor_operadora']
    merged['status'] = merged['diferenca'].apply(lambda x: 'PENDENTE' if abs(x) > 0.01 else 'OK')
    
    return merged[merged['status'] == 'PENDENTE']

def extrair_cartoes(df):
    """Extrai totais por tipo de cartão"""
    resultado = {'credito': 0.0, 'debito': 0.0, 'parcelado': 0.0}
    if df is None or df.empty:
        return resultado
    
    if 'tipo' in df.columns:
        tipos = df['tipo'].astype(str).str.lower()
        resultado['credito'] = df[tipos.str.contains('credito|crédito', na=False)]['valor'].sum()
        resultado['debito'] = df[tipos.str.contains('debito|débito', na=False)]['valor'].sum()
    
    if 'parcelas' in df.columns:
        resultado['parcelado'] = df[df['parcelas'] > 1]['valor'].sum()
    
    return resultado

# ============================================
# 4. INTERFACE PRINCIPAL
# ============================================

st.title("💰 Conta Certa - Conciliação Financeira")
st.markdown("---")

with st.sidebar:
    st.header("📥 Carregar Arquivos")
    
    arquivo_siac = st.file_uploader(
        "📊 Sistema da Loja (SIAC/NCR)",
        type=["xlsx", "xls", "csv"],
        key="siac",
        help="Arquivo de fechamento de caixa do sistema da loja"
    )
    
    arquivo_operadora = st.file_uploader(
        "💳 Extrato da Operadora (Cielo, Rede, etc.)",
        type=["xlsx", "xls", "csv"],
        key="operadora",
        help="Arquivo de extrato da operadora de cartão"
    )
    
    st.markdown("---")
    processar = st.button("🚀 PROCESSAR", type="primary", use_container_width=True)

# Tela inicial
if not processar:
    st.info("👈 **Como usar:** Faça upload dos arquivos e clique em PROCESSAR")
    
    st.markdown("""
    ### 📋 O que o sistema faz:
    
    | Funcionalidade | Descrição |
    |----------------|-----------|
    | 🔍 **Conciliação** | Compara SIAC vs Operadora automaticamente |
    | ⚠️ **Divergências** | Mostra diferenças por terminal |
    | 💳 **Cartões** | Separa crédito, débito e parcelado |
    | 📥 **Exportação** | Gera relatório Excel completo |
    | 🔄 **CSV/Excel** | Aceita qualquer formato |
    """)
    
    with st.expander("📖 Formato esperado dos arquivos"):
        st.markdown("""
        **O sistema aceita:**
        - Coluna com valores (pode ser: valor, total, vlr, R$)
        - Coluna de terminal/PDV (opcional)
        - Data (opcional)
        
        **Formatos suportados:**
        - Excel (.xlsx, .xls)
        - CSV (qualquer separador e encoding)
        
        O sistema se adapta automaticamente ao seu arquivo!
        """)
    st.stop()

# Validação de arquivos
if not arquivo_siac:
    st.warning("⚠️ Carregue o arquivo do SIAC")
    st.stop()

if not arquivo_operadora:
    st.warning("⚠️ Carregue o arquivo da operadora")
    st.stop()

# ============================================
# PROCESSAMENTO COM SPINNER (Feedback visual)
# ============================================

with st.spinner("🔄 Carregando e processando arquivos..."):
    
    # Carrega SIAC
    df_siac, erro_siac = carregar_arquivo(arquivo_siac, "siac")
    if erro_siac:
        st.error(f"❌ Erro ao ler arquivo SIAC: {erro_siac}")
        st.info("💡 Verifique se o arquivo não está corrompido ou em formato diferente")
        st.stop()
    
    df_siac = padronizar_colunas(df_siac)
    st.success(f"✅ SIAC carregado: {len(df_siac)} registros | Total: R$ {df_siac['valor'].sum():,.2f}")
    
    # Carrega Operadora
    df_operadora, erro_oper = carregar_arquivo(arquivo_operadora, "operadora")
    if erro_oper:
        st.error(f"❌ Erro ao ler arquivo da Operadora: {erro_oper}")
        st.stop()
    
    df_operadora = padronizar_colunas(df_operadora)
    st.success(f"✅ Operadora carregada: {len(df_operadora)} transações | Total: R$ {df_operadora['valor'].sum():,.2f}")

# ============================================
# CONCILIAÇÃO COM SPINNER
# ============================================

with st.spinner("🔄 Calculando conciliação..."):
    
    total_siac = df_siac['valor'].sum()
    total_oper = df_operadora['valor'].sum()
    diferenca_total = total_siac - total_oper
    percentual = (total_oper / total_siac * 100) if total_siac > 0 else 0
    
    divergencias = conciliar(df_siac, df_operadora)

# ============================================
# EXIBIÇÃO DOS RESULTADOS
# ============================================

st.header("📊 Resultados da Conciliação")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Vendas SIAC", f"R$ {total_siac:,.2f}")

with col2:
    st.metric("Total Operadora", f"R$ {total_oper:,.2f}")

with col3:
    st.metric("Diferença", f"R$ {diferenca_total:,.2f}", 
              delta="✅ OK" if abs(diferenca_total) < 0.01 else "⚠️ Pendente")

with col4:
    st.metric("Conciliação", f"{percentual:.1f}%",
              delta="✅" if percentual >= 99.5 else "⚠️")

st.markdown("---")

# Divergências
st.subheader("⚠️ Divergências Encontradas")

if not divergencias.empty:
    st.error(f"🔴 Encontradas {len(divergencias)} divergências no valor total de R$ {divergencias['diferenca'].sum():,.2f}")
    st.dataframe(divergencias, use_container_width=True)
else:
    st.success("✅ Nenhuma divergência encontrada! Tudo conciliado.")

# Gráficos
col1, col2 = st.columns(2)

with col1:
    if not divergencias.empty:
        fig = px.bar(divergencias, x='terminal', y='diferenca', 
                     title='Divergências por Terminal',
                     labels={'diferenca': 'Diferença (R$)'},
                     color='diferenca', color_continuous_scale='Reds')
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📊 Sem divergências para exibir")

with col2:
    cartoes = extrair_cartoes(df_operadora)
    if sum(cartoes.values()) > 0:
        fig2 = px.pie(values=list(cartoes.values()), 
                      names=list(cartoes.keys()),
                      title='Composição de Pagamentos',
                      color_discrete_sequence=['#1f77b4', '#ff7f0e', '#2ca02c'])
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("💳 Sem dados de cartões para exibir")

# ============================================
# EXPORTAÇÃO
# ============================================

st.markdown("---")
st.subheader("📎 Exportar Resultados")

with st.spinner("🔄 Gerando relatório..."):
    
    excel_buffer = BytesIO()
    
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        # Resumo
        resumo = pd.DataFrame({
            'Métrica': ['Data', 'Total Vendas SIAC', 'Total Operadora', 'Diferença', 'Percentual', 'Status'],
            'Valor': [
                datetime.now().strftime('%d/%m/%Y %H:%M'),
                f'R$ {total_siac:,.2f}',
                f'R$ {total_oper:,.2f}',
                f'R$ {diferenca_total:,.2f}',
                f'{percentual:.2f}%',
                'Concluído' if abs(diferenca_total) < 0.01 else 'Pendente'
            ]
        })
        resumo.to_excel(writer, sheet_name='Resumo', index=False)
        
        # Divergências
        if not divergencias.empty:
            divergencias.to_excel(writer, sheet_name='Divergencias', index=False)
        
        # Dados completos
        df_siac.to_excel(writer, sheet_name='Dados_SIAC', index=False)
        df_operadora.to_excel(writer, sheet_name='Dados_Operadora', index=False)

# Botão de download
st.download_button(
    label="📥 Baixar Relatório Excel",
    data=excel_buffer.getvalue(),
    file_name=f"relatorio_conciliacao_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# ============================================
# RODAPÉ
# ============================================

st.markdown("---")
st.caption("🔒 **Conta Certa** - Conciliação Financeira | Dados processados localmente, nenhuma informação é armazenada | Versão Robusta|Desenvolvido por Glailton Nascimento.")

# Opcional: Mostrar informações de debug (útil para suporte)
with st.expander("🔧 Informações técnicas"):
    st.write(f"SIAC: {len(df_siac)} registros, {df_siac['valor'].sum():.2f}")
    st.write(f"Operadora: {len(df_operadora)} registros, {df_operadora['valor'].sum():.2f}")
    st.write(f"Divergências: {len(divergencias)}")
