from __future__ import annotations

from langchain_core.embeddings import Embeddings

from app.config.settings import Settings


def get_embeddings(settings:Settings)->Embeddings:
    raise NotImplementedError("embeddings provider lands with doc-rag")
