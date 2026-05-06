"""
Nó Projeto — representa um desafio criativo real.

O projeto é o contexto onde o grafo ganha dados.
Cada interação dentro de um projeto alimenta as arestas entre pessoas.
"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from models.db import DB
from models.embeddings import gerar_embedding


class ProjetoCreate(BaseModel):
    criador_id: str
    titulo: str
    descricao_desafio: str = Field(
        ...,
        description="Descreve o desafio em aberto — o que ainda não sabes resolver.",
        min_length=30,
    )


class ProjetoOut(BaseModel):
    id: str
    titulo: str
    descricao_desafio: str
    fase_atual: str
    energia_colaboracao: float
    resultado_gerado: bool
    criado_em: str
    n_participantes: int = 0


def criar_projeto(data: ProjetoCreate) -> ProjetoOut:
    projeto_id = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()

    # O embedding do desafio permite encontrar projetos complementares
    # e pessoas cujas lacunas coincidem com o que o projeto precisa
    embedding_desafio = gerar_embedding(data.descricao_desafio)

    query = """
    MATCH (criador:Pessoa {id: $criador_id})
    CREATE (proj:Projeto {
        id: $id,
        titulo: $titulo,
        descricao_desafio: $descricao,
        desafio_embedding: $embedding,
        fase_atual: 'fusao',
        energia_colaboracao: 0.5,
        resultado_gerado: false,
        criado_em: $agora
    })
    CREATE (criador)-[:PARTICIPOU_EM {
        papel: 'iniciador',
        entrada_em: $agora
    }]->(proj)
    RETURN proj
    """

    DB.run(query,
        criador_id=data.criador_id,
        id=projeto_id,
        titulo=data.titulo,
        descricao=data.descricao_desafio,
        embedding=embedding_desafio,
        agora=agora,
    )

    return obter_projeto(projeto_id)


def obter_projeto(projeto_id: str) -> Optional[ProjetoOut]:
    query = """
    MATCH (proj:Projeto {id: $id})
    OPTIONAL MATCH (p:Pessoa)-[:PARTICIPOU_EM]->(proj)
    RETURN proj, count(DISTINCT p) AS n_participantes
    """
    rows = DB.run(query, id=projeto_id)
    if not rows:
        return None
    row = rows[0]
    proj = row["proj"]
    return ProjetoOut(
        id=proj["id"],
        titulo=proj["titulo"],
        descricao_desafio=proj["descricao_desafio"],
        fase_atual=proj["fase_atual"],
        energia_colaboracao=proj["energia_colaboracao"],
        resultado_gerado=proj["resultado_gerado"],
        criado_em=proj["criado_em"],
        n_participantes=row["n_participantes"],
    )


def adicionar_participante(projeto_id: str, pessoa_id: str, papel: str = "colaborador"):
    """Liga uma pessoa a um projeto com aresta PARTICIPOU_EM."""
    query = """
    MATCH (proj:Projeto {id: $projeto_id})
    MATCH (p:Pessoa {id: $pessoa_id})
    MERGE (p)-[r:PARTICIPOU_EM]->(proj)
    ON CREATE SET r.papel = $papel, r.entrada_em = $agora
    RETURN r
    """
    DB.run(query,
        projeto_id=projeto_id,
        pessoa_id=pessoa_id,
        papel=papel,
        agora=datetime.utcnow().isoformat(),
    )


def avancar_fase(projeto_id: str, nova_fase: str):
    """
    Fases: fusao → friccao → convergencia → execucao → integracao
    Chamado pelo agente de inferência quando detecta mudança de padrão.
    """
    fases_validas = {"fusao", "friccao", "convergencia", "execucao", "integracao"}
    if nova_fase not in fases_validas:
        raise ValueError(f"Fase inválida: {nova_fase}")

    DB.run(
        "MATCH (proj:Projeto {id: $id}) SET proj.fase_atual = $fase",
        id=projeto_id, fase=nova_fase,
    )