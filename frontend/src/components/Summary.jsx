const labels = { document_type: "Document type", concise_summary: "Plain-language summary", parties_or_entities_mentioned: "Parties and entities", important_sections_or_clauses: "Important clauses", key_obligations: "Key obligations", important_dates: "Important dates", financial_terms: "Financial terms", potentially_important_legal_points: "Legal points to review" };

export default function Summary({ data }) {
  return <div className="prose-legal">{Object.entries(data || {}).map(([key, value]) => <section key={key}>
    <h2>{labels[key] || key.replaceAll("_", " ")}</h2>
    {Array.isArray(value) ? <ul>{(value.length ? value : ["Not specified"]).map((item, index) => <li key={index}>{String(item)}</li>)}</ul> : <p>{value || "Not specified"}</p>}
  </section>)}</div>;
}
