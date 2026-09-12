from rag import answer

if __name__ == "__main__":
    question = input("\nEnter your legal question: ")

    result = answer(question)

    print("\n" + "=" * 70)
    print("ANSWER")
    print("=" * 70)

    print(result["answer"])

    print("\n" + "=" * 70)
    print("SOURCES")
    print("=" * 70)

    for i, source in enumerate(result["sources"], 1):
        print(
            f"{i}. {source['source']} "
            f"(Page {source['page']}, "
            f"Score: {source['score']:.4f})"
        )