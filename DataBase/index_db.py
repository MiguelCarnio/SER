import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


DB_PATH = Path(__file__).with_name("clothes.db")
LEGACY_JSON_PATH = Path(__file__).with_name("clothes.json")
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
    registro = _normalizar_registro(roupa)
    placeholders = ", ".join("?" for _ in COLUNAS_ROUPA)
    colunas = ", ".join(COLUNAS_ROUPA)
    valores = tuple(registro[coluna] for coluna in COLUNAS_ROUPA)

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

    migracao = conexao.execute(
        "SELECT valor FROM metadados WHERE chave = ?",
        ("migracao_clothes_json_v1",),
    ).fetchone()
    if migracao is None:
        try:
            dados_antigos = json.loads(LEGACY_JSON_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
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
    conexao = _abrir_conexao()
    conexao.close()


def carregar_roupas() -> List[Dict[str, Any]]:
    conexao = _abrir_conexao()
    try:
        registros = conexao.execute("SELECT * FROM roupas ORDER BY id").fetchall()
        return [dict(registro) for registro in registros]
    finally:
        conexao.close()


def salvar_roupas(roupas: List[Dict[str, Any]]) -> None:
    conexao = _abrir_conexao()
    try:
        with conexao:
            conexao.execute("DELETE FROM roupas")
            for roupa in roupas:
                try:
                    roupa_id = int(roupa["id"]) if roupa.get("id") is not None else None
                except (TypeError, ValueError):
                    roupa_id = None
                _inserir_roupa(conexao, roupa, roupa_id)
    finally:
        conexao.close()


def validar_roupa(roupa: Dict[str, Any]) -> List[str]:
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


def remover_roupa_por_id(roupa_id: int) -> bool:
    conexao = _abrir_conexao()
    try:
        with conexao:
            cursor = conexao.execute("DELETE FROM roupas WHERE id = ?", (roupa_id,))
        return cursor.rowcount > 0
    finally:
        conexao.close()


def listar_roupas() -> List[Dict[str, Any]]:
    return carregar_roupas()


def buscar_roupas(filtros: Dict[str, Any]) -> List[Dict[str, Any]]:
    roupas = carregar_roupas()
    resultado: List[Dict[str, Any]] = []

    for item in roupas:
        ok = True
        for chave, valor in filtros.items():
            if valor is None:
                continue
            if str(item.get(chave, "")).lower() != str(valor).lower():
                ok = False
                break
        if ok:
            resultado.append(item)

    return resultado


def menu_interativo() -> None:
    print("\nSistema de roupas em SQLite")
    print("1 - adicionar roupa")
    print("2 - listar roupas")
    print("3 - remover roupa por id")
    print("0 - sair")

    while True:
        opcao = input("\nEscolha: ").strip()

        if opcao == "1":
            roupa = {
                "nome": input("Nome: "),
                "cor": input("Cor: "),
                "estilo": input("Estilo (casual/formal/esportivo): "),
                "corte": input("Corte (regular/solto/ajustado/acinturado): "),
                "temperatura": input("Temperatura (frio/calor/ambos): "),
                "tipo": input("Tipo: "),
                "material": input("Material (opcional): ") or "",
                "tamanho": input("Tamanho (opcional): ") or "",
                "genero": input("Gênero (opcional): ") or "",
                "estacao": input("Estação (opcional): ") or "",
                "imagem": input("Imagem (caminho/opcional): ") or "",
                "observacoes": input("Observações (opcional): ") or "",
            }
            try:
                nova = add_roupa(roupa)
                print("Roupa adicionada com sucesso:", nova)
            except ValueError as e:
                print("Erro:", e)

        elif opcao == "2":
            itens = listar_roupas()
            if not itens:
                print("Nenhuma roupa cadastrada.")
            else:
                for item in itens:
                    print(item)

        elif opcao == "3":
            itens = listar_roupas()
            if not itens:
                print("Nenhuma roupa cadastrada para remover.")
                continue
            for item in itens:
                print(item)
            try:
                roupa_id = int(input("Digite o ID da roupa para remover: ").strip())
            except ValueError:
                print("ID inválido.")
                continue

            removido = remover_roupa_por_id(roupa_id)
            if removido:
                print("Roupa removida com sucesso.")
            else:
                print("Nenhuma roupa com esse ID foi encontrada.")

        elif opcao == "0":
            print("Saindo...")
            break

        else:
            print("Opção inválida.")


if __name__ == "__main__":
    menu_interativo()

