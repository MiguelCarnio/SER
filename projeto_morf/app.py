import sys
from pathlib import Path


try:
    from .interface import iniciar
except ImportError:
    raiz_projeto = str(Path(__file__).resolve().parent.parent)
    if raiz_projeto not in sys.path:
        sys.path.insert(0, raiz_projeto)
    from projeto_morf.interface import iniciar


def main():
    iniciar()


if __name__ == "__main__":
    main()