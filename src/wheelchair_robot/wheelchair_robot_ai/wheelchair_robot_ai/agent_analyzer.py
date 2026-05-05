#!/usr/bin/env python3
# agent_analyzer.py
import os
import json
import glob
import sys
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate

class AgentState(TypedDict):
    raw_logs: str
    analysis_report: str

def read_logs(state: AgentState):
    log_dir = os.path.expanduser('~/wheelchair_ws/driving_data')
    list_of_files = glob.glob(f'{log_dir}/*.json')
    
    if not list_of_files:
        print("\033[93m\n[알림] 분석할 로그 파일이 없습니다. 주행을 먼저 진행해주세요.\033[0m")
        sys.exit(0)
        
    latest_file = max(list_of_files, key=os.path.getmtime)
    print(f"\033[90m📄 분석 대상: {os.path.basename(latest_file)}\033[0m")
    
    logs = []
    with open(latest_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()[-100:]
        for line in lines:
            try:
                logs.append(json.loads(line.strip()))
            except:
                pass
                
    if not logs:
        print("\033[92m\n=======================================================")
        print(" 🟢 [완벽] 수집된 에러/정지 로그가 없습니다. 안전 주행 완료!")
        print("=======================================================\n\033[0m")
        sys.exit(0)
    
    return {"raw_logs": json.dumps(logs, indent=2, ensure_ascii=False)}
def analyze_logs(state: AgentState):
    from langchain_ollama import ChatOllama
    from langchain_core.prompts import PromptTemplate
    import re
    
    llm = ChatOllama(model="qwen2.5:7b", temperature=0.1) 
    
    # ⭐️ 프롬프트에 신뢰도(Confidence Score) 요구 항목 추가
    prompt = PromptTemplate(
        input_variables=["logs"],
        template="""
당신은 자율주행 휠체어 로봇의 수석 AI 엔지니어입니다.
아래 로그를 분석하고 반드시 아래의 마크다운 표 양식으로 대답하세요.

[운행 로그]
{logs}

## 📊 AI 디버깅 리포트
| 항목 | 분석 결과 |
|---|---|
| 🎯 AI 신뢰도 | [0~100]% (반드시 숫자만 적을 것) |
| 🚨 핵심 원인 | (1~2줄 요약) |
| 🛠️ 조언 | (해결책) |
"""
    )
    chain = prompt | llm
    response = chain.invoke({"logs": state["raw_logs"]})
    return {"analysis_report": response.content}


def main(args=None):
    print("\033[96m🔄 AI가 데이터를 분석 중입니다. 잠시만 기다려주세요...\033[0m")
    
    workflow = StateGraph(AgentState)
    workflow.add_node("read", read_logs)
    workflow.add_node("analyze", analyze_logs)
    workflow.set_entry_point("read")
    workflow.add_edge("read", "analyze")
    workflow.add_edge("analyze", END)
    
    app = workflow.compile()
    
    result = app.invoke({"raw_logs": "", "analysis_report": ""})
    report_content = result["analysis_report"]
    
    # 터미널에 출력
    print("\033[96m\n================= [ 🤖 AI 분석 완료 ] =================\033[0m\n")
    print(report_content)
    
    # ⭐️ 새로 추가된 부분: Human-in-the-loop 피드백 루프 파싱 로직
    import re
    # 정규식으로 AI 대답에서 '신뢰도' 숫자만 추출
    confidence_match = re.search(r'🎯 AI 신뢰도\s*\|\s*(\d+)', report_content)
    
    if confidence_match:
        confidence = int(confidence_match.group(1))
        
        # 신뢰도가 50 미만일 때 사용자에게 질문
        if confidence < 50:
            print("\033[91m\n[경고] AI의 원인 분석 신뢰도가 50% 미만입니다. 데이터가 부족합니다.\033[0m")
            user_input = input("\033[93m❓ 추가 센서 로그(yaml, 파라미터 등)를 제공하시겠습니까? (Y/N): \033[0m")
            
            if user_input.lower() == 'y':
                print("\n\033[92m[시스템] 추가 데이터 수집 모드를 활성화합니다... (2차 분석 파이프라인 연동 대기)\033[0m")
            else:
                print("\033[90m[시스템] 기존 분석 결과로 리포트를 마감합니다.\033[0m")
    
    print("\033[96m\n=======================================================\033[0m\n")

    # 기존 리포트 저장 코드 (유지됨)
    try:
        log_dir = os.path.expanduser('~/wheelchair_ws/driving_data')
        # 최신 JSON 파일 이름을 찾아서, 확장자만 .md로 변경
        latest_json = max(glob.glob(f'{log_dir}/*.json'), key=os.path.getmtime)
        report_filename = os.path.basename(latest_json).replace('.json', '_report.md')
        report_path = os.path.join(log_dir, report_filename)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"\033[92m💾 AI 분석 리포트가 성공적으로 저장되었습니다: {report_filename}\033[0m")
    except Exception as e:
        print(f"\033[91m⚠️ 리포트 저장 실패: {e}\033[0m")

if __name__ == "__main__":
    main()