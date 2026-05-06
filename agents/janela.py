"""
Agente de Janela de Abertura

Detecta quando uma pessoa está num momento de transição ou bloqueio
que a torna mais permeável a novas conexões e colaborações.

A "janela de abertura" é o timing engine do sistema —
o agente de composição só sugere colaborações quando pelo menos
uma das pessoas tem janela aberta. O mesmo par em momento errado
produz resultado diferente do que no momento certo.

Sinais monitorados:
- Projeto recente terminou (integração completa)
- Bloqueio criativo sem resolução há N dias
- Energia de colaboração em queda num projeto activo
- Muito tempo sem actividade (inércia = abertura)
- Pessoa nova na plataforma (janela aberta por definição)
- Mudança de papel detectada (novo projeto, novo contexto)
"""

from datetime import datetime
from models.db import DB
from models.pessoa import actualizar_pessoa, PessoaUpdate


# ─── Limiares configuráveis ───────────────────────────────────────────────────

DIAS_SEM_ACTIVIDADE = 21        # dias sem interação → janela aberta
ENERGIA_MINIMA = 0.30           # energia abaixo disto → janela aberta
DIAS_POS_INTEGRACAO = 14        # janela aberta N dias após projeto terminar
MIN_INTERACOES_BLOQUEIO = 3     # bloqueios consecutivos sem resolução


# ─── Detectores individuais ───────────────────────────────────────────────────

def _projeto_recentemente_integrado(pessoa_id: str) -> bool:
    """
    Pessoa cujo projeto mais recente entrou em fase de integração
    (terminou) nos últimos DIAS_POS_INTEGRACAO dias.
    """
    rows = DB.run("""
    MATCH (p:Pessoa {id: $id})-[:PARTICIPOU_EM]->(proj:Projeto)
    WHERE proj.fase_atual = 'integracao'
    WITH proj ORDER BY proj.criado_em DESC LIMIT 1
    RETURN proj.criado_em AS criado_em
    """, id=pessoa_id)

    if not rows:
        return False

    try:
        criado = datetime.fromisoformat(rows[0]["criado_em"])
        dias = (datetime.utcnow() - criado).days
        return dias <= DIAS_POS_INTEGRACAO
    except Exception:
        return False


def _energia_baixa_em_projeto_activo(pessoa_id: str) -> bool:
    """
    Projeto activo com energia de colaboração abaixo do limiar mínimo.
    Sinal de esgotamento ou deriva — pessoa está disponível para algo novo.
    """
    rows = DB.run("""
    MATCH (p:Pessoa {id: $id})-[:PARTICIPOU_EM]->(proj:Projeto)
    WHERE proj.fase_atual IN ['fusao', 'friccao', 'convergencia', 'execucao']
    RETURN proj.energia_colaboracao AS energia
    ORDER BY energia ASC
    LIMIT 1
    """, id=pessoa_id)

    if not rows:
        return False

    energia = rows[0].get("energia", 1.0)
    return energia < ENERGIA_MINIMA


def _inatividade_prolongada(pessoa_id: str) -> bool:
    """
    Nenhuma interação registada nos últimos DIAS_SEM_ACTIVIDADE dias.
    Inércia prolongada é frequentemente sinal de abertura a algo novo.
    """
    rows = DB.run("""
    MATCH (p:Pessoa {id: $id})-[:PARTICIPOU_EM]->(proj:Projeto)
    MATCH (proj)-[:GEROU_MOMENTO]->(m:Momento)
    RETURN m.timestamp AS ultima
    ORDER BY m.timestamp DESC
    LIMIT 1
    """, id=pessoa_id)

    if not rows:
        # Sem actividade registada → janela aberta (pessoa nova ou inactiva)
        return True

    try:
        ultima = datetime.fromisoformat(rows[0]["ultima"])
        dias = (datetime.utcnow() - ultima).days
        return dias >= DIAS_SEM_ACTIVIDADE
    except Exception:
        return True


def _bloqueio_criativo_declarado(pessoa_id: str) -> bool:
    """
    Múltiplos momentos de bloqueio sem resolução num projeto activo.
    Quando alguém verbaliza estar preso, está a sinalizar que precisa
    de uma perspectiva exterior.
    """
    rows = DB.run("""
    MATCH (p:Pessoa {id: $id})-[:PARTICIPOU_EM]->(proj:Projeto)
    MATCH (proj)-[:GEROU_MOMENTO]->(m:Momento)
    WHERE m.tipo = 'bloqueio'
      AND m.resolucao = 'pendente'
    RETURN count(m) AS n_bloqueios
    """, id=pessoa_id)

    if not rows:
        return False

    return rows[0]["n_bloqueios"] >= MIN_INTERACOES_BLOQUEIO


def _pessoa_nova(pessoa_id: str) -> bool:
    """
    Pessoa criada há menos de 7 dias e sem projetos.
    Janela sempre aberta — está a construir o seu contexto relacional.
    """
    rows = DB.run("""
    MATCH (p:Pessoa {id: $id})
    OPTIONAL MATCH (p)-[:PARTICIPOU_EM]->(proj:Projeto)
    RETURN p.criado_em AS criado_em, count(proj) AS n_projetos
    """, id=pessoa_id)

    if not rows:
        return False

    row = rows[0]
    if row["n_projetos"] > 0:
        return False

    try:
        criado = datetime.fromisoformat(row["criado_em"])
        dias = (datetime.utcnow() - criado).days
        return dias <= 7
    except Exception:
        return True


# ─── Avaliação composta ────────────────────────────────────────────────────────

class ResultadoJanela:
    """Resultado da avaliação de janela com razão explícita."""

    def __init__(self, aberta: bool, razoes: list[str], urgencia: str):
        self.aberta = aberta
        self.razoes = razoes
        self.urgencia = urgencia  # "imediata" | "activa" | "latente" | "fechada"

    def to_dict(self) -> dict:
        return {
            "janela_aberta": self.aberta,
            "urgencia": self.urgencia,
            "razoes": self.razoes,
        }


def avaliar_janela(pessoa_id: str) -> ResultadoJanela:
    """
    Avalia o estado de janela de abertura de uma pessoa.

    Urgência:
    - imediata: bloqueio activo + energia baixa (precisa de ajuda agora)
    - activa:   transição recente ou inatividade (receptiva mas não urgente)
    - latente:  pessoa nova sem historial
    - fechada:  projecto activo com boa energia
    """
    razoes = []
    sinais_activos = 0

    if _pessoa_nova(pessoa_id):
        razoes.append("Pessoa nova na plataforma — sem contexto relacional ainda formado.")
        return ResultadoJanela(True, razoes, "latente")

    if _bloqueio_criativo_declarado(pessoa_id):
        razoes.append(f"Mais de {MIN_INTERACOES_BLOQUEIO} bloqueios sem resolução em projecto activo.")
        sinais_activos += 2  # sinal forte

    if _energia_baixa_em_projeto_activo(pessoa_id):
        razoes.append(f"Energia de colaboração abaixo de {ENERGIA_MINIMA} num projecto activo.")
        sinais_activos += 2  # sinal forte

    if _projeto_recentemente_integrado(pessoa_id):
        razoes.append(f"Projecto terminou nos últimos {DIAS_POS_INTEGRACAO} dias — momento de transição.")
        sinais_activos += 1

    if _inatividade_prolongada(pessoa_id):
        razoes.append(f"Sem interações há mais de {DIAS_SEM_ACTIVIDADE} dias.")
        sinais_activos += 1

    if sinais_activos == 0:
        return ResultadoJanela(False, ["Projecto activo com energia estável."], "fechada")

    urgencia = "imediata" if sinais_activos >= 3 else "activa"
    return ResultadoJanela(True, razoes, urgencia)


# ─── Ciclo de actualização ────────────────────────────────────────────────────

def actualizar_janela(pessoa_id: str) -> ResultadoJanela:
    """
    Avalia e persiste o estado de janela no nó Pessoa.
    Chamado pelo agente de inferência após cada interação.
    """
    resultado = avaliar_janela(pessoa_id)
    actualizar_pessoa(pessoa_id, PessoaUpdate(janela_abertura=resultado.aberta))
    return resultado


def pessoas_com_janela_aberta(urgencia: str | None = None) -> list[dict]:
    """
    Retorna todas as pessoas com janela aberta.
    Filtro opcional por urgência: 'imediata' | 'activa' | 'latente'

    Usado pelo agente de serendipidade para identificar
    momentos de intervenção.
    """
    rows = DB.run("""
    MATCH (p:Pessoa {janela_abertura: true})
    RETURN p.id AS id, p.nome AS nome,
           p.estilo_pensamento AS estilo,
           p.multiplicador_rede AS multiplicador,
           p.criado_em AS criado_em
    ORDER BY p.multiplicador_rede DESC
    """)

    if not urgencia:
        return rows

    # Filtrar por urgência (requer avaliar cada pessoa — apenas para listas pequenas)
    resultado = []
    for row in rows:
        avaliacao = avaliar_janela(row["id"])
        if avaliacao.urgencia == urgencia:
            resultado.append({**row, "urgencia": avaliacao.urgencia})
    return resultado