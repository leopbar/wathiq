"""Azure AI Search: the policy retriever, in Azure mode.

Returns the same `Retrieved` objects as the pgvector retriever in `rag/index.py`, so the
findings panel, the citations and the few-shot selector do not change at all. Only where the
nearest chunk is found changes.

**The index is built from the same corpus.** `rag/chunking.py` already splits the synthetic
policy pack into cited sections; this module uploads those exact chunks, with the same
citation, heading and text. There is no second copy of the policy content and no second
chunking strategy — which is the point of putting the retriever behind an interface in M3.

**Hybrid search, not pure vector.** The query carries both the embedding and the original
words, and the service combines them with reciprocal rank fusion. That matters here: a policy
lookup often contains an exact token — a citation like `§4.2`, a licence type, a rule code —
and a pure vector search is precisely the thing that loses exact tokens. Keyword search alone
would miss "lapsed" against "expired". Together they cover each other. (DECISIONS #70)

**This adapter is written and tested, but the demo deployment does not use it.** The free AI
Search tier is one service per subscription and it was already taken, so switching Wathiq to
Azure AI Search would mean paying for a Basic service to do what the pgvector retriever
already does correctly. The pgvector retriever stays the default; set
`WATHIQ_AZURE_SEARCH_ENDPOINT` and this takes over. (DECISIONS #71)
"""

from __future__ import annotations

import logging
from typing import Any

from app.azure.credentials import credential_for, describe_credential, require_sdk
from app.core.config import settings
from app.rag.chunking import load_corpus
from app.rag.embedder import get_embedder
from app.rag.index import MIN_SIMILARITY, Retrieved

logger = logging.getLogger(__name__)

# The vector field's profile name. Only referenced when the index is created.
_VECTOR_PROFILE = "wathiq-vector-profile"
_VECTOR_ALGORITHM = "wathiq-hnsw"


def _client() -> Any:
    module = require_sdk("azure.search.documents", "Azure AI Search")
    return module.SearchClient(
        endpoint=settings.azure_search_endpoint.strip(),
        index_name=settings.azure_search_index,
        credential=credential_for(settings.azure_search_key, "Azure AI Search"),
    )


def _index_client() -> Any:
    module = require_sdk("azure.search.documents.indexes", "Azure AI Search")
    return module.SearchIndexClient(
        endpoint=settings.azure_search_endpoint.strip(),
        credential=credential_for(settings.azure_search_key, "Azure AI Search"),
    )


def _document_key(citation: str) -> str:
    """A key Azure AI Search accepts.

    Keys may only contain letters, digits, underscore, dash and equals — and a citation like
    `POL-KYC-001 §4.2` contains neither an acceptable space nor an acceptable section sign. The
    citation itself is kept in its own field, so nothing is lost by encoding the key.
    """
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in citation)


def ensure_index() -> None:
    """Create the index if it does not exist. Idempotent.

    The schema mirrors the `policy_chunks` table: same fields, same meanings. `citation` is
    filterable so an exact lookup stays an exact lookup rather than becoming a search.
    """
    indexes = require_sdk("azure.search.documents.indexes", "Azure AI Search")
    models_module = require_sdk("azure.search.documents.indexes.models", "Azure AI Search")
    del indexes

    client = _index_client()
    existing = {index.name for index in client.list_indexes()}
    if settings.azure_search_index in existing:
        return

    dimensions = get_embedder().dimensions
    index = models_module.SearchIndex(
        name=settings.azure_search_index,
        fields=[
            models_module.SimpleField(
                name="id", type="Edm.String", key=True, filterable=True
            ),
            models_module.SimpleField(
                name="citation", type="Edm.String", filterable=True, sortable=True
            ),
            models_module.SimpleField(name="policy_id", type="Edm.String", filterable=True),
            models_module.SearchableField(name="policy_title", type="Edm.String"),
            models_module.SimpleField(name="section", type="Edm.String", filterable=True),
            models_module.SearchableField(name="heading", type="Edm.String"),
            models_module.SearchableField(name="text", type="Edm.String"),
            models_module.SearchField(
                name="embedding",
                type="Collection(Edm.Single)",
                searchable=True,
                vector_search_dimensions=dimensions,
                vector_search_profile_name=_VECTOR_PROFILE,
            ),
        ],
        vector_search=models_module.VectorSearch(
            algorithms=[models_module.HnswAlgorithmConfiguration(name=_VECTOR_ALGORITHM)],
            profiles=[
                models_module.VectorSearchProfile(
                    name=_VECTOR_PROFILE, algorithm_configuration_name=_VECTOR_ALGORITHM
                )
            ],
        ),
    )
    client.create_index(index)
    logger.info("azure search: created index %s (%d dimensions)", index.name, dimensions)


def rebuild() -> int:
    """Upload every chunk of the policy corpus. Returns the number uploaded.

    `merge_or_upload`, so re-running it replaces each chunk in place rather than duplicating
    it — the same idempotence `rag/index.rebuild()` gets from deleting the table first.
    """
    ensure_index()
    embedder = get_embedder()
    chunks = load_corpus()

    payload = [
        {
            "id": _document_key(chunk.citation),
            "citation": chunk.citation,
            "policy_id": chunk.policy_id,
            "policy_title": chunk.policy_title,
            "section": chunk.section,
            "heading": chunk.heading,
            "text": chunk.text,
            "embedding": embedder.embed(chunk.embedding_text),
        }
        for chunk in chunks
    ]
    if payload:
        _client().merge_or_upload_documents(documents=payload)
    logger.info("azure search: indexed %d chunk(s) with %s", len(payload), embedder.version)
    return len(payload)


def _to_retrieved(document: dict[str, Any], similarity: float) -> Retrieved:
    return Retrieved(
        citation=str(document.get("citation", "")),
        policy_id=str(document.get("policy_id", "")),
        policy_title=str(document.get("policy_title", "")),
        section=str(document.get("section", "")),
        heading=str(document.get("heading", "")),
        text=str(document.get("text", "")),
        similarity=round(similarity, 4),
    )


def by_citation(citation: str) -> Retrieved | None:
    """The exact section a rule cites — a filter, not a search."""
    results = list(
        _client().search(
            search_text="*",
            filter=f"citation eq '{citation.strip()}'",
            top=1,
        )
    )
    return _to_retrieved(results[0], 1.0) if results else None


def search(query: str, limit: int = 3) -> list[Retrieved]:
    """Nearest policy sections, by hybrid keyword + vector search."""
    vector = get_embedder().embed(query)
    if not any(vector):
        return []

    models_module = require_sdk("azure.search.documents.models", "Azure AI Search")
    top = max(1, min(limit, 20))
    results = _client().search(
        search_text=query,
        vector_queries=[
            models_module.VectorizedQuery(
                vector=vector, k_nearest_neighbors=top, fields="embedding"
            )
        ],
        top=top,
    )

    retrieved: list[Retrieved] = []
    for document in results:
        # `@search.score` from a hybrid query is a fused rank score, NOT a cosine similarity,
        # so it must not be compared against `MIN_SIMILARITY` as though it were one. We
        # recompute the cosine against the stored vector, which is the number the rest of the
        # system means by "similarity" and the number the UI displays.
        score = _cosine_against(vector, document.get("embedding"))
        if score is None or score >= MIN_SIMILARITY:
            retrieved.append(_to_retrieved(dict(document), score if score is not None else 0.0))
    return retrieved[:top]


def _cosine_against(query: list[float], stored: Any) -> float | None:
    """Cosine similarity to the stored vector, or `None` if it was not returned."""
    if not isinstance(stored, list) or not stored:
        return None
    from app.rag.embedder import cosine

    return cosine(query, [float(value) for value in stored])


def label() -> str:
    auth = describe_credential(settings.azure_search_key)
    return f"Azure AI Search ({settings.azure_search_index}, hybrid, {auth})"


__all__ = ["by_citation", "ensure_index", "label", "rebuild", "search"]
