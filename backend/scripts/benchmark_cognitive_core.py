import time
from pathlib import Path
from tempfile import TemporaryDirectory

from app.container import settings
from app.core.cognitive_graph import cognitive_graph_service
from app.core.database import database, initialize_database, utc_now


def run(count: int) -> float:
    with TemporaryDirectory(prefix="jarvis-cognitive-benchmark-") as directory:
        previous = settings.database_path
        settings.database_path = Path(directory) / "jarvis.db"
        try:
            initialize_database(); now=utc_now()
            rows=[(f"m{i}",f"Memória controlada projeto grupo{i%120:03} tópico item{i%90:03}","project" if i%2 else "fact",3,"system",None,now,now,None) for i in range(count)]
            with database() as connection:
                connection.executemany("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?)",rows)
            started=time.perf_counter(); graph=cognitive_graph_service.build([]); elapsed=time.perf_counter()-started
            print(f"{count:>5} memórias | {len(graph['edges']):>5} relações | {elapsed:.4f}s")
            return elapsed
        finally: settings.database_path=previous


if __name__ == "__main__":
    for size in (100,1000,5000): run(size)
