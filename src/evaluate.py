import time
from rag import retrieve

TESTS = [
    ("What is the right to information under Indian law?", ["rti"]),
    ("What is meant by free consent in a contract?", ["contract"]),
    ("What is the Bharatiya Nyaya Sanhita?", ["bns"]),
    ("What is the purpose of the Bharatiya Sakshya Adhiniyam?", ["bsa"]),
    ("What does the Bharatiya Nagarik Suraksha Sanhita deal with?", ["bnss"]),
]

if __name__ == "__main__":
    hits_total = 0
    for q, expected in TESTS:
        t = time.perf_counter()
        results = retrieve(q, top_k=5)
        latency = time.perf_counter() - t
        names = [x["source"] for x in results]
        hit = any(any(e in n for e in expected) for n in names)
        hits_total += int(hit)
        print(f"{q}\n  hit={hit} latency={latency:.3f}s sources={names}\n")
    print(f"Retrieval hit@5: {hits_total}/{len(TESTS)} = {hits_total/len(TESTS):.1%}")
