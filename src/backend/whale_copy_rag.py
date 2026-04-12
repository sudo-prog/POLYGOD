"""
WhaleCopyRAG — God-tier whale copy-trading intelligence engine.

Uses PropertyGraphIndex for building a knowledge graph of whale entities,
strategies, and PnL patterns. Integrates with mem0 for long-term memory
and queries the graph for optimal whale strategies.
"""

import json
import logging

try:
    from llama_index.core import Document, PropertyGraphIndex, StorageContext
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from qdrant_client import AsyncQdrantClient

    HAS_LLAMA_INDEX = True
except ImportError:
    HAS_LLAMA_INDEX = False

try:
    from mem0 import Memory as _Mem0Memory  # mem0ai exports Memory, not Mem0
except ImportError:
    _Mem0Memory = None

from src.backend.config import settings
from src.backend.polymarket.client import polymarket_client

logger = logging.getLogger(__name__)

# Initialize Mem0
mem0 = None
if _Mem0Memory is not None:
    try:
        mem0_config = json.loads(settings.MEM0_CONFIG)
        mem0 = _Mem0Memory.from_config(mem0_config)
    except Exception as e:
        logger.warning(f"Mem0 initialization failed in WhaleCopyRAG: {e}")


class WhaleCopyRAG:
    """
    Whale Copy-Trade RAG engine — builds a Property Graph of whale entities
    and strategies, then queries for optimal patterns to inform POLYGOD's
    trading decisions.

    Graph structure:
        wallet → market → strategy → pnl
        wallet → fill_type → frequency → win_rate
    """

    def __init__(self):
        self._index = None
        self._qdrant_client = None

    async def _get_qdrant_client(self) -> "AsyncQdrantClient | None":
        """Get or create the Qdrant client for vector/graph storage."""
        if not HAS_LLAMA_INDEX:
            return None
        if self._qdrant_client is None:
            try:
                self._qdrant_client = AsyncQdrantClient(
                    url=getattr(settings, "QDRANT_URL", "http://qdrant:6333")
                )
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")
                return None
        return self._qdrant_client

    async def _get_index(self) -> "PropertyGraphIndex | None":
        """Load or create the PropertyGraphIndex for whale strategies."""
        if not HAS_LLAMA_INDEX:
            return None

        if self._index is None:
            try:
                qdrant = await self._get_qdrant_client()
                if qdrant is None:
                    return None

                vector_store = QdrantVectorStore(
                    client=qdrant,
                    collection_name="whale_fills",
                    aclient=qdrant,
                )
                storage_context = StorageContext.from_defaults(
                    vector_store=vector_store,
                )

                # Try to load existing index, or create empty one
                try:
                    self._index = PropertyGraphIndex.from_existing(
                        storage_context=storage_context,
                    )
                    logger.info("WhaleCopyRAG: loaded existing PropertyGraphIndex")
                except Exception:
                    # No existing index — create a new one with empty docs
                    self._index = PropertyGraphIndex.from_documents(
                        [],
                        storage_context=storage_context,
                    )
                    logger.info("WhaleCopyRAG: created new PropertyGraphIndex")
            except Exception as e:
                logger.error(f"WhaleCopyRAG: failed to init index: {e}")
                self._index = None

        return self._index

    async def _ingest_fills(self, fills: list[dict]) -> list["Document"]:
        """
        Convert fill data into Documents for graph ingestion.
        Each fill becomes a rich text document describing:
        - Wallet behavior
        - Trade direction
        - PnL outcome
        - Market context
        """
        documents = []
        for fill in fills:
            wallet = fill.get(
                "wallet", fill.get("taker_order", {}).get("maker_address", "unknown")
            )
            side = fill.get("side", fill.get("taker_order", {}).get("side", "unknown"))
            size = fill.get("size", 0)
            price = fill.get("price", 0)
            pnl = fill.get("pnl", 0)
            market_id = fill.get("market_id", fill.get("asset_id", "unknown"))
            timestamp = fill.get("timestamp", fill.get("match_time", ""))

            text = (
                f"Wallet {wallet} executed a {side} trade "
                f"with size {size} at price {price} "
                f"on market {market_id} with PnL {pnl} "
                f"at {timestamp}. "
                f"Strategy pattern: {'high-volume whale' if size > 1000 else 'small fish'} "
                f"{'profitable' if pnl > 0 else 'loss'} trade."
            )
            doc = Document(
                text=text,
                metadata={
                    "wallet": wallet,
                    "side": side,
                    "size": size,
                    "price": price,
                    "pnl": pnl,
                    "market_id": market_id,
                    "timestamp": str(timestamp),
                },
            )
            documents.append(doc)
        return documents

    async def enrich_state(self, state: dict) -> dict:
        """
        Enrich the POLYGOD graph state with whale copy-trading intelligence.

        Steps:
        1. Fetch recent fills for the current market
        2. Ingest fills into the PropertyGraphIndex
        3. Query for top profitable whale strategies in similar niches
        4. Inject whale_context into the state

        Returns the updated state with whale_context populated.
        """
        market_id = state.get("market_id", "")
        logger.info(f"WhaleCopyRAG: enriching state for market {market_id}")

        try:
            # Step 1: Fetch recent whale fills
            fills = await polymarket_client.get_recent_fills(market_id, limit=50)
            logger.info(f"WhaleCopyRAG: retrieved {len(fills)} fills")

            # Step 2: Build graph docs and ingest
            if fills:
                docs = await self._ingest_fills(fills)
                index = await self._get_index()
                if index is not None:
                    for doc in docs:
                        try:
                            index.insert(doc)
                        except Exception as e:
                            logger.debug(f"WhaleCopyRAG: insert failed for doc: {e}")
                    logger.info(
                        f"WhaleCopyRAG: ingested {len(docs)} whale fill documents"
                    )

            # Step 3: Query for top profitable strategies
            market_title = state.get("question", market_id)
            query = (
                f"Top profitable whale strategies and wallets for {market_title} "
                "and similar niche markets. What patterns lead to profits?"
            )

            whale_strategies = ""
            index = await self._get_index()
            if index is not None:
                try:
                    query_engine = index.as_query_engine()
                    response = await query_engine.aquery(query)
                    whale_strategies = str(response)
                    logger.info(
                        f"WhaleCopyRAG: query returned {len(whale_strategies)} chars"
                    )
                except Exception as e:
                    logger.debug(f"WhaleCopyRAG: query failed: {e}")

            # Fallback if no index or query failed
            if not whale_strategies and fills:
                profitable_fills = [f for f in fills if f.get("pnl", 0) > 0]
                whale_strategies = (
                    f"WhaleCopyRAG Summary: {len(fills)} fills analyzed, "
                    f"{len(profitable_fills)} profitable. "
                    f"{'Largest profitable fill: ' + str(profitable_fills[0]) if profitable_fills else 'No profitable fills found.'} "  # noqa: E501
                    "Install llama-index for full PropertyGraphIndex RAG capabilities."
                )
            elif not whale_strategies:
                whale_strategies = "No whale activity detected for this market."

            # Step 4: Inject into state
            state["whale_context"] = whale_strategies

            # Step 5: Store to mem0 for long-term memory
            if mem0:
                try:
                    mem0.add(
                        f"Whale RAG enriched for {market_id}: {whale_strategies[:300]}",
                        user_id="polygod_swarm",
                        metadata={"market_id": market_id, "fills_count": len(fills)},
                    )
                except Exception as e:
                    logger.debug(f"WhaleCopyRAG: mem0 add failed: {e}")

        except Exception as e:
            logger.error(f"WhaleCopyRAG: enrich_state failed: {e}")
            state["whale_context"] = f"WhaleCopyRAG error: {str(e)}"

        return state


# Singleton instance
whale_rag = WhaleCopyRAG()
