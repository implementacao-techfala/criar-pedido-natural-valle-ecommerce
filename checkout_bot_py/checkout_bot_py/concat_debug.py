"""
concat_debug.py
----------------
Rode:  python concat_debug.py

Cria (ou sobrescreve) debug_bundle.txt contendo o conteúdo
dos arquivos relevantes do projeto.
"""

import pathlib
import datetime

# 1. Configurações -----------------------------------------------

# extensões/nomes que queremos salvar
KEEP_EXT  = {".py", ".txt", ".md", ".env", ".toml", ".yaml", ".yml"}
KEEP_FILE = {"Dockerfile", "requirements.txt", ".env.example"}

# pastas que NÃO queremos percorrer
SKIP_DIR  = {".venv", "Lib", "Include", "Scripts",
             "__pycache__", ".git", "node_modules", "dist", "build"}

# arquivo de saída
OUT_FILE = pathlib.Path("debug_bundle.txt")

# 2. Funções utilitárias ------------------------------------------

def should_keep(path: pathlib.Path) -> bool:
    """Decide se o arquivo será incluído na concatenação."""
    if any(part in SKIP_DIR for part in path.parts):
        return False
    if path.name in KEEP_FILE:
        return True
    return path.suffix.lower() in KEEP_EXT

def banner(path: pathlib.Path) -> str:
    """Cria um cabeçalho bonitinho para cada arquivo no txt."""
    line = "=" * 80
    return f"\n{line}\n# {path.as_posix()}\n{line}\n"

# 3. Percorre e concatena -----------------------------------------

def main():
    base = pathlib.Path(__file__).resolve().parent
    files = sorted(p for p in base.rglob("*") if p.is_file() and should_keep(p))

    with OUT_FILE.open("w", encoding="utf-8") as out:
        out.write(f"# DEBUG BUNDLE gerado em {datetime.datetime.now()}\n")
        out.write("# Contém apenas arquivos relevantes para revisão.\n\n")

        for f in files:
            try:
                out.write(banner(f))
                out.write(f.read_text(encoding="utf-8", errors="ignore"))
                out.write("\n")  # garante quebra de linha final
            except Exception as e:
                print(f"[WARN] Não consegui ler {f}: {e}")

    print(f"✅  Arquivo criado: {OUT_FILE} ({OUT_FILE.stat().st_size/1024:.1f} KB)")

# -----------------------------------------------------------------
if __name__ == "__main__":
    main()
