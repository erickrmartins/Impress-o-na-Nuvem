# Impressao na Nuvem

Aplicativo desktop desenvolvido em Python com interface grafica em Tkinter, projetado para automacao de fluxos logisticos. O sistema monitora de forma continua uma pasta especifica no Google Drive, detecta novos arquivos PDF de etiquetas de envio (10x15 cm) e realiza o envio direto para impressoras termicas utilizando o utilitario SumatraPDF.

## Funcionalidades Principais

* **Monitoramento Continuo:** Verificacao periodica e automatizada de diretorios no Google Drive para captura instantanea de novos documentos PDF.

* **Impressao Silenciosa:** Integracao otimizada com o SumatraPDF para o direcionamento de arquivos diretamente a impressora termica padrao do sistema operacional.

* **Controle de Historico e Auditoria:** Armazenamento estruturado de metadados de impressoes bem-sucedidas (data, hora e identificador do arquivo), exibidos dinamicamente em interface tabular.

* **Gestao de Ciclo de Vida de Arquivos:** Rotinas automatizadas para higienizacao de arquivos locais temporarios e gerenciamento de itens na nuvem.

* **Arquitetura Multi-Thread:** Execucao das requisicoes de rede e operacoes de hardware isoladas em segundo plano, preservando a fluidez e a responsividade da interface grafica.

## Stack Tecnologica

* **Linguagem:** Python 3.8+

* **Interface Grafica:** `tkinter` e `ttk` com personalizacao de estilos visuais

* **APIs e Integracoes:** Google API Client (`google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`) para autenticacao OAuth 2.0

* **Dependencias Externas:** SumatraPDF para renderizacao e envio de comandos de impressao em modo silencioso

## Pre-requisitos de Instalacao

1. Python 3.8 ou superior instalado no ambiente de execucao.

2. SumatraPDF instalado no sistema (caminho padrao sugerido: `C:\Program Files\SumatraPDF\SumatraPDF.exe`).

3. Credenciais da API do Google Cloud (`credentials.json`) configuradas atraves de um projeto no Google Cloud Console com a Google Drive API habilitada.

## Configuracao e Execucao

1. Clone o repositorio do projeto para a sua maquina local.

2. Instale as dependencias necessarias executando o comando no terminal:

   ```
   pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 pywin32
   ```

3. Certifique-se de que o arquivo `credentials.json` esta alocado na raiz do diretorio do projeto.

4. Inicie a aplicacao executando o script principal:

   ```
   python imprimir_etiquetas_gui_2.py