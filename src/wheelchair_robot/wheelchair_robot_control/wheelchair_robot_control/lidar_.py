import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rclpy.qos import qos_profile_sensor_data  
import math

class LidarAngleViewer(Node):
    def __init__(self):
        super().__init__('lidar_angle_viewer')
        
        self.subscription = self.create_subscription(
            LaserScan,
            '/scan',
            self.listener_callback,
            qos_profile_sensor_data)  
            
        self.target_angle_deg = 30.0 

    def listener_callback(self, msg):
        target_angle_rad = math.radians(self.target_angle_deg)

        if msg.angle_min <= target_angle_rad <= msg.angle_max:
            index = int((target_angle_rad - msg.angle_min) / msg.angle_increment)
            
            if 0 <= index < len(msg.ranges):
                distance = msg.ranges[index]
                if math.isinf(distance) or math.isnan(distance):
                    pass 
                else:
                    self.get_logger().info(f"각도 {self.target_angle_deg}도의 거리: {distance:.3f} 미터")
        else:
            self.get_logger().info(f"{self.target_angle_deg}도는 현재 라이다의 측정 각도 범위 밖에 있습니다.")

def main(args=None):
    rclpy.init(args=args)
    node = LidarAngleViewer()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()