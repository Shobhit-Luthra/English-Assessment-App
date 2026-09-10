from pydantic import BaseModel, Field


class SpeakingScore(BaseModel):
    item_id: str
    fluency: int = Field(ge=1, le=6)
    grammar: int = Field(ge=1, le=6)
    vocabulary: int = Field(ge=1, le=6)
    task_fulfilment: int = Field(ge=1, le=6)
    justification: str


class WritingScore(BaseModel):
    item_id: str
    grammar: int = Field(ge=1, le=6)
    vocabulary: int = Field(ge=1, le=6)
    tone_appropriateness: int = Field(ge=1, le=6)
    task_fulfilment: int = Field(ge=1, le=6)
    justification: str


class AttemptScores(BaseModel):
    speaking: list[SpeakingScore]
    writing: list[WritingScore]
