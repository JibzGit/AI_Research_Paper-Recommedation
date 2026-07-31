import json

# Bumped whenever SYSTEM_PROMPT or build_user_prompt()'s template text
# changes -- part of the cluster_labels cache key (see labeling.py), so a
# prompt edit is treated as requiring regeneration, never silently reusing
# a label generated under different instructions.
PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You are labeling a cluster of research paper abstracts for an internal research-discovery tool.
You will be given statistical evidence about one cluster: its size, keywords extracted by
TF-IDF, its category distribution, several representative papers (title + abstract) nearest
the cluster's center, its average membership confidence, and its density-based persistence.

Rules, all mandatory:
1. Base your name, description, and evidence ONLY on the supplied information. Never invent
   papers, methods, datasets, authors, or claims not present in the input.
2. Return your answer only via the cluster_label tool. No prose outside the tool call.
3. cluster_name: 3-8 words, specific if the evidence is coherent, broader and more general if
   the evidence is mixed or the category distribution is scattered.
4. short_description: 1-2 sentences, describing what unites the papers -- distinguish whether
   the unifying theme is a RESEARCH METHOD (e.g. "sparse signal recovery techniques") or an
   APPLICATION DOMAIN (e.g. "medical imaging diagnostics") when the evidence supports one
   reading more than the other. Do not conflate the two.
5. Avoid generic, near-meaningless labels such as "Artificial Intelligence Papers" or "Machine
   Learning Research" -- if the evidence is too weak to support anything more specific, say so
   plainly in the description rather than defaulting to a vague catch-all name.
6. confidence: your own calibrated estimate in [0, 1] of how coherent this cluster actually is,
   informed by (but not required to match) the supplied average_membership_probability and
   cluster_persistence values.
7. evidence: for each entry, paper_id MUST be exactly one of the paper_id values supplied to
   you. Never fabricate a paper_id. reason: one short clause tying that specific paper to your
   proposed cluster_name."""


def build_user_prompt(cluster_summary: dict) -> str:
    return (
        "Cluster summary:\n"
        f"{json.dumps(cluster_summary, indent=2, default=str)}\n\n"
        "Return your answer only via the cluster_label tool call."
    )
