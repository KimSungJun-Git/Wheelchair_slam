from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # 대화 메시지 배열 (BaseMessage 타입으로 자동 변환/누적됨)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    # memory.md에서 읽어온 컨텍스트 텍스트
    memory_context: str