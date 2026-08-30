from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.document_content_index_service import DocumentContentIndexService
from app.services.document_hybrid_retrieval_service import (
    DocumentHybridRetrievalService,
)
from app.services.document_library_service import DocumentLibraryService
from app.services.document_semantic_index_service import DocumentSemanticIndexService
from app.services.local_embedding_service import LocalEmbeddingService
from app.services.technical_consultant_acceptance_service import (
    TechnicalAcceptanceReport,
    TechnicalConsultantAcceptanceError,
    TechnicalConsultantAcceptanceService,
    load_technical_acceptance_baseline,
)
from app.services.technical_product_comparison_service import (
    TechnicalProductComparisonService,
)
from app.services.technical_product_decision_service import (
    TechnicalProductDecisionService,
)
from app.services.technical_product_retrieval_service import (
    TechnicalProductRetrievalService,
)


DEFAULT_BASELINE_PATH = (
    PROJECT_ROOT / "evaluation" / "technical_consultant_real_corpus.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evalúa el consultor técnico contra el catálogo local sin modificar "
            "documentos, índices ni modelos."
        )
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="Línea base JSON versionada.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        dest="case_ids",
        help="Ejecuta solo este identificador; se puede repetir.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Muestra el informe completo como JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Guarda además el informe JSON en esta ruta.",
    )
    return parser.parse_args(argv)


def build_acceptance_service() -> TechnicalConsultantAcceptanceService:
    library = DocumentLibraryService()
    content = DocumentContentIndexService(library)
    embedding = LocalEmbeddingService()
    semantic = DocumentSemanticIndexService(content, embedding)
    hybrid = DocumentHybridRetrievalService(content, semantic)
    retrieval = TechnicalProductRetrievalService(hybrid)
    comparison = TechnicalProductComparisonService(retrieval, content)
    decision = TechnicalProductDecisionService(comparison)
    return TechnicalConsultantAcceptanceService(
        decision,
        embedding_model=embedding.model,
    )


def render_text_report(report: TechnicalAcceptanceReport) -> str:
    lines = [
        "Evaluación del consultor técnico",
        (
            f"Modelo de embeddings: {report.actual_embedding_model} "
            f"(esperado: {report.expected_embedding_model})"
        ),
    ]
    for drift in report.global_drifts:
        lines.append(
            f"DRIFT global {drift.field}: "
            f"esperado={drift.expected!r} actual={drift.actual!r}"
        )
    for case in report.cases:
        status = "PASS" if case.passed else "DRIFT"
        lines.append(
            f"{status} {case.case_id} · {case.duration_seconds:.3f}s "
            f"· {case.retrieval_mode}"
        )
        for drift in case.drifts:
            lines.append(
                f"  {drift.field}: "
                f"esperado={drift.expected!r} actual={drift.actual!r}"
            )
    passed_count = sum(case.passed for case in report.cases)
    lines.append(
        f"Resultado: {'PASS' if report.passed else 'DRIFT'} "
        f"· {passed_count}/{len(report.cases)} casos sin desviaciones"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        baseline = load_technical_acceptance_baseline(args.baseline)
        service = build_acceptance_service()
        report = service.evaluate(
            baseline,
            case_ids=tuple(args.case_ids),
        )
    except TechnicalConsultantAcceptanceError as exc:
        print(f"No se pudo ejecutar la evaluación: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(
        report.to_dict(),
        ensure_ascii=False,
        indent=2,
    )
    if args.output is not None:
        output_path = args.output.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload if args.json else render_text_report(report))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
