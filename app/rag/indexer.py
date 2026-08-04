import csv
import hashlib
import json
import math
import re
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer

from app.config import ROOT_DIR, get_settings
from app.rag.embeddings import get_embedding_provider


SUPPORTED_SUFFIXES = {".md", ".txt", ".json", ".csv", ".pdf", ".docx"}


class IndexCompatibilityError(RuntimeError):
    pass


def _safe_source(path: Path) -> str:
    try:
        return path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return f"external/{path.name}"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_text(text: str, chunk_size: int = 420, overlap: int = 60) -> list[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return []
    chunks, start = [], 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = end - overlap
    return chunks


def _read_document(path: Path) -> tuple[str, str | None]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8"), None
    if suffix == ".json":
        return json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False, indent=2), None
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        return "\n".join(" | ".join(row) for row in rows), None
    if suffix == ".docx":
        doc = Document(path)
        return "\n".join(paragraph.text for paragraph in doc.paragraphs), None
    if suffix == ".pdf":
        reader = PdfReader(path)
        if len(reader.pages) > get_settings().max_pdf_pages:
            return "", f"PDF 超过 {get_settings().max_pdf_pages} 页限制"
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        if not clean_text(extracted):
            try:
                import fitz
                import pytesseract
                from PIL import Image

                document = fitz.open(path)
                pages = []
                for page in document:
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                    pages.append(pytesseract.image_to_string(image, lang="chi_sim+eng"))
                document.close()
                extracted = "\n".join(pages)
            except Exception as exc:
                return "", f"PDF 没有可提取文本且 OCR 失败: {str(exc)[:180]}"
            if not clean_text(extracted):
                return "", "PDF OCR 后仍未提取到有效文本"
        return extracted, None
    raise ValueError(f"unsupported document type: {suffix}")


def _metadata(path: Path, corpus_type: str, raw: str) -> dict[str, Any]:
    sidecar = path.with_suffix(path.suffix + ".metadata.json")
    extra = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    relative = _safe_source(path)
    inferred_title = path.stem
    if path.suffix.lower() == ".md":
        inferred_title = next(
            (line.lstrip("# ").strip() for line in raw.splitlines() if line.strip().startswith("#")),
            path.stem,
        )
    title = extra.get("title") or inferred_title
    stat = path.stat()
    return {
        "document_id": extra.get("document_id") or hashlib.sha256(relative.encode()).hexdigest()[:20],
        "title": title, "source_path": relative, "document_type": path.suffix.lower().lstrip("."),
        "department": extra.get("department", "通用"), "version": str(extra.get("version", "1.0")),
        "updated_at": extra.get("updated_at") or datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        "access_scope": extra.get("access_scope", "authenticated"), "corpus_type": corpus_type,
        "content_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "is_active": extra.get("is_active", True),
    }


def _source_roots(source_dir: Path | None = None) -> list[tuple[Path, str]]:
    settings = get_settings()
    if source_dir:
        corpus = "enterprise" if "enterprise" in source_dir.parts else "mock"
        return [(source_dir, corpus)]
    roots = [(settings.project_path(settings.mock_knowledge_dir), "mock"),
             (settings.project_path(settings.enterprise_knowledge_dir), "enterprise")]
    legacy = ROOT_DIR / "knowledge_base"
    if not roots[0][0].exists():
        roots.insert(0, (legacy, "mock"))
    return roots


def build_index(source_dir: Path | None = None, output_path: Path | None = None) -> dict[str, Any]:
    settings = get_settings()
    output_path = output_path or settings.project_path(settings.knowledge_index_path)
    records, failures, skipped, hashes = [], [], 0, set()
    for root, corpus_type in _source_roots(source_dir):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES or path.name.endswith(".metadata.json"):
                continue
            try:
                raw, warning = _read_document(path)
                if warning:
                    failures.append({"source": _safe_source(path), "reason": warning})
                    continue
                metadata = _metadata(path, corpus_type, raw)
                if metadata["content_hash"] in hashes:
                    skipped += 1
                    continue
                hashes.add(metadata["content_hash"])
                for index, chunk in enumerate(split_text(raw)):
                    records.append({**metadata, "chunk_id": f"{metadata['document_id']}-{index}",
                                    "chunk_index": index, "content": chunk})
            except Exception as exc:
                failures.append({"source": _safe_source(path), "reason": str(exc)[:300]})
    provider = get_embedding_provider()
    vectors: list[list[float]] = []
    actual_mode = provider.mode
    fallback_reason = None
    if provider.mode != "tfidf_fallback" and records:
        try:
            vectors = provider.embed([record["content"] for record in records])
        except Exception as exc:
            if not settings.allow_mock_fallback:
                raise
            actual_mode, fallback_reason = "tfidf_fallback", str(exc)[:300]
    for index, record in enumerate(records):
        record["embedding"] = vectors[index] if vectors else None
        record["embedding_model"] = provider.model_name if vectors else "tfidf_char_2_4"
    payload = {
        "schema_version": 2, "retrieval_mode": actual_mode,
        "embedding_model": provider.model_name if vectors else "tfidf_char_2_4",
        "embedding_dimension": len(vectors[0]) if vectors else 0,
        "built_at": datetime.now(UTC).isoformat(), "documents": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    index_version_id = str(uuid.uuid4())
    checksum = hashlib.sha256(encoded).hexdigest()
    version_artifact = None
    if output_path.resolve() == settings.project_path(settings.knowledge_index_path).resolve():
        versions_dir = settings.project_path(settings.knowledge_index_versions_dir)
        versions_dir.mkdir(parents=True, exist_ok=True)
        version_artifact = versions_dir / f"{index_version_id}.json"
        version_artifact.write_bytes(encoded)
    temporary = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, output_path)
    build_catalog(records)
    document_chunk_counts: dict[str, int] = {}
    for record in records:
        document_id = str(record["document_id"])
        document_chunk_counts[document_id] = document_chunk_counts.get(document_id, 0) + 1
    return {"mode": actual_mode, "embedding_model": payload["embedding_model"],
            "embedding_dimension": payload["embedding_dimension"], "document_count": len(records),
            "document_chunk_counts": document_chunk_counts,
            "failed": len(failures), "skipped": skipped, "failures": failures,
            "fallback_reason": fallback_reason, "path": str(output_path),
            "index_version_id": index_version_id, "checksum": checksum,
            "version_artifact": str(version_artifact) if version_artifact else None}


def build_catalog(records: list[dict[str, Any]]) -> dict[str, Any]:
    catalog: dict[str, dict[str, Any]] = {}
    for row in records:
        if row["document_id"] not in catalog:
            entities = sorted(set(re.findall(r"(?:ORDER|AUTH)\d{3}", row["content"])))
            catalog[row["document_id"]] = {key: row[key] for key in (
                "document_id", "title", "department", "document_type", "updated_at", "access_scope", "corpus_type"
            )} | {"core_entities": entities}
    path = get_settings().project_path(get_settings().knowledge_catalog_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {"generated_at": datetime.now(UTC).isoformat(), "documents": list(catalog.values())}
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0


def search(query: str, top_k: int = 3, doc_type: str | None = None,
           allowed_scopes: list[str] | None = None, corpus_type: str | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    index_path = settings.project_path(settings.knowledge_index_path)
    if not index_path.exists():
        build_index(output_path=index_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    # v1 indexes did not contain access/corpus metadata or stable document ids.
    # Rebuild them from the source documents instead of trying to mix formats.
    if payload.get("schema_version") != 2:
        build_index(output_path=index_path)
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    configured_corpus = corpus_type or settings.knowledge_corpus
    scopes = set(allowed_scopes or ["public", "authenticated"])
    docs = [row for row in payload["documents"] if row.get("is_active", True)
            and row.get("access_scope", "authenticated") in scopes
            and (configured_corpus == "mixed" or row.get("corpus_type") == configured_corpus)
            and (not doc_type or row.get("document_type") == doc_type or row.get("department") == doc_type)]
    if not docs:
        return []
    semantic_scores: list[float] = [0.0] * len(docs)
    current_provider = get_embedding_provider()
    if payload.get("retrieval_mode") != "tfidf_fallback":
        if payload.get("embedding_model") != current_provider.model_name:
            raise IndexCompatibilityError("Embedding 模型与现有索引不一致，请重建知识库索引")
        query_vector = current_provider.embed([query])[0]
        if len(query_vector) != payload.get("embedding_dimension"):
            raise IndexCompatibilityError("Embedding 维度与现有索引不一致，请重建知识库索引")
        semantic_scores = [_cosine(query_vector, row["embedding"]) for row in docs]
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), sublinear_tf=True)
    matrix = vectorizer.fit_transform([row["content"] for row in docs] + [query])
    lexical_scores = (matrix[:-1] @ matrix[-1].T).toarray().ravel().tolist()
    semantic_rank = {index: rank for rank, index in enumerate(sorted(range(len(docs)), key=lambda i: semantic_scores[i], reverse=True), 1)}
    lexical_rank = {index: rank for rank, index in enumerate(sorted(range(len(docs)), key=lambda i: lexical_scores[i], reverse=True), 1)}
    ranked = sorted(range(len(docs)), key=lambda i: (1 / (60 + semantic_rank[i]) if semantic_scores[i] else 0) + 1 / (60 + lexical_rank[i]), reverse=True)
    results = []
    for rank, index in enumerate(ranked[: max(top_k * 2, top_k)], 1):
        semantic, lexical = float(semantic_scores[index]), float(lexical_scores[index])
        valid = semantic >= settings.embedding_min_score if payload.get("retrieval_mode") != "tfidf_fallback" else lexical >= settings.lexical_min_score
        if not valid or (semantic <= 0 and lexical <= 0):
            continue
        row = docs[index]
        results.append({
            "title": row["title"], "source": f"doc:{row['document_id']}", "snippet": row["content"],
            "relevance": round(max(semantic, lexical), 4), "semantic_score": round(semantic, 4),
            "lexical_score": round(lexical, 4), "rank": rank, "retrieval_mode": payload["retrieval_mode"],
            "metadata": {key: row[key] for key in ("document_id", "document_type", "department", "version", "updated_at", "access_scope", "corpus_type", "chunk_id", "chunk_index", "embedding_model")},
        })
        if len(results) >= top_k:
            break
    return results
