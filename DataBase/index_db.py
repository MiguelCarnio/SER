import json
from pathlib import Path
from typing import Any, Dict, List


DB_PATH = Path(__file__).with_name("clothes.json")


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
}
VALID_ESTILO = {"casual", "formal", "esportivo"}
VALID_CORTE = {"regular", "solto", "ajustado", "acinturado"}
VALID_TAMANHO = {"PP", "P", "M", "G", "GG"}
VALID_GENERO = {"masculino", "feminino", "unissex"}


def carregar_roupas() -> List[Dict[str, Any]]:
    if not DB_PATH.exists():
        DB_PATH.write_text("[]", encoding="utf-8")
        return []

    try:
        dados = json.loads(DB_PATH.read_text(encoding="utf-8"))
        if isinstance(dados, list):
            return dados
    except Exception:
        pass

    DB_PATH.write_text("[]", encoding="utf-8")
    return []


def salvar_roupas(roupas: List[Dict[str, Any]]) -> None:
    DB_PATH.write_text(json.dumps(roupas, ensure_ascii=False, indent=2), encoding="utf-8")


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

    roupas = carregar_roupas()
    nova = {
        "id": len(roupas) + 1,
        "nome": roupa["nome"].strip(),
        "cor": roupa["cor"].strip(),
        "estilo": roupa["estilo"].strip().lower(),
        "corte": roupa["corte"].strip().lower(),
        "temperatura": roupa["temperatura"].strip().lower(),
        "tipo": roupa["tipo"].strip().lower(),
        "material": (roupa.get("material") or "").strip(),
        "tamanho": (roupa.get("tamanho") or "").strip().upper(),
        "genero": (roupa.get("genero") or "").strip().lower(),
        "estacao": (roupa.get("estacao") or "").strip(),
        "imagem": (roupa.get("imagem") or "").strip(),
        "observacoes": (roupa.get("observacoes") or "").strip(),
    }

    roupas.append(nova)
    salvar_roupas(roupas)
    return nova


def remover_roupa_por_id(roupa_id: int) -> bool:
    roupas = carregar_roupas()
    nova_lista = [item for item in roupas if item.get("id") != roupa_id]

    if len(nova_lista) == len(roupas):
        return False

    for i, item in enumerate(nova_lista, start=1):
        item["id"] = i

    salvar_roupas(nova_lista)
    return True


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
    print("\nSistema simples de roupas em JSON")
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

