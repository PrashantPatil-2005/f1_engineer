"""
MCP Server — Semantic Search Tool

Vector search through processed race data chunks via FAISS.
"""

import json
import logging

logger = logging.getLogger(__name__)


async def search_race_data_tool(
    year: int,
    race: str,
    query: str,
    session_type: str = "R",
    top_k: int = 5,
) -> str:
    """Semantic search through processed race data chunks."""
    try:
        from src.data_loader.load_race import load_session
        from src.data_processor.process_data import load_chunks, process_session, save_chunks
        from src.retrieval.retriever import Retriever

        # Load or build chunks
        chunks = load_chunks(year, race, session_type)
        if chunks is None:
            session_data = load_session(year, race, session_type)
            chunks = process_session(session_data)
            save_chunks(chunks, year, race, session_type)

        # Build or load FAISS index and query
        retriever = Retriever()
        index, indexed_chunks = retriever.load_or_build(
            chunks, year, race, session_type
        )
        results = retriever.query(query, index, indexed_chunks, top_k=top_k)

        matches = []
        for item in results:
            matches.append({
                "text": item["chunk"]["text"],
                "score": round(item["score"], 4),
                "metadata": item["chunk"].get("metadata", {}),
            })

        return json.dumps({
            "query": query,
            "year": year,
            "race": race,
            "session_type": session_type,
            "results": matches,
        })
    except Exception as e:
        logger.error(f"search_race_data_tool failed: {e}")
        return json.dumps({"error": str(e), "tool": "search_race_data"})
