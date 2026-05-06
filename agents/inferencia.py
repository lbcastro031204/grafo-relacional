"""
Agente de Inferência

Corre em background e actualiza o grafo com base em comportamento observado.
Nunca pergunta — observa e deduz.

O que infere:
- Estilo de pensamento (a partir do padrão de interações)
- Tolerância à ambiguidade (como reage a momentos de bloqueio)
- Fase actual de cada projeto
- Competências demonstradas (a partir do que fez, não do que declarou)
- Lacunas (o que a pessoa precisou mas não tinha)
- Janela de abertura (sinais de transição ou bloqueio criativo)
- Multiplicador de rede (pontes que criou)
"""

from models.db import DB
from models.embeddings import gerar_embedding
from models.pessoa import actualizar_pessoa, PessoaUpdate
from models.projeto import avancar_fase
from models.aresta import registar_competencia, registar_lacuna, CompetenciaCreate
from queries.cypher import historico_interacoes
from agents.janela import actualizar_janela
from datetime import datetime


def inferir_estilo_pensamento(pessoa_id: str) -> str | None:
    """
    Infere estilo de pensamento a partir do padrão de iniciação de interações.

    Linear: inicia maioritariamente decisões e estrutura
    Associativo: inicia convergências e impulsos criativos
    Sistémico: inicia conflitos construtivos e questiona premissas
    """
    rows = DB.run("""
    MATCH (p:Pessoa {id: $id})-[:PARTICIPOU_EM]->(proj:Projeto)
    MATCH (proj)-[:GEROU_MOMENTO]->(m:Momento {iniciador: $id})
    RETURN m.tipo AS tipo, count(*) AS n
    """, id=pessoa_id)

    if not rows:
        return None

    contagens = {r["tipo"]: r["n"] for r in rows}
    total = sum(contagens.values())
    if total < 5:  # dados insuficientes
        return None

    decisoes = contagens.get("decisao", 0) / total
    convergencias = contagens.get("convergencia", 0) / total
    conflitos = contagens.get("conflito", 0) / total

    if decisoes > 0.5:
        return "linear"
    elif convergencias > 0.4:
        return "associativo"
    elif conflitos > 0.3:
        return "sistémico"
    return None


def inferir_tolerancia_ambiguidade(pessoa_id: str) -> float | None:
    """
    Alguém com alta tolerância à ambiguidade:
    - Continua a interagir durante fases de bloqueio
    - Não abandona projetos na fase de fricção
    - Tem ratio alto de impulso/bloqueio nas suas interações
    """
    rows = DB.run("""
    MATCH (p:Pessoa {id: $id})-[:PARTICIPOU_EM]->(proj:Projeto)
    MATCH (proj)-[:GEROU_MOMENTO]->(m:Momento)
    WHERE proj.fase_atual IN ['friccao', 'convergencia']
    RETURN
        count(CASE WHEN m.tipo = 'bloqueio' THEN 1 END) AS bloqueios,
        count(CASE WHEN m.tipo = 'impulso' THEN 1 END) AS impulsos,
        count(*) AS total
    """, id=pessoa_id)

    if not rows or rows[0]["total"] < 3:
        return None

    r = rows[0]
    if r["total"] == 0:
        return None

    # Alta tolerância = mais impulsos que bloqueios em momentos difíceis
    ratio = (r["impulsos"] - r["bloqueios"]) / r["total"]
    # Normalizar para 0.0–1.0
    return round(max(0.0, min(1.0, (ratio + 1) / 2)), 2)


def inferir_fase_projeto(projeto_id: str) -> str | None:
    """
    Detecta em que fase o projeto está com base no padrão recente de interações.

    Fusão: maioritariamente impulsos e decisões simples
    Fricção: conflitos aumentam, bloqueios aparecem
    Convergência: conflitos diminuem, convergências aumentam
    Execução: interações diminuem em frequência mas são decisões
    """
    interacoes = historico_interacoes(projeto_id)
    if len(interacoes) < 3:
        return None

    # Analisar as últimas 10 interações
    recentes = interacoes[-10:]
    tipos = [i["tipo"] for i in recentes]

    n_conflitos = tipos.count("conflito")
    n_convergencias = tipos.count("convergencia")
    n_bloqueios = tipos.count("bloqueio")
    n_decisoes = tipos.count("decisao")
    total = len(tipos)

    if n_conflitos / total > 0.4:
        return "friccao"
    elif n_convergencias / total > 0.4:
        return "convergencia"
    elif n_decisoes / total > 0.5 and n_conflitos < 2:
        return "execucao"
    return None



def calcular_multiplicador_rede(pessoa_id: str) -> float:
    """
    Multiplicador de rede = quantas colaborações bem-sucedidas
    esta pessoa gerou para outros (para além dos seus próprios projetos).

    Valor 0.0–10.0+ (sem tecto rígido)
    """
    rows = DB.run("""
    MATCH (a:Pessoa {id: $id})-[c:COLABOROU_COM]-(b:Pessoa)
    WHERE c.n_interacoes >= 3
    WITH count(DISTINCT b) AS colaboracoes_directas
    RETURN colaboracoes_directas * 1.0 AS multiplicador
    """, id=pessoa_id)

    if not rows:
        return 0.0

    return round(rows[0].get("multiplicador", 0.0), 2)


# ─── Ciclo de inferência completo ────────────────────────────────────────────

def correr_inferencia_pessoa(pessoa_id: str):
    """
    Ponto de entrada para atualizar o perfil de uma pessoa.
    Deve correr periodicamente (ex: após cada interação registada).
    """
    updates = {}

    estilo = inferir_estilo_pensamento(pessoa_id)
    if estilo:
        updates["estilo_pensamento"] = estilo

    tolerancia = inferir_tolerancia_ambiguidade(pessoa_id)
    if tolerancia is not None:
        updates["tolerancia_ambiguidade"] = tolerancia

    resultado_janela = actualizar_janela(pessoa_id)
    updates["janela_abertura"] = resultado_janela.aberta

    multiplicador = calcular_multiplicador_rede(pessoa_id)
    updates["multiplicador_rede"] = multiplicador

    if updates:
        actualizar_pessoa(pessoa_id, PessoaUpdate(**updates))

    print(f"[inferência] Pessoa {pessoa_id}: {updates}")


def correr_inferencia_projeto(projeto_id: str):
    """Atualiza a fase do projeto com base no padrão de interações."""
    nova_fase = inferir_fase_projeto(projeto_id)
    if nova_fase:
        avancar_fase(projeto_id, nova_fase)
        print(f"[inferência] Projeto {projeto_id} → fase: {nova_fase}")