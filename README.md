# Impressao Automatica de Etiquetas

Aplicativo desenvolvido em TypeScript com arquitetura moderna para automacao de fluxos logisticos. O sistema monitora de forma continua uma pasta especifica no Google Drive, detecta novos arquivos PDF de etiquetas de envio e gerencia o envio direto para impressoras termicas.

---

## Funcionalidades Principais

* **Monitoramento Continuo:** Verificacao periodica de diretorios no Google Drive para captura instantanea de novos documentos.
* **Impressao Direta:** Integracao otimizada para o direcionamento de arquivos diretamente a impressora termica padrao.
* **Controle de Historico:** Armazenamento estruturado de metadados de impressoes realizadas, exibidos em interface tabular.
* **Gestao de Ciclo de Vida:** Rotinas automatizadas para higienizacao de arquivos temporarios e gerenciamento de itens na nuvem.
* **Arquitetura Assincrona:** Isolamento de requisicoes de rede e operacoes de hardware em segundo plano para preservacao da performance.

---

## Stack Tecnologica

* **Linguagem:** TypeScript
* **Ambiente de Execucao:** Node.js
* **Integracoes:** Google Drive API e servicos de impressao do sistema operacional

---

## Pre-requisitos de Instalacao

1. Node.js instalado no ambiente de execucao.
2. Ferramentas de impressao termica configuradas no sistema operacional.
3. Credenciais de acesso a API do Google Cloud configuradas no ambiente.

---

## Configuracao e Execucao

1. Clone o repositorio do projeto para a sua maquina local.
2. Instale as dependencias necessarias executando o comando no terminal:
   ```bash
   npm install
   ```
3. Inicie a aplicacao em modo de desenvolvimento:
   ```bash
   npm run dev