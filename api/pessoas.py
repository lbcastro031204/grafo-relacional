"""
Nó central do grafo — representa uma pessoa com contexto relacional completo.

O perfil não é preenchido por formulário. Começa com mínimo absoluto
e enriquece-se por observação de comportamento ao longo do tempo.
"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from models.db import DB
from models.embeddings import gerar_embedding


# ─── Schema Pydantic ───────────────────────────────────────────────────────────

class PessoaCreate(BaseModel):
    """Input mínimo para criar uma pessoa — apenas o essencial."""
    nome: str
    email: str
    descricao_projeto_dificil: str = Field(
        ...,
        description="Descreve um projeto recente onde a colaboração foi difícil mas valeu a pena.",
        min_length=50,
    )


class PessoaUpdate(BaseModel):
    """Campos actualizados pelo agente de inferência — nunca pelo utilizador directamente."""
    estilo_pensamento: Optional[str] = None          # linear | associativo | sistémico
    tolerancia_ambiguidade: Optional[float] = None   # 0.0–1.0
    ritmo_resposta: Optional[str] = None             # rapido | pausado | assimetrico
    janela_abertura: Optional[bool] = None
    multiplicador_rede: Optional[float] = None


class PessoaOut(BaseModel):
    id: str
    nome: str
    email: str
    estilo_pensamento: Optional[str]
    tolerancia_ambiguidade: Optional[float]
    ritmo_resposta: Optional[str]
    janela_abertura: bool
    multiplicador_rede: float
    criado_em: str
    n_projetos: int = 0
    n_colaboracoes: int = 0


# ─── Operações no grafo ────────────────────────────────────────────────────────

def criar_pessoa(data: PessoaCreate) -> PessoaOut:
    """
    Cria o nó Pessoa com embedding de valores inferido
    a partir da descrição do projeto difícil.

    O embedding captura: valores implícitos, estilo narrativo,
    atitude face ao conflito, e o que a pessoa valoriza em colaboração.
    """
    pessoa_id = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()

    # Gerar embedding de valores a partir da descrição livre
    embedding = gerar_embedding(data.descricao_projeto_dificil)

    query = """
    CREATE (p:Pessoa {
        id: $id,
        nome: $nome,
        email: $email,
        descricao_original: $descricao,
        valores_embedding: $embedding,
        estilo_pensamento: null,
        tolerancia_ambiguidade: null,
        ritmo_resposta: null,
        janela_abertura: false,
        multiplicador_rede: 0.0,
        criado_em: $agora,
        actualizado_em: $agora
    })
    RETURN p
    """

    DB.run(query,
        id=pessoa_id,
        nome=data.nome,
        email=data.email,
        descricao=data.descricao_projeto_dificil,
        embedding=embedding,
        agora=agora,
    )

    return obter_pessoa(pessoa_id)


def obter_pessoa(pessoa_id: str) -> Optional[PessoaOut]:
    query = """
    MATCH (p:Pessoa {id: $id})
    OPTIONAL MATCH (p)-[:PARTICIPOU_EM]->(proj:Projeto)
    OPTIONAL MATCH (p)-[:COLABOROU_COM]-(outro:Pessoa)
    RETURN p,
           count(DISTINCT proj) AS n_projetos,
           count(DISTINCT outro) AS n_colaboracoes
    """
    rows = DB.run(query, id=pessoa_id)
    if not rows:
        return None

    row = rows[0]
    p = row["p"]
    return PessoaOut(
        id=p["id"],
        nome=p["nome"],
        email=p["email"],
        estilo_pensamento=p.get("estilo_pensamento"),
        tolerancia_ambiguidade=p.get("tolerancia_ambiguidade"),
        ritmo_resposta=p.get("ritmo_resposta"),
        janela_abertura=p.get("janela_abertura", False),
        multiplicador_rede=p.get("multiplicador_rede", 0.0),
        criado_em=p["criado_em"],
        n_projetos=row["n_projetos"],
        n_colaboracoes=row["n_colaboracoes"],
    )


def actualizar_pessoa(pessoa_id: str, dados: PessoaUpdate) -> Optional[PessoaOut]:
    """
    Actualizado pelo agente de inferência — não pelo utilizador.
    Apenas campos não-nulos são escritos.
    """
    campos = {k: v for k, v in dados.model_dump().items() if v is not None}
    if not campos:
        return obter_pessoa(pessoa_id)

    set_clause = ", ".join(f"p.{k} = ${k}" for k in campos)
    query = f"""
    MATCH (p:Pessoa {{id: $id}})
    SET {set_clause}, p.actualizado_em = $agora
    RETURN p
    """
    DB.run(query, id=pessoa_id, agora=datetime.utcnow().isoformat(), **campos)
    return obter_pessoa(pessoa_id)


def listar_pessoas() -> list[PessoaOut]:
    query = """
    MATCH (p:Pessoa)
    OPTIONAL MATCH (p)-[:PARTICIPOU_EM]->(proj:Projeto)
    OPTIONAL MATCH (p)-[:COLABOROU_COM]-(outro:Pessoa)
    RETURN p,
           count(DISTINCT proj) AS n_projetos,
           count(DISTINCT outro) AS n_colaboracoes
    ORDER BY p.criado_em DESC
    """
    rows = DB.run(query)
    resultado = []
    for row in rows:
        p = row["p"]
        resultado.append(PessoaOut(
            id=p["id"],
            nome=p["nome"],
            email=p["email"],
            estilo_pensamento=p.get("estilo_pensamento"),
            tolerancia_ambiguidade=p.get("tolerancia_ambiguidade"),
            ritmo_resposta=p.get("ritmo_resposta"),
            janela_abertura=p.get("janela_abertura", False),
            multiplicador_rede=p.get("multiplicador_rede", 0.0),
            criado_em=p["criado_em"],
            n_projetos=row["n_projetos"],
            n_colaboracoes=row["n_colaboracoes"],
        ))
    return resultado