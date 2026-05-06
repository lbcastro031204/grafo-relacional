# Grafo Relacional

> Uma infraestrutura de IA para criar conexão humana real — remodelando como as pessoas se descobrem, constroem relações significativas e colaboram para desbloquear novas oportunidades.

---

## A ideia

As plataformas actuais conectam pessoas por interesses superficiais ou currículos. Este projecto parte de uma premissa diferente:

**A conexão humana profunda não emerge de perfis declarados — emerge de comportamento observado ao longo do tempo.**

O Grafo Relacional é a infraestrutura base para construir agentes de IA que:

- Detectam **tensões produtivas** entre pessoas — não semelhanças, mas diferenças específicas que geram alquimia criativa
- Observam **padrões de colaboração** sem perguntar nada directamente
- Identificam **janelas de abertura** — momentos em que alguém está receptivo a novas conexões
- Sugerem **com quem colaborar e porquê** — com explicação da tensão específica que vai gerar algo novo
- Mapeiam **lacunas** de cada perfil e quem na rede as preenche

Não é um sistema de recomendação. É um grafo vivo que aprende como as pessoas realmente se relacionam.

---

## Estado actual — MVP

Este repositório é o MVP funcional. Está operacional e pode ser corrido localmente hoje.

O que está construído:

- **Grafo Neo4j** com 6 tipos de nó (Pessoa, Projeto, Momento, Competência, Lacuna, Organização) e arestas temporais com peso que evolui
- **Embeddings locais** via `sentence-transformers` — sem custo de API, suporte nativo a português
- **Agente de composição** — dado um desafio, sugere quem deve colaborar e explica a tensão produtiva específica
- **Agente de inferência** — actualiza perfis por observação de comportamento, não por formulários
- **Agente de janela** — detecta quando uma pessoa está num momento de transição e mais receptiva a novas conexões
- **API REST** com FastAPI — 6 endpoints principais
- **Frontend** em HTML/CSS/JS puro — sem framework, zero dependências de build

O que ainda não está:

- Autenticação e multi-tenant
- Endpoint de listagem de projectos
- Notificações e sugestões proactivas
- Dashboard de métricas de rede
- Deploy em produção

---

## Arranque (Windows)

```powershell
# 1. Neo4j via Docker (tudo numa linha)
docker run -d --name neo4j-relacional -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password123 neo4j:5

# 2. Ambiente Python
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Configuração
Copy-Item .env.example .env

# 4. Seed — cria schema, índices e 6 perfis de exemplo
python seed/seed_data.py

# 5. API
uvicorn api.main:app --reload

# 6. Frontend — abre frontend.html directamente no browser
```

API disponível em `http://localhost:8000/docs`

## Arranque (Mac / Linux)

```bash
# 1. Neo4j via Docker
docker run -d --name neo4j-relacional \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password123 neo4j:5

# 2. Ambiente Python
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Configuração
cp .env.example .env

# 4. Seed
python seed/seed_data.py

# 5. API
uvicorn api.main:app --reload
```

---

## Arquitectura

```
grafo-relacional/
│
├── models/                  — nós e arestas do grafo
│   ├── pessoa.py            — nó central: perfil + embedding de valores
│   ├── projeto.py           — contexto onde as colaborações acontecem
│   ├── aresta.py            — interações, competências, lacunas
│   ├── embeddings.py        — modelo local sentence-transformers
│   └── db.py                — conexão Neo4j (singleton)
│
├── agents/                  — os três agentes activos
│   ├── composicao.py        — sugere com quem colaborar + explica porquê
│   ├── inferencia.py        — actualiza o grafo por observação contínua
│   └── janela.py            — detecta momentos de abertura relacional
│
├── queries/
│   └── cypher.py            — queries Cypher reutilizáveis + cálculo de complementaridade
│
├── api/
│   └── main.py              — FastAPI: 6 endpoints REST
│
├── seed/
│   ├── setup_schema.py      — constraints, índices, índices vectoriais Neo4j
│   └── seed_data.py         — 6 perfis reais com tensões complementares
│
├── config/
│   └── settings.py          — configuração via pydantic-settings
│
├── frontend.html            — interface completa (zero dependências de build)
├── .env.example
└── requirements.txt
```

### Os três agentes

**`composicao.py`** — dado um perfil (e opcionalmente um desafio), calcula complementaridade entre todos os candidatos disponíveis. Usa cosine similarity entre embeddings de valores (base mínima de 0.65) e detecta tensões produtivas entre competências (similaridade entre 0.20 e 0.40 — diferentes o suficiente para gerar faísca, semelhantes o suficiente para não ser incompatibilidade). Retorna top 3 com explicação em linguagem natural.

**`inferencia.py`** — corre após cada interação registada. Infere estilo de pensamento (linear / associativo / sistémico) a partir do padrão de iniciação de interacções. Infere tolerância à ambiguidade a partir do comportamento em fases de fricção. Calcula multiplicador de rede. Chama o agente de janela para actualizar disponibilidade.

**`janela.py`** — detecta 5 sinais independentes: projecto recentemente integrado, energia baixa em projecto activo, inactividade prolongada, bloqueio criativo declarado, pessoa nova sem historial. Classifica urgência em `imediata / activa / latente / fechada`.

### O grafo

Cada pessoa começa com 3 campos e 1 embedding. Com 2-3 projectos, o grafo tem densidade suficiente para sugestões úteis. Com 20+ pessoas e 10+ projectos, começa a revelar padrões que ninguém consegue ver manualmente — conectores silenciosos, tensões que tendem a gerar os resultados mais inesperados, lacunas estruturais entre grupos que nunca se cruzaram.

O princípio central: **nada é recolhido por formulário**. Tudo emerge de comportamento observado.

---

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Health check básico |
| GET | `/health` | Verifica conexão Neo4j |
| POST | `/pessoas` | Criar pessoa + gerar embedding de valores |
| GET | `/pessoas` | Listar todos os perfis |
| GET | `/pessoas/{id}` | Perfil completo com contagens |
| POST | `/projetos` | Criar projecto + sugestões automáticas |
| GET | `/projetos/{id}` | Detalhes do projecto |
| POST | `/projetos/{id}/participantes/{pid}` | Adicionar participante |
| POST | `/interacoes` | Registar interação (alimenta o grafo + dispara inferência) |
| GET | `/sugestoes/{id}` | Com quem esta pessoa deve colaborar (+ desafio opcional) |
| GET | `/lacunas/{id}` | Lacunas detectadas + quem na rede as preenche |

---

## Contribuir

Este projecto está no início. O que mais precisa agora:

**Código**
- `GET /projetos` — endpoint de listagem de projectos (para o select do frontend)
- Autenticação simples (API key por organização)
- Testes unitários para os agentes
- Deploy com Docker Compose (Neo4j + API + serve do frontend)

**Dados e validação**
- Testar com pessoas reais e validar se as sugestões fazem sentido
- Calibrar os limiares de similaridade (0.65 para valores, 0.40 para tensão) com dados reais
- Perceber se o agente de janela detecta bem os momentos de abertura

**Produto**
- Notificações proactivas ("há alguém no grafo que preenche a tua lacuna")
- Dashboard de métricas de rede (quem são os conectores, que lacunas estruturais existem)
- Exportação do grafo para visualização em Gephi ou similar

**Ideias maiores**
- Agente de serendipidade — cruzar pessoas de projectos diferentes que estão a resolver problemas complementares
- Agente de reputação relacional — reputação baseada em como te relacionas, não no que declaras
- Privacidade diferencial — os embeddings já são vectores irreversíveis, mas há mais a fazer

Se exploraste isto e tens uma perspectiva diferente sobre qualquer um destes problemas, abre uma issue. O projecto interessa-me mais como conversa do que como código.

---

## Stack

| Componente | Tecnologia | Porquê |
|------------|------------|--------|
| Grafo | Neo4j 5 | Cypher maduro, índices vectoriais nativos, GDS para algoritmos de rede |
| Embeddings | sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` | Suporte a português, 384 dimensões, sem custo de API, corre em CPU |
| API | FastAPI + Python | Rápido de iterar, integração nativa com Neo4j |
| Frontend | HTML/CSS/JS puro | Zero dependências de build, abre directamente no browser |
| Configuração | pydantic-settings | Type-safe, lê .env automaticamente |

---

## Contexto

Este projecto nasceu de uma exploração sobre que agentes de IA ainda não foram criados para facilitar conexão humana real. A premissa de partida: as ferramentas existentes optimizam para eficiência e métricas fáceis de medir — e destroem o que é impossível de medir.

Os seis agentes explorados na origem deste projecto:

1. **Afinidade profunda** — vai além de interesses declarados
2. **Vulnerabilidade calibrada** — cria intimidade psicológica segura
3. **Serendipidade intencional** — encontros que parecem acaso mas foram calculados ← *o mais poderoso*
4. **Co-criação guiada** — orquestra a alquimia criativa entre pessoas ← *este repositório*
5. **Reputação relacional** — confiança baseada em como te relacionas
6. **Legado de conexões** — preserva redes de impacto humano

Este MVP é a fundação. O grafo que se constrói aqui é a infraestrutura de contexto que torna os outros cinco possíveis.

---

*Construído em Portugal. Questões em português são bem-vindas.*
