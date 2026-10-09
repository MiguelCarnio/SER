import json
import os
import unicodedata
import uuid
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from DataBase import index_db


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

PROMPT_ANALISE = """
Analise a imagem da peça de vestuário e extraia as seguintes informações no formato JSON rigoroso.
Se o objeto na imagem NÃO for uma roupa ou calçado, retorne: {"eh_roupa": false, "mensagem": "Não é uma roupa"}

Modelo do JSON desejado:
{
  "eh_roupa": true,
  "nome": "Nome descritivo da peça",
  "categoria": "camiseta, calca, bermuda, calçado, jaqueta, etc.",
  "cor_dominante": "cor principal",
  "estilo": "casual, esporte, formal, streetwear, etc.",
  "estacao": "verao, inverno, todas",
  "material": "algodão, jeans, couro, etc.",
  "observacoes": "detalhes adicionais da roupa"
}
"""

MODELOS_GEMINI = (
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
)
EXTENSOES_IMAGEM = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}
MIMES_IMAGEM = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

TIPOS_EQUIVALENTES = {
    "camisa": "camiseta",
    "t shirt": "camiseta",
    "calca jeans": "calca",
    "bermuda": "short",
    "shorts": "short",
    "sweater": "sueter",
    "coat": "casaco",
    "jacket": "jaqueta",
    "dress": "vestido",
    "skirt": "saia",
    "shoe": "calcado",
    "shoes": "calcado",
    "calzado": "calcado",
    "calcado": "calcado",
    "tenis": "calcado",
    "bota": "calcado",
    "sandalia": "calcado",
    "acessorio": "acessorio",
}
TIPOS_PARTE_SUPERIOR = {"camiseta", "blusa", "sueter", "casaco", "jaqueta"}
TIPOS_PARTE_INFERIOR = {"calca", "short", "saia"}
CLIMAS_VALIDOS = {"calor", "frio", "ameno"}


def normalizar_texto(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return "".join(
        caractere for caractere in texto if not unicodedata.combining(caractere)
    ).strip().lower()


def salvar_imagem_roupa(conteudo, content_type, filename):
    mime_type = (content_type or "").lower()
    extensao = EXTENSOES_IMAGEM.get(mime_type)
    if not extensao:
        extensao = Path(filename or "").suffix.lower()
        if extensao not in MIMES_IMAGEM:
            raise ValueError("Formato de imagem não suportado.")

    nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
    caminho = UPLOAD_DIR / nome_arquivo
    caminho.write_bytes(conteudo)
    return caminho, f"/static/uploads/{nome_arquivo}"


def caminho_imagem_roupa(roupa):
    imagem = str(roupa.get("imagem") or "")
    if not imagem.startswith("/static/uploads/"):
        return None

    caminho = UPLOAD_DIR / Path(imagem).name
    if caminho.resolve().parent != UPLOAD_DIR.resolve() or not caminho.is_file():
        return None
    return caminho


def roupa_para_banco(dados, imagem=""):
    categoria = normalizar_texto(dados.get("categoria"))
    tipo = TIPOS_EQUIVALENTES.get(categoria, categoria)
    if tipo not in index_db.VALID_TIPO:
        tipo = "roupa"

    estilo_detectado = normalizar_texto(dados.get("estilo"))
    if any(palavra in estilo_detectado for palavra in ("formal", "social", "elegante")):
        estilo = "formal"
    elif any(palavra in estilo_detectado for palavra in ("esport", "sport", "academia")):
        estilo = "esportivo"
    else:
        estilo = "casual"

    estacao = str(dados.get("estacao") or "").strip()
    estacao_normalizada = normalizar_texto(estacao)
    if any(palavra in estacao_normalizada for palavra in ("inverno", "frio")):
        temperatura = "frio"
    elif any(palavra in estacao_normalizada for palavra in ("verao", "calor")):
        temperatura = "calor"
    else:
        temperatura = "ambos"

    return {
        "nome": str(dados.get("nome") or "Roupa identificada").strip(),
        "cor": str(dados.get("cor_dominante") or "não identificada").strip(),
        "estilo": estilo,
        "corte": "regular",
        "temperatura": temperatura,
        "tipo": tipo,
        "material": str(dados.get("material") or "").strip(),
        "estacao": estacao,
        "imagem": imagem,
        "observacoes": str(dados.get("observacoes") or "").strip(),
    }


def pontuar_combinacao(nova, existente):
    pontos = 0
    estilo_novo = normalizar_texto(nova.get("estilo"))
    estilo_existente = normalizar_texto(existente.get("estilo"))
    if estilo_novo and estilo_novo == estilo_existente:
        pontos += 4

    cor_nova = normalizar_texto(nova.get("cor"))
    cor_existente = normalizar_texto(existente.get("cor"))
    cores_neutras = ("preto", "branco", "cinza", "bege", "marrom", "navy")
    if cor_nova and cor_nova == cor_existente:
        pontos += 3
    elif any(cor in cor_nova for cor in cores_neutras) or any(
        cor in cor_existente for cor in cores_neutras
    ):
        pontos += 1

    estacao_nova = normalizar_texto(nova.get("estacao"))
    estacao_existente = normalizar_texto(existente.get("estacao"))
    if estacao_nova and estacao_nova == estacao_existente:
        pontos += 2

    temperatura_nova = nova.get("temperatura")
    temperatura_existente = existente.get("temperatura")
    if temperatura_nova == temperatura_existente:
        pontos += 2
    elif "ambos" in (temperatura_nova, temperatura_existente):
        pontos += 1

    material_novo = normalizar_texto(nova.get("material"))
    material_existente = normalizar_texto(existente.get("material"))
    if material_novo and material_novo == material_existente:
        pontos += 1

    if nova.get("tipo") != existente.get("tipo"):
        pontos += 2

    return round(pontos / 14 * 100)


def _grupo_roupa(roupa):
    tipo = normalizar_texto(roupa.get("tipo"))
    tipo = TIPOS_EQUIVALENTES.get(tipo, tipo)
    if tipo in TIPOS_PARTE_SUPERIOR:
        return "superior"
    if tipo in TIPOS_PARTE_INFERIOR:
        return "inferior"
    if tipo == "vestido":
        return "vestido"
    if tipo == "calcado":
        return "calcado"

    descricao = normalizar_texto(f"{roupa.get('nome', '')} {roupa.get('observacoes', '')}")
    if any(palavra in descricao for palavra in ("bermuda", "short", "calca", "saia")):
        return "inferior"
    if any(palavra in descricao for palavra in ("camiseta", "camisa", "blusa", "sueter", "jaqueta", "casaco")):
        return "superior"
    if any(palavra in descricao for palavra in ("vestido", "macacao")):
        return "vestido"
    if any(palavra in descricao for palavra in ("tenis", "sapato", "bota", "sandalia", "calcado")):
        return "calcado"
    return None


def _eh_complementar(roupa_base, candidata):
    grupo_base = _grupo_roupa(roupa_base)
    grupo_candidata = _grupo_roupa(candidata)
    complementos = {
        "superior": {"inferior"},
        "inferior": {"superior"},
        "vestido": {"calcado"},
        "calcado": {"superior", "inferior", "vestido"},
    }
    return grupo_candidata in complementos.get(grupo_base, set())


def _clima_compativel(roupa, clima):
    if clima is None:
        return True
    clima = normalizar_texto(clima)
    if clima not in CLIMAS_VALIDOS:
        raise ValueError("Escolha um clima válido: calor, frio ou ameno.")

    temperatura = normalizar_texto(roupa.get("temperatura"))
    estacao = normalizar_texto(roupa.get("estacao"))
    if temperatura in ("", "ambos"):
        return True
    if clima == "ameno":
        return temperatura == "ameno" or any(
            palavra in estacao
            for palavra in ("ameno", "meia-estacao", "meia estacao", "primavera", "outono", "transicao", "todas")
        )
    if temperatura == clima:
        return True
    palavras_clima = ("inverno", "frio") if clima == "frio" else ("verao", "calor")
    return any(palavra in estacao for palavra in palavras_clima)


def encontrar_melhor_combinacao(nova, roupas_existentes, clima=None):
    candidatas = [
        roupa
        for roupa in roupas_existentes
        if roupa.get("id") != nova.get("id")
        and _eh_complementar(nova, roupa)
        and _clima_compativel(roupa, clima)
    ]
    if not candidatas:
        return None

    roupa = max(candidatas, key=lambda item: pontuar_combinacao(nova, item))
    return {"roupa": roupa, "compatibilidade": pontuar_combinacao(nova, roupa)}


def analisar_imagem(conteudo_bytes, content_type, filename):
    if client is None:
        return {"eh_roupa": False, "mensagem": "GEMINI_API_KEY não configurada."}
    if not conteudo_bytes:
        return {"eh_roupa": False, "mensagem": "Arquivo vazio."}
    if len(conteudo_bytes) > MAX_UPLOAD_BYTES:
        return {"eh_roupa": False, "mensagem": "A imagem deve ter no máximo 12 MB."}

    mime_type = "image/jpeg" if content_type == "image/jpg" else content_type or "image/jpeg"
    imagem_part = types.Part.from_bytes(data=conteudo_bytes, mime_type=mime_type)
    ultimo_erro = None
    for modelo in MODELOS_GEMINI:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=[imagem_part, PROMPT_ANALISE],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            texto = getattr(response, "text", None)
            if not texto:
                continue
            dados = json.loads(texto)
            if not isinstance(dados, dict):
                continue
            if dados.get("eh_roupa") is not True:
                return {
                    "eh_roupa": False,
                    "mensagem": dados.get("mensagem") or "A imagem não foi identificada como roupa.",
                    "salva_no_banco": False,
                }

            caminho_imagem, imagem_url = salvar_imagem_roupa(conteudo_bytes, content_type, filename)
            roupa_nova = roupa_para_banco(dados, imagem_url)
            try:
                roupa_salva = index_db.add_roupa(roupa_nova)
            except Exception:
                caminho_imagem.unlink(missing_ok=True)
                raise
            return {
                **dados,
                "salva_no_banco": True,
                "roupa_adicionada": roupa_salva,
            }
        except Exception as exc:
            ultimo_erro = exc

    return {
        "eh_roupa": False,
        "mensagem": f"Não foi possível acessar o modelo do Gemini. Motivo: {ultimo_erro}",
    }


def combinar_roupa(roupa_id, clima):
    if client is None:
        raise RuntimeError("GEMINI_API_KEY não configurada.")
    clima = normalizar_texto(clima)
    if clima not in CLIMAS_VALIDOS:
        raise ValueError("Escolha um clima válido: calor, frio ou ameno.")

    roupas = index_db.listar_roupas()
    roupa_base = next((item for item in roupas if item.get("id") == roupa_id), None)
    if roupa_base is None:
        raise ValueError("Roupa não encontrada no banco.")

    imagem_base = caminho_imagem_roupa(roupa_base)
    if imagem_base is None:
        raise ValueError("A foto desta roupa não está disponível.")
    if not _clima_compativel(roupa_base, clima):
        return {
            "melhor_combinacao": None,
            "mensagem": f"A peça escolhida não é adequada para clima {clima}. Selecione outra peça ou outro clima.",
        }

    candidatas = [
        item
        for item in roupas
        if item.get("id") != roupa_id
        and _eh_complementar(roupa_base, item)
        and _clima_compativel(item, clima)
    ]
    if not candidatas:
        return {
            "melhor_combinacao": None,
            "mensagem": f"Não há uma peça complementar adequada para clima {clima} no seu guarda-roupa.",
        }

    candidatas.sort(key=lambda item: pontuar_combinacao(roupa_base, item), reverse=True)
    candidatas = candidatas[:8]
    conteudos = [
        f"Clima escolhido: {clima}. Escolha somente uma peça que complemente a roupa de referência para montar um look nesse clima. Parte de cima deve combinar com parte de baixo (calça, bermuda ou saia), e parte de baixo com parte de cima. Considere cores e estilo; nunca escolha uma peça do mesmo grupo ou apenas parecida. Responda somente em JSON: {{\"id\": inteiro, \"compatibilidade\": inteiro de 0 a 100, \"motivo\": texto curto}}. O id precisa pertencer a uma candidata.",
        "FOTO DE REFERÊNCIA:",
        types.Part.from_bytes(
            data=imagem_base.read_bytes(),
            mime_type=MIMES_IMAGEM.get(imagem_base.suffix.lower(), "image/jpeg"),
        ),
    ]
    candidatas_por_id = {item["id"]: item for item in candidatas}
    for candidata in candidatas:
        conteudos.append(
            "CANDIDATA id={id}: nome={nome}; tipo={tipo}; cor={cor}; estilo={estilo}; estacao={estacao}; temperatura={temperatura}; material={material}.".format(
                id=candidata["id"],
                nome=candidata.get("nome", ""),
                tipo=candidata.get("tipo", ""),
                cor=candidata.get("cor", ""),
                estilo=candidata.get("estilo", ""),
                estacao=candidata.get("estacao", ""),
                temperatura=candidata.get("temperatura", ""),
                material=candidata.get("material", ""),
            )
        )
        imagem_candidata = caminho_imagem_roupa(candidata)
        if imagem_candidata is not None:
            conteudos.append(
                types.Part.from_bytes(
                    data=imagem_candidata.read_bytes(),
                    mime_type=MIMES_IMAGEM.get(imagem_candidata.suffix.lower(), "image/jpeg"),
                )
            )

    ultimo_erro = None
    for modelo in MODELOS_GEMINI:
        try:
            response = client.models.generate_content(
                model=modelo,
                contents=conteudos,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            dados = json.loads(getattr(response, "text", "") or "{}")
            candidata = candidatas_por_id.get(int(dados.get("id")))
            if candidata is None:
                raise ValueError("A IA retornou um id que não está no banco.")
            compatibilidade = max(0, min(100, int(dados.get("compatibilidade", 0))))
            return {
                "melhor_combinacao": {
                    "roupa": candidata,
                    "compatibilidade": compatibilidade,
                    "motivo": str(dados.get("motivo") or "Combina com a peça enviada."),
                },
                "metodo": "Gemini",
            }
        except Exception as exc:
            ultimo_erro = exc

    raise RuntimeError(f"A IA não conseguiu comparar as roupas: {ultimo_erro}")