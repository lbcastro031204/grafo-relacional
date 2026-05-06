"""
Embeddings locais usando sentence-transformers.

Modelo escolhido: paraphrase-multilingual-MiniLM-L12-v2
- Suporta português nativamente
- 384 dimensões — leve e rápido
- Sem custo de API — corre em CPU

Os embeddings são a fundação do grafo:
- Embedding de valores (da descrição do projeto difícil)
- Embedding de competências (do que foi demonstrado)
- Embedding de desafios (de cada projeto)
"""

from functools import lru_cache
from sentence_transformers import SentenceTransformer
from config.settings import settings
import numpy as np


@lru_cache(maxsize=1)
def _modelo():
    """Carrega o modelo uma vez e mantém em memória."""
    print(f"[embeddings] A carregar modelo {settings.embedding_model}...")
    return SentenceTransformer(settings.embedding_model)


def gerar_embedding(texto: str) -> list[float]:
    """Gera embedding normalizado para um texto."""
    modelo = _modelo()
    vetor = modelo.encode(texto, normalize_embeddings=True)
    return vetor.tolist()


def similaridade_cosine(v1: list[float], v2: list[float]) -> float:
    """
    Cosine similarity entre dois vetores já normalizados.
    Retorna valor entre -1.0 e 1.0 (na prática 0.0–1.0 para textos).

    > 0.80 — muito semelhantes (mesmo universo de valores)
    > 0.65 — compatíveis (base suficiente para colaborar)
    < 0.40 — divergentes (tensão potencialmente produtiva)
    < 0.20 — muito divergentes (risco de incompatibilidade)
    """
    a = np.array(v1)
    b = np.array(v2)
    return float(np.dot(a, b))  # já normalizados, dot = cosine


def tensao_produtiva(emb_a: list[float], emb_b: list[float]) -> bool:
    """
    Retorna True se os embeddings têm diferença suficiente
    para gerar tensão criativa mas não são incompatíveis.
    Usado para detectar pares de competências complementares.
    """
    sim = similaridade_cosine(emb_a, emb_b)
    return 0.20 <= sim <= settings.limiar_tensao_produtiva