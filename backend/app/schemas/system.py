from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class StackItem(BaseModel):
    name: str
    version: str
    why: str
    alternative: str


class StackLayer(BaseModel):
    layer: str
    items: list[StackItem]


class ServiceStatus(BaseModel):
    name: str
    status: Literal["healthy", "degraded", "down", "disabled"]
    detail: str


class Diagram(BaseModel):
    key: str
    title: str
    description: str
    mermaid: str


class SystemInfo(BaseModel):
    mode: Literal["demo", "azure"]
    version: str
    build_sha: str
    started_at: datetime
    stack: list[StackLayer]
    services: list[ServiceStatus]
    diagrams: list[Diagram]


class GraphDiagram(BaseModel):
    mermaid: str
    source: Literal["live", "planned"]
