# Etiquetas — Impressão Automática de Etiquetas

Aplicação desktop para Windows desenvolvida em Python/Tkinter para monitorar uma pasta do Google Drive, identificar novos arquivos PDF de etiquetas, baixá-los, imprimi-los automaticamente em uma impressora térmica e registrar o histórico das impressões.

## Visão geral

O fluxo principal do sistema é:

```text
Google Drive
    │
    │ monitoramento periódico
    ▼
Pasta configurada
    │
    │ novo PDF
    ▼
Download local
    │
    ▼
SumatraPDF
    │
    ▼
Impressora térmica
    │
    ├── registro no histórico
    └── limpeza opcional do arquivo no Drive
```

O Google Drive funciona como fonte dos arquivos. A pasta local `etiquetas_baixadas/` é utilizada como área temporária de processamento, enquanto `historico_impressoes.json` registra quais arquivos já foram impressos.

---

## Principais funcionalidades

- Monitoramento automático de uma pasta do Google Drive.
- Identificação de novos arquivos PDF.
- Download temporário das etiquetas.
- Impressão automática utilizando o SumatraPDF.
- Configuração da impressora térmica.
- Histórico das etiquetas impressas.
- Contagem de impressões do dia.
- Prevenção de reimpressão por meio do ID do arquivo no Google Drive.
- Limpeza automática de arquivos já impressos no Google Drive.
- Autenticação OAuth do Google Drive.
- Notificações por e-mail via Gmail.
- Notificações por WhatsApp via CallMeBot.
- Inicialização automática com o Windows.
- Interface gráfica em Tkinter.
- Interface visual personalizada com cartões, botões arredondados e efeitos visuais do Windows.
- Execução do monitoramento em segundo plano para manter a interface responsiva.
- System Tray para manter a aplicação em segundo plano.
- Logs persistentes e rotativos em arquivo.

---

## Estrutura do projeto

O projeto principal é concentrado no arquivo:

```text
imprimir_etiquetas_gui.py
```

Durante a execução, a aplicação utiliza arquivos e diretórios auxiliares:

```text
.
├── imprimir_etiquetas_gui.py
├── config.json
├── token.json
├── historico_impressoes.json
├── app.log
└── etiquetas_baixadas/
```

### `imprimir_etiquetas_gui.py`

Contém toda a aplicação:

- interface gráfica;
- configurações;
- autenticação;
- integração com Google Drive;
- monitoramento;
- download;
- impressão;
- notificações;
- histórico;
- limpeza de arquivos;
- inicialização com Windows;
- System Tray;
- tratamento de erros.

### `config.json`

Armazena as configurações da aplicação, incluindo:

- ID da pasta do Google Drive;
- nome da impressora;
- caminho do SumatraPDF;
- opções de inicialização;
- notificações;
- limpeza automática;
- demais preferências.

As credenciais sensíveis são protegidas no Windows utilizando DPAPI. Configurações antigas contendo credenciais em texto simples são migradas para o formato protegido quando suportado pelo ambiente.

> **Importante:** não versionar `config.json` caso ele contenha informações específicas da instalação.

### `token.json`

Credencial/token utilizado para autenticação do Google Drive.

Esse arquivo é gerado/utilizado pelo fluxo OAuth e deve ser tratado como informação sensível.

### `historico_impressoes.json`

Mantém o histórico das etiquetas impressas.

O histórico é utilizado, entre outras coisas, para evitar que o mesmo arquivo do Google Drive seja impresso novamente.

O histórico possui limite de crescimento para evitar armazenamento indefinido.

### `app.log`

Arquivo de log persistente da aplicação.

O log utiliza rotação de arquivos para evitar crescimento ilimitado.

### `etiquetas_baixadas/`

Diretório temporário utilizado durante o processamento dos PDFs.

Depois da impressão, o PDF local é removido.

---

# Requisitos

## Sistema operacional

O projeto foi desenvolvido com foco em:

- Windows;
- impressora térmica instalada no Windows;
- Google Drive;
- SumatraPDF.

Alguns recursos, como inicialização automática, efeitos visuais e DPAPI, são específicos do Windows.

## Python

É necessário ter uma versão do Python compatível com as bibliotecas utilizadas pelo projeto.

## SumatraPDF

O SumatraPDF é utilizado para executar a impressão dos PDFs.

O caminho do executável deve ser configurado na aplicação, por exemplo:

```text
C:\Program Files\SumatraPDF\SumatraPDF.exe
```

A impressora térmica também precisa estar instalada e configurada no Windows.

---

# Dependências

As principais bibliotecas utilizadas pelo projeto incluem:

- `tkinter`
- `google-auth`
- `google-auth-oauthlib`
- `google-api-python-client`
- `google-auth-httplib2`
- `pystray`
- `Pillow`

Também são utilizadas bibliotecas padrão do Python, como:

- `json`
- `os`
- `pathlib`
- `threading`
- `queue`
- `subprocess`
- `smtplib`
- `logging`
- `socket`
- `datetime`

A lista exata de imports deve ser considerada a fonte de verdade para a montagem do ambiente de execução.

---

# Instalação

## 1. Clonar/copiar o projeto

Coloque o arquivo principal em uma pasta de trabalho:

```text
Etiquetas/
└── imprimir_etiquetas_gui.py
```

## 2. Criar ambiente virtual

No Windows:

```powershell
python -m venv .venv
```

Ative o ambiente:

```powershell
.venv\Scripts\activate
```

## 3. Instalar as dependências

Instale as bibliotecas necessárias para o Google Drive e System Tray:

```powershell
pip install google-auth google-auth-oauthlib google-api-python-client google-auth-httplib2 pystray Pillow
```

O `tkinter` normalmente acompanha instalações do Python para Windows.

## 4. Configurar o Google Drive

É necessário possuir uma aplicação OAuth configurada no Google Cloud e disponibilizar as credenciais OAuth esperadas pelo fluxo utilizado pelo projeto.

Na primeira autenticação, a aplicação abre o fluxo de autorização no navegador.

Após a autorização, o token é armazenado localmente em:

```text
token.json
```

Se a credencial expirar ou precisar ser renovada, a aplicação sinaliza a situação na interface.

---

# Configuração

Abra a aplicação e acesse a aba **Configurações**.

## Google Drive

Informe:

```text
ID da pasta do Google Drive
```

É possível utilizar o botão:

```text
Testar pasta do Drive
```

para verificar o acesso.

O teste possui proteção contra múltiplos cliques simultâneos.

## Impressora

Informe exatamente o nome da impressora térmica instalada no Windows.

Exemplo:

```text
Minha Impressora Térmica
```

## SumatraPDF

Informe o caminho para:

```text
SumatraPDF.exe
```

A configuração de papel/tamanho da etiqueta deve ser realizada no Windows conforme a impressora utilizada.

O projeto considera etiquetas de aproximadamente:

```text
10 × 15 cm
```

## Notificações por e-mail

Quando habilitado, o sistema pode enviar notificações utilizando Gmail/SMTP.

São configurados:

- remetente;
- senha de aplicativo;
- destinatário.

A senha de aplicativo é armazenada de forma protegida no Windows.

A conexão SMTP possui timeout para impedir que uma falha de rede bloqueie indefinidamente o processamento.

## Notificações por WhatsApp

A integração utiliza o CallMeBot.

São configurados:

- telefone;
- API Key.

O telefone passa por validação de formato antes da gravação.

## Limpeza automática

A aplicação pode remover do Google Drive arquivos que já foram impressos após um período configurável.

O número de dias precisa ser um inteiro positivo.

## Inicialização com Windows

A aplicação possui opção para iniciar automaticamente com o Windows.

---

# Operação

Depois de configurar os parâmetros:

1. Salve as configurações.
2. Autentique o Google Drive quando solicitado.
3. Verifique se a impressora está instalada e disponível.
4. Inicie o monitoramento.
5. Coloque os PDFs de etiquetas na pasta configurada do Google Drive.

A aplicação verifica periodicamente a pasta.

Quando encontra um PDF novo:

```text
PDF encontrado
    ↓
Download
    ↓
Impressão
    ↓
Registro no histórico
    ↓
Remoção do arquivo local
```

Se a limpeza automática estiver habilitada, o arquivo já impresso poderá posteriormente ser enviado para a lixeira do Google Drive conforme a configuração.

---

# Proteções de estabilidade

A aplicação possui mecanismos específicos para evitar que uma falha externa congele o monitoramento.

## Impressão

A chamada do SumatraPDF possui timeout de:

```text
120 segundos
```

Isso evita que uma caixa de diálogo ou problema no controlador da impressora mantenha a thread de impressão bloqueada indefinidamente.

## OAuth

O servidor local utilizado pelo fluxo OAuth possui limite de:

```text
180 segundos
```

Assim, fechar o navegador ou abandonar a autenticação não mantém o processo aguardando indefinidamente.

## SMTP

A conexão SMTP possui timeout de:

```text
20 segundos
```

Isso reduz o impacto de falhas de rede, firewall ou indisponibilidade do servidor.

## Concorrência

O teste da pasta do Drive impede novas execuções enquanto um teste já está em andamento.

O monitoramento principal também é executado fora da thread da interface gráfica.

---

# Arquitetura

A aplicação pode ser entendida em duas camadas principais:

```text
┌─────────────────────────────────────┐
│               App                   │
│             Tkinter                 │
│                                     │
│ Monitor | Configurações | Histórico │
└─────────────────┬───────────────────┘
                  │ eventos/controle
                  ▼
┌─────────────────────────────────────┐
│          MotorImpressao             │
│                                     │
│ Google Drive                        │
│    ↓                                │
│ Monitoramento                       │
│    ↓                                │
│ Download                            │
│    ↓                                │
│ SumatraPDF                          │
│    ↓                                │
│ Impressora                          │
│    ↓                                │
│ Histórico / Limpeza / Notificações  │
└─────────────────────────────────────┘
```

A interface gráfica não executa diretamente o processamento pesado. O motor utiliza uma thread de trabalho e envia eventos para a interface através de uma fila.

Os principais eventos tratados pela interface incluem:

```text
log
status
impresso
proxima_checagem
credencial_expirada
```

A interface consulta essa fila periodicamente utilizando o mecanismo `after()` do Tkinter.

---

# Histórico e prevenção de duplicidade

Cada arquivo do Google Drive possui um ID próprio.

Esse ID é utilizado pelo histórico para determinar se o arquivo já foi processado.

Isso é importante porque o nome do arquivo não é a única referência confiável para identificar uma operação já realizada.

O histórico também permite:

- mostrar as impressões na interface;
- contar impressões do dia;
- evitar reprocessamentos;
- manter rastreabilidade básica da operação.

---

# Segurança

O projeto possui alguns cuidados para informações sensíveis:

- tokens do Google Drive são armazenados separadamente;
- credenciais de notificação são protegidas por DPAPI no Windows;
- arquivos de configuração sensíveis não devem ser compartilhados ou versionados;
- o token pode ser removido pela própria interface;
- autenticação expirada é detectada e comunicada ao usuário.

## Arquivos que não devem ser publicados

Evite enviar para Git ou compartilhar:

```text
config.json
token.json
historico_impressoes.json
app.log
```

Especialmente:

```text
token.json
config.json
```

---

# Logs

A aplicação mantém logs persistentes em:

```text
app.log
```

O arquivo registra eventos importantes da execução, incluindo operações do monitoramento e erros.

O sistema utiliza rotação para evitar que o arquivo cresça indefinidamente.

Isso permite investigar problemas que ocorreram antes de a aplicação ser encerrada.

---

# System Tray

Quando o suporte ao System Tray está disponível, a aplicação pode permanecer funcionando na área de notificação do Windows.

A janela principal pode ser ocultada enquanto o monitoramento continua ativo.

As ações disponíveis incluem:

```text
Abrir
Parar monitoramento
Sair
```

Se as bibliotecas do tray não estiverem disponíveis, a aplicação possui comportamento de fallback para não interromper o funcionamento principal.

---

# Tratamento de erros

O projeto possui tratamento específico para situações como:

- credencial Google expirada;
- falha de autenticação;
- pasta do Drive inacessível;
- erro de download;
- erro de impressão;
- timeout de impressão;
- timeout de autenticação;
- timeout SMTP;
- HTTP 429 do Google Drive;
- falhas de leitura/escrita de JSON;
- problemas de configuração;
- tentativa de executar múltiplas instâncias da aplicação.

A aplicação também utiliza um mecanismo de instância única para impedir que duas cópias do programa sejam executadas simultaneamente.

Isso é especialmente importante porque duas instâncias poderiam tentar imprimir a mesma etiqueta.

---

# Desenvolvimento

Para executar diretamente durante o desenvolvimento:

```powershell
python imprimir_etiquetas_gui.py
```

Antes de testar impressão real, recomenda-se verificar:

1. impressora instalada;
2. nome da impressora correto;
3. SumatraPDF funcionando;
4. pasta do Google Drive acessível;
5. autenticação válida;
6. tamanho da etiqueta configurado no Windows.

---

# Fluxo recomendado para testes

## Teste básico

1. Abrir a aplicação.
2. Configurar o Drive.
3. Configurar a impressora.
4. Testar a pasta.
5. Iniciar o monitoramento.
6. Colocar um PDF de teste no Drive.
7. Confirmar o download.
8. Confirmar a impressão.
9. Confirmar o registro no histórico.

## Teste de estabilidade

Verificar:

- desligar/desconectar temporariamente a impressora;
- interromper a rede;
- cancelar/abandonar o OAuth;
- provocar uma falha de SMTP;
- clicar várias vezes em “Testar pasta do Drive”;
- fechar e reabrir a aplicação;
- iniciar uma segunda instância;
- minimizar para o System Tray.

O objetivo é confirmar que nenhuma dessas situações deixa a aplicação permanentemente bloqueada.

---

# Boas práticas para manutenção

Ao modificar o projeto:

- preservar a execução do monitoramento fora da thread principal do Tkinter;
- evitar chamadas de rede sem timeout;
- evitar `subprocess` sem timeout;
- manter o histórico como mecanismo de idempotência;
- não armazenar novas credenciais em texto simples;
- registrar falhas relevantes no log;
- evitar operações demoradas diretamente nos callbacks da interface;
- manter a proteção contra múltiplas instâncias;
- validar configurações antes de iniciar o monitoramento.

---

# Segurança e versionamento com Git

Se o projeto for colocado em um repositório Git, recomenda-se criar um `.gitignore` semelhante a:

```gitignore
__pycache__/
*.py[cod]

.venv/
venv/
env/

config.json
token.json
historico_impressoes.json
app.log

etiquetas_baixadas/

*.log
```

Os arquivos contendo credenciais, tokens e dados locais de execução não devem ser commitados.

---

# Estado atual

O projeto possui como objetivo principal fornecer uma automação contínua e resiliente para impressão de etiquetas a partir do Google Drive.

As melhorias de estabilidade implementadas incluem:

- timeout de impressão;
- timeout do OAuth;
- timeout SMTP;
- proteção contra testes concorrentes;
- proteção local de credenciais;
- logging persistente;
- validação de configurações;
- integração com System Tray;
- prevenção de múltiplas instâncias;
- tratamento de credenciais expiradas;
- tratamento de erros de rede;
- recuperação segura de arquivos JSON.

---

# Próximas melhorias possíveis

Algumas evoluções que podem ser consideradas futuramente:

- criação de instalador `.exe`;
- atualização automática da aplicação;
- arquivo `requirements.txt` ou `pyproject.toml` mantido junto ao código;
- testes automatizados;
- testes de integração com uma pasta de Drive dedicada;
- painel de métricas;
- configuração de horários de operação;
- fila explícita de impressão;
- mecanismo de retry configurável para falhas de impressão;
- assinatura digital do executável;
- backup do histórico;
- exportação do histórico para CSV.

---

## Licença

Defina aqui a licença do projeto caso ele seja distribuído publicamente.

Exemplo:

```text
MIT License
```

ou substitua pela licença definida pelo proprietário do projeto.
