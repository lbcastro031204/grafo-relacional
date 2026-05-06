"""
Arestas do grafo — onde o valor relacional é armazenado.

As arestas são temporais e têm peso que evolui.
Nunca são criadas por formulário — emergem de comportamento observado.
"""

import uuid
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel
from models.db import DB


TipoInteracao = Literal["decisao", "conflito", "convergencia", "bloqueio", "impulso"]
TipoCompetencia = Literal["declarada", "inferida", "demonstrada"]


# ─── Registar interação (alimenta as arestas) ──────────────────────────────────

class InteracaoCreate(BaseModel):
    projeto_id: str
    iniciador_id: str
    receptor_id: str
    tipo: TipoInteracao
    intensidade: float = 0.5          # 0.0–1.0
    descricao: Optional[str] = None   # opcional — o agente infere do contexto


def registar_interacao(data: InteracaoCreate) -> dict:
    """
    Regista uma interação entre duas pessoas num projeto.
    Cria ou actualiza a aresta COLABOROU_COM com peso acumulado.
    Cria um nó Momento que preserva o histórico granular.
    """
    momento_id = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()

    # 1. Criar nó Momento (historial granular)
    DB.run("""
    CREATE (m:Momento {
        id: $id,
        projeto_id: $projeto_id,
        tipo: $tipo,
        intensidade: $intensidade,
        descricao: $descricao,
        timestamp: $agora,
        resolucao: 'pendente'
    })
    """,
        id=momento_id,
        projeto_id=data.projeto_id,
        tipo=data.tipo,
        intensidade=data.intensidade,
        descricao=data.descricao or "",
        agora=agora,
    )

    # 2. Ligar momento ao projeto
    DB.run("""
    MATCH (proj:Projeto {id: $projeto_id})
    MATCH (m:Momento {id: $momento_id})
    CREATE (proj)-[:GEROU_MOMENTO]->(m)
    """, projeto_id=data.projeto_id, momento_id=momento_id)

    # 3. Criar ou actualizar aresta COLABOROU_COM entre as duas pessoas
    # O peso acumula — quanto mais interações, mais forte a aresta
    DB.run("""
    MATCH (a:Pessoa {id: $id_a})
    MATCH (b:Pessoa {id: $id_b})
    MERGE (a)-[r:COLABOROU_COM]-(b)
    ON CREATE SET
        r.peso = $intensidade,
        r.n_interacoes = 1,
        r.primeira_em = $agora,
        r.ultima_em = $agora,
        r.tipos = [$tipo]
    ON MATCH SET
        r.peso = r.peso + ($intensidade * 0.1),
        r.n_interacoes = r.n_interacoes + 1,
        r.ultima_em = $agora,
        r.tipos = r.tipos + [$tipo]
    """,
        id_a=data.iniciador_id,
        id_b=data.receptor_id,
        intensidade=data.intensidade,
        tipo=data.tipo,
        agora=agora,
    )

    return {"momento_id": momento_id, "status": "registado"}


# ─── Competências demonstradas ────────────────────────────────────────────────

class CompetenciaCreate(BaseModel):
    pessoa_id: str
    nome: str
    tipo: TipoCompetencia = "demonstrada"
    contexto: str = ""                # em que projeto/situação foi observada
    confianca: float = 0.8            # 0.0–1.0


def registar_competencia(data: CompetenciaCreate, embedding: list[float]) -> str:
    """
    Cria nó Competência e liga à pessoa via TEM_DEMONSTRADO.
    O peso de evidência é: demonstrada (1.0) > inferida (0.6) > declarada (0.3)
    """
    comp_id = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()

    peso_evidencia = {"demonstrada": 1.0, "inferida": 0.6, "declarada": 0.3}[data.tipo]

    DB.run("""
    MERGE (c:Competencia {nome: $nome})
    ON CREATE SET
        c.id = $id,
        c.embedding = $embedding,
        c.criada_em = $agora
    WITH c
    MATCH (p:Pessoa {id: $pessoa_id})
    MERGE (p)-[r:TEM_DEMONSTRADO]->(c)
    ON CREATE SET
        r.tipo = $tipo,
        r.confianca = $confianca,
        r.peso_evidencia = $peso_evidencia,
        r.contexto = $contexto,
        r.registado_em = $agora
    ON MATCH SET
        r.confianca = CASE WHEN $confianca > r.confianca THEN $confianca ELSE r.confianca END,
        r.peso_evidencia = CASE WHEN $peso_evidencia > r.peso_evidencia THEN $peso_evidencia ELSE r.peso_evidencia END
    RETURN c.id
    """,
        id=comp_id,
        nome=data.nome,
        embedding=embedding,
        pessoa_id=data.pessoa_id,
        tipo=data.tipo,
        confianca=data.confianca,
        peso_evidencia=peso_evidencia,
        contexto=data.contexto,
        agora=agora,
    )

    return comp_id


# ─── Lacunas detectadas ───────────────────────────────────────────────────────

def registar_lacuna(pessoa_id: str, descricao: str, embedding: list[float], urgencia: str = "latente"):
    """
    Regista uma lacuna detectada pelo agente de inferência.
    Urgência: bloqueante | latente | futura
    """
    lacuna_id = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()

    DB.run("""
    CREATE (l:Lacuna {
        id: $id,
        descricao: $descricao,
        descricao_embedding: $embedding,
        urgencia: $urgencia,
        resolvida: false,
        criada_em: $agora
    })
    WITH l
    MATCH (p:Pessoa {id: $pessoa_id})
    CREATE (p)-[:TEM_LACUNA {detectada_em: $agora}]->(l)
    """,
        id=lacuna_id,
        descricao=descricao,
        embedding=embedding,
        urgencia=urgencia,
        pessoa_id=pessoa_id,
        agora=agora,
    )

    return lacuna_id