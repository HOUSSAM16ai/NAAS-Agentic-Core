from pydantic import BaseModel, Field


class Founder(BaseModel):
    first_name: str
    last_name: str
    name: str
    first_name_ar: str
    last_name_ar: str
    name_ar: str
    birth_date: str
    role: str
    role_ar: str
    github: str
    email: str


class Project(BaseModel):
    name: str
    description: str
    description_en: str
    version: str
    repository: str
    license: str


class OvermindInfo(BaseModel):
    name: str
    name_ar: str
    role: str
    role_ar: str
    birth_date: str
    version: str
    purpose: str
    purpose_en: str


class Philosophy(BaseModel):
    heritage: str
    principles: list[str]
    values: list[str]


class AgentPrinciple(BaseModel):
    number: int
    statement: str


class AgentInfo(BaseModel):
    name: str
    role: str
    capabilities: list[str]


class Capabilities(BaseModel):
    knowledge: list[str]
    actions: list[str]
    intelligence: list[str]
    super_tools: list[str]


class Milestone(BaseModel):
    date: str
    event: str


class History(BaseModel):
    milestones: list[Milestone]


class IdentitySchema(BaseModel):
    founder: Founder
    project: Project
    overmind: OvermindInfo
    philosophy: Philosophy
    agent_principles: list[AgentPrinciple] = Field(default_factory=list)
    system_principles: list[AgentPrinciple] = Field(default_factory=list)
    architecture_system_principles: list[AgentPrinciple] = Field(default_factory=list)
    agents: dict[str, AgentInfo]
    capabilities: Capabilities
    history: History
