#!/usr/bin/env python3
"""navigate_to_pose action status bag → 목적지 도달 성공률 계산"""
import sys
from collections import Counter
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

TARGET_TOPIC = "/navigate_to_pose/_action/status"
STATUS_NAMES = {0:"UNKNOWN",1:"ACCEPTED",2:"EXECUTING",3:"CANCELING",
                4:"SUCCEEDED",5:"CANCELED",6:"ABORTED"}
TERMINAL = {4, 5, 6}

def detect_storage_id(p: Path) -> str:
    if p.is_dir():
        if list(p.glob("*.mcap")): return "mcap"
        if list(p.glob("*.db3")):  return "sqlite3"
    if p.suffix == ".mcap": return "mcap"
    return "sqlite3"

def main(bag_arg: str) -> None:
    bag_path = Path(bag_arg).expanduser()
    if not bag_path.exists():
        print(f"❌ 경로가 없습니다: {bag_path}"); sys.exit(1)
    storage_id = detect_storage_id(bag_path)
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id=storage_id),
        rosbag2_py.ConverterOptions(input_serialization_format="cdr",
                                    output_serialization_format="cdr"))
    type_map = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if TARGET_TOPIC not in type_map:
        print(f"❌ bag 안에 {TARGET_TOPIC} 토픽이 없습니다.")
        print(f"   bag에 들어있는 토픽: {list(type_map.keys())}"); sys.exit(1)
    msg_type = get_message(type_map[TARGET_TOPIC])
    final_status: dict = {}
    n_messages = 0
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic != TARGET_TOPIC: continue
        n_messages += 1
        msg = deserialize_message(data, msg_type)
        for st in msg.status_list:
            final_status[tuple(st.goal_info.goal_id.uuid)] = st.status
    counts = Counter(final_status.values())
    total = len(final_status)
    terminal_total = sum(counts[c] for c in TERMINAL)
    succeeded = counts.get(4, 0); aborted = counts.get(6, 0)
    print("=" * 50)
    print(f"  bag         : {bag_path.name}  (storage={storage_id})")
    print(f"  status 메시지: {n_messages} 개")
    print(f"  발견 goal   : {total} 개")
    print("=" * 50)
    for code in sorted(counts):
        print(f"    {STATUS_NAMES.get(code, code):<10} : {counts[code]}")
    print("-" * 50)
    if terminal_total == 0:
        print("  종료된 goal이 없습니다. 실제로 목적지를 보내고 끝까지 주행했는지 확인하세요.")
        return
    rate_all = succeeded / terminal_total * 100
    denom_strict = succeeded + aborted
    rate_strict = succeeded / denom_strict * 100 if denom_strict else 0.0
    print(f"  ▶ 성공률 (취소 포함): {succeeded}/{terminal_total} = {rate_all:.1f}%")
    print(f"  ▶ 성공률 (취소 제외): {succeeded}/{denom_strict} = {rate_strict:.1f}%")
    print("=" * 50)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "goal_results_new")
