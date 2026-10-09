"""Interface Tkinter do guarda-roupa, câmera e recomendações de combinação."""

import threading
import tkinter as tk
from tempfile import NamedTemporaryFile
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageGrab, ImageOps, ImageTk

from DataBase import index_db
from projeto_morf import servicos

try:
    import cv2
except ImportError:
    cv2 = None


# Mapeia extensões aceitas para os tipos enviados ao analisador de imagens.
TIPOS_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


class GuardaRoupaApp:
    """Coordena widgets, câmera, operações do banco e chamadas aos serviços."""

    def __init__(self, root):
        """Prepara o estado da janela, monta os controles e liga a webcam."""
        self.root = root
        self.root.title("Guarda-Roupa IA")
        self.root.geometry("1040x700")
        self.root.minsize(820, 600)
        self.root.configure(bg="#f6f7f4")

        self.imagem_selecionada = None
        self.imagem_temporaria = None
        self.roupa_atual_id = None
        self.roupas_por_rotulo = {}
        self.foto_preview = None
        self.foto_combinacao = None
        self.camera = None
        self.quadro_atual = None
        self.camera_after_id = None
        self.analisando = False

        self._configurar_estilos()
        index_db.inicializar_banco()
        self._montar_interface()
        self._atualizar_lista_roupas()
        self.root.protocol("WM_DELETE_WINDOW", self._fechar)
        self._conectar_camera()

    def _configurar_estilos(self):
        """Define a paleta e os estilos compartilhados pelos widgets ttk."""
        estilo = ttk.Style(self.root)
        estilo.theme_use("clam")
        estilo.configure("TFrame", background="#f6f7f4")
        estilo.configure("TLabel", background="#f6f7f4", foreground="#252a27", font=("TkDefaultFont", 10))
        estilo.configure("Title.TLabel", font=("TkDefaultFont", 21, "bold"), foreground="#252a27")
        estilo.configure("Muted.TLabel", foreground="#737a75")
        estilo.configure("Section.TLabel", font=("TkDefaultFont", 12, "bold"), foreground="#252a27")
        estilo.configure("Accent.TButton", background="#536c5a", foreground="#ffffff", font=("TkDefaultFont", 10, "bold"), padding=(14, 10), borderwidth=0)
        estilo.map("Accent.TButton", background=[("active", "#405747"), ("disabled", "#bbc2bc")])
        estilo.configure("TButton", background="#e5e8e3", foreground="#252a27", padding=(10, 8), borderwidth=0)
        estilo.map("TButton", background=[("active", "#d9ded8")])
        estilo.configure("TCombobox", padding=7, fieldbackground="#ffffff")

    def _montar_interface(self):
        """Constrói a área da câmera e os controles de resultado e combinação."""
        principal = ttk.Frame(self.root, padding=(24, 20, 24, 22))
        principal.pack(fill="both", expand=True)

        topo = ttk.Frame(principal)
        topo.pack(fill="x", pady=(0, 18))
        ttk.Label(topo, text="Meu guarda-roupa", style="Title.TLabel").pack(anchor="w")
        ttk.Label(topo, text="Mostre uma peça à câmera para analisar e combinar.", style="Muted.TLabel").pack(anchor="w", pady=(3, 0))

        conteudo = ttk.Frame(principal)
        conteudo.pack(fill="both", expand=True)
        conteudo.columnconfigure(0, weight=6, minsize=380)
        conteudo.columnconfigure(1, weight=4, minsize=300)
        conteudo.rowconfigure(0, weight=1)

        esquerda = ttk.Frame(conteudo)
        esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        direita = ttk.Frame(conteudo)
        direita.grid(row=0, column=1, sticky="nsew", padx=(18, 0))

        ttk.Label(esquerda, text="Câmera ao vivo", style="Section.TLabel").pack(anchor="w", pady=(0, 9))
        self.preview = tk.Label(esquerda, text="Conectando à câmera...", bg="#252a27", fg="#f6f7f4", font=("TkDefaultFont", 11), justify="center")
        self.preview.pack(fill="both", expand=True)

        self.botao_analisar = ttk.Button(esquerda, text="Tirar foto e analisar", style="Accent.TButton", command=self._analisar)
        self.botao_analisar.pack(fill="x", pady=(10, 0))

        ttk.Label(direita, text="Resultado", style="Section.TLabel").pack(anchor="w")
        self.status = ttk.Label(direita, text="A câmera será iniciada automaticamente.", style="Muted.TLabel", wraplength=330)
        self.status.pack(anchor="w", pady=(6, 12))

        self.resultado = tk.Text(direita, height=9, wrap="word", bg="#ffffff", fg="#303632", relief="flat", padx=10, pady=9, font=("TkDefaultFont", 10), state="disabled")
        self.resultado.pack(fill="both", expand=True)

        separador = ttk.Separator(direita)
        separador.pack(fill="x", pady=13)
        ttk.Label(direita, text="Combinar com outra peça", style="Section.TLabel").pack(anchor="w")
        ttk.Label(direita, text="Escolha a peça e o clima para montar o look.", style="Muted.TLabel").pack(anchor="w", pady=(4, 8))

        ttk.Label(direita, text="Clima", style="Muted.TLabel").pack(anchor="w", pady=(4, 3))
        self.seletor_clima = ttk.Combobox(
            direita,
            state="readonly",
            values=("Calor", "Ameno", "Frio"),
        )
        self.seletor_clima.pack(fill="x", pady=(0, 9))

        linha_combo = ttk.Frame(direita)
        linha_combo.pack(fill="x")
        self.seletor_roupas = ttk.Combobox(linha_combo, state="readonly")
        self.seletor_roupas.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.seletor_roupas.bind("<<ComboboxSelected>>", self._selecionar_roupa)
        self.botao_combinar = ttk.Button(linha_combo, text="Comparar", style="Accent.TButton", command=self._combinar)
        self.botao_combinar.pack(side="right")

        self.foto_combinacao_label = tk.Label(direita, bg="#f6f7f4", height=4)
        self.foto_combinacao_label.pack(fill="x", pady=(10, 0))
        self._definir_resultado("Os detalhes da peça aparecerão aqui.")

        self.preview.bind("<Configure>", self._redimensionar_preview)
        self.root.bind_all("<Control-v>", self._colar_imagem)

    def _usar_imagem(self, caminho, mensagem, temporaria=False):
        """Usa uma imagem colada e libera qualquer arquivo temporário anterior."""
        if self.imagem_temporaria and self.imagem_temporaria != caminho:
            self.imagem_temporaria.unlink(missing_ok=True)
        self.imagem_selecionada = caminho
        self.imagem_temporaria = caminho if temporaria else None
        self._definir_status(mensagem)
        self._atualizar_rotulo_acao()

    def _colar_imagem(self, _evento=None):
        """Carrega uma imagem do clipboard ao pressionar Ctrl+V."""
        try:
            conteudo = ImageGrab.grabclipboard()
        except (OSError, NotImplementedError):
            conteudo = None

        if isinstance(conteudo, Image.Image):
            formatos = {
                "JPEG": (".jpg", "JPEG"),
                "JPG": (".jpg", "JPEG"),
                "PNG": (".png", "PNG"),
                "WEBP": (".webp", "WEBP"),
                "GIF": (".gif", "GIF"),
                "BMP": (".bmp", "BMP"),
            }
            extensao, formato = formatos.get((conteudo.format or "PNG").upper(), (".png", "PNG"))
            with NamedTemporaryFile(suffix=extensao, delete=False) as arquivo:
                caminho = Path(arquivo.name)
            imagem = conteudo.convert("RGB") if formato == "JPEG" else conteudo
            imagem.save(caminho, format=formato)
            self._usar_imagem(caminho, "Imagem colada. Pronta para análise.", temporaria=True)
            return "break"

        if isinstance(conteudo, (list, tuple)):
            for item in conteudo:
                caminho = Path(str(item)).expanduser()
                if caminho.is_file() and caminho.suffix.lower() in TIPOS_MIME:
                    self._usar_imagem(caminho, "Imagem colada. Pronta para análise.")
                    return "break"

        try:
            texto = self.root.clipboard_get().strip()
        except tk.TclError:
            texto = ""
        caminho = Path(texto).expanduser() if texto else None
        if caminho and caminho.is_file() and caminho.suffix.lower() in TIPOS_MIME:
            self._usar_imagem(caminho, "Imagem carregada do clipboard. Pronta para análise.")
            return "break"

        self._definir_status(
            "Não encontrei uma imagem no clipboard. No Linux, instale wl-clipboard ou xclip para colar imagens.",
            erro=True,
        )
        return "break"

    def _redimensionar_preview(self, _evento=None):
        """Redesenha o quadro da câmera quando o espaço de vídeo muda de tamanho."""
        if self.quadro_atual is None:
            return
        self._mostrar_quadro(self.quadro_atual)

    def _conectar_camera(self):
        """Abre a webcam principal e mostra uma mensagem caso não esteja acessível."""
        if cv2 is None:
            self._definir_status("OpenCV não está instalado. Instale as dependências para usar a câmera.", erro=True)
            self.preview.configure(text="Câmera indisponível", image="")
            self._atualizar_rotulo_acao()
            return

        if self.camera_after_id is not None:
            self.root.after_cancel(self.camera_after_id)
            self.camera_after_id = None
        if self.camera is not None:
            self.camera.release()
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            camera.release()
            self.camera = None
            self.quadro_atual = None
            self.preview.configure(text="Câmera não encontrada\nConecte uma câmera e tente novamente", image="")
            self._definir_status("Não foi possível acessar a câmera.", erro=True)
            self._atualizar_rotulo_acao()
            return

        self.camera = camera
        self._definir_status("Câmera conectada.")
        self._atualizar_rotulo_acao()
        self._atualizar_camera()

    def _atualizar_camera(self):
        """Lê e agenda o próximo quadro para manter o preview ao vivo."""
        if self.camera is None:
            return
        sucesso, quadro = self.camera.read()
        if sucesso:
            primeiro_quadro = self.quadro_atual is None
            self.quadro_atual = quadro
            self._mostrar_quadro(quadro)
            if primeiro_quadro:
                self._atualizar_rotulo_acao()
        elif self.quadro_atual is None:
            self.preview.configure(text="Aguardando imagem da câmera...", image="")
        self.camera_after_id = self.root.after(33, self._atualizar_camera)

    def _mostrar_quadro(self, quadro):
        """Espelha e ajusta um quadro da webcam ao tamanho do widget de preview."""
        largura = max(320, self.preview.winfo_width() - 8)
        altura = max(260, self.preview.winfo_height() - 8)
        espelhado = cv2.flip(quadro, 1)
        imagem = ImageOps.contain(
            Image.fromarray(cv2.cvtColor(espelhado, cv2.COLOR_BGR2RGB)),
            (largura, altura),
        )
        self.foto_preview = ImageTk.PhotoImage(imagem)
        self.preview.configure(image=self.foto_preview, text="")

    def _atualizar_rotulo_acao(self):
        """Ajusta o texto e disponibilidade do botão conforme o estado da câmera."""
        if self.analisando:
            self.botao_analisar.configure(text="Analisando...")
            self.botao_analisar.state(["disabled"])
        elif self.imagem_selecionada:
            self.botao_analisar.configure(text="Analisar imagem colada")
            self.botao_analisar.state(["!disabled"])
        elif self.quadro_atual is not None:
            self.botao_analisar.configure(text="Tirar foto e analisar")
            self.botao_analisar.state(["!disabled"])
        elif cv2 is not None:
            self.botao_analisar.configure(text="Tentar conectar à câmera")
            self.botao_analisar.state(["!disabled"])
        else:
            self.botao_analisar.configure(text="Câmera indisponível")
            self.botao_analisar.state(["disabled"])

    def _executar_em_segundo_plano(self, tarefa, sucesso):
        """Executa uma operação lenta fora do loop gráfico e devolve o resultado à UI."""
        def executar():
            """Roda a tarefa e agenda seu resultado ou erro no loop Tkinter."""
            try:
                resultado = tarefa()
            except Exception as exc:
                self.root.after(0, lambda erro=exc: self._tarefa_falhou(erro))
            else:
                self.root.after(0, lambda: sucesso(resultado))

        threading.Thread(target=executar, daemon=True).start()

    def _tarefa_falhou(self, erro):
        """Mostra uma falha de serviço e restaura os controles da janela."""
        self.analisando = False
        self._definir_status(str(erro), erro=True)
        self._habilitar_botoes()

    def _analisar(self):
        """Captura o quadro atual ou usa a imagem colada e inicia a análise."""
        if self.imagem_selecionada:
            caminho = self.imagem_selecionada
            content_type = TIPOS_MIME.get(caminho.suffix.lower())
            try:
                conteudo = caminho.read_bytes()
            except OSError as exc:
                self._definir_status(f"Não foi possível ler a imagem: {exc}", erro=True)
                return
            if self.imagem_temporaria == caminho:
                caminho.unlink(missing_ok=True)
            filename = caminho.name
            self.imagem_selecionada = None
            self.imagem_temporaria = None
        else:
            if self.quadro_atual is None:
                self._conectar_camera()
                if self.quadro_atual is None:
                    return
            sucesso, imagem_codificada = cv2.imencode(".jpg", self.quadro_atual)
            if not sucesso:
                self._definir_status("Não foi possível capturar a imagem da câmera.", erro=True)
                return
            conteudo = imagem_codificada.tobytes()
            content_type = "image/jpeg"
            filename = "foto-camera.jpg"

        self.analisando = True
        self._definir_status("Analisando a foto e salvando a peça...")
        self._definir_resultado("A IA está identificando a roupa. Isso pode levar alguns segundos.")
        self.botao_combinar.state(["disabled"])
        self._atualizar_rotulo_acao()
        self._executar_em_segundo_plano(
            lambda: servicos.analisar_imagem(conteudo, content_type, filename),
            self._analise_concluida,
        )

    def _analise_concluida(self, dados):
        """Apresenta os atributos reconhecidos e seleciona a peça recém-salva."""
        self.analisando = False
        self._habilitar_botoes()
        roupa = dados.get("roupa_adicionada")
        if not dados.get("eh_roupa") or not dados.get("salva_no_banco") or not roupa:
            mensagem = dados.get("mensagem", "A imagem não foi identificada como roupa.")
            self._definir_status(mensagem, erro=True)
            self._definir_resultado(mensagem)
            return

        self.roupa_atual_id = roupa["id"]
        self._atualizar_lista_roupas(selecionar_id=self.roupa_atual_id)
        linhas = [
            "Roupa reconhecida e adicionada ao guarda-roupa.",
            f"Nome: {roupa.get('nome')}",
            f"Tipo: {roupa.get('tipo')}",
            f"Cor: {roupa.get('cor')}",
            f"Estilo: {roupa.get('estilo')}",
        ]
        linhas.extend(["", "Escolha o clima e toque em Comparar para ver peças complementares."])
        self._definir_status("Análise concluída. Peça salva no guarda-roupa.")
        self._definir_resultado("\n".join(linhas))

    def _atualizar_lista_roupas(self, selecionar_id=None):
        """Atualiza o seletor de peças preservando, quando possível, a seleção."""
        roupas = index_db.listar_roupas()
        self.roupas_por_rotulo = {
            f"{roupa['id']}  ·  {roupa['nome']}": roupa for roupa in roupas
        }
        rotulos = list(self.roupas_por_rotulo)
        self.seletor_roupas.configure(values=rotulos)
        if selecionar_id is not None:
            for rotulo, roupa in self.roupas_por_rotulo.items():
                if roupa.get("id") == selecionar_id:
                    self.seletor_roupas.set(rotulo)
                    break
        elif rotulos and not self.seletor_roupas.get():
            self.seletor_roupas.set(rotulos[0])
        self.botao_combinar.state(["!disabled"] if roupas else ["disabled"])

    def _selecionar_roupa(self, _evento=None):
        """Sincroniza o ID interno com a opção atualmente escolhida no seletor."""
        self.roupa_atual_id = self.roupas_por_rotulo.get(self.seletor_roupas.get(), {}).get("id")

    def _combinar(self):
        """Exige clima e peça de referência antes de iniciar a recomendação."""
        self._selecionar_roupa()
        if self.roupa_atual_id is None:
            messagebox.showinfo("Escolha uma peça", "Selecione uma roupa do guarda-roupa para comparar.")
            return
        clima = self.seletor_clima.get().lower()
        if not clima:
            self._definir_status("Escolha o clima para encontrar uma combinação adequada.", erro=True)
            self.seletor_clima.focus_set()
            return
        roupa_id = self.roupa_atual_id
        self._definir_status(f"Procurando peças complementares para clima {clima}...")
        self._definir_resultado("A IA está procurando uma peça de outra categoria adequada ao clima escolhido.")
        self.botao_combinar.state(["disabled"])
        self._executar_em_segundo_plano(
            lambda: servicos.combinar_roupa(roupa_id, clima),
            self._combinacao_concluida,
        )

    def _combinacao_concluida(self, dados):
        """Exibe a peça recomendada ou a mensagem de ausência de combinação."""
        self._habilitar_botoes()
        combinacao = dados.get("melhor_combinacao")
        if not combinacao:
            mensagem = dados.get("mensagem", "Cadastre outra roupa para comparar.")
            self._definir_status(mensagem)
            self._definir_resultado(mensagem)
            self._limpar_foto_combinacao()
            return

        roupa = combinacao["roupa"]
        linhas = [
            f"A IA recomenda: {roupa.get('nome')}",
            f"Compatibilidade: {combinacao.get('compatibilidade')}%",
            f"Tipo: {roupa.get('tipo')} | Cor: {roupa.get('cor')} | Estilo: {roupa.get('estilo')}",
            f"Motivo: {combinacao.get('motivo')}",
        ]
        caminho_imagem = servicos.caminho_imagem_roupa(roupa)
        if caminho_imagem:
            self._mostrar_foto_combinacao(caminho_imagem)
        else:
            self._limpar_foto_combinacao()
        self._definir_status("Combinação visual encontrada pela IA.")
        self._definir_resultado("\n".join(linhas))

    def _mostrar_foto_combinacao(self, caminho):
        """Carrega a miniatura da peça recomendada na área de resultado."""
        imagem = ImageOps.contain(Image.open(caminho).convert("RGB"), (480, 150))
        self.foto_combinacao = ImageTk.PhotoImage(imagem)
        self.foto_combinacao_label.configure(image=self.foto_combinacao, text="")

    def _limpar_foto_combinacao(self):
        """Remove a miniatura anterior quando não há uma nova recomendação."""
        self.foto_combinacao = None
        self.foto_combinacao_label.configure(image="")

    def _definir_status(self, texto, erro=False):
        """Atualiza a mensagem curta de estado e destaca falhas em vermelho."""
        self.status.configure(text=texto, foreground="#a43c35" if erro else "#68746d")

    def _definir_resultado(self, texto):
        """Substitui o texto de resultado e mantém o campo somente para leitura."""
        self.resultado.configure(state="normal")
        self.resultado.delete("1.0", "end")
        self.resultado.insert("1.0", texto)
        self.resultado.configure(state="disabled")

    def _habilitar_botoes(self):
        """Restaura o botão principal e recarrega as roupas disponíveis."""
        self._atualizar_rotulo_acao()
        self._atualizar_lista_roupas()

    def _fechar(self):
        """Cancela o ciclo da webcam, libera recursos e fecha a janela."""
        if self.camera_after_id is not None:
            self.root.after_cancel(self.camera_after_id)
        if self.camera is not None:
            self.camera.release()
        if self.imagem_temporaria is not None:
            self.imagem_temporaria.unlink(missing_ok=True)
        self.root.destroy()


def iniciar():
    """Cria a janela raiz e inicia o loop de eventos do Tkinter."""
    root = tk.Tk()
    GuardaRoupaApp(root)
    root.mainloop()