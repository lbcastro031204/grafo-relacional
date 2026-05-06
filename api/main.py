"""
API principal — interface HTTP para o grafo relacional.

Todos os endpoints são simples wrappers sobre os modelos e agentes.
A lógica de negócio vive nos agentes, não aqui.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from models.pessoa import criar_pessoa, obter_pessoa, listar_pessoas, PessoaCreate
from models.projeto import criar_projeto, obter_projeto, adicionar_participante, ProjetoCreate
from models.aresta import registar_interacao, InteracaoCreate
from agents.composicao import sugerir_colaboradores
from agents.inferencia import correr_inferencia_pessoa, correr_inferencia_projeto
from models.db import DB

app = FastAPI(
    title="Grafo Relacional — MVP",
    description="Infraestrutura de contexto relacional para conexão humana real.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "versao": "0.1.0"}


@app.get("/health")
def health():
    try:
        DB.run("RETURN 1")
        return {"neo4j": "ok"}
    except Exception as e:
        raise HTTPException(503, f"Neo4j indisponível: {e}")


# ─── Pessoas ──────────────────────────────────────────────────────────────────

@app.post("/pessoas", summary="Criar pessoa + gerar embedding de valores")
def post_pessoa(data: PessoaCreate):
    """
    Cria uma pessoa com mínimo absoluto.
    O embedding de valores é gerado automaticamente a partir
    da descrição do projeto difícil.
    """
    pessoa = criar_pessoa(data)
    return pessoa


@app.get("/pessoas", summary="Listar todas as pessoas")
def get_pessoas():
    return listar_pessoas()


@app.get("/pessoas/{pessoa_id}", summary="Perfil completo de uma pessoa")
def get_pessoa(pessoa_id: str):
    pessoa = obter_pessoa(pessoa_id)
    if not pessoa:
        raise HTTPException(404, "Pessoa não encontrada")
    return pessoa


# ─── Projetos ─────────────────────────────────────────────────────────────────

@app.post("/projetos", summary="Criar projeto + sugerir colaboradores automaticamente")
def post_projeto(data: ProjetoCreate):
    """
    Cria o projeto e imediatamente sugere com quem colaborar
    com base no desafio descrito.
    """
    projeto = criar_projeto(data)
    sugestoes = sugerir_colaboradores(
        pessoa_id=data.criador_id,
        descricao_desafio=data.descricao_desafio,
    )
    return {
        "projeto": projeto,
        "sugestoes_colaboradores": sugestoes,
    }


@app.get("/projetos/{projeto_id}", summary="Detalhes do projeto")
def get_projeto(projeto_id: str):
    projeto = obter_projeto(projeto_id)
    if not projeto:
        raise HTTPException(404, "Projeto não encontrado")
    return projeto


@app.post("/projetos/{projeto_id}/participantes/{pessoa_id}")
def post_participante(projeto_id: str, pessoa_id: str, papel: str = "colaborador"):
    """Adiciona uma pessoa a um projeto existente."""
    adicionar_participante(projeto_id, pessoa_id, papel)
    return {"status": "adicionado"}


# ─── Interações ───────────────────────────────────────────────────────────────

@app.post("/interacoes", summary="Registar interação entre pessoas num projeto")
def post_interacao(data: InteracaoCreate):
    """
    Cada interação alimenta o grafo:
    - Cria nó Momento com historial granular
    - Actualiza aresta COLABOROU_COM com peso acumulado
    - Dispara inferência para ambas as pessoas e o projeto
    """
    resultado = registar_interacao(data)

    # Inferência assíncrona (em produção: queue, aqui: síncrona)
    correr_inferencia_pessoa(data.iniciador_id)
    correr_inferencia_pessoa(data.receptor_id)
    correr_inferencia_projeto(data.projeto_id)

    return resultado


# ─── Sugestões (o coração do agente) ─────────────────────────────────────────

@app.get("/sugestoes/{pessoa_id}", summary="Com quem esta pessoa deve colaborar?")
def get_sugestoes(pessoa_id: str, desafio: str | None = None):
    """
    O endpoint mais importante — retorna sugestões de colaboração
    com explicação da tensão produtiva específica.

    Parâmetro opcional `desafio`: descrição do desafio actual,
    afina as sugestões para o contexto específico.
    """
    resultado = sugerir_colaboradores(
        pessoa_id=pessoa_id,
        descricao_desafio=desafio,
    )
    return resultado


@app.get("/lacunas/{pessoa_id}", summary="Lacunas detectadas e quem as preenche")
def get_lacunas(pessoa_id: str):
    """
    Retorna lacunas detectadas no perfil desta pessoa
    e, para cada uma, quem na rede poderia preenchê-la.
    """
    from queries.cypher import lacunas_de_pessoa, pessoas_com_embedding
    from models.embeddings import similaridade_cosine

    lacunas = lacunas_de_pessoa(pessoa_id)
    todas_pessoas = pessoas_com_embedding()

    resultado = []
    for lacuna in lacunas:
        emb_lacuna = lacuna.get("embedding")
        if not emb_lacuna:
            continue

        matches = []
        for pessoa in todas_pessoas:
            if pessoa["id"] == pessoa_id:
                continue
            # Comparar embedding da lacuna com embedding de valores da pessoa
            # (aproximação: pessoas com valores no domínio da lacuna)
            sim = similaridade_cosine(emb_lacuna, pessoa["embedding"])
            if sim > 0.55:
                matches.append({
                    "pessoa_id": pessoa["id"],
                    "pessoa_nome": pessoa["nome"],
                    "relevancia": round(sim, 3),
                })

        matches.sort(key=lambda x: x["relevancia"], reverse=True)
        resultado.append({
            "lacuna": lacuna["descricao"],
            "urgencia": lacuna["urgencia"],
            "potenciais_respostas": matches[:3],
        })

    return {"pessoa_id": pessoa_id, "lacunas": resultado}