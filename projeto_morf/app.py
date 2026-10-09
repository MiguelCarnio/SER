"""Ponto de entrada do aplicativo desktop Guarda-Roupa IA."""

import sys
from pathlib import Path


try:
    from .interface import iniciar
except ImportError:
    # Ao executar este arquivo diretamente, adiciona a raiz para achar o pacote.
    raiz_projeto = str(Path(__file__).resolve().parent.parent)
    if raiz_projeto not in sys.path:
        sys.path.insert(0, raiz_projeto)
    from projeto_morf.interface import iniciar


def main():
    """Inicia a interface gráfica do aplicativo."""
    iniciar()


if __name__ == "__main__":
    # Permite iniciar pelo botão Run do editor ou com `python app.py`.
    main()