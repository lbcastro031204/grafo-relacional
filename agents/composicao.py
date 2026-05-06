"""
Agente de Composição de Equipa

O agente mais importante do MVP — dado um desafio ou uma pessoa,
sugere com quem colaborar e explica porquê a tensão é produtiva.

Lógica:
1. Obter embedding de valores da pessoa A
2. Filtrar: só pessoas com janela de abertura (ou sem histórico)
3. Filtrar: excluir quem já colaborou com A
4. Para cada candidato: calcular complementaridade
5. Ordenar por score e retornar top 3
6. Para cada sugestão: gerar explicação da tensão específica
"""

from models.db import DB
from models.embeddings import gerar_embedding
from queries.cypher import (
    pessoas_com_embedding,
    competencias_de_pessoa,
    lacunas_de_pessoa,
    colaboracoes_existentes,
    calcular_complementaridade,
)
from config.settings import settings
from pydantic import BaseModel
from typing import Optional


class SugestaoColaboracao(BaseModel):
    pessoa_id: str
    pessoa_nome: str
    score_complementaridade: float
    similaridade_valores: float
    tensoes_produtivas: list[dict]
    razao_principal: str          # explicação humana da tensão
    lacunas_preenchidas: list[str]
    janela_aberta: bool


class ResultadoComposicao(BaseModel):
    para_pessoa_id: str
    sugestoes: list[SugestaoColaboracao]
    contexto_desafio: Optional[str] = None


def sugerir_colaboradores(
    pessoa_id: str,
    descricao_desafio: Optional[str] = None,
    max_sugestoes: int = 3,
) -> ResultadoComposicao:
    """
    Ponto de entrada principal do agente.

    Se for fornecida uma descrição de desafio, o agente também considera
    quem tem competências relevantes para esse desafio específico.
    """

    # 1. Obter perfil da pessoa que pede sugestão
    rows = DB.run("""
    MATCH (p:Pessoa {id: $id})
    RETURN p.valores_embedding AS embedding,
           p.estilo_pensamento AS estilo,
           p.tolerancia_ambiguidade AS tolerancia
    """, id=pessoa_id)

    if not rows or not rows[0].get("embedding"):
        return ResultadoComposicao(
            para_pessoa_id=pessoa_id,
            sugestoes=[],
            contexto_desafio=descricao_desafio,
        )

    emb_a = rows[0]["embedding"]
    comps_a = competencias_de_pessoa(pessoa_id)
    lacunas_a = lacunas_de_pessoa(pessoa_id)
    ja_colaborou = colaboracoes_existentes(pessoa_id)

    # Embedding do desafio para filtrar por relevância (opcional)
    emb_desafio = gerar_embedding(descricao_desafio) if descricao_desafio else None

    # 2. Obter todos os candidatos
    candidatos = pessoas_com_embedding()

    scores = []
    for cand in candidatos:
        cand_id = cand["id"]

        # Excluir a própria pessoa e quem já colaborou
        if cand_id == pessoa_id:
            continue
        if cand_id in ja_colaborou:
            continue

        emb_b = cand["embedding"]
        if not emb_b:
            continue

        # 3. Calcular complementaridade
        comps_b = competencias_de_pessoa(cand_id)
        comp = calcular_complementaridade(emb_a, emb_b, comps_a, comps_b)

        # Filtro mínimo: valores suficientemente compatíveis
        if comp["similaridade_valores"] < settings.similaridade_valores_minima:
            continue

        # 4. Detectar lacunas da pessoa A que candidato preenche
        lacunas_preenchidas = _lacunas_preenchidas_por(lacunas_a, comps_b)

        # Bónus se candidato tem janela de abertura
        score_final = comp["score_total"]
        if cand.get("janela_abertura"):
            score_final = min(score_final + 0.05, 1.0)

        scores.append({
            "cand": cand,
            "comp": comp,
            "lacunas_preenchidas": lacunas_preenchidas,
            "score_final": score_final,
        })

    # 5. Ordenar e seleccionar top N
    scores.sort(key=lambda x: x["score_final"], reverse=True)
    top = scores[:max_sugestoes]

    sugestoes = []
    for item in top:
        cand = item["cand"]
        comp = item["comp"]
        razao = _gerar_razao(
            comp["tensoes_produtivas"],
            item["lacunas_preenchidas"],
            comp["similaridade_valores"],
        )
        sugestoes.append(SugestaoColaboracao(
            pessoa_id=cand["id"],
            pessoa_nome=cand["nome"],
            score_complementaridade=round(item["score_final"], 3),
            similaridade_valores=comp["similaridade_valores"],
            tensoes_produtivas=comp["tensoes_produtivas"],
            razao_principal=razao,
            lacunas_preenchidas=item["lacunas_preenchidas"],
            janela_aberta=cand.get("janela_abertura", False),
        ))

    return ResultadoComposicao(
        para_pessoa_id=pessoa_id,
        sugestoes=sugestoes,
        contexto_desafio=descricao_desafio,
    )


# ─── Helpers privados ──────────────────────────────────────────────────────────

def _lacunas_preenchidas_por(
    lacunas: list[dict],
    comps_candidato: list[dict],
) -> list[str]:
    """
    Verifica que lacunas da pessoa A são cobertas pelas
    competências do candidato B.
    """
    from models.embeddings import similaridade_cosine
    preenchidas = []
    for lacuna in lacunas:
        emb_lacuna = lacuna.get("embedding")
        if not emb_lacuna:
            continue
        for comp in comps_candidato:
            emb_comp = comp.get("embedding")
            if not emb_comp:
                continue
            # Lacuna preenchida se competência é suficientemente relevante
            if similaridade_cosine(emb_lacuna, emb_comp) > 0.60:
                preenchidas.append(lacuna["descricao"])
                break
    return preenchidas


def _gerar_razao(
    tensoes: list[dict],
    lacunas: list[str],
    sim_valores: float,
) -> str:
    """
    Gera uma explicação humana da razão para colaborar.
    Simples e directa — sem jargão.
    """
    partes = []

    if tensoes:
        t = tensoes[0]
        partes.append(
            f"A tensão entre '{t['competencia_a']}' e '{t['competencia_b']}' "
            f"cria espaço para algo que nenhum dos dois criaria sozinho."
        )

    if lacunas:
        partes.append(
            f"Esta pessoa preenche directamente: {lacunas[0]}."
        )

    if sim_valores >= 0.80:
        partes.append("Os valores de base são muito próximos — a diferença é de estilo, não de direcção.")
    elif sim_valores >= 0.65:
        partes.append("Há alinhamento suficiente de valores para a tensão ser produtiva.")

    return " ".join(partes) if partes else "Perfis complementares com base de valores compatível."