import httpx
import duckdb
import os

URL_CNAE = "https://dadosabertos.rfb.gov.br/CNPJ/Cnaes.zip"
RAW_DIR = "data/raw"
ZIP_PATH = os.path.join(RAW_DIR, "Cnaes.zip")
DB_PATH = "data/radar.duckdb"

def main():
    print(f"Baixando {URL_CNAE}...")
    

    try:
        with httpx.stream("GET", URL_CNAE, verify=False, timeout=120.0) as response:
            response.raise_for_status()
            with open(ZIP_PATH, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        print("Download concluído com sucesso!")
    except httpx.TimeoutException:
        print("Erro: O servidor da Receita demorou demais para responder. Tente rodar novamente.")
        return
    except Exception as e:
        print(f"Erro no download: {e}")
        return

    print("Iniciando ingestão no DuckDB...")
    con = duckdb.connect(DB_PATH)
    
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    
    query = f"""
    CREATE OR REPLACE TABLE bronze.cnaes AS 
    SELECT * FROM read_csv('{ZIP_PATH}', 
        delim=';', 
        header=false, 
        encoding='ISO-8859-1',
        columns={{'id_cnae': 'VARCHAR', 'descricao': 'VARCHAR'}}
    )
    """
    con.execute(query)
    print("Tabela bronze.cnaes criada no DuckDB com sucesso!\n")
    
    print("Amostra dos dados ingeridos:")
    print(con.execute("SELECT * FROM bronze.cnaes LIMIT 5").fetchdf())
    
    con.close()

if __name__ == "__main__":
    main()