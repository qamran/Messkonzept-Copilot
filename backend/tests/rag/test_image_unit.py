"""MKC-50 (MKC-49 review, open point): the backend image ships the corpus sources file, as
MKC-21 ships `operators.yaml` (`tests/extraction/test_operators_file.py`), so `mkc corpus
load` in the container finds it at `/app/data/corpus_sources.yaml`."""

import re
from pathlib import Path, PurePosixPath

BACKEND = Path(__file__).resolve().parents[2]
DOCKERFILE = BACKEND / "Dockerfile"


def test_the_image_ships_corpus_sources_yaml() -> None:
    runtime = DOCKERFILE.read_text(encoding="utf-8").split(" AS runtime", 1)[1]
    workdir = PurePosixPath(re.findall(r"^WORKDIR (\S+)", runtime, re.M)[-1])
    copies = re.findall(r"^COPY (?!--from)(\S+) (\S+)$", runtime, re.M)
    shipped = {workdir / dest for src, dest in copies if src == "data/corpus_sources.yaml"}
    assert shipped == {PurePosixPath("/app/data/corpus_sources.yaml")}
    assert (BACKEND / "data" / "corpus_sources.yaml").is_file()
