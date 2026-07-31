from pydantic import BaseModel, Field

# The exact JSON Schema sent to Anthropic as a forced tool call -- this is
# the mechanism that makes the output "strict" (the model can only respond
# via this tool, not free-form text), not just a prompt instruction hoping
# for compliance. Kept in sync by hand with ClusterLabelResult below; the
# Pydantic model is the second, independent validation layer applied to
# whatever the tool call actually returns.
CLUSTER_LABEL_TOOL_SCHEMA = {
    "name": "cluster_label",
    "description": "Structured name, description, keywords, confidence, and evidence for one paper cluster.",
    "input_schema": {
        "type": "object",
        "properties": {
            "cluster_name": {"type": "string"},
            "short_description": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "paper_id": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["paper_id", "reason"],
                },
            },
        },
        "required": ["cluster_name", "short_description", "keywords", "confidence", "evidence"],
    },
}


class EvidenceItem(BaseModel):
    paper_id: str
    reason: str


class ClusterLabelResult(BaseModel):
    """Validated structured output. Confidence range is enforced by Pydantic
    itself (Field constraints); evidence paper_id membership in the
    supplied representative-paper set is NOT enforced here (this model has
    no knowledge of what was supplied) -- that check happens separately in
    labeling.py, where the input context is available."""

    cluster_name: str = Field(min_length=1)
    short_description: str = Field(min_length=1)
    keywords: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceItem]
