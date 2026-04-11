"""
F1 AI Race Engineer — FAISS Retriever

Builds and queries FAISS vector indices from processed stint chunks.
Uses Google Gemini text-embedding-004 (768 dims) for embeddings.

Architecture:
- One FAISS index per {year}_{race}_{session} (keeps indices small ~50 chunks)
- Uses IndexFlatIP (inner product on L2-normalized vectors = cosine similarity)
- Persistence: faiss.write_index / faiss.read_index — rebuild only when new data arrives

Usage:
    from src.retrieval.retriever import Retriever

    retriever = Retriever()
    results = retriever.query("Verstappen tyre strategy", chunks, top_k=8)
"""

import time
import json
import logging
from pathlib import Path
import numpy as np
import faiss
# from google import genai
from sentence_transformers import SentenceTransformer
from config import config

logger = logging.getLogger(__name__)


class Retriever:
    """FAISS-based vector retriever for F1 stint chunks."""

    def __init__(self):
        # self._client = genai.Client(api_key=config.GOOGLE_API_KEY)
        # self._dimension = config.EMBEDDING_DIMENSIONS
        self._model = SentenceTransformer(config.EMBEDDING_MODEL)
        self._dimension = config.EMBEDDING_DIMENSIONS  # 384

    # ──────────────────────────────────────────
    # Embedding generation
    # ──────────────────────────────────────────

    def _embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        Generate embeddings for a list of texts using sentence-transformers (local).

        Returns:
            np.ndarray of shape (len(texts), 384), dtype float32, L2-normalized.
        """
        # all_embeddings = []
        # batch_size = 100
        #
        # for i in range(0, len(texts), batch_size):
        #     batch = texts[i : i + batch_size]
        #     response = self._client.models.embed_content(
        #         model=config.EMBEDDING_MODEL,
        #         contents=batch,
        #         config={
        #             "task_type": "RETRIEVAL_DOCUMENT",
        #         },
        #     )
        #     for embedding in response.embeddings:
        #         all_embeddings.append(embedding.values)
        #
        # embeddings = np.array(all_embeddings, dtype="float32")
        #
        # # L2-normalize for cosine similarity via inner product
        # norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        # norms[norms == 0] = 1  # Avoid division by zero
        # embeddings = embeddings / norms
        #
        # return embeddings

        embeddings = self._model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True,   # L2-normalize built-in
            convert_to_numpy=True,
        ).astype("float32")
        return embeddings

    def _embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string. Returns (1, 384) array, L2-normalized."""
        # response = self._client.models.embed_content(
        #     model=config.EMBEDDING_MODEL,
        #     contents=query,
        #     config={
        #         "task_type": "RETRIEVAL_QUERY",
        #     },
        # )
        # embedding = np.array([response.embeddings[0].values], dtype="float32")
        #
        # # L2-normalize
        # norm = np.linalg.norm(embedding)
        # if norm > 0:
        #     embedding = embedding / norm
        #
        # return embedding

        embedding = self._model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype("float32")
        return embedding

    # ──────────────────────────────────────────
    # Index management
    # ──────────────────────────────────────────

    def _index_path(self, year: int, race: str, session_type: str) -> Path:
        """Get the file path for a persisted FAISS index."""
        race_slug = race.lower().replace(" ", "_").replace("grand_prix", "gp")
        return config.FAISS_DIR / f"{year}_{race_slug}_{session_type}.index"

    def _metadata_path(self, year: int, race: str, session_type: str) -> Path:
        """Get the file path for the chunk metadata mapping."""
        race_slug = race.lower().replace(" ", "_").replace("grand_prix", "gp")
        return config.FAISS_DIR / f"{year}_{race_slug}_{session_type}_meta.json"

    def build_index(
        self,
        chunks: list[dict],
        year: int,
        race: str,
        session_type: str,
    ) -> tuple[faiss.Index, list[dict]]:
        """
        Build a FAISS index from processed chunks and persist to disk.

        Args:
            chunks: List of chunk dicts with 'text' and 'metadata' keys.
            year, race, session_type: For persistence path naming.

        Returns:
            (faiss_index, chunks) tuple.
        """
        t_start = time.perf_counter()

        texts = [chunk["text"] for chunk in chunks]
        logger.info(f"Embedding {len(texts)} chunks...")

        embeddings = self._embed_texts(texts)

        # Build FAISS index (inner product = cosine similarity on normalized vectors)
        index = faiss.IndexFlatIP(self._dimension)
        index.add(embeddings)

        t_elapsed = time.perf_counter() - t_start
        logger.info(f"Built FAISS index ({index.ntotal} vectors) in {t_elapsed:.2f}s")

        # Persist index
        index_path = self._index_path(year, race, session_type)
        faiss.write_index(index, str(index_path))

        # Persist chunk metadata (for retrieval — we need text + metadata back)
        meta_path = self._metadata_path(year, race, session_type)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Index persisted to {index_path}")

        return index, chunks

    def load_index(
        self, year: int, race: str, session_type: str
    ) -> tuple[faiss.Index, list[dict]] | None:
        """
        Load a persisted FAISS index from disk.

        Returns (index, chunks) or None if not found.
        """
        index_path = self._index_path(year, race, session_type)
        meta_path = self._metadata_path(year, race, session_type)

        if not index_path.exists() or not meta_path.exists():
            return None

        index = faiss.read_index(str(index_path))

        with open(meta_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        logger.info(
            f"Loaded persisted index: {index.ntotal} vectors from {index_path}"
        )
        return index, chunks

    def load_or_build(
        self,
        chunks: list[dict],
        year: int,
        race: str,
        session_type: str,
    ) -> tuple[faiss.Index, list[dict]]:
        """
        Load existing FAISS index or build a new one.

        Checks disk first. If index exists, loads it. Otherwise builds from chunks.
        """
        result = self.load_index(year, race, session_type)
        if result is not None:
            return result

        logger.info("No persisted index found. Building new index...")
        return self.build_index(chunks, year, race, session_type)

    # ──────────────────────────────────────────
    # Query
    # ──────────────────────────────────────────

    def query(
        self,
        query_text: str,
        index: faiss.Index,
        chunks: list[dict],
        top_k: int | None = None,
    ) -> list[dict]:
        """
        Search the FAISS index for the most relevant chunks.

        Args:
            query_text: The search query (natural language).
            index: The FAISS index to search.
            chunks: The chunk metadata list (parallel to index vectors).
            top_k: Number of results to return. Defaults to config.TOP_K.

        Returns:
            List of dicts, each with:
                - chunk: the original chunk dict (text + metadata)
                - score: float cosine similarity score
        """
        if top_k is None:
            top_k = config.TOP_K

        # Clamp top_k to index size
        top_k = min(top_k, index.ntotal)

        t_start = time.perf_counter()

        query_embedding = self._embed_query(query_text)
        distances, indices = index.search(query_embedding, top_k)

        t_elapsed = time.perf_counter() - t_start

        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(chunks):
                continue
            results.append({
                "chunk": chunks[idx],
                "score": float(distances[0][i]),
            })

        if results:
            logger.info(
                f"Retrieved {len(results)} chunks in {t_elapsed:.3f}s "
                f"(top score: {results[0]['score']:.4f})"
            )
        else:
            logger.info(f"Retrieved 0 chunks in {t_elapsed:.3f}s")

        return results
