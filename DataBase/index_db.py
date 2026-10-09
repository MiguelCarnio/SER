"""Persistência SQLite e migração dos registros antigos do guarda-roupa."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


# O banco fica junto deste módulo para funcionar de qualquer diretório de execução.
DB_PATH = Path(__file__).with_name("clothes.db")
# Este JSON é mantido como fonte de migração para instalações antigas.
LEGACY_JSON_PATH = Path(__file__).with_name("clothes.json")
# A ordem é compartilhada pela montagem dos comandos SQL e dos valores inseridos.
COLUNAS_ROUPA = (
    "nome",
    "cor",
    "estilo",
    "corte",
    "temperatura",
    "tipo",
    "material",
    "tamanho",
    "genero",
    "estacao",
    "imagem",
    "observacoes",
)


# Conjuntos aceitos pela validação antes de gravar dados no SQLite.
VALID_TEMPERATURA = {"frio", "calor", "ambos"}
VALID_TIPO = {
    "camiseta",
    "casaco",
    "vestido",
    "jaqueta",
    "calca",
    "saia",
    "blusa",
    "sueter",
    "short",
    "calcado",
    "acessorio",
    "roupa",
}
VALID_ESTILO = {"casual", "formal", "esportivo"}
VALID_CORTE = {"regular", "solto", "ajustado", "acinturado"}
VALID_TAMANHO = {"PP", "P", "M", "G", "GG"}
VALID_GENERO = {"masculino", "feminino", "unissex"}


def _normalizar_registro(roupa: Dict[str, Any]) -> Dict[str, str]:
    """Completa campos opcionais e padroniza valores textuais do registro."""
    return {
        "nome": str(roupa.get("nome") or "Roupa identificada").strip(),
        "cor": str(roupa.get("cor") or "não identificada").strip(),
        "estilo": str(roupa.get("estilo") or "casual").strip().lower(),
        "corte": str(roupa.get("corte") or "regular").strip().lower(),
        "temperatura": str(roupa.get("temperatura") or "ambos").strip().lower(),
        "tipo": str(roupa.get("tipo") or "roupa").strip().lower(),
        "material": str(roupa.get("material") or "").strip(),
        "tamanho": str(roupa.get("tamanho") or "").strip().upper(),
        "genero": str(roupa.get("genero") or "").strip().lower(),
        "estacao": str(roupa.get("estacao") or "").strip(),
        "imagem": str(roupa.get("imagem") or "").strip(),
        "observacoes": str(roupa.get("observacoes") or "").strip(),
    }


def _inserir_roupa(
    conexao: sqlite3.Connection,
    roupa: Dict[str, Any],
    roupa_id: int | None = None,
) -> int:
    """Insere uma roupa e preserva o ID quando está migrando dados antigos."""
    registro = _normalizar_registro(roupa)
    placeholders = ", ".join("?" for _ in COLUNAS_ROUPA)
    colunas = ", ".join(COLUNAS_ROUPA)
    valores = tuple(registro[coluna] for coluna in COLUNAS_ROUPA)

    # O INSERT OR IGNORE evita duplicar IDs já presentes durante a migração.
    if roupa_id is None:
        cursor = conexao.execute(
            f"INSERT INTO roupas ({colunas}) VALUES ({placeholders})",
            valores,
        )
    else:
        cursor = conexao.execute(
            f"INSERT OR IGNORE INTO roupas (id, {colunas}) VALUES (?, {placeholders})",
            (roupa_id, *valores),
        )
    return roupa_id or cursor.lastrowid


def _abrir_conexao() -> sqlite3.Connection:
    """Abre o banco, garante as tabelas e executa a migração uma única vez."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(DB_PATH, timeout=10)
    conexao.row_factory = sqlite3.Row
    conexao.executescript(
        """
        CREATE TABLE IF NOT EXISTS roupas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cor TEXT NOT NULL,
            estilo TEXT NOT NULL,
            corte TEXT NOT NULL,
            temperatura TEXT NOT NULL,
            tipo TEXT NOT NULL,
            material TEXT NOT NULL DEFAULT '',
            tamanho TEXT NOT NULL DEFAULT '',
            genero TEXT NOT NULL DEFAULT '',
            estacao TEXT NOT NULL DEFAULT '',
            imagem TEXT NOT NULL DEFAULT '',
            observacoes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS metadados (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        );
        """
    )

    # O metadado impede que o JSON legado seja importado novamente em cada acesso.
    migracao = conexao.execute(
        "SELECT valor FROM metadados WHERE chave = ?",
        ("migracao_clothes_json_v1",),
    ).fetchone()
    if migracao is None:
        try:
            dados_antigos = json.loads(LEGACY_JSON_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Um arquivo ausente ou inválido não impede a criação do banco vazio.
            dados_antigos = []

        if isinstance(dados_antigos, list):
            for roupa in dados_antigos:
                if isinstance(roupa, dict):
                    try:
                        roupa_id = int(roupa["id"]) if roupa.get("id") is not None else None
                    except (TypeError, ValueError):
                        roupa_id = None
                    _inserir_roupa(conexao, roupa, roupa_id)

        conexao.execute(
            "INSERT INTO metadados (chave, valor) VALUES (?, ?)",
            ("migracao_clothes_json_v1", "concluida"),
        )
        conexao.commit()

    return conexao


def inicializar_banco() -> None:
    """Cria o esquema e fecha a conexão inicial usada na partida do app."""
    conexao = _abrir_conexao()
    conexao.close()


def carregar_roupas() -> List[Dict[str, Any]]:
    """Retorna todas as roupas em ordem de cadastro como dicionários."""
    conexao = _abrir_conexao()
    try:
        registros = conexao.execute("SELECT * FROM roupas ORDER BY id").fetchall()
        return [dict(registro) for registro in registros]
    finally:
        # A conexão é fechada mesmo que a consulta ou conversão falhe.
        conexao.close()


def validar_roupa(roupa: Dict[str, Any]) -> List[str]:
    """Lista todos os campos ausentes ou valores fora dos conjuntos permitidos."""
    erros: List[str] = []

    campos_obrigatorios = ["nome", "cor", "estilo", "corte", "temperatura", "tipo"]
    for campo in campos_obrigatorios:
        valor = roupa.get(campo)
        if valor is None or str(valor).strip() == "":
            erros.append(f"Campo '{campo}' é obrigatório.")

    if roupa.get("temperatura") not in VALID_TEMPERATURA:
        erros.append(f"temperatura inválida. Use: {sorted(VALID_TEMPERATURA)}")

    if roupa.get("tipo") not in VALID_TIPO:
        erros.append(f"tipo inválido. Use: {sorted(VALID_TIPO)}")

    if roupa.get("estilo") not in VALID_ESTILO:
        erros.append(f"estilo inválido. Use: {sorted(VALID_ESTILO)}")

    if roupa.get("corte") not in VALID_CORTE:
        erros.append(f"corte inválido. Use: {sorted(VALID_CORTE)}")

    if roupa.get("tamanho") and roupa.get("tamanho") not in VALID_TAMANHO:
        erros.append(f"tamanho inválido. Use: {sorted(VALID_TAMANHO)}")

    if roupa.get("genero") and roupa.get("genero") not in VALID_GENERO:
        erros.append(f"gênero inválido. Use: {sorted(VALID_GENERO)}")

    imagem = roupa.get("imagem")
    if imagem is not None and imagem != "" and not isinstance(imagem, str):
        erros.append("imagem precisa ser uma URL ou caminho em texto.")

    return erros


def add_roupa(roupa: Dict[str, Any]) -> Dict[str, Any]:
    """Valida, grava e devolve a roupa incluindo o ID criado no banco."""
    erros = validar_roupa(roupa)
    if erros:
        raise ValueError("; ".join(erros))

    registro = _normalizar_registro(roupa)
    conexao = _abrir_conexao()
    try:
        with conexao:
            roupa_id = _inserir_roupa(conexao, registro)
        return {"id": roupa_id, **registro}
    finally:
        conexao.close()


def listar_roupas() -> List[Dict[str, Any]]:
    """Expõe a consulta principal usada pela interface e pelos serviços."""
    return carregar_roupas()

