"""The metadata contract for every CareCover document."""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

Short = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]

Values = Annotated[list[Short], Field(default_factory=list, max_length=8)]

# CareCover supports these two schemes.
Scheme = Literal["PM-JAY", "CMCHIS"]

Schemes = Annotated[
    list[Scheme],
    Field(default_factory=list, max_length=8),
]


class DocMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_kind: Literal[
        "guideline",
        "rule",
        "notice",
        "list",
        "report",
        "faq",
        "form",
        "tutorial",
        "reference",
        "other",
    ]
    year: int | None = Field(default=None, ge=1950, le=2027)
    language: Literal["en", "ta", "hi", "other"]
    summary: str = Field(min_length=20, max_length=300)
    topics: Annotated[list[Short], Field(min_length=1, max_length=6)]

    scheme: Schemes
    package_code: Values
    procedure: Values
    rate: Values
    preauth_required: Values

    @field_validator("topics")
    @classmethod
    def _tidy(cls, value: list[str]) -> list[str]:
        """Lowercase topics and remove duplicates."""
        return list(dict.fromkeys(topic.lower() for topic in value))
