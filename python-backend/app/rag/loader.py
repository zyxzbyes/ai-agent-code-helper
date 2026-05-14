from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoadedDocument:
    source: str
    file_name: str
    content: str


def load_documents(docs_dir: str) -> list[LoadedDocument]:
    root = Path(docs_dir)
    if not root.exists():
        return []

    documents: list[LoadedDocument] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        content = path.read_text(encoding="utf-8")
        if content.strip():
            documents.append(
                LoadedDocument(
                    source=str(path),
                    file_name=path.name,
                    content=content,
                )
            )
    return documents
