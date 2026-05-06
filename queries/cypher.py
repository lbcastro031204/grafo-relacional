"""
Queries Cypher reutilizáveis — o vocabulário do grafo.

Cada função retorna dados brutos do Neo4j.
Os agentes interpretam e decidem com base nestes dados.
"""

from models.db import DB
from models.embeddings import similaridade_cosine
from config.settings import settings


def pessoas_com_embedding() -> list[dict]:
    """Retorna todas as pessoas com o seu embedding de valores."""
    return DB.run("""
    MATCH (p:Pessoa)
    WHERE p.valores_embedding IS NOT NULL
    RETURN p.id AS id, p.nome AS nome,
           p.valores_embedding AS embedding,
           p.janela_abertura AS janela_abertura,
           p.estilo_pensamento AS estilo,
           p.tolerancia_ambiguidade AS tolerancia,
           p.multiplicador_rede AS multiplicador
    """)


def competencias_de_pessoa(pessoa_id: str) -> list[dict]:
    """Competências de uma pessoa ordenadas por peso de evidência."""
    return DB.run("""
    MATCH (p:Pessoa {id: $id})-[r:TEM_DEMONSTRADO]->(c:Competencia)
    RETURN c.id AS id, c.nome AS nome, c.embedding AS embedding,
           r.tipo AS tipo, r.confianca AS confianca,
           r.peso_evidencia AS peso_evidencia
    ORDER BY r.peso_evidencia DESC
    """, id=pessoa_id)


def lacunas_de_pessoa(pessoa_id: str) -> list[dict]:
    """Lacunas não resolvidas de uma pessoa."""
    return DB.run("""
    MATCH (p:Pessoa {id: $id})-[:TEM_LACUNA]->(l:Lacuna)
    WHERE l.resolvida = false
    RETURN l.id AS id, l.descricao AS descricao,
           l.descricao_embedding AS embedding,
           l.urgencia AS urgencia
    ORDER BY CASE l.urgencia
        WHEN 'bloqueante' THEN 0
        WHEN 'latente' THEN 1
        ELSE 2
    END
    """, id=pessoa_id)


def colaboracoes_existentes(pessoa_id: str) -> set[str]:
    """IDs de pessoas com quem esta pessoa já colaborou."""
    rows = DB.run("""
    MATCH (p:Pessoa {id: $id})-[:COLABOROU_COM]-(outro:Pessoa)
    RETURN outro.id AS id
    """, id=pessoa_id)
    return {r["id"] for r in rows}


def historico_interacoes(projeto_id: str) -> list[dict]:
    """Todas as interações de um projeto ordenadas por tempo."""
    return DB.run("""
    MATCH (proj:Projeto {id: $id})-[:GEROU_MOMENTO]->(m:Momento)
    RETURN m.tipo AS tipo, m.intensidade AS intensidade,
           m.timestamp AS timestamp, m.resolucao AS resolucao
    ORDER BY m.timestamp ASC
    """, id=projeto_id)


def pontes_criadas_por(pessoa_id: str) -> list[dict]:
    """Conexões que esta pessoa gerou entre outros."""
    return DB.run("""
    MATCH (a:Pessoa {id: $id})-[ponte:CONECTOU]->(par)
    RETURN ponte.resultado_da_ponte AS resultado, ponte.contexto AS contexto
    """, id=pessoa_id)


def calcular_complementaridade(
    emb_a: list[float],
    emb_b: list[float],
    comps_a: list[dict],
    comps_b: list[dict],
) -> dict:
    """
    Calcula a complementaridade entre dois perfis.

    Retorna:
    - similaridade_valores: 0.0–1.0 (deve ser > 0.65 para colaborar)
    - tensoes_produtivas: lista de pares de competências com tensão útil
    - score_total: heurística combinada
    """
    sim_valores = similaridade_cosine(emb_a, emb_b)

    tensoes = []
    for ca in comps_a:
        if not ca.get("embedding"):
            continue
        for cb in comps_b:
            if not cb.get("embedding"):
                continue
            sim_comp = similaridade_cosine(ca["embedding"], cb["embedding"])
            # Tensão produtiva: diferentes o suficiente mas não incompatíveis
            if 0.20 <= sim_comp <= settings.limiar_tensao_produtiva:
                tensoes.append({
                    "competencia_a": ca["nome"],
                    "competencia_b": cb["nome"],
                    "diferenca": round(1 - sim_comp, 2),
                })

    # Score: valores alinhados + tensões criativas
    score = sim_valores * 0.6 + min(len(tensoes) * 0.1, 0.4)

    return {
        "similaridade_valores": round(sim_valores, 3),
        "tensoes_produtivas": tensoes,
        "score_total": round(score, 3),
    }