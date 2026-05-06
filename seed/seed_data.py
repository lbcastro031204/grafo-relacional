"""
Dados de seed — 6 pessoas reais com perfis complementares.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.pessoa import criar_pessoa, PessoaCreate
from models.projeto import criar_projeto, adicionar_participante, ProjetoCreate
from models.aresta import (
    registar_interacao, InteracaoCreate,
    registar_competencia, CompetenciaCreate,
    registar_lacuna,
)
from models.embeddings import gerar_embedding
from agents.inferencia import correr_inferencia_pessoa
from models.db import DB
from seed.setup_schema import setup


PESSOAS = [
    PessoaCreate(
        nome="Ana Ferreira",
        email="ana@exemplo.pt",
        descricao_projeto_dificil=(
            "Liderei a reestruturação de uma equipa de produto de 12 pessoas. "
            "A colaboração foi difícil porque eu via os padrões sistémicos mas "
            "as pessoas precisavam de acção imediata. Aprendi que a visão só tem "
            "valor quando é traduzida em passos que outros conseguem dar agora. "
            "No final, criar uma linguagem partilhada entre os que pensam em sistemas "
            "e os que pensam em tarefas foi o verdadeiro trabalho."
        ),
    ),
    PessoaCreate(
        nome="Bruno Santos",
        email="bruno@exemplo.pt",
        descricao_projeto_dificil=(
            "Construí o primeiro produto da empresa em 6 semanas com um designer "
            "que queria perfeição e eu queria velocidade. A tensão foi real — ele "
            "achava que eu sacrificava qualidade, eu achava que ele sacrificava "
            "aprendizagem. O que funcionou foi definir o que era reversível e o que "
            "não era. Nas decisões irreversíveis, ele tinha razão. Nas reversíveis, "
            "eu tinha razão. Saímos ambos melhores."
        ),
    ),
    PessoaCreate(
        nome="Catarina Lopes",
        email="catarina@exemplo.pt",
        descricao_projeto_dificil=(
            "Redesenhei o processo de onboarding de uma plataforma de saúde mental. "
            "A dificuldade foi trabalhar com médicos que sabiam tudo sobre o conteúdo "
            "mas nada sobre como as pessoas experienciam ansiedade num ecrã. "
            "Aprendi a criar empatia para experiências que as pessoas têm vergonha "
            "de admitir. O mais difícil foi que os dados diziam uma coisa e as "
            "histórias das pessoas diziam outra — e ambos tinham razão."
        ),
    ),
    PessoaCreate(
        nome="David Rodrigues",
        email="david@exemplo.pt",
        descricao_projeto_dificil=(
            "Construí um sistema de recomendação para uma plataforma de educação. "
            "A colaboração difícil foi com a equipa de pedagogia — eles queriam "
            "preservar a serendipidade do aprendizado e eu queria optimizar métricas. "
            "Descobri que optimizar para o que é fácil de medir destrói o que é "
            "impossível de medir. Hoje meço coisas diferentes e o produto é pior "
            "nos dashboards e melhor na vida real."
        ),
    ),
    PessoaCreate(
        nome="Elena Costa",
        email="elena@exemplo.pt",
        descricao_projeto_dificil=(
            "Facilitei a fusão cultural de duas organizações com valores opostos — "
            "uma muito hierárquica, outra muito flat. A dificuldade foi que ambas "
            "achavam que a sua cultura era superior. O que funcionou foi criar "
            "situações onde cada uma precisava da outra para sobreviver. "
            "Aprendi que a cultura não muda por discurso — muda por dependência "
            "mútua criada em condições de stress real."
        ),
    ),
    PessoaCreate(
        nome="Francisco Mendes",
        email="francisco@exemplo.pt",
        descricao_projeto_dificil=(
            "Passei 3 anos a desenvolver um modelo de machine learning para "
            "diagnóstico precoce de doenças raras. A colaboração difícil foi "
            "com os clínicos — eles precisavam de explicações e eu tinha "
            "caixas negras. Aprendi que a confiança num sistema técnico depende "
            "de conseguir explicar o porquê de cada decisão, não apenas a decisão. "
            "Mudei de otimizar accuracy para otimizar interpretabilidade."
        ),
    ),
]


COMPETENCIAS_SEED = {
    "ana@exemplo.pt": [
        ("Pensamento sistémico", "Demonstrado ao redesenhar estrutura de equipa de 12 pessoas"),
        ("Tradução de visão em acção", "Criou linguagem partilhada entre perfis divergentes"),
        ("Liderança em ambiguidade", "Geriu reestruturação sem mapa claro"),
    ],
    "bruno@exemplo.pt": [
        ("Execução rápida com qualidade calibrada", "Produto em 6 semanas com decisões reversíveis/irreversíveis"),
        ("Gestão de tensão criativa", "Trabalhou produtivamente com perfil oposto ao seu"),
        ("Priorização sob pressão", "Definiu critérios claros em situação de conflito"),
    ],
    "catarina@exemplo.pt": [
        ("Design de experiência emocional", "Onboarding de saúde mental com dados e histórias"),
        ("Síntese de dados qualitativos e quantitativos", "Navegou contradição entre dados e narrativas"),
        ("Empatia em contextos sensíveis", "Trabalhou com experiências de vergonha e ansiedade"),
    ],
    "david@exemplo.pt": [
        ("Sistemas de recomendação", "Construiu recomendação para plataforma educativa"),
        ("Métricas alternativas", "Redesenhou o que medir para capturar valor real"),
        ("Colaboração interdisciplinar técnica", "Trabalhou com pedagogos sem background técnico"),
    ],
    "elena@exemplo.pt": [
        ("Facilitação de fusões culturais", "Uniu duas organizações com valores opostos"),
        ("Criação de dependência mútua", "Desenhou situações de necessidade real"),
        ("Mudança organizacional por comportamento", "Alterou cultura sem discurso"),
    ],
    "francisco@exemplo.pt": [
        ("Machine learning interpretável", "Mudou de accuracy para interpretabilidade"),
        ("Comunicação técnica com não-técnicos", "Explicou caixas negras a clínicos"),
        ("Diagnóstico por IA", "3 anos em doenças raras"),
    ],
}


def seed():
    print("A popular o grafo com dados de seed...")

    DB.run("MATCH (n) DETACH DELETE n")
    print("  ✓ Grafo limpo")

    pessoas_criadas = {}
    for pessoa_data in PESSOAS:
        pessoa = criar_pessoa(pessoa_data)
        pessoas_criadas[pessoa_data.email] = pessoa
        print(f"  ✓ Criada: {pessoa.nome} ({pessoa.id[:8]}...)")

    print("\nA registar competências...")
    for email, comps in COMPETENCIAS_SEED.items():
        pessoa = pessoas_criadas[email]
        for nome_comp, contexto in comps:
            embedding = gerar_embedding(nome_comp + " " + contexto)
            registar_competencia(
                CompetenciaCreate(
                    pessoa_id=pessoa.id,
                    nome=nome_comp,
                    tipo="demonstrada",
                    contexto=contexto,
                    confianca=0.85,
                ),
                embedding=embedding,
            )
        print(f"  ✓ Competências de {email.split('@')[0]}: {len(comps)}")

    print("\nA criar projeto de exemplo...")
    ana = pessoas_criadas["ana@exemplo.pt"]
    bruno = pessoas_criadas["bruno@exemplo.pt"]
    francisco = pessoas_criadas["francisco@exemplo.pt"]

    projeto = criar_projeto(ProjetoCreate(
        criador_id=ana.id,
        titulo="Plataforma de co-criação distribuída",
        descricao_desafio=(
            "Precisamos de construir uma plataforma que permita equipas remotas "
            "colaborar em desafios criativos sem perder a energia do trabalho presencial. "
            "O problema central é que as ferramentas actuais optimizam para eficiência "
            "e destroem a serendipidade. Queremos o oposto."
        ),
    ))
    adicionar_participante(projeto.id, bruno.id, "colaborador")
    print(f"  ✓ Projeto criado: {projeto.titulo}")

    interacoes = [
        InteracaoCreate(projeto_id=projeto.id, iniciador_id=ana.id, receptor_id=bruno.id,
                       tipo="decisao", intensidade=0.6,
                       descricao="Definição do âmbito inicial do projeto"),
        InteracaoCreate(projeto_id=projeto.id, iniciador_id=bruno.id, receptor_id=ana.id,
                       tipo="conflito", intensidade=0.7,
                       descricao="Bruno quer MVP em 2 semanas, Ana quer validar premissas primeiro"),
        InteracaoCreate(projeto_id=projeto.id, iniciador_id=ana.id, receptor_id=bruno.id,
                       tipo="convergencia", intensidade=0.8,
                       descricao="Acordo: 1 semana de validação + 2 semanas de construção"),
        InteracaoCreate(projeto_id=projeto.id, iniciador_id=bruno.id, receptor_id=ana.id,
                       tipo="impulso", intensidade=0.9,
                       descricao="Bruno apresenta protótipo funcional — Ana expande a visão"),
    ]

    for interacao in interacoes:
        registar_interacao(interacao)
    print(f"  ✓ {len(interacoes)} interações simuladas")

    lacuna_emb = gerar_embedding("facilitar conversas difíceis entre perfis muito diferentes")
    registar_lacuna(
        pessoa_id=bruno.id,
        descricao="Facilitar conversas difíceis entre perfis muito diferentes",
        embedding=lacuna_emb,
        urgencia="latente",
    )
    print("  ✓ Lacuna registada para Bruno")

    print("\nA correr inferência inicial...")
    for pessoa in pessoas_criadas.values():
        correr_inferencia_pessoa(pessoa.id)

    print(f"\nSeed completo — {len(PESSOAS)} pessoas, 1 projeto, {len(interacoes)} interações")
    print("\nTesta com:")
    print(f"  GET /sugestoes/{ana.id}")
    print(f"  GET /sugestoes/{francisco.id}")
    print(f"  GET /lacunas/{bruno.id}")

    DB.close()


if __name__ == "__main__":
    setup()
    seed()