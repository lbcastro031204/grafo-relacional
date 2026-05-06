"""
Setup do schema Neo4j — corre uma vez antes de começar.

Cria:
- Constraints de unicidade (evita duplicados)
- Índices para queries rápidas
- Índice vectorial para similaridade de embeddings (Neo4j 5+)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.db import DB
from config.settings import settings


def setup():
    print("A criar schema Neo4j...")

    # ─── Constraints de unicidade ──────────────────────────────────────────────
    constraints = [
        "CREATE CONSTRAINT pessoa_id IF NOT EXISTS FOR (p:Pessoa) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT pessoa_email IF NOT EXISTS FOR (p:Pessoa) REQUIRE p.email IS UNIQUE",
        "CREATE CONSTRAINT projeto_id IF NOT EXISTS FOR (p:Projeto) REQUIRE p.id IS UNIQUE",
        "CREATE CONSTRAINT momento_id IF NOT EXISTS FOR (m:Momento) REQUIRE m.id IS UNIQUE",
        "CREATE CONSTRAINT competencia_nome IF NOT EXISTS FOR (c:Competencia) REQUIRE c.nome IS UNIQUE",
        "CREATE CONSTRAINT lacuna_id IF NOT EXISTS FOR (l:Lacuna) REQUIRE l.id IS UNIQUE",
    ]

    for c in constraints:
        try:
            DB.run(c)
            print(f"  ✓ {c[:60]}...")
        except Exception as e:
            print(f"  ~ já existe: {e}")

    # ─── Índices para queries frequentes ──────────────────────────────────────
    indices = [
        "CREATE INDEX pessoa_janela IF NOT EXISTS FOR (p:Pessoa) ON (p.janela_abertura)",
        "CREATE INDEX pessoa_estilo IF NOT EXISTS FOR (p:Pessoa) ON (p.estilo_pensamento)",
        "CREATE INDEX projeto_fase IF NOT EXISTS FOR (p:Projeto) ON (p.fase_atual)",
        "CREATE INDEX momento_tipo IF NOT EXISTS FOR (m:Momento) ON (m.tipo)",
        "CREATE INDEX momento_timestamp IF NOT EXISTS FOR (m:Momento) ON (m.timestamp)",
        "CREATE INDEX competencia_tipo IF NOT EXISTS FOR (c:Competencia) ON (c.tipo)",
        "CREATE INDEX lacuna_urgencia IF NOT EXISTS FOR (l:Lacuna) ON (l.urgencia)",
        "CREATE INDEX lacuna_resolvida IF NOT EXISTS FOR (l:Lacuna) ON (l.resolvida)",
    ]

    for idx in indices:
        try:
            DB.run(idx)
            print(f"  ✓ {idx[:60]}...")
        except Exception as e:
            print(f"  ~ já existe: {e}")

    # ─── Índice vectorial para embeddings (Neo4j 5.11+) ───────────────────────
    # Permite queries de similaridade directamente no grafo (sem Weaviate externo)
    vector_indices = [
        f"""
        CREATE VECTOR INDEX pessoa_valores_idx IF NOT EXISTS
        FOR (p:Pessoa) ON p.valores_embedding
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {settings.embedding_dim},
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """,
        f"""
        CREATE VECTOR INDEX competencia_embedding_idx IF NOT EXISTS
        FOR (c:Competencia) ON c.embedding
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {settings.embedding_dim},
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """,
        f"""
        CREATE VECTOR INDEX lacuna_embedding_idx IF NOT EXISTS
        FOR (l:Lacuna) ON l.descricao_embedding
        OPTIONS {{
            indexConfig: {{
                `vector.dimensions`: {settings.embedding_dim},
                `vector.similarity_function`: 'cosine'
            }}
        }}
        """,
    ]

    for vidx in vector_indices:
        try:
            DB.run(vidx)
            print(f"  ✓ Índice vectorial criado")
        except Exception as e:
            print(f"  ~ Índice vectorial: {e} (requer Neo4j 5.11+)")

    print("\nSchema pronto.")
    DB.close()


if __name__ == "__main__":
    setup()