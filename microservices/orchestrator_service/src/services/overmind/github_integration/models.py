from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GitHubBranch(BaseModel):
    name: str
    sha: str
    protected: bool


class GitHubCommitAuthor(BaseModel):
    name: str
    email: str | None = None
    date: datetime | str


class GitHubCommit(BaseModel):
    sha: str
    message: str
    author: str | GitHubCommitAuthor  # Can be just name or object depending on endpoint
    date: str
    url: str
    files_changed: int | None = None
    additions: int | None = None
    deletions: int | None = None


class GitHubPR(BaseModel):
    number: int
    title: str
    state: str
    author: str
    head: str
    base: str
    created_at: str
    url: str


class GitHubIssue(BaseModel):
    number: int
    title: str
    state: str
    author: str
    labels: list[str]
    created_at: str
    url: str


class GitHubFileContent(BaseModel):
    path: str
    content: str
    sha: str
    size: int


class RepoInfo(BaseModel):
    owner: str
    name: str
    full_name: str | None = None
    description: str | None = None
    stars: int | None = None
    forks: int | None = None
    open_issues: int | None = None
    default_branch: str | None = None
    private: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None
    url: str | None = None
    error: str | None = None

    model_config = ConfigDict(extra="ignore")
