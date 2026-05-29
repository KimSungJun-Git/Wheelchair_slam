from langgraph.graph import StateGraph, START, END
from state import AgentState
from nodes import load_memory_node, generate_response_node

# 1. 워크플로우 그래프 선언
workflow = StateGraph(AgentState)

# 2. 정의된 노드 등록
workflow.add_node("load_memory", load_memory_node)
workflow.add_node("generate_response", generate_response_node)

# 3. 실행 흐름 연결 (엣지 설정)
workflow.add_edge(START, "load_memory")
workflow.add_edge("load_memory", "generate_response")
workflow.add_edge("generate_response", END)

# 4. 앱 컴파일
app = workflow.compile()

if __name__ == "__main__":
    # 질문 입력 및 에이전트 실행 테스트
    user_question = "Nav2 Stack의 Keepout 필터를 설정할 때 주로 고려해야 할 파라미터는 무엇인가요?"
    
    initial_state = {
        "messages": [{"role": "user", "content": user_question}]
    }
    
    print("--- 에이전트 가동 및 답변 생성 중 ---")
    for output in app.stream(initial_state):
        for key, value in output.items():
            if key == "generate_response":
                print(f"\n[AI 응답]:\n{value['messages'][-1].content}")