# Arquivo: src/enriquecimento.py
import duckdb
import json
from pydantic import BaseModel, Field

# Configurações
DB_PATH = "data/radar.duckdb"
USAR_MOCK_LLM = True # Mantenha True para testar o pipeline primeiro

# 1. Definimos o contrato de saída da IA (Princípio: Saída sempre estruturada)
class ContextoComercial(BaseModel):
    atividade_provavel: str = Field(description="Interpretação prática do que a empresa faz baseada no CNAE")
    publico_alvo: str = Field(description="Quem são os prováveis clientes desta empresa?")
    dor_provavel: str = Field(description="Quais dores operacionais uma empresa recém-aberta nesse setor possui?")
    abordagem_sugerida: str = Field(description="Como o vendedor deve iniciar a conversa (ação sugerida)?")
    confianca_ia: str = Field(description="Alta, Média ou Baixa")

def chamar_llm(cnpj: str, cnae_desc: str, municipio: str) -> str:
    """
    Função que encapsula a chamada para a IA (Ollama local ou API OpenAI-compatible).
    Por enquanto, retorna o MOCK garantindo o contrato do Pydantic.
    """
    if USAR_MOCK_LLM:
        mock_response = ContextoComercial(
            atividade_provavel="Escritório focado em assessoria contábil e fiscal.",
            publico_alvo="Pequenas e médias empresas (PMEs) da região local.",
            dor_provavel="Necessidade de estruturar processos iniciais, folha de pagamento e obrigações fiscais sem grande equipe interna.",
            abordagem_sugerida=f"Olá! Vi que acabaram de iniciar operações em {municipio}. Como estão lidando com a estruturação financeira neste começo? Nós ajudamos empresas como a sua a focar no cliente enquanto cuidamos do BPO Financeiro.",
            confianca_ia="Alta"
        )
        return mock_response.model_dump_json()
    
    pass

def main():
    print("--- INICIANDO ENRIQUECIMENTO COM IA (GOLD LAYER) ---")
    
    con = duckdb.connect(DB_PATH)
    
    # Buscamos as oportunidades geradas pelo dbt usando método nativo (sem Pandas/Numpy)
    cursor = con.execute("""
        SELECT cnpj, municipio_nome, cnae_descricao, opportunity_score 
        FROM gld_opportunities 
        ORDER BY opportunity_score DESC
    """)
    
    colunas = [desc[0] for desc in cursor.description]
    linhas = cursor.fetchall()

    if not linhas:
        print("[AVISO] Nenhuma oportunidade encontrada para enriquecer.")
        return

    resultados = []
    
    print(f"[PROCESSANDO] Enriquecendo {len(linhas)} oportunidade(s)...")
    for linha in linhas:
        # Transforma a tupla em um dicionário para facilitar o acesso
        row = dict(zip(colunas, linha))
        
        # Chama a IA para interpretar o contexto
        json_ia = chamar_llm(row['cnpj'], row['cnae_descricao'], row['municipio_nome'])
        
        # Faz o parse do JSON garantido pelo Pydantic
        contexto = json.loads(json_ia)
        
        resultados.append((
            row['cnpj'],
            contexto['atividade_provavel'],
            contexto['publico_alvo'],
            contexto['dor_provavel'],
            contexto['abordagem_sugerida'],
            contexto['confianca_ia']
        ))

    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    con.execute("DROP TABLE IF EXISTS gold.gld_opportunities_enriched")
    
    # Criamos uma tabela temporária para receber a resposta da IA
    con.execute("""
        CREATE TEMP TABLE temp_resultados (
            cnpj VARCHAR, 
            atividade_provavel VARCHAR, 
            publico_alvo VARCHAR, 
            dor_provavel VARCHAR, 
            abordagem_sugerida VARCHAR, 
            confianca_ia VARCHAR
        )
    """)
    
    # Inserimos os dados rapidamente de forma nativa
    con.executemany("INSERT INTO temp_resultados VALUES (?, ?, ?, ?, ?, ?)", resultados)
    
    # Gravamos o resultado final fazendo JOIN com a tabela do dbt
    con.execute("""
        CREATE TABLE gold.gld_opportunities_enriched AS 
        SELECT 
            o.*,
            e.atividade_provavel,
            e.publico_alvo,
            e.dor_provavel,
            e.abordagem_sugerida,
            e.confianca_ia
        FROM gld_opportunities o
        LEFT JOIN temp_resultados e ON o.cnpj = e.cnpj
    """)

    print("[OK] Tabela gold.gld_opportunities_enriched criada com sucesso!")
    print("--- ENRIQUECIMENTO FINALIZADO ---")
    con.close()

if __name__ == "__main__":
    main()