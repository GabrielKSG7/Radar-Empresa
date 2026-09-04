import httpx
import duckdb
import os
import time
import zipfile

URLS = {
    "cnaes": "https://dadosabertos.rfb.gov.br/CNPJ/Cnaes.zip",
    "municipios": "https://dadosabertos.rfb.gov.br/CNPJ/Municipios.zip",
    "estabelecimentos": "https://dadosabertos.rfb.gov.br/CNPJ/Estabelecimentos0.zip"
}

RAW_DIR = "data/raw"
DB_PATH = "data/radar.duckdb"

def baixar_arquivo(nome, url, tentativas=2):
    zip_path = os.path.join(RAW_DIR, f"{nome}.zip")
    if os.path.exists(zip_path):
        print(f"[SKIP] {nome}.zip já existe localmente.")
        return zip_path

    for tentativa in range(1, tentativas + 1):
        print(f"[DOWNLOADING] Baixando {nome} (Tentativa {tentativa}/{tentativas})...")
        try:
            with httpx.stream("GET", url, verify=False, timeout=120.0) as response:
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)
            print(f"[OK] {nome} baixado com sucesso!")
            return zip_path
        except Exception as e:
            print(f"[ERRO] Falha na tentativa {tentativa}: {e}")
            if tentativa < tentativas:
                time.sleep(5)
    return None

def gerar_dados_mock():
    print("\n[MOCK] Gerando dados fictícios para desenvolvimento...")
    with zipfile.ZipFile(os.path.join(RAW_DIR, "cnaes.zip"), "w") as z:
        z.writestr("cnaes.csv", "6920601;Atividades de contabilidade\n6204000;Consultoria em TI\n".encode('iso-8859-1'))

    with zipfile.ZipFile(os.path.join(RAW_DIR, "municipios.zip"), "w") as z:
        z.writestr("municipios.csv", "5403;VARGINHA\n7107;SAO PAULO\n".encode('iso-8859-1'))

    hoje_mock = time.strftime("%Y%m%d")
    est_csv = (
        f"11111111;0001;99;1;X;02;X;X;X;X;{hoje_mock};6920601;X;X;X;X;X;X;X;MG;5403\n"
        f"22222222;0001;88;1;X;02;X;X;X;X;20200101;6204000;X;X;X;X;X;X;X;MG;5403\n"
        f"33333333;0001;77;1;X;02;X;X;X;X;{hoje_mock};6920601;X;X;X;X;X;X;X;SP;7107\n"
    )
    with zipfile.ZipFile(os.path.join(RAW_DIR, "estabelecimentos.zip"), "w") as z:
        z.writestr("estabelecimentos.csv", est_csv.encode('iso-8859-1'))
    print("[MOCK] Arquivos gerados com sucesso!")

def extrair_csv(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as z:
        nome_csv = z.namelist()[0]
        z.extract(nome_csv, RAW_DIR)
        # Correção Crítica: Forçando barras normais no Windows para o DuckDB não quebrar
        return os.path.join(RAW_DIR, nome_csv).replace('\\', '/')

def main():
    print("--- INICIANDO INGESTÃO BRONZE ---")
    os.makedirs(RAW_DIR, exist_ok=True)
    caminhos_zip = {}
    usar_mock = False

    for nome, url in URLS.items():
        caminho = baixar_arquivo(nome, url)
        if not caminho:
            usar_mock = True
            break
        caminhos_zip[nome] = caminho

    if usar_mock:
        gerar_dados_mock()
        caminhos_zip = {
            "cnaes": "data/raw/cnaes.zip",
            "municipios": "data/raw/municipios.zip",
            "estabelecimentos": "data/raw/estabelecimentos.zip"
        }

    print("\n[INGESTÃO] Extraindo arquivos ZIP...")
    caminhos_csv = {}
    for nome, zip_path in caminhos_zip.items():
        caminhos_csv[nome] = extrair_csv(zip_path)

    print("[INGESTÃO] Conectando ao DuckDB...")
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

    print("[INGESTÃO] Criando tabela bronze.cnaes...")
    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.cnaes AS
        SELECT * FROM read_csv('{caminhos_csv['cnaes']}', delim=';', header=false, encoding='latin-1',
        columns={{'id_cnae': 'VARCHAR', 'descricao': 'VARCHAR'}})
    """)

    print("[INGESTÃO] Criando tabela bronze.municipios...")
    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.municipios AS
        SELECT * FROM read_csv('{caminhos_csv['municipios']}', delim=';', header=false, encoding='latin-1',
        columns={{'id_municipio': 'VARCHAR', 'descricao': 'VARCHAR'}})
    """)

    print("[INGESTÃO] Criando tabela bronze.estabelecimentos...")
    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.estabelecimentos AS
        SELECT column00 as cnpj_basico, column01 as cnpj_ordem, column02 as cnpj_dv,
               column03 as identificador_matriz_filial, column05 as situacao_cadastral,
               column10 as data_inicio_atividade, column11 as cnae_principal,
               column20 as id_municipio, column19 as uf
        FROM read_csv('{caminhos_csv['estabelecimentos']}', delim=';', header=false, encoding='latin-1')
    """)

    print("--- SCRIPT FINALIZADO COM SUCESSO ---")
    con.close()

if __name__ == "__main__":
    main()