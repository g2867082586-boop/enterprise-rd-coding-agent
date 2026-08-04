from app.rag.indexer import _metadata, build_index, search, split_text


def test_splitter_has_overlap_and_bounds() -> None:
    chunks = split_text("星云商城" * 200, chunk_size=100, overlap=20)
    assert len(chunks) > 2
    assert all(len(chunk) <= 100 for chunk in chunks)


def test_pdf_title_uses_filename_not_hash_prefixed_extracted_code(tmp_path) -> None:
    path = tmp_path / "神经网络-辅助资料.pdf"
    path.write_bytes(b"placeholder")

    metadata = _metadata(path, "enterprise", "# params = 3 here\nnetwork notes")

    assert metadata["title"] == "神经网络-辅助资料"


def test_search_has_source_and_explicit_retrieval_mode(tmp_path) -> None:
    build_index(output_path=tmp_path / "index.json")
    from app.config import get_settings

    settings = get_settings()
    original = settings.knowledge_index_path
    settings.knowledge_index_path = str(tmp_path / "index.json")
    try:
        results = search("ORDER002 库存预占超时", top_k=2, corpus_type="mock")
    finally:
        settings.knowledge_index_path = original
    assert results[0]["source"]
    assert results[0]["retrieval_mode"] in {"tfidf_fallback", "local_semantic", "openai_compatible"}
    assert "ORDER002" in results[0]["snippet"]
