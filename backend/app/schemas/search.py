from pydantic import BaseModel


class SearchResultItem(BaseModel):
    kind: str  # "employee" | "approval_request" | "asset"
    id: int
    title: str
    subtitle: str
    url: str


class SearchResultsOut(BaseModel):
    results: list[SearchResultItem]
