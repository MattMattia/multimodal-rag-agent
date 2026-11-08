"""S10: RAGEvaluationService metrics (hand-computed values) and POST /demo/evaluate."""

import math

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.demo_seeder import GOLDEN_FILENAMES
from app.services.evaluation import (
    GOLDEN_EVAL_QUERIES,
    RAGEvaluationService,
    hit_rate_at_k,
    is_relevant,
    mean,
    ndcg_at_k,
    reciprocal_rank,
)


@pytest.fixture
def http():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# --- metric formulas (binary relevance, results in rank order) ----------------------------------
def test_hit_rate_at_k():
    assert hit_rate_at_k([0, 0, 1, 0, 1], 5) == 1.0
    assert hit_rate_at_k([0, 0, 1, 0, 1], 2) == 0.0
    assert hit_rate_at_k([0, 0, 0], 3) == 0.0
    assert hit_rate_at_k([], 3) == 0.0


def test_reciprocal_rank_is_one_over_the_rank_of_the_first_relevant_result():
    assert reciprocal_rank([1, 0, 0]) == 1.0
    assert reciprocal_rank([0, 0, 1, 1]) == pytest.approx(1 / 3)
    assert reciprocal_rank([0, 0, 0]) == 0.0
    assert reciprocal_rank([]) == 0.0
    assert reciprocal_rank([0, 0, 1], k=2) == 0.0  # the first relevant result is beyond the cut-off


def test_mrr_is_the_mean_reciprocal_rank_over_queries():
    # queries with first relevant at rank 1, rank 2 and not found: (1 + 1/2 + 0) / 3 = 0.5
    assert mean([reciprocal_rank(r) for r in ([1, 0], [0, 1], [0, 0])]) == pytest.approx(0.5)
    assert mean([]) == 0.0


def test_ndcg_at_k_matches_hand_computed_values():
    # DCG@5 = 1/log2(4) + 1/log2(6) = 0.5 + 0.38685 ; IDCG@5 = 1/log2(2) + 1/log2(3) = 1 + 0.63093
    expected = (1 / math.log2(4) + 1 / math.log2(6)) / (1 / math.log2(2) + 1 / math.log2(3))
    assert expected == pytest.approx(0.54377, abs=1e-4)
    assert ndcg_at_k([0, 0, 1, 0, 1], 5) == pytest.approx(expected)
    # perfect ordering, nothing relevant, empty, and a cut-off that hides the only relevant hit
    assert ndcg_at_k([1, 1, 0], 3) == 1.0
    assert ndcg_at_k([0, 0, 0], 3) == 0.0
    assert ndcg_at_k([], 3) == 0.0
    assert ndcg_at_k([0, 1], 1) == 0.0
    # IDCG from the corpus: 3 relevant blocks exist, k=5 -> ideal = 1 + 1/log2(3) + 1/log2(4) = 2.13093
    # DCG@5 of [0,0,1,0,1] = 0.5 + 0.38685 = 0.88685 -> nDCG = 0.41617 (recall-aware, lower than 0.54377)
    assert ndcg_at_k([0, 0, 1, 0, 1], 5, total_relevant=3) == pytest.approx(0.41617, abs=1e-4)
    # one relevant block exists and it is ranked first -> perfect; ideal is capped at k
    assert ndcg_at_k([1, 0, 0], 3, total_relevant=1) == 1.0
    assert ndcg_at_k([1, 1], 2, total_relevant=10) == 1.0  # min(k, 10) = 2 relevant slots, both filled
    assert ndcg_at_k([1, 0], 2, total_relevant=2) == pytest.approx(1 / (1 + 1 / math.log2(3)))
    assert ndcg_at_k([0, 0], 2, total_relevant=0) == 0.0
    # [0,1,0,1] @4 -> DCG = 1/log2(3) + 1/log2(5) = 1.06161 ; IDCG = 1 + 1/log2(3) = 1.63093 ; nDCG = 0.65090
    assert ndcg_at_k([0, 1, 0, 1], 4) == pytest.approx(0.6509, abs=1e-4)


def test_is_relevant_requires_expected_document_and_a_keyword_in_content_or_parent():
    result = {"document_name": "a.pdf", "content": "ingresos", "parent_content": "contexto EBITDA 34%"}
    assert is_relevant(result, ["a.pdf"], ["ebitda"])  # case-insensitive, parent context counts
    assert not is_relevant(result, ["b.pdf"], ["ebitda"])
    assert not is_relevant(result, ["a.pdf"], ["latam"])
    assert is_relevant({"document_name": "a.pdf", "content": "x", "parent_content": None}, ["a.pdf"], [])


# --- dataset -----------------------------------------------------------------------------------
def test_golden_eval_queries_are_8_and_mapped_to_the_golden_corpus():
    assert len(GOLDEN_EVAL_QUERIES) == 8
    assert len({q["query"] for q in GOLDEN_EVAL_QUERIES}) == 8
    for q in GOLDEN_EVAL_QUERIES:
        assert q["query"] and q["expected_keywords"]
        assert q["expected_doc_filenames"] and set(q["expected_doc_filenames"]) <= set(GOLDEN_FILENAMES)
    assert set(GOLDEN_FILENAMES) == {f for q in GOLDEN_EVAL_QUERIES for f in q["expected_doc_filenames"]}
    assert {"text", "table", "security", "diagram"} <= {q["category"] for q in GOLDEN_EVAL_QUERIES}


def test_at_least_three_queries_are_paraphrased_or_cross_lingual():
    """No exact keyword of the expected answer may appear in the query (so BM25 cannot match it trivially)."""
    from app.services import lexical

    def overlaps(q):
        query_tokens = set(lexical.tokenize(q["query"]))
        return any(set(lexical.tokenize(k)) & query_tokens for k in q["expected_keywords"])

    assert sum(1 for q in GOLDEN_EVAL_QUERIES if not overlaps(q)) >= 3


# --- service + endpoint ------------------------------------------------------------------------
async def test_evaluate_endpoint_compares_three_modes_on_the_seeded_corpus(http, sqlite_db, demo_dirs):
    async with http as client:
        await client.post("/api/v1/demo/seed")
        resp = await client.post("/api/v1/demo/evaluate", json={"top_k": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["top_k"] == 5 and body["num_queries"] == 8
    assert body["embedding_mode"] == "mock"
    assert any("SHA-256" in w and "dense" in w and "hybrid" in w for w in body["warnings"])
    assert body["modes"]["sparse"]["semantic"] is True
    assert body["modes"]["dense"]["semantic"] is False and body["modes"]["hybrid"]["semantic"] is False
    assert set(body["modes"]) == {"dense", "sparse", "hybrid"}
    for name, mode in body["modes"].items():
        for metric in ("hit_rate_at_k", "mrr", "ndcg_at_k"):
            assert 0.0 <= mode[metric] <= 1.0, (name, metric)
        assert mode["avg_latency_ms"] >= 0.0
        assert len(mode["per_query"]) == 8
        row = mode["per_query"][0]
        assert {"id", "query", "category", "hit", "reciprocal_rank", "ndcg", "latency_ms", "relevances",
                "top_documents"} <= set(row)
    assert body["modes"]["sparse"]["hit_rate_at_k"] >= 0.5  # paraphrased queries: no longer trivially 1.0


async def test_evaluate_endpoint_returns_409_when_the_corpus_is_not_seeded(http, sqlite_db, demo_dirs):
    async with http as client:
        resp = await client.post("/api/v1/demo/evaluate")
    assert resp.status_code == 409
    assert "/api/v1/demo/seed" in resp.json()["detail"]


async def test_evaluate_validates_top_k(http):
    async with http as client:
        assert (await client.post("/api/v1/demo/evaluate", json={"top_k": 0})).status_code == 422
        assert (await client.post("/api/v1/demo/evaluate", json={"top_k": 99})).status_code == 422


async def test_service_aggregates_per_query_metrics(sqlite_db, demo_dirs):
    from app.core import database
    from app.services import demo_seeder

    await demo_seeder.seed_demo_corpus()
    async with database.AsyncSessionLocal() as db:
        report = await RAGEvaluationService().evaluate(db, top_k=3, modes=("sparse",))
    sparse = report["modes"]["sparse"]
    rows = sparse["per_query"]
    assert sparse["hit_rate_at_k"] == pytest.approx(mean([1.0 if r["hit"] else 0.0 for r in rows]))
    assert sparse["mrr"] == pytest.approx(mean([r["reciprocal_rank"] for r in rows]))
    assert sparse["ndcg_at_k"] == pytest.approx(mean([r["ndcg"] for r in rows]))
    assert all(len(r["relevances"]) <= 3 for r in rows)
