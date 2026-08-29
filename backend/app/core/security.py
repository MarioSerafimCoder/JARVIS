from pathlib import Path


ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def validate_upload(filename: str, size: int) -> str:
    if not filename or Path(filename).name != filename:
        raise ValueError("Nome de arquivo inválido.")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValueError("Formato não suportado. Use PDF, DOCX, TXT ou MD.")
    if size > MAX_UPLOAD_BYTES:
        raise ValueError("O arquivo excede o limite de 20 MB.")
    return extension


def safe_child_path(root: Path, filename: str) -> Path:
    root = root.resolve()
    target = (root / filename).resolve()
    if root not in target.parents:
        raise ValueError("Caminho externo ao diretório permitido.")
    return target

