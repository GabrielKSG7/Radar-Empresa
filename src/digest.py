import duckdb
import os
from datetime import datetime

# Configurações
DB_PATH = "data/radar.duckdb"
DIGEST_DIR = "data/digests"

def formatar_oportunidade(row: dict) -> str:
    """Formata uma linha de oportunidade em um bloco Markdown elegante."""
    return f"""
### 🏢 Oportunidade: CNPJ {row['cnpj']}
* **Local e Setor:** {row['municipio_nome']} | {row['cnae_descricao']}
* 🔥 **Opportunity Score:** {row['opportunity_score']}/100
* 📊 **Por que é uma oportunidade?** {row['score_explanation']}

#### 🧠 Inteligência Comercial (IA)
* **O que a empresa faz:** {row['atividade_provavel']}
* **Público-alvo provável:** {row['publico_alvo']}
* **Dor operacional esperada:** {row['dor_provavel']}

#### 💬 Sugestão de Abordagem (Copy-Paste)
> {row['abordagem_sugerida']}

---
"""

def main():
    print("--- GERANDO DIGEST DE OPORTUNIDADES ---")
    
    os.makedirs(DIGEST_DIR, exist_ok=True)
    
    con = duckdb.connect(DB_PATH)
    
    # Buscamos as oportunidades enriquecidas (usando dicionários nativos)
    cursor = con.execute("""
        SELECT *
        FROM gold.gld_opportunities_enriched 
        ORDER BY opportunity_score DESC
    """)
    
    colunas = [desc[0] for desc in cursor.description]
    linhas = cursor.fetchall()
    
    if not linhas:
        print("[AVISO] Nenhuma oportunidade para gerar no Digest de hoje.")
        con.close()
        return

    data_hoje = datetime.now().strftime("%Y-%m-%d")
    arquivo_saida = os.path.join(DIGEST_DIR, f"radar_digest_{data_hoje}.md")
    
    # Cabeçalho do Documento
    markdown_content = f"# 🎯 Radar B2B - Digest Diário\n"
    markdown_content += f"**Data:** {data_hoje}\n"
    markdown_content += f"**Oportunidades Encontradas:** {len(linhas)}\n\n"
    markdown_content += "Aqui estão as empresas com maior probabilidade de fechamento hoje, baseadas no seu ICP e eventos recentes.\n\n---\n"
    
    # Adicionando cada oportunidade formatada
    for linha in linhas:
        row = dict(zip(colunas, linha))
        markdown_content += formatar_oportunidade(row)
        
    # Salvando o arquivo
    with open(arquivo_saida, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        
    print(f"[OK] Digest gerado com sucesso em: {arquivo_saida}")
    con.close()

if __name__ == "__main__":
    main()