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
    llm = ChatOllama(model="qwen2.5:7b", temperature=0.1) 
    
    # ⭐️ AI가 표 형식으로 대답하도록 프롬프트 강력하게 통제
    prompt = PromptTemplate(
        input_variables=["logs"],
        template="""
당신은 자율주행 휠체어 로봇의 안전 분석 AI입니다.
아래는 오늘 주행 중 발생한 운행 로그입니다.

[운행 로그]
{logs}

위 데이터를 분석하여 사용자가 한눈에 파악할 수 있게 마크다운 리포트를 작성해주세요.
설명은 최대한 짧게 하고, 반드시 아래 양식을 그대로 지켜서 표 형식으로 출력하세요:

## 📊 주행 안전 요약
| 항목 | 결과 |
|---|---|
| 🛑 총 에러 횟수 | [N]건 |
| ⚠️ 안전 급정거 | [N]건 |
| 💡 종합 평가 | (한 줄 요약. 예: 🟢 매우 안전함 / 🟡 주의 필요 / 🔴 위험) |

### 🚨 주요 발생 원인
* (원인이 없다면 '특이사항 없음'으로 기재, 있다면 핵심만 짧게 1~2줄 요약)

### 🛠️ 엔지니어 조언 (파라미터 튜닝)
* (센서나 Nav2 파라미터 튜닝에 대한 명확하고 짧은 조언 1~2개)
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
    print("\033[96m\n=======================================================\033[0m\n")

    # ⭐️ 새로 추가된 부분: 분석 리포트를 파일로 영구 저장하기
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