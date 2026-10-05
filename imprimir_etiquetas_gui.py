"""
Interface gráfica para monitorar uma pasta do Google Drive e imprimir
automaticamente os PDFs novos (etiquetas 10x15) na impressora térmica.

Configuração é feita pela própria interface (fica salva em config.json).
Histórico de impressões (com data/hora) fica salvo em
historico_impressoes.json e é exibido na aba "Histórico".
"""

import os
import io
import sys
import json
import time
import queue
import socket
import smtplib
import ssl
import urllib.request
import urllib.parse
import threading
import subprocess
import ctypes
from ctypes import wintypes
import tkinter as tk
from email.mime.text import MIMEText
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError, GoogleAuthError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# Escopo "drive" (leitura/escrita) é necessário para mover arquivos
# antigos para a lixeira. Se você já tinha um token.json gerado com o
# escopo antigo (só leitura), apague-o e autorize de novo.
SCOPES = ["https://www.googleapis.com/auth/drive"]
DOWNLOAD_DIR = Path("etiquetas_baixadas")
HISTORICO_PATH = Path("historico_impressoes.json")
CONFIG_PATH = Path("config.json")
TOKEN_PATH = Path("token.json")
POLL_INTERVAL_SECONDS = 30

MENSAGEM_CREDENCIAL_EXPIRADA = (
    "Credencial do Google Drive expirada ou inválida. "
    "Abra Configurações, aperte “Excluir token.json” e reinicie o aplicativo."
)

CONFIG_PADRAO = {
    "folder_id": "",
    "printer_name": "",
    "sumatra_path": r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
    "notif_email_ativo": False,
    "notif_email_remetente": "",
    "notif_email_senha_app": "",
    "notif_email_destino": "",
    "notif_whatsapp_ativo": False,
    "notif_whatsapp_telefone": "",
    "notif_whatsapp_apikey": "",
    "limpeza_automatica_ativa": True,
    "dias_para_excluir": 5,
}

# Intervalo mínimo entre notificações de falha repetidas, pra não
# inundar seu e-mail/WhatsApp se o mesmo erro continuar acontecendo.
INTERVALO_MIN_NOTIFICACAO = 15 * 60  # 15 minutos

# Porta local usada apenas como trava para impedir duas instâncias abertas
# ao mesmo tempo (evita baixar/imprimir o mesmo arquivo em duplicidade).
PORTA_TRAVA_INSTANCIA = 47612


class CredencialExpirada(Exception):
    """Token inválido ou expirado; o usuário precisa excluir token.json e reiniciar."""


def obter_trava_instancia():
    """Tenta reservar uma porta local fixa. Se já estiver em uso, é porque
    outra instância do programa já está rodando nesta máquina."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", PORTA_TRAVA_INSTANCIA))
        sock.listen(1)
        return sock
    except OSError:
        sock.close()
        return None


def caminho_atalho_startup():
    pasta = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return pasta / "ImpressaoEtiquetas.lnk"


def iniciar_com_windows_ativo():
    return caminho_atalho_startup().exists()


def ativar_inicio_com_windows():
    """Cria um atalho na pasta Startup do Windows apontando para este
    script, usando pythonw.exe (sem abrir janela de terminal)."""
    import win32com.client

    script = str(Path(__file__).resolve())
    pythonw = str(Path(sys.executable).with_name("pythonw.exe"))
    if not Path(pythonw).exists():
        pythonw = sys.executable

    shell = win32com.client.Dispatch("WScript.Shell")
    atalho = shell.CreateShortcut(str(caminho_atalho_startup()))
    atalho.TargetPath = pythonw
    atalho.Arguments = f'"{script}"'
    atalho.WorkingDirectory = str(Path(script).parent)
    atalho.IconLocation = pythonw
    atalho.Save()


def desativar_inicio_com_windows():
    caminho = caminho_atalho_startup()
    if caminho.exists():
        caminho.unlink()


# ---------- Paleta (vidro âmbar translúcido, estilo flyout do Windows) ----------
COR_FUNDO = "#f4f5f3"          # --color-main-bg
COR_CARD = "#ffffff"           # --color-card-bg
COR_CARD_BRILHO = "#e8eef0"    # --color-tint
COR_TEXTO = "#164a68"          # --color-card-text-main
COR_TEXTO_MUTED = "#46515a"    # --color-card-text-sec
COR_BORDA = "rgba(31, 42, 51, 0.09)" # Como o Tkinter não aceita rgba direto, usamos um equivalente opaco equivalente (ex: #e6e8ea) ou ajustado para a borda:
COR_BORDA = "#e3e7ea"          # Equivalente sólido para a borda
COR_BORDA_BRILHO = "#d2d8dc"
COR_ACCENT = "#f2a900"         # --color-button-bg
COR_ACCENT_HOVER = "#d99700"   # Tom ligeiramente mais escuro para o hover
COR_ACCENT_FG = "#17242c"      # --color-button-text
COR_SUCESSO = "#10b981"
COR_SUCESSO_BG = "#dcfce7"
COR_ALERTA = "#f59e0b"
COR_ALERTA_BG = "#fef3c7"
COR_ERRO = "#ef4444"
COR_ERRO_BG = "#fee2e2"
COR_PARADO_BG = "#ffffff"
RAIO_CARD = 12
RAIO_BOTAO = 8
FONTE_UI = "Segoe UI"

# Ícones (glifos) usados nas linhas de configuração, no mesmo espírito
# ícone + texto + seta do menu de referência.
ICONE_CONEXAO = "🖶"
ICONE_WINDOWS = "🗗"
ICONE_TOKEN = "🔑"
ICONE_ALERTA = "🔔"
ICONE_LIMPEZA = "🧹"
ICONE_SETA = "›"


def _hex_para_rgb(cor):
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_para_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, int(c))) for c in rgb])


def _misturar(cor_a, cor_b, t):
    a, b = _hex_para_rgb(cor_a), _hex_para_rgb(cor_b)
    return _rgb_para_hex(a[i] + (b[i] - a[i]) * t for i in range(3))


def _poligono_arredondado(x1, y1, x2, y2, raio):
    raio = max(0, min(raio, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + raio, y1,
        x2 - raio, y1,
        x2, y1,
        x2, y1 + raio,
        x2, y2 - raio,
        x2, y2,
        x2 - raio, y2,
        x1 + raio, y2,
        x1, y2,
        x1, y2 - raio,
        x1, y1 + raio,
        x1, y1,
    ]


def _desenhar_retangulo_arredondado(canvas, x1, y1, x2, y2, raio, preenchimento, borda, largura_borda=1, tags="shape"):
    pontos = _poligono_arredondado(x1, y1, x2, y2, raio)
    return canvas.create_polygon(
        pontos, smooth=True, splinesteps=16,
        fill=preenchimento, outline=borda, width=largura_borda, tags=tags,
    )


def _pintar_fundo_espelhado(canvas, largura, altura):
    """Gradiente + reflexo diagonal, para simular vidro mesmo sem Acrylic."""
    canvas.delete("vidro")
    if largura < 2 or altura < 2:
        return
    passos = max(24, min(72, altura // 8))
    for i in range(passos):
        t = i / max(passos - 1, 1)
        if t < 0.45:
            cor = _misturar(COR_FUNDO_TOPO, COR_FUNDO, t / 0.45)
        else:
            cor = _misturar(COR_FUNDO, COR_FUNDO_BASE, (t - 0.45) / 0.55)
        y1 = int(altura * i / passos)
        y2 = int(altura * (i + 1) / passos) + 1
        canvas.create_rectangle(0, y1, largura, y2, fill=cor, outline=cor, tags="vidro")
    # Reflexo principal (canto superior) — tons âmbar
    canvas.create_oval(
        largura * 0.35, -altura * 0.38, largura * 1.15, altura * 0.42,
        fill="#5a4030", outline="", tags="vidro",
    )
    canvas.create_oval(
        largura * 0.48, -altura * 0.28, largura * 1.05, altura * 0.28,
        fill="#6e4e34", outline="", tags="vidro",
    )
    # Faixa especular diagonal
    for i, t in enumerate((0.12, 0.18, 0.28)):
        cor = _misturar("#9a6e46", COR_FUNDO, 0.55 + i * 0.12)
        canvas.create_polygon(
            largura * (0.08 + i * 0.04), 0,
            largura * (0.22 + i * 0.04), 0,
            largura * (0.02 + i * 0.03), altura,
            largura * (-0.12 + i * 0.03), altura,
            fill=cor, outline="", tags="vidro",
        )
    # Reflexo inferior (espelho)
    canvas.create_oval(
        -largura * 0.2, altura * 0.72, largura * 0.55, altura * 1.35,
        fill="#2a1c14", outline="", tags="vidro",
    )
    canvas.tag_lower("vidro")


def _hwnd_toplevel(widget):
    hwnd = widget.winfo_id()
    user32 = ctypes.windll.user32
    parent = user32.GetParent(hwnd)
    return parent or hwnd


def aplicar_efeito_vidro(janela):
    """Acrylic/Mica + barra escura no Windows, quando o sistema permite."""
    if sys.platform != "win32":
        return
    try:
        janela.update_idletasks()
        hwnd = _hwnd_toplevel(janela)
        dwmapi = ctypes.windll.dwmapi
        escuro = ctypes.c_int(1)
        for attr in (20, 19):
            dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(escuro), ctypes.sizeof(escuro))

        class MARGINS(ctypes.Structure):
            _fields_ = [
                ("cxLeftWidth", ctypes.c_int),
                ("cxRightWidth", ctypes.c_int),
                ("cyTopHeight", ctypes.c_int),
                ("cyBottomHeight", ctypes.c_int),
            ]

        margens = MARGINS(-1, -1, -1, -1)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margens))

        # 3 = Acrylic (translucid), 2 = Mica
        backdrop = ctypes.c_int(3)
        dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))

        class ACCENTPOLICY(ctypes.Structure):
            _fields_ = [
                ("AccentState", ctypes.c_uint),
                ("AccentFlags", ctypes.c_uint),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId", ctypes.c_uint),
            ]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [
                ("Attribute", ctypes.c_int),
                ("Data", ctypes.c_void_p),
                ("SizeOfData", ctypes.c_size_t),
            ]

        accent = ACCENTPOLICY()
        accent.AccentState = 4  # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2
        accent.GradientColor = 0xCC241a14  # ABGR: âmbar escuro translúcido
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19
        data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.SizeOfData = ctypes.sizeof(accent)
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
    except Exception:
        pass


class CardEspelhado(tk.Frame):
    """Card fosco, borda clara e brilho no topo (vidro)."""

    def __init__(self, parent, raio=RAIO_CARD, **kwargs):
        super().__init__(parent, bg=COR_FUNDO, **kwargs)
        self.raio = raio
        self.canvas = tk.Canvas(self, bg=COR_FUNDO, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=COR_CARD)
        self._janela = self.canvas.create_window(14, 14, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._redesenhar)
        self.bind("<Configure>", self._redesenhar)
        self._ultima_medida = (0, 0)

    def _redesenhar(self, event=None):
        self.update_idletasks()
        largura = max(self.winfo_width(), 48)
        altura_inner = max(self.inner.winfo_reqheight(), 24)
        altura = altura_inner + 28
        medida = (largura, altura)
        if medida == self._ultima_medida and self.canvas.find_withtag("shape"):
            return
        self._ultima_medida = medida
        self.canvas.config(width=largura, height=altura)
        self.canvas.delete("shape")
        _desenhar_retangulo_arredondado(
            self.canvas, 2, 2, largura - 3, altura - 3,
            self.raio, COR_CARD, COR_BORDA, 1,
        )
        brilho_h = min(36, max(20, altura // 3))
        _desenhar_retangulo_arredondado(
            self.canvas, 3, 3, largura - 4, 3 + brilho_h,
            self.raio - 3, COR_CARD_BRILHO, COR_CARD_BRILHO, 0,
        )
        self.canvas.create_line(
            22, 3, largura - 22, 3, fill=COR_BORDA_BRILHO, width=1, tags="shape",
        )
        self.canvas.coords(self._janela, 16, 14)
        self.canvas.itemconfig(self._janela, width=max(largura - 32, 20))
        self.canvas.tag_lower("shape")


class BotaoArredondado(tk.Canvas):
    def __init__(
        self, parent, texto, comando, primario=True, raio=RAIO_BOTAO, estado="normal", fundo=None,
    ):
        fundo = fundo or COR_FUNDO
        super().__init__(parent, highlightthickness=0, bd=0, bg=fundo, cursor="hand2")
        self.texto = texto
        self.comando = comando
        self.primario = primario
        self.raio = raio
        self._estado = estado
        self._hover = False
        fonte = (FONTE_UI, 10) if primario else (FONTE_UI, 10)
        tmp = tk.Label(self, text=texto, font=fonte)
        tmp.update_idletasks()
        largura = tmp.winfo_reqwidth() + 40
        altura = tmp.winfo_reqheight() + 16
        tmp.destroy()
        self.config(width=largura, height=altura)
        self.bind("<Button-1>", self._clicar)
        self.bind("<Enter>", self._entrar)
        self.bind("<Leave>", self._sair)
        self._desenhar()

    def _cores(self):
        if self._estado == "disabled":
            return COR_CARD_BRILHO, COR_TEXTO_MUTED
        if self.primario:
            fundo = COR_ACCENT_HOVER if self._hover else COR_ACCENT
            return fundo, COR_ACCENT_FG
        fundo = "#3a3a46" if self._hover else COR_CARD_BRILHO
        return fundo, COR_TEXTO

    def _desenhar(self):
        self.delete("all")
        w, h = int(self["width"]), int(self["height"])
        fundo, fg = self._cores()
        borda = "" if self.primario else COR_BORDA
        _desenhar_retangulo_arredondado(self, 1, 1, w - 2, h - 2, self.raio, fundo, borda or fundo, 1)
        if self.primario and self._estado == "normal":
            self.create_line(16, 2, w - 16, 2, fill=COR_ACCENT_FG, tags="shape")
        self.create_text(w / 2, h / 2, text=self.texto, fill=fg, font=(FONTE_UI, 10), tags="label")

    def _clicar(self, _event=None): 
        if self._estado == "disabled":
            return
        if self.comando:
            self.comando()

    def _entrar(self, _event=None):
        self._hover = True
        self._desenhar()

    def _sair(self, _event=None):
        self._hover = False
        self._desenhar()

    def config_estado(self, estado):
        self._estado = estado
        self.config(cursor="" if estado == "disabled" else "hand2")
        self._desenhar()


class Interruptor(tk.Frame):
    def __init__(self, parent, texto, variable, fundo=COR_CARD):
        super().__init__(parent, bg=fundo)
        self.variable = variable
        self.canvas = tk.Canvas(self, width=42, height=24, bg=fundo, highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack(side="left")
        tk.Label(self, text=texto, bg=fundo, fg=COR_TEXTO, font=(FONTE_UI, 10), anchor="w").pack(
            side="left", padx=(10, 0)
        )
        self.canvas.bind("<Button-1>", self._alternar)
        variable.trace_add("write", lambda *_: self._desenhar())
        self._desenhar()

    def _alternar(self, _event=None):
        self.variable.set(not self.variable.get())

    def _desenhar(self):
        self.canvas.delete("all")
        ligado = bool(self.variable.get())
        fundo = COR_ACCENT if ligado else COR_BORDA_BRILHO
        _desenhar_retangulo_arredondado(self.canvas, 1, 3, 41, 21, 10, fundo, fundo, 0, "sw")
        cx = 31 if ligado else 11
        self.canvas.create_oval(cx - 7, 5, cx + 7, 19, fill=COR_CARD if ligado else COR_CARD, outline="")


def carregar_config():
    if CONFIG_PATH.exists():
        dados = json.loads(CONFIG_PATH.read_text())
        return {**CONFIG_PADRAO, **dados}
    return dict(CONFIG_PADRAO)


def salvar_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def carregar_historico():
    if HISTORICO_PATH.exists():
        return json.loads(HISTORICO_PATH.read_text())
    return []


def salvar_historico(historico):
    HISTORICO_PATH.write_text(json.dumps(historico, indent=2, ensure_ascii=False))


def erro_indica_credencial_expirada(exc):
    if isinstance(exc, CredencialExpirada):
        return True
    if isinstance(exc, RefreshError):
        return True
    if isinstance(exc, HttpError) and getattr(exc, "resp", None) is not None:
        if int(exc.resp.status) == 401:
            return True
        corpo = ""
        try:
            corpo = (exc.content or b"").decode("utf-8", errors="ignore").lower()
        except Exception:
            corpo = ""
        if int(exc.resp.status) == 403 and any(
            chave in corpo for chave in ("invalid", "auth", "expired", "unauthenticated")
        ):
            return True
    texto = str(exc).lower()
    chaves = (
        "invalid_grant",
        "token has been expired",
        "token expired",
        "invalid credentials",
        "refresh token",
        "unauthenticated",
        "access_denied",
        "expired or revoked",
    )
    return any(chave in texto for chave in chaves)


def mensagem_amigavel_excecao(exc, contexto=""):
    prefixo = f"{contexto}: " if contexto else ""
    if erro_indica_credencial_expirada(exc):
        return prefixo + MENSAGEM_CREDENCIAL_EXPIRADA
    if isinstance(exc, FileNotFoundError):
        return prefixo + f"Arquivo não encontrado: {exc}"
    if isinstance(exc, subprocess.CalledProcessError):
        detalhe = (exc.stderr or exc.stdout or str(exc)).strip()
        return prefixo + f"Falha ao executar o comando de impressão. {detalhe}"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return prefixo + "Tempo esgotado na conexão. Verifique a internet e tente de novo."
    if isinstance(exc, (ConnectionError, OSError)) and getattr(exc, "errno", None):
        return prefixo + f"Falha de rede ({type(exc).__name__}): {exc}"
    if isinstance(exc, HttpError):
        status = getattr(getattr(exc, "resp", None), "status", "?")
        return prefixo + f"Erro da API do Drive (HTTP {status}): {exc}"
    if isinstance(exc, GoogleAuthError):
        return prefixo + f"Erro de autenticação Google: {exc}"
    return prefixo + f"{type(exc).__name__}: {exc}"


class MotorImpressao:
    """Roda em thread separada; comunica com a GUI por uma fila de eventos."""

    def __init__(self, config, eventos: queue.Queue):
        self.config = config
        self.eventos = eventos
        self._parar = threading.Event()
        self._thread = None
        self.service = None
        self._ultima_notificacao = 0

    def log(self, msg):
        self.eventos.put(("log", msg))

    def status(self, msg):
        self.eventos.put(("status", msg))

    def impresso(self, nome):
        self.eventos.put(("impresso", nome))

    def proxima_checagem(self, segundos):
        self.eventos.put(("proxima_checagem", segundos))

    def iniciar(self):
        self._parar.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def parar(self):
        self._parar.set()

    def _sinalizar_credencial_expirada(self, detalhe=""):
        self.status("Credencial expirada")
        self.log(MENSAGEM_CREDENCIAL_EXPIRADA)
        if detalhe:
            self.log(f"Detalhe técnico: {detalhe}")
        self.eventos.put(("credencial_expirada", detalhe or MENSAGEM_CREDENCIAL_EXPIRADA))
        self._notificar_falha(MENSAGEM_CREDENCIAL_EXPIRADA)
        self._parar.set()

    def _autenticar(self):
        creds = None
        if TOKEN_PATH.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
            except Exception as e:
                raise CredencialExpirada(
                    f"Não foi possível ler token.json ({e}). Exclua o token e reinicie."
                ) from e
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    raise CredencialExpirada(str(e)) from e
            else:
                if creds and not creds.valid:
                    raise CredencialExpirada(
                        "O token salvo não é mais válido. Exclua token.json e reinicie."
                    )
                if not os.path.exists("credentials.json"):
                    raise FileNotFoundError(
                        "credentials.json não encontrado (veja instrucoes.txt)"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
        return build("drive", "v3", credentials=creds)

    def _listar_pdfs(self):
        query = (
            f"'{self.config['folder_id']}' in parents and "
            "mimeType='application/pdf' and trashed=false"
        )
        resultados = (
            self.service.files()
            .list(q=query, fields="files(id, name, modifiedTime)")
            .execute()
        )
        return resultados.get("files", [])

    def _baixar(self, file_id, nome):
        DOWNLOAD_DIR.mkdir(exist_ok=True)
        caminho = DOWNLOAD_DIR / nome
        request = self.service.files().get_media(fileId=file_id)
        fh = io.FileIO(caminho, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.close()
        return caminho

    def _imprimir(self, caminho_pdf):
        sumatra = self.config["sumatra_path"]
        if not Path(sumatra).exists():
            raise FileNotFoundError(f"SumatraPDF não encontrado em: {sumatra}")
        try:
            subprocess.run(
                [
                    sumatra,
                    "-print-to",
                    self.config["printer_name"],
                    "-silent",
                    str(caminho_pdf),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            raise FileNotFoundError(f"SumatraPDF não encontrado em: {sumatra}") from e
        except subprocess.CalledProcessError as e:
            detalhe = (e.stderr or e.stdout or "").strip() or str(e)
            raise RuntimeError(
                f"Falha ao enviar '{Path(caminho_pdf).name}' para a impressora "
                f"'{self.config['printer_name']}': {detalhe}"
            ) from e

    def _apagar_pdf_local(self, caminho):
        try:
            Path(caminho).unlink(missing_ok=True)
        except Exception as e:
            self.log(f"Aviso: não foi possível apagar o PDF local '{Path(caminho).name}': {e}")

    def _limpar_pdfs_locais_ja_impressos(self, nomes_impressos):
        """A pasta local é só um staging: o que já foi impresso não precisa ficar."""
        if not DOWNLOAD_DIR.exists():
            return
        for arquivo in DOWNLOAD_DIR.glob("*.pdf"):
            if arquivo.name in nomes_impressos:
                self._apagar_pdf_local(arquivo)

    def _limpar_antigos(self, arquivos, impressos_ids):
        """Move para a lixeira do Drive (e apaga localmente) etiquetas que
        JÁ FORAM IMPRESSAS por este programa e cuja última modificação no
        Drive passou do prazo configurado. Nunca mexe em arquivos ainda
        não impressos, mesmo que sejam antigos."""
        if not self.config.get("limpeza_automatica_ativa", True):
            return

        try:
            dias = int(self.config.get("dias_para_excluir", 5))
        except (TypeError, ValueError):
            dias = 5
        limite = datetime.now(timezone.utc) - timedelta(days=dias)

        for arquivo in arquivos:
            if arquivo["id"] not in impressos_ids:
                continue

            modificado_str = arquivo.get("modifiedTime")
            if not modificado_str:
                continue
            try:
                modificado = datetime.fromisoformat(modificado_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            if modificado < limite:
                self._excluir_arquivo(arquivo)

    def _excluir_arquivo(self, arquivo):
        nome = arquivo["name"]
        file_id = arquivo["id"]

        self._apagar_pdf_local(DOWNLOAD_DIR / nome)

        try:
            self.service.files().update(fileId=file_id, body={"trashed": True}).execute()
            self.log(f"Movido para a lixeira do Drive (arquivo antigo): {nome}")
        except Exception as e:
            if erro_indica_credencial_expirada(e):
                raise CredencialExpirada(str(e)) from e
            self.log(mensagem_amigavel_excecao(e, f"Erro ao mover '{nome}' para a lixeira do Drive"))

    def _notificar_falha(self, mensagem):
        agora = time.time()
        if agora - self._ultima_notificacao < INTERVALO_MIN_NOTIFICACAO:
            return
        self._ultima_notificacao = agora

        if self.config.get("notif_email_ativo"):
            self._enviar_email_falha(mensagem)
        if self.config.get("notif_whatsapp_ativo"):
            self._enviar_whatsapp_falha(mensagem)

    def _enviar_email_falha(self, mensagem):
        try:
            remetente = self.config["notif_email_remetente"]
            destino = self.config["notif_email_destino"]
            msg = MIMEText(f"Falha no programa de impressão de etiquetas:\n\n{mensagem}")
            msg["Subject"] = "⚠️ Falha - Impressão de Etiquetas"
            msg["From"] = remetente
            msg["To"] = destino

            contexto = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=contexto) as servidor:
                servidor.login(remetente, self.config["notif_email_senha_app"])
                servidor.sendmail(remetente, [destino], msg.as_string())
            self.log("Notificação de falha enviada por e-mail.")
        except Exception as e:
            self.log(mensagem_amigavel_excecao(e, "Erro ao enviar e-mail de notificação"))

    def _enviar_whatsapp_falha(self, mensagem):
        try:
            texto = urllib.parse.quote(f"⚠️ Falha no programa de etiquetas: {mensagem}")
            url = (
                "https://api.callmebot.com/whatsapp.php?"
                f"phone={self.config['notif_whatsapp_telefone']}"
                f"&text={texto}&apikey={self.config['notif_whatsapp_apikey']}"
            )
            urllib.request.urlopen(url, timeout=10)
            self.log("Notificação de falha enviada por WhatsApp.")
        except Exception as e:
            self.log(mensagem_amigavel_excecao(e, "Erro ao enviar WhatsApp de notificação"))

    def _loop(self):
        try:
            self.status("Conectando ao Google Drive...")
            self.service = self._autenticar()
        except CredencialExpirada as e:
            self._sinalizar_credencial_expirada(str(e))
            return
        except Exception as e:
            if erro_indica_credencial_expirada(e):
                self._sinalizar_credencial_expirada(str(e))
                return
            self.status("Erro de conexão")
            self.log(mensagem_amigavel_excecao(e, "Falha ao conectar no Drive"))
            self._notificar_falha(mensagem_amigavel_excecao(e, "Não foi possível conectar ao Google Drive"))
            return

        historico = carregar_historico()
        impressos_ids = {item["id"] for item in historico}
        nomes_impressos = {item.get("nome", "") for item in historico}
        self._limpar_pdfs_locais_ja_impressos(nomes_impressos)
        self.status("Monitorando")
        self.log("Conectado. Monitorando a pasta do Drive...")

        while not self._parar.is_set():
            try:
                arquivos = self._listar_pdfs()
                novos = [a for a in arquivos if a["id"] not in impressos_ids]

                for arquivo in novos:
                    if self._parar.is_set():
                        break
                    self.log(f"Novo arquivo encontrado: {arquivo['name']}")
                    caminho = None
                    try:
                        caminho = self._baixar(arquivo["id"], arquivo["name"])
                    except Exception as e:
                        if erro_indica_credencial_expirada(e):
                            raise CredencialExpirada(str(e)) from e
                        self.log(mensagem_amigavel_excecao(e, f"Erro ao baixar {arquivo['name']}"))
                        self._notificar_falha(mensagem_amigavel_excecao(e, f"Erro ao baixar '{arquivo['name']}'"))
                        continue
                    try:
                        self._imprimir(caminho)
                        agora = datetime.now().isoformat(timespec="seconds")
                        self.log(f"Impresso: {arquivo['name']}")
                        historico.append(
                            {"id": arquivo["id"], "nome": arquivo["name"], "data_hora": agora}
                        )
                        impressos_ids.add(arquivo["id"])
                        nomes_impressos.add(arquivo["name"])
                        salvar_historico(historico)
                        self.impresso(arquivo["name"])
                    except Exception as e:
                        if erro_indica_credencial_expirada(e):
                            raise CredencialExpirada(str(e)) from e
                        self.log(mensagem_amigavel_excecao(e, f"Erro ao imprimir {arquivo['name']}"))
                        self._notificar_falha(mensagem_amigavel_excecao(e, f"Erro ao imprimir '{arquivo['name']}'"))
                    finally:
                        if caminho is not None:
                            self._apagar_pdf_local(caminho)

                self._limpar_pdfs_locais_ja_impressos(nomes_impressos)
                self._limpar_antigos(arquivos, impressos_ids)

            except CredencialExpirada as e:
                self._sinalizar_credencial_expirada(str(e))
                return
            except Exception as e:
                if erro_indica_credencial_expirada(e):
                    self._sinalizar_credencial_expirada(str(e))
                    return
                self.log(mensagem_amigavel_excecao(e, "Erro ao consultar o Drive"))
                self._notificar_falha(mensagem_amigavel_excecao(e, "Erro ao consultar o Google Drive"))

            for restante in range(POLL_INTERVAL_SECONDS, 0, -1):
                if self._parar.is_set():
                    break
                self.proxima_checagem(restante)
                time.sleep(1)

        self.proxima_checagem(None)
        self.log("Monitoramento parado.")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Etiquetas")
        self.geometry("740x680")
        self.minsize(640, 560)
        self.configure(bg=COR_FUNDO)

        self.config_dados = carregar_config()
        self.eventos = queue.Queue()
        self.motor = None
        self.rodando = False
        self._credencial_expirada = False
        self._aba_ativa = "monitor"

        self._configurar_estilo()
        self._montar_interface()
        self._atualizar_contador_hoje()
        self.after(200, self._processar_eventos)
        self.after(80, lambda: aplicar_efeito_vidro(self))

    def _configurar_estilo(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background=COR_FUNDO)
        style.configure("TLabel", background=COR_FUNDO, foreground=COR_TEXTO, font=(FONTE_UI, 10))
        style.configure("Muted.TLabel", background=COR_CARD, foreground=COR_TEXTO_MUTED, font=(FONTE_UI, 9))
        style.configure("Titulo.TLabel", background=COR_FUNDO, foreground=COR_TEXTO, font=(FONTE_UI, 22))
        style.configure("Sub.TLabel", background=COR_FUNDO, foreground=COR_TEXTO_MUTED, font=(FONTE_UI, 10))
        style.configure("CardTitulo.TLabel", background=COR_CARD, foreground=COR_TEXTO, font=(FONTE_UI, 12))
        style.configure("Metrica.TLabel", background=COR_CARD, foreground=COR_TEXTO, font=(FONTE_UI, 28))
        style.configure("Hint.TLabel", background=COR_CARD, foreground=COR_TEXTO_MUTED, font=(FONTE_UI, 9))

        style.configure(
            "Glass.TEntry",
            fieldbackground=COR_CARD,
            foreground=COR_TEXTO,
            padding=8,
            bordercolor=COR_BORDA,
            lightcolor=COR_BORDA_BRILHO,
            darkcolor=COR_BORDA,
            insertcolor=COR_TEXTO,
        )
        style.map("Glass.TEntry", fieldbackground=[("focus", COR_CARD)])

        style.configure(
            "Treeview",
            background=COR_CARD,
            fieldbackground=COR_CARD,
            foreground=COR_TEXTO,
            rowheight=30,
            font=(FONTE_UI, 10),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=COR_CARD,
            foreground=COR_TEXTO_MUTED,
            font=(FONTE_UI, 9),
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", COR_CARD_BRILHO)],
            foreground=[("selected", COR_ACCENT)],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=COR_CARD_BRILHO,
            troughcolor=COR_FUNDO,
            bordercolor=COR_FUNDO,
            arrowcolor=COR_TEXTO_MUTED,
        )

    def _montar_interface(self):
        self.fundo = tk.Canvas(self, bg=COR_FUNDO, highlightthickness=0, bd=0)
        self.fundo.place(x=0, y=0, relwidth=1, relheight=1)
        self.fundo.bind("<Configure>", lambda e: _pintar_fundo_espelhado(self.fundo, e.width, e.height))

        shell = tk.Frame(self, bg=COR_FUNDO)
        shell.place(relx=0, rely=0, relwidth=1, relheight=1)

        container = tk.Frame(shell, bg=COR_FUNDO, padx=28, pady=22)
        container.pack(fill="both", expand=True)

        header = tk.Frame(container, bg=COR_FUNDO)
        header.pack(fill="x", pady=(0, 8))

        titulos = tk.Frame(header, bg=COR_FUNDO)
        titulos.pack(side="left")
        tk.Label(titulos, text="Etiquetas", bg=COR_FUNDO, fg=COR_TEXTO, font=(FONTE_UI, 22)).pack(anchor="w")
        tk.Label(titulos, text="Impressão automática", bg=COR_FUNDO, fg=COR_TEXTO_MUTED, font=(FONTE_UI, 10)).pack(anchor="w")

        status = tk.Frame(header, bg=COR_FUNDO)
        status.pack(side="right")
        self.lbl_status_dot = tk.Label(status, text="●", bg=COR_FUNDO, fg=COR_TEXTO_MUTED, font=(FONTE_UI, 9))
        self.lbl_status_dot.pack(side="left", padx=(0, 6))
        self.lbl_status = tk.Label(status, text="Parado", bg=COR_FUNDO, fg=COR_TEXTO_MUTED, font=(FONTE_UI, 10))
        self.lbl_status.pack(side="left")

        self.tabs_canvas = tk.Canvas(container, height=40, bg=COR_FUNDO, highlightthickness=0, bd=0)
        self.tabs_canvas.pack(fill="x", pady=(12, 16))
        self.tabs_canvas.bind("<Button-1>", self._clicar_aba)
        self._tab_areas = []

        self.banner_credencial = tk.Frame(container, bg=COR_ERRO_BG)
        inner_banner = tk.Frame(self.banner_credencial, bg=COR_ERRO_BG, padx=14, pady=12)
        inner_banner.pack(fill="x")
        self.lbl_banner = tk.Label(
            inner_banner,
            text=MENSAGEM_CREDENCIAL_EXPIRADA,
            bg=COR_ERRO_BG,
            fg=COR_ERRO,
            font=(FONTE_UI, 9),
            wraplength=640,
            justify="left",
            anchor="w",
        )
        self.lbl_banner.pack(fill="x")

        self.corpo = tk.Frame(container, bg=COR_FUNDO)
        self.corpo.pack(fill="both", expand=True)

        aba_monitor = tk.Frame(self.corpo, bg=COR_FUNDO)
        aba_config = tk.Frame(self.corpo, bg=COR_FUNDO)
        aba_historico = tk.Frame(self.corpo, bg=COR_FUNDO)
        self._abas = {"monitor": aba_monitor, "config": aba_config, "historico": aba_historico}

        self._montar_aba_monitor(aba_monitor)
        self._montar_aba_configuracoes(aba_config)
        self._montar_aba_historico(aba_historico)
        self._mostrar_aba("monitor")

        class _NotebookCompat:
            def __init__(self, app):
                self._app = app

            def select(self, indice):
                mapa = {0: "monitor", 1: "config", 2: "historico"}
                self._app._mostrar_aba(mapa.get(indice, "monitor"))

        self.notebook = _NotebookCompat(self)

    def _desenhar_abas(self):
        c = self.tabs_canvas
        c.delete("all")
        c.update_idletasks()
        w = max(c.winfo_width(), 200)
        itens = [("monitor", "Monitor"), ("config", "Configurações"), ("historico", "Histórico")]
        self._tab_areas = []
        x = 0
        for chave, rotulo in itens:
            largura = 118 if chave != "config" else 140
            ativo = chave == self._aba_ativa
            cor = COR_TEXTO if ativo else COR_TEXTO_MUTED
            c.create_text(x + 8, 16, text=rotulo, fill=cor, font=(FONTE_UI, 11), anchor="w")
            if ativo:
                c.create_line(x + 8, 34, x + largura - 24, 34, fill=COR_ACCENT, width=2)
            self._tab_areas.append((x, x + largura, chave))
            x += largura

    def _clicar_aba(self, event):
        for x1, x2, chave in self._tab_areas:
            if x1 <= event.x < x2:
                self._mostrar_aba(chave)
                return

    def _mostrar_aba(self, nome):
        self._aba_ativa = nome
        for chave, frame in self._abas.items():
            frame.pack_forget()
        self._abas[nome].pack(fill="both", expand=True)
        self._desenhar_abas()

    def _definir_status(self, texto, cor_bg, cor_fg):
        self.lbl_status.config(text=texto, fg=cor_fg)
        self.lbl_status_dot.config(fg=cor_fg)

    def _mostrar_banner_credencial(self, visivel=True):
        if visivel:
            self.banner_credencial.pack(fill="x", pady=(0, 12), before=self.corpo)
        else:
            self.banner_credencial.pack_forget()

    def _card(self, parent):
        card = CardEspelhado(parent)
        card.pack(fill="x", pady=(0, 14))
        return card.inner

    def _aba_rolavel(self, parent):
        canvas = tk.Canvas(parent, bg=COR_FUNDO, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        conteudo = tk.Frame(canvas, bg=COR_FUNDO)

        frame_id = canvas.create_window((0, 0), window=conteudo, anchor="nw")

        def _atualizar_regiao(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            _pintar_fundo_espelhado(canvas, canvas.winfo_width(), max(canvas.winfo_height(), 1))
            canvas.tag_lower("vidro")

        def _ajustar_largura(event):
            canvas.itemconfig(frame_id, width=event.width)
            _pintar_fundo_espelhado(canvas, event.width, max(event.height, 1))
            canvas.tag_lower("vidro")

        conteudo.bind("<Configure>", _atualizar_regiao)
        canvas.bind("<Configure>", _ajustar_largura)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _rolar(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _rolar))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        return conteudo

    def _montar_aba_monitor(self, parent):
        conteudo = self._aba_rolavel(parent)

        metricas = tk.Frame(conteudo, bg=COR_FUNDO)
        metricas.pack(fill="x", pady=(4, 0))

        card_hoje = CardEspelhado(metricas)
        card_hoje.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=(0, 14))
        ttk.Label(card_hoje.inner, text="Hoje", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        self.lbl_contador_hoje = ttk.Label(card_hoje.inner, text="0", style="Metrica.TLabel")
        self.lbl_contador_hoje.pack(anchor="w", pady=(0, 8))

        card_proxima = CardEspelhado(metricas)
        card_proxima.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 14))
        ttk.Label(card_proxima.inner, text="Próxima verificação", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        self.lbl_proxima_checagem = ttk.Label(card_proxima.inner, text="—", style="Metrica.TLabel")
        self.lbl_proxima_checagem.pack(anchor="w", pady=(0, 8))

        botoes = tk.Frame(conteudo, bg=COR_FUNDO)
        botoes.pack(fill="x", pady=(0, 14))
        self.btn_iniciar = BotaoArredondado(botoes, "Iniciar", self._iniciar, primario=True)
        self.btn_iniciar.pack(side="left")
        self.btn_parar = BotaoArredondado(botoes, "Parar", self._parar, primario=False)
        self.btn_parar.pack(side="left", padx=10)
        self.btn_parar.config_estado("disabled")

        card_log = CardEspelhado(conteudo)
        card_log.pack(fill="both", expand=True)
        ttk.Label(card_log.inner, text="Atividade", style="CardTitulo.TLabel").pack(anchor="w", pady=(2, 10))

        self.log_text = tk.Text(
            card_log.inner, state="disabled", wrap="word", height=14, bd=0,
            bg=COR_CARD, fg=COR_TEXTO_MUTED, font=(FONTE_UI, 10), padx=4, pady=4,
            insertbackground=COR_TEXTO, highlightthickness=0,
        )
        self.log_text.pack(fill="both", expand=True)

    def _montar_aba_configuracoes(self, parent):
        conteudo = self._aba_rolavel(parent)

        card_config = self._card(conteudo)
        ttk.Label(card_config, text=f"{ICONE_CONEXAO}  Conexão", style="CardTitulo.TLabel").pack(anchor="w", pady=(0, 10))

        self.var_folder = tk.StringVar(value=self.config_dados["folder_id"])
        self.var_printer = tk.StringVar(value=self.config_dados["printer_name"])
        self.var_sumatra = tk.StringVar(value=self.config_dados["sumatra_path"])

        self._campo(card_config, "ID da pasta no Drive", self.var_folder)
        self._campo(card_config, "Nome da impressora térmica", self.var_printer)
        self._campo(card_config, "Caminho do SumatraPDF.exe", self.var_sumatra)

        ttk.Label(
            card_config,
            text="Etiqueta 10×15 cm: use esse tamanho como padrão no Windows.",
            style="Hint.TLabel", justify="left",
        ).pack(anchor="w", pady=(6, 0))

        self.var_iniciar_windows = tk.BooleanVar(value=iniciar_com_windows_ativo())
        Interruptor(card_config, f"{ICONE_WINDOWS}  Iniciar com o Windows", self.var_iniciar_windows).pack(anchor="w", pady=(14, 4))

        card_token = self._card(conteudo)
        ttk.Label(card_token, text=f"{ICONE_TOKEN}  Google Drive", style="CardTitulo.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(
            card_token,
            text="Se a credencial expirar, exclua o token e reinicie o aplicativo.",
            style="Hint.TLabel", justify="left",
        ).pack(anchor="w", pady=(0, 10))
        self.btn_excluir_token = BotaoArredondado(
            card_token, "Excluir token.json", self._excluir_token, primario=False, fundo=COR_CARD,
        )
        self.btn_excluir_token.pack(anchor="w")

        card_notif = self._card(conteudo)
        ttk.Label(card_notif, text=f"{ICONE_ALERTA}  Alertas", style="CardTitulo.TLabel").pack(anchor="w", pady=(0, 10))

        self.var_notif_email = tk.BooleanVar(value=self.config_dados["notif_email_ativo"])
        Interruptor(card_notif, "E-mail (Gmail)", self.var_notif_email).pack(anchor="w", pady=(0, 8))

        self.var_email_remetente = tk.StringVar(value=self.config_dados["notif_email_remetente"])
        self.var_email_senha = tk.StringVar(value=self.config_dados["notif_email_senha_app"])
        self.var_email_destino = tk.StringVar(value=self.config_dados["notif_email_destino"])
        self._campo(card_notif, "Gmail remetente", self.var_email_remetente)
        self._campo(card_notif, "Senha de app", self.var_email_senha, senha=True)
        self._campo(card_notif, "E-mail de destino", self.var_email_destino)

        ttk.Label(
            card_notif,
            text="Senha de app: myaccount.google.com/apppasswords",
            style="Hint.TLabel", justify="left",
        ).pack(anchor="w", pady=(4, 12))

        self.var_notif_whatsapp = tk.BooleanVar(value=self.config_dados["notif_whatsapp_ativo"])
        Interruptor(card_notif, "WhatsApp (CallMeBot)", self.var_notif_whatsapp).pack(anchor="w", pady=(0, 8))

        self.var_whatsapp_telefone = tk.StringVar(value=self.config_dados["notif_whatsapp_telefone"])
        self.var_whatsapp_apikey = tk.StringVar(value=self.config_dados["notif_whatsapp_apikey"])
        self._campo(card_notif, "Telefone (ex: 5532999999999)", self.var_whatsapp_telefone)
        self._campo(card_notif, "Apikey do CallMeBot", self.var_whatsapp_apikey)

        ttk.Label(
            card_notif,
            text="Ative em callmebot.com/whatsapp e copie a apikey recebida.",
            style="Hint.TLabel", justify="left",
        ).pack(anchor="w", pady=(4, 0))

        card_limpeza = self._card(conteudo)
        ttk.Label(card_limpeza, text=f"{ICONE_LIMPEZA}  Limpeza", style="CardTitulo.TLabel").pack(anchor="w", pady=(0, 10))

        self.var_limpeza_ativa = tk.BooleanVar(value=self.config_dados.get("limpeza_automatica_ativa", True))
        Interruptor(card_limpeza, "Excluir etiquetas antigas já impressas", self.var_limpeza_ativa).pack(
            anchor="w", pady=(0, 8)
        )

        self.var_dias_exclusao = tk.StringVar(value=str(self.config_dados.get("dias_para_excluir", 5)))
        self._campo(card_limpeza, "Excluir após quantos dias sem modificação", self.var_dias_exclusao)

        ttk.Label(
            card_limpeza,
            text="No Drive vai para a lixeira. O PDF local some após imprimir.",
            style="Hint.TLabel", justify="left",
        ).pack(anchor="w", pady=(6, 0))

        botoes = tk.Frame(conteudo, bg=COR_FUNDO)
        botoes.pack(fill="x", pady=(4, 20))
        self.btn_salvar = BotaoArredondado(botoes, "Salvar", self._salvar, primario=True)
        self.btn_salvar.pack(side="left")

    def _montar_aba_historico(self, parent):
        conteudo = self._aba_rolavel(parent)
        card = CardEspelhado(conteudo)
        card.pack(fill="both", expand=True, pady=(4, 0))
        inner = card.inner

        topo = tk.Frame(inner, bg=COR_CARD)
        topo.pack(fill="x", pady=(0, 10))
        ttk.Label(topo, text="Impressões", style="CardTitulo.TLabel").pack(side="left")
        self.btn_atualizar_hist = BotaoArredondado(
            topo, "Atualizar", self._recarregar_historico, primario=False, fundo=COR_CARD,
        )
        self.btn_atualizar_hist.pack(side="right")

        colunas = ("data_hora", "nome")
        self.tree_historico = ttk.Treeview(inner, columns=colunas, show="headings", height=14)
        self.tree_historico.heading("data_hora", text="Quando")
        self.tree_historico.heading("nome", text="Arquivo")
        self.tree_historico.column("data_hora", width=160, anchor="w")
        self.tree_historico.column("nome", width=340, anchor="w")
        self.tree_historico.pack(fill="both", expand=True, side="left")

        scroll = ttk.Scrollbar(inner, orient="vertical", command=self.tree_historico.yview)
        self.tree_historico.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        self._recarregar_historico()

    def _campo(self, parent, label, var, senha=False):
        frame = tk.Frame(parent, bg=COR_CARD)
        frame.pack(fill="x", pady=5)
        tk.Label(frame, text=label, bg=COR_CARD, fg=COR_TEXTO_MUTED, font=(FONTE_UI, 9)).pack(anchor="w")
        ttk.Entry(frame, textvariable=var, show="*" if senha else "", style="Glass.TEntry").pack(fill="x", pady=(4, 0))

    def _salvar(self):
        try:
            dias_exclusao = int(self.var_dias_exclusao.get().strip())
            if dias_exclusao < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Configuração inválida",
                "O número de dias para exclusão deve ser um número inteiro maior que zero.",
            )
            return

        self.config_dados = {
            "folder_id": self.var_folder.get().strip(),
            "printer_name": self.var_printer.get().strip(),
            "sumatra_path": self.var_sumatra.get().strip(),
            "notif_email_ativo": self.var_notif_email.get(),
            "notif_email_remetente": self.var_email_remetente.get().strip(),
            "notif_email_senha_app": self.var_email_senha.get().strip(),
            "notif_email_destino": self.var_email_destino.get().strip(),
            "notif_whatsapp_ativo": self.var_notif_whatsapp.get(),
            "notif_whatsapp_telefone": self.var_whatsapp_telefone.get().strip(),
            "notif_whatsapp_apikey": self.var_whatsapp_apikey.get().strip(),
            "limpeza_automatica_ativa": self.var_limpeza_ativa.get(),
            "dias_para_excluir": dias_exclusao,
        }
        salvar_config(self.config_dados)

        try:
            if self.var_iniciar_windows.get():
                ativar_inicio_com_windows()
            else:
                desativar_inicio_com_windows()
        except Exception as e:
            messagebox.showwarning(
                "Início com o Windows",
                f"Configuração salva, mas não foi possível ajustar o início "
                f"automático com o Windows:\n{e}\n\n"
                f"(Verifique se o pywin32 está instalado: pip install pywin32)",
            )
            return

        messagebox.showinfo("Configuração", "Configuração salva com sucesso.")

    def _excluir_token(self):
        if self.rodando:
            messagebox.showwarning(
                "Monitoramento ativo",
                "Pare o monitoramento antes de excluir o token.json.",
            )
            return
        if not TOKEN_PATH.exists():
            messagebox.showinfo("Token", "Não há token.json para excluir.")
            return
        confirmar = messagebox.askyesno(
            "Excluir token.json",
            "Isso desconecta o Google Drive neste computador.\n\n"
            "Depois de excluir, feche e abra o aplicativo de novo para autorizar.",
        )
        if not confirmar:
            return
        try:
            TOKEN_PATH.unlink()
        except Exception as e:
            messagebox.showerror("Token", f"Não foi possível excluir o token.json:\n{e}")
            return
        self._adicionar_log("token.json excluído. Reinicie o aplicativo para autorizar de novo.")
        fechar = messagebox.askyesno(
            "Token excluído",
            "token.json foi excluído.\n\nDeseja fechar o aplicativo agora para reiniciar?",
        )
        if fechar:
            self.destroy()

    def _iniciar(self):
        if self._credencial_expirada and TOKEN_PATH.exists():
            messagebox.showwarning(
                "Credencial expirada",
                MENSAGEM_CREDENCIAL_EXPIRADA,
            )
            self._mostrar_aba("config")
            return
        if not self.config_dados["folder_id"] or not self.config_dados["printer_name"]:
            messagebox.showwarning(
                "Configuração incompleta",
                "Preencha e salve o ID da pasta e o nome da impressora antes de iniciar.",
            )
            return

        self._definir_status("Iniciando...", COR_ALERTA_BG, COR_ALERTA)
        self.motor = MotorImpressao(self.config_dados, self.eventos)
        self.motor.iniciar()
        self.rodando = True
        self.btn_iniciar.config_estado("disabled")
        self.btn_parar.config_estado("normal")
        self.btn_salvar.config_estado("disabled")

    def _parar(self):
        if self.motor:
            self.motor.parar()
        self.rodando = False
        self.btn_iniciar.config_estado("normal")
        self.btn_parar.config_estado("disabled")
        self.btn_salvar.config_estado("normal")
        self.lbl_proxima_checagem.config(text="—")
        if not self._credencial_expirada:
            self._definir_status("Parado", COR_PARADO_BG, COR_TEXTO_MUTED)

    def _adicionar_log(self, msg):
        hora = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{hora}    {msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _atualizar_contador_hoje(self):
        historico = carregar_historico()
        hoje = date.today().isoformat()
        total_hoje = sum(1 for item in historico if item["data_hora"].startswith(hoje))
        self.lbl_contador_hoje.config(text=str(total_hoje))

    def _recarregar_historico(self):
        for item in self.tree_historico.get_children():
            self.tree_historico.delete(item)
        historico = carregar_historico()
        for item in reversed(historico):
            try:
                dt = datetime.fromisoformat(item["data_hora"])
                texto_data = dt.strftime("%d/%m/%Y %H:%M:%S")
            except ValueError:
                texto_data = item["data_hora"]
            self.tree_historico.insert("", "end", values=(texto_data, item["nome"]))

    def _tratar_credencial_expirada(self):
        self._credencial_expirada = True
        self._parar()
        self._definir_status("Credencial expirada", COR_ERRO_BG, COR_ERRO)
        self._mostrar_banner_credencial(True)
        self._mostrar_aba("config")
        self.btn_iniciar.config_estado("disabled")

    def _processar_eventos(self):
        try:
            while True:
                tipo, valor = self.eventos.get_nowait()
                if tipo == "log":
                    self._adicionar_log(valor)
                elif tipo == "status":
                    mapa = {
                        "Monitorando": (COR_SUCESSO_BG, COR_SUCESSO),
                        "Parado": (COR_PARADO_BG, COR_TEXTO_MUTED),
                        "Erro de conexão": (COR_ERRO_BG, COR_ERRO),
                        "Credencial expirada": (COR_ERRO_BG, COR_ERRO),
                    }
                    cor_bg, cor_fg = mapa.get(valor, (COR_ALERTA_BG, COR_ALERTA))
                    self._definir_status(valor, cor_bg, cor_fg)
                elif tipo == "impresso":
                    self._atualizar_contador_hoje()
                    self._recarregar_historico()
                elif tipo == "proxima_checagem":
                    if valor is None:
                        self.lbl_proxima_checagem.config(text="—")
                    else:
                        self.lbl_proxima_checagem.config(text=f"{valor}s")
                elif tipo == "credencial_expirada":
                    self._tratar_credencial_expirada()
        except queue.Empty:
            pass
        self.after(200, self._processar_eventos)


if __name__ == "__main__":
    trava = obter_trava_instancia()
    if trava is None:
        raiz_temp = tk.Tk()
        raiz_temp.withdraw()
        messagebox.showwarning(
            "Já está em execução",
            "O programa de impressão de etiquetas já está aberto.\n\n"
            "Verifique a barra de tarefas — não é possível abrir duas\n"
            "instâncias ao mesmo tempo (evita imprimir em duplicidade).",
        )
        raiz_temp.destroy()
        sys.exit(0)

    try:
        App().mainloop()
    finally:
        trava.close()
