#!/usr/bin/env python3
import rclpy
from nav2_simple_commander.robot_navigator import BasicNavigator
from geometry_msgs.msg import PoseStamped
import time

def custom_pose(nav,x, y, w):
# x: 3.8 y: 1.0 z: 0.01 왼쪽 위
# x: 1.4 y: -1.25 z: 0.02 오른쪽 중앙
# x: 1.4 y: 2.2 z: 0.01 왼쪽 중앙
# x: 0.0 y: 0.0 z: 0.0 초기 위치
#ros2 topic echo /clicked_point

    goal_pose = PoseStamped()
    goal_pose.header.frame_id = 'map'
    goal_pose.header.stamp = nav.get_clock().now().to_msg()
    goal_pose.pose.position.x = x
    goal_pose.pose.position.y = y
    goal_pose.pose.orientation.w = w
    return goal_pose    

def main():
    
    rclpy.init()
    nav = BasicNavigator()
    # 1. 내비게이션 시스템이 준비될 때까지 대기
    nav.waitUntilNav2Active()
    patrol_point = [
        (3.8, 1.0, 1.0),
        (1.4, -1.25, 1.0),
        (1.4, 2.2, 1.0),
        (0.0, 0.0, 1.0)
    ]
    print("순찰 시작!")
    
    for x, y, w in patrol_point:
        goal = custom_pose(nav, x, y, w)
        nav.goToPose(goal)

        # 4. 이동 완료까지 상태 확인
        while not nav.isTaskComplete():
            feedback = nav.getFeedback()
            if feedback:
                print(f'남은 거리: {feedback.distance_remaining:.2f} m', end='\r')
        print(f"\n도착 지점: x:{x}, y:{y}")
        time.sleep(2)
        


    
    print('목표 지점에 도착했습니다!')
    
    
    rclpy.shutdown()

if __name__ == '__main__':
    main()
