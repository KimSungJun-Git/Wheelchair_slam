import os
from state import AgentState
from langchain_ollama import ChatOllama 
from langchain_core.prompts import ChatPromptTemplate

# 1. 파일에서 대화 맥락을 로드하는 노드
def load_memory_node(state: AgentState):
    file_path = "memory.md"
    context = ""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            context = f.read()
    return {"memory_context": context}

# 2. 컨텍스트를 주입하여 LLM 응답을 생성하는 노드
def generate_response_node(state: AgentState):
    context = state.get("memory_context", "")
    
    # 로컬 Ollama 모델 또는 사용 중인 LangChain LLM 객체 설정
    llm = ChatOllama(model="llama3", temperature=0.2) 
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "너는 자율주행 및 로봇 개발을 돕는 전문 AI 어시스턴트야. 아래의 프로젝트 개발 맥락과 제약 조건을 항상 기억하고 응답에 반영해줘:\n\n{context}"),
        ("placeholder", "{messages}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"messages": state["messages"], "context": context})
    
    return {"messages": [response]}