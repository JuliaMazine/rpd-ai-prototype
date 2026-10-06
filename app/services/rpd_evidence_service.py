"""Exact source excerpts with stable IDs, locations and text fingerprints."""
from hashlib import sha256
import re

class Sources(list):
    def __init__(self, names, chunks, full_text):
        super().__init__(names)
        self.chunks = chunks
        self.full_text = full_text

def normalize(text):
    return " ".join(text.split())

def source_documents(materials_text):
    pieces = re.split(r"(?m)^\[Источник: ([^\n]+)\]\n", materials_text)
    if len(pieces) == 1:
        return [("Материалы преподавателя", materials_text)]
    return [(pieces[index], pieces[index + 1]) for index in range(1, len(pieces), 2)]

def source_context(materials_text, budget=16000):
    documents = source_documents(materials_text)
    allowance = max(200, budget // max(1, len(documents)))
    chunks = {}
    parts = []
    for source_index, (name, body) in enumerate(documents, 1):
        markers = list(re.finditer(r"(?m)^(Страница|Слайд|Ячейка)\s+(\d+)[^\n]*\n", body))
        regions = []
        if markers:
            for index, marker in enumerate(markers):
                end = markers[index + 1].start() if index + 1 < len(markers) else len(body)
                regions.append((marker.end(), end, f"{marker.group(1)} {marker.group(2)}"))
        else:
            regions = [(0, len(body), "Текст")]
        candidates = []
        for start, end, location in regions:
            for offset in range(start, end, 700):
                finish = min(offset + 700, end)
                excerpt = body[offset:finish]
                if excerpt.strip():
                    candidates.append((offset, finish, location, excerpt))
        count = min(len(candidates), max(1, allowance // 900))
        if not count:
            continue
        indices = sorted(set(round(i * (len(candidates) - 1) / max(1, count - 1)) for i in range(count)))
        for local_index, candidate_index in enumerate(indices, 1):
            start, end, location, excerpt = candidates[candidate_index]
            chunk_id = f"S{source_index}E{local_index}"
            chunk = {"id": chunk_id, "filename": name, "location": location,
                     "start": start, "end": end, "text": excerpt,
                     "source_sha256": sha256(body.encode()).hexdigest()}
            block = f"[{chunk_id}] {name}, {location}, символы {start}–{end}\n{excerpt}"
            if sum(len(part) + 2 for part in parts) + len(block) > budget:
                continue
            chunks[chunk_id] = chunk
            parts.append(block)
    return "\n\n".join(parts), Sources([name for name, _ in documents], chunks, "\n".join(body for _, body in documents))

def verify_reference(reference, sources):
    if not isinstance(sources, Sources):
        raise ValueError("Source excerpts are required for evidence validation")
    chunk = sources.chunks.get(reference.excerpt_id)
    if not chunk:
        raise ValueError(f"Unknown source excerpt: {reference.excerpt_id}")
    quote = normalize(reference.quote)
    if len(quote) < 8 or quote not in normalize(chunk["text"]):
        raise ValueError(f"Quote must be copied exactly from {reference.excerpt_id}")
    return chunk
