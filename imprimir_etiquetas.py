    """
    Monitora uma pasta do Google Drive e imprime automaticamente
    os PDFs novos (etiquetas) na impressora térmica configurada.

    CONFIGURAÇÃO NECESSÁRIA (veja instruções.txt):
    1. credentials.json (do Google Cloud Console)
    2. SumatraPDF instalado
    3. Preencher as variáveis na seção CONFIG abaixo
    """

    import os
    import io
    import json
    import time
    import subprocess
    from pathlib import Path

    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    # ========== CONFIG (edite aqui) ==========
    FOLDER_ID = "COLOQUE_AQUI_O_ID_DA_PASTA_DO_DRIVE"
    PRINTER_NAME = "NOME_EXATO_DA_SUA_IMPRESSORA_TERMICA"
    SUMATRA_PATH = r"C:\Program Files\SumatraPDF\SumatraPDF.exe"
    POLL_INTERVAL_SECONDS = 30
    # ==========================================

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    DOWNLOAD_DIR = Path("etiquetas_baixadas")
    PRINTED_LOG = Path("impressos.json")


    def autenticar_drive():
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return build("drive", "v3", credentials=creds)


    def carregar_impressos():
        if PRINTED_LOG.exists():
            return set(json.loads(PRINTED_LOG.read_text()))
        return set()


    def salvar_impressos(ids):
        PRINTED_LOG.write_text(json.dumps(list(ids)))


    def listar_pdfs(service):
        query = (
            f"'{FOLDER_ID}' in parents and mimeType='application/pdf' "
            "and trashed=false"
        )
        resultados = (
            service.files().list(q=query, fields="files(id, name)").execute()
        )
        return resultados.get("files", [])


    def baixar_arquivo(service, file_id, nome):
        DOWNLOAD_DIR.mkdir(exist_ok=True)
        caminho = DOWNLOAD_DIR / nome
        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(caminho, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.close()
        return caminho


    def imprimir(caminho_pdf):
        subprocess.run(
            [SUMATRA_PATH, "-print-to", PRINTER_NAME, "-silent", str(caminho_pdf)],
            check=True,
        )


    def main():
        service = autenticar_drive()
        impressos = carregar_impressos()

        print("Monitorando pasta do Google Drive... (Ctrl+C para parar)")
        while True:
            try:
                arquivos = listar_pdfs(service)
                novos = [a for a in arquivos if a["id"] not in impressos]

                for arquivo in novos:
                    print(f"Novo arquivo encontrado: {arquivo['name']}")
                    caminho = baixar_arquivo(service, arquivo["id"], arquivo["name"])
                    try:
                        imprimir(caminho)
                        print(f"Impresso: {arquivo['name']}")
                        impressos.add(arquivo["id"])
                        salvar_impressos(impressos)
                    except Exception as e:
                        print(f"Erro ao imprimir {arquivo['name']}: {e}")

            except Exception as e:
                print(f"Erro ao consultar o Drive: {e}")

            time.sleep(POLL_INTERVAL_SECONDS)


    if __name__ == "__main__":
        main()
