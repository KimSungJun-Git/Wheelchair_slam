import rclpy
from rclpy.node import Node
import telebot
from telebot import types
import threading
import subprocess
import os
import requests
import json
import glob

# ⭐️ 설정
TOKEN = '8176057872:AAG8_ztRllbQsxby72WeOhFy8Fcvr7AGhew'
bot = telebot.TeleBot(TOKEN)
OLLAMA_API_URL = "http://localhost:11434/api/generate"
WS_PATH = os.path.expanduser("~/wheelchair_ws")

class ActionAgentNode(Node):
    def __init__(self):
        super().__init__('action_agent_node')
        self.get_logger().info("🚀 자율 행동형 자비스 가동!")
        threading.Thread(target=self.run_bot, daemon=True).start()

    def run_bot(self):
        @bot.message_handler(func=lambda message: True)
        def handle_message(message):
            user_input = message.text
            chat_id = message.chat.id
            bot.send_message(chat_id, "🧠 상황 분석 및 작업 설계 중...")

            # ⭐️ AI에게 성준님의 워크스페이스 구조를 힌트로 줍니다.
            pkg_list = os.listdir(os.path.join(WS_PATH, "src")) if os.path.exists(os.path.join(WS_PATH, "src")) else []

            system_prompt = f"""
            너는 성준님의 로봇 비서 '자비스'야. 사용자의 명령을 분석해서 [행동]을 결정해.
            반드시 아래 JSON 형식으로만 답해.

            1. shell: 폴더 생성, 빌드, 파일 찾기 등 터미널 명령이 필요할 때
            2. send_file: 특정 파일을 사용자에게 직접 전송해야 할 때 (경로를 정확히 추론해)
            3. chat: 단순 질문이나 대화일 때

            현재 워크스페이스: {WS_PATH}
            내부 패키지 목록: {pkg_list}
            사용자 명령: {user_input}

            예시: "SLAM 파일 보내줘" -> {{"action": "send_file", "path": "{WS_PATH}/src/your_pkg/config/slam.yaml", "msg": "SLAM 파일을 찾아서 보냅니다."}}
            """

            try:
                response = requests.post(OLLAMA_API_URL, json={
                    "model": "qwen3:8b",
                    "prompt": system_prompt,
                    "stream": False,
                    "format": "json"
                })
                
                res_data = json.loads(response.json().get("response", "{}"))
                action = res_data.get("action")
                
                # ✅ 1. 파일 직접 전송 기능 (메시지 길이 에러 방지)
                if action == "send_file":
                    file_path = res_data.get("path")
                    if os.path.exists(file_path):
                        bot.send_message(chat_id, f"📂 **파일 발견:** {res_data.get('msg')}")
                        with open(file_path, 'rb') as f:
                            bot.send_document(chat_id, f)
                    else:
                        # 파일 경로가 정확하지 않으면 다시 검색 시도
                        bot.send_message(chat_id, f"🔍 파일을 찾는 중... (`{file_path}` 없음)")
                        search_cmd = f"find {WS_PATH} -name '*slam*' | head -n 1"
                        found_path = subprocess.getoutput(search_cmd)
                        if found_path and os.path.exists(found_path):
                            with open(found_path, 'rb') as f:
                                bot.send_document(chat_id, f)
                        else:
                            bot.send_message(chat_id, "❌ 파일을 찾지 못했습니다. 파일명을 정확히 말씀해주세요.")

                # ✅ 2. 터미널 명령어 실행 기능
                elif action == "shell":
                    target_cmd = res_data.get("command")
                    bot.send_message(chat_id, f"🛠️ **작업 실행:** {res_data.get('msg')}\n`$ {target_cmd}`")
                    
                    process = subprocess.run(target_cmd, shell=True, executable='/bin/bash', capture_output=True, text=True)
                    
                    if process.returncode == 0:
                        output = process.stdout if process.stdout else "성공 (출력 없음)"
                        bot.send_message(chat_id, f"✅ 완료:\n{output[:3000]}")
                    else:
                        bot.send_message(chat_id, f"❌ 오류:\n{process.stderr[:3000]}")

                # ✅ 3. 일반 대화
                else:
                    bot.send_message(chat_id, res_data.get("msg", "네, 성준님. 무엇을 도와드릴까요?"))

            except Exception as e:
                bot.send_message(chat_id, f"❌ 에이전트 실행 실패: {e}")

        bot.infinity_polling()

def main():
    rclpy.init()
    node = ActionAgentNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()