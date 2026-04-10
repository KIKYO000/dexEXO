#!/usr/bin/env python3
"""
FTP 灵巧手关节映射控制器
功能:
  四指(index/middle/ring/little):
    1. 用户发送关节1角度(Excel G列值)
    2. 通过3次多项式自动计算关节2角度(Excel H列值)
    3. 同时控制关节1和关节2
  
  大拇指(thumb):
    1. thumb_1: 直接控制,无映射
    2. thumb_2: 用户输入(Excel C列)
    3. thumb_3: 通过映射计算(Excel D列)
    4. thumb_4: 通过映射计算(Excel E列)
  
映射模型: 3次多项式拟合
数据来源: 驱动器行程与角度关系表.xls
  - 四指: G列->H列
  - 大拇指: C列->D列, C列->E列
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
import pandas as pd
import numpy as np
import os


class Joint12MappingController(Node):
    def __init__(self):
        super().__init__('ftp_joint12_mapping_controller')
        
        # 加载映射数据
        self.load_mapping_data()
        
        # 定义除大拇指外的4个手指,每只手8个关节
        fingers = {
            'right': ['index', 'middle', 'ring', 'little'],
            'left': ['index', 'middle', 'ring', 'little']
        }
        
        # 存储当前目标位置(用于速度控制)
        self.current_joint1_targets = {}
        self.current_joint2_targets = {}
        
        # 存储当前估计位置(用于计算速度,假设从0开始)
        self.current_joint1_positions = {}
        self.current_joint2_positions = {}
        
        # PD控制器参数
        self.Kp = 2.0  # 比例增益 (调整响应速度)
        self.max_velocity = 1.0  # 最大速度限制 (rad/s)
        
        # 创建发布者和订阅者
        self.joint1_subs = {}
        self.joint1_pubs = {}
        self.joint2_pubs = {}
        
        for hand in ['right', 'left']:
            for finger in fingers[hand]:
                # 订阅用户输入的关节1角度
                input_topic = f'/ftp/{hand}_hand/{finger}/joint1/cmd'
                self.joint1_subs[f'{hand}_{finger}'] = self.create_subscription(
                    Float64,
                    input_topic,
                    lambda msg, h=hand, f=finger: self.joint1_callback(msg, h, f),
                    10
                )
                
                # 发布到仿真环境的关节1
                j1_sim_topic = f'/model/ftp_{hand}_hand_nested/joint/{hand}_{finger}_1_joint/cmd_vel'
                self.joint1_pubs[f'{hand}_{finger}'] = self.create_publisher(
                    Float64, j1_sim_topic, 10
                )
                
                # 发布到仿真环境的关节2
                j2_sim_topic = f'/model/ftp_{hand}_hand_nested/joint/{hand}_{finger}_2_joint/cmd_vel'
                self.joint2_pubs[f'{hand}_{finger}'] = self.create_publisher(
                    Float64, j2_sim_topic, 10
                )
                
                # 初始化目标位置和当前位置为0(伸直状态)
                key = f'{hand}_{finger}'
                self.current_joint1_targets[key] = 0.0
                self.current_joint2_targets[key] = 0.0
                self.current_joint1_positions[key] = 0.0
                self.current_joint2_positions[key] = 0.0
        
        # 添加大拇指控制
        # thumb_1: 直接控制, thumb_2: 输入, thumb_3/4: 映射计算
        self.thumb1_subs = {}  # thumb_1订阅者
        self.thumb2_subs = {}  # thumb_2订阅者(映射输入)
        self.thumb1_pubs = {}  # thumb_1发布者
        self.thumb2_pubs = {}  # thumb_2发布者
        self.thumb3_pubs = {}  # thumb_3发布者
        self.thumb4_pubs = {}  # thumb_4发布者
        
        # 存储大拇指目标和当前位置
        self.current_thumb1_targets = {}
        self.current_thumb2_targets = {}
        self.current_thumb3_targets = {}
        self.current_thumb4_targets = {}
        self.current_thumb1_positions = {}
        self.current_thumb2_positions = {}
        self.current_thumb3_positions = {}
        self.current_thumb4_positions = {}
        
        for hand in ['right', 'left']:
            # thumb_1: 直接控制(不映射)
            thumb1_topic = f'/ftp/{hand}_hand/thumb/joint1/cmd'
            self.thumb1_subs[hand] = self.create_subscription(
                Float64,
                thumb1_topic,
                lambda msg, h=hand: self.thumb1_callback(msg, h),
                10
            )
            thumb1_sim_topic = f'/model/ftp_{hand}_hand_nested/joint/{hand}_thumb_1_joint/cmd_vel'
            self.thumb1_pubs[hand] = self.create_publisher(Float64, thumb1_sim_topic, 10)
            
            # thumb_2: 映射输入
            thumb2_topic = f'/ftp/{hand}_hand/thumb/joint2/cmd'
            self.thumb2_subs[hand] = self.create_subscription(
                Float64,
                thumb2_topic,
                lambda msg, h=hand: self.thumb2_callback(msg, h),
                10
            )
            thumb2_sim_topic = f'/model/ftp_{hand}_hand_nested/joint/{hand}_thumb_2_joint/cmd_vel'
            self.thumb2_pubs[hand] = self.create_publisher(Float64, thumb2_sim_topic, 10)
            
            # thumb_3/4: 映射输出
            thumb3_sim_topic = f'/model/ftp_{hand}_hand_nested/joint/{hand}_thumb_3_joint/cmd_vel'
            self.thumb3_pubs[hand] = self.create_publisher(Float64, thumb3_sim_topic, 10)
            thumb4_sim_topic = f'/model/ftp_{hand}_hand_nested/joint/{hand}_thumb_4_joint/cmd_vel'
            self.thumb4_pubs[hand] = self.create_publisher(Float64, thumb4_sim_topic, 10)
            
            # 初始化大拇指位置
            self.current_thumb1_targets[hand] = 0.0
            self.current_thumb2_targets[hand] = 0.0
            self.current_thumb3_targets[hand] = 0.0
            self.current_thumb4_targets[hand] = 0.0
            self.current_thumb1_positions[hand] = 0.0
            self.current_thumb2_positions[hand] = 0.0
            self.current_thumb3_positions[hand] = 0.0
            self.current_thumb4_positions[hand] = 0.0
        
        # 创建定时器,以10Hz频率持续发布当前目标位置
        self.timer = self.create_timer(0.1, self.publish_targets)
        
        # 初始化打印时间戳
        self.last_print_time = self.get_clock().now()
        
        self.get_logger().info('✅ 关节1-2映射控制器已初始化')
        self.get_logger().info(f'� 关节1范围: {self.joint1_min:.4f} ~ {self.joint1_max:.4f} rad')
        self.get_logger().info(f'              ({np.degrees(self.joint1_min):.2f}° ~ {np.degrees(self.joint1_max):.2f}°)')
        self.get_logger().info(f'📐 关节2范围: {self.joint2_min:.4f} ~ {self.joint2_max:.4f} rad')
        self.get_logger().info(f'              ({np.degrees(self.joint2_min):.2f}° ~ {np.degrees(self.joint2_max):.2f}°)')
        self.get_logger().info('')
        self.get_logger().info('🎮 订阅话题格式: /ftp/<hand>_hand/<finger>/joint1/cmd')
        self.get_logger().info('   示例: /ftp/right_hand/index/joint1/cmd')
        self.get_logger().info('   手指: index, middle, ring, little')
        self.get_logger().info('   手: right_hand, left_hand')
        self.get_logger().info('   ⚠️  输入角度使用Excel G列值 (1.52~3.14 rad, 87°~180°)')
    
    def load_mapping_data(self):
        """
        使用3次多项式拟合建立映射关系
        
        四指映射:
        - G列(关节1): 1.52 ~ 3.14 rad (87° ~ 180°)
        - H列(关节2): 1.29 ~ 3.17 rad (74° ~ 182°)
        
        大拇指映射:
        - C列(thumb_2输入): 101.10° ~ 140.18°
        - D列(thumb_3输出): 145.05° ~ 189.25°
        - E列(thumb_4输出): 136.12° ~ 170.34°
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        excel_path = os.path.join(script_dir, '..', '驱动器行程与角度关系表.xls')
        
        if not os.path.exists(excel_path):
            self.get_logger().error(f'❌ 找不到映射文件: {excel_path}')
            raise FileNotFoundError(excel_path)
        
        # 读取 Excel
        df = pd.read_excel(excel_path, header=None)
        
        # ==== 四指映射 (G->H) ====
        G_deg = df.iloc[2:, 6].dropna().values.astype(float)
        H_deg = df.iloc[2:, 7].dropna().values.astype(float)
        
        # 转换为弧度
        G_rad = np.radians(G_deg)
        H_rad = np.radians(H_deg)
        
        # 数据从大到小,反转为从小到大
        G_rad = G_rad[::-1]
        H_rad = H_rad[::-1]
        
        # 3次多项式拟合: H = a*G^3 + b*G^2 + c*G + d
        self.poly_coeffs = np.polyfit(G_rad, H_rad, 3)
        self.poly_model = np.poly1d(self.poly_coeffs)
        
        # 记录四指范围
        self.joint1_min = G_rad.min()
        self.joint1_max = G_rad.max()
        self.joint2_min = H_rad.min()
        self.joint2_max = H_rad.max()
        
        # 计算四指拟合精度
        H_fitted = self.poly_model(G_rad)
        rmse = np.sqrt(np.mean((H_rad - H_fitted)**2))
        
        self.get_logger().info(f'✅ 四指多项式映射模型已建立 (3次多项式)')
        self.get_logger().info(f'   数据点: {len(G_rad)}, RMSE: {np.degrees(rmse):.4f}°')
        self.get_logger().info(f'   系数: a={self.poly_coeffs[0]:.6e}, b={self.poly_coeffs[1]:.6e}')
        self.get_logger().info(f'        c={self.poly_coeffs[2]:.6e}, d={self.poly_coeffs[3]:.6e}')
        
        # ==== 大拇指映射 (C->D, C->E) ====
        C_deg = df.iloc[2:, 2].dropna().values.astype(float)  # thumb_2
        D_deg = df.iloc[2:, 3].dropna().values.astype(float)  # thumb_3
        E_deg = df.iloc[2:, 4].dropna().values.astype(float)  # thumb_4
        
        # 转换为弧度
        C_rad = np.radians(C_deg)
        D_rad = np.radians(D_deg)
        E_rad = np.radians(E_deg)
        
        # 数据从大到小,反转为从小到大
        C_rad = C_rad[::-1]
        D_rad = D_rad[::-1]
        E_rad = E_rad[::-1]
        
        # C->D映射 (thumb_2 -> thumb_3)
        self.thumb_cd_coeffs = np.polyfit(C_rad, D_rad, 3)
        self.thumb_cd_model = np.poly1d(self.thumb_cd_coeffs)
        
        # C->E映射 (thumb_2 -> thumb_4)
        self.thumb_ce_coeffs = np.polyfit(C_rad, E_rad, 3)
        self.thumb_ce_model = np.poly1d(self.thumb_ce_coeffs)
        
        # 记录大拇指范围
        self.thumb2_min = C_rad.min()
        self.thumb2_max = C_rad.max()
        self.thumb3_min = D_rad.min()
        self.thumb3_max = D_rad.max()
        self.thumb4_min = E_rad.min()
        self.thumb4_max = E_rad.max()
        
        # 计算大拇指拟合精度
        D_fitted = self.thumb_cd_model(C_rad)
        E_fitted = self.thumb_ce_model(C_rad)
        rmse_d = np.sqrt(np.mean((D_rad - D_fitted)**2))
        rmse_e = np.sqrt(np.mean((E_rad - E_fitted)**2))
        
        self.get_logger().info(f'✅ 大拇指映射模型已建立 (3次多项式)')
        self.get_logger().info(f'   C->D: 数据点: {len(C_rad)}, RMSE: {np.degrees(rmse_d):.4f}°')
        self.get_logger().info(f'   C->E: 数据点: {len(C_rad)}, RMSE: {np.degrees(rmse_e):.4f}°')
    
    def map_joint1_to_joint2(self, joint1_angle):
        """
        使用3次多项式将关节1角度映射到关节2角度
        
        Args:
            joint1_angle: 关节1角度(弧度, Excel G列值)
        
        Returns:
            joint2_angle: 关节2角度(弧度, Excel H列值)
        """
        # 限制在有效范围内
        joint1_clamped = np.clip(joint1_angle, self.joint1_min, self.joint1_max)
        
        if abs(joint1_clamped - joint1_angle) > 0.001:  # 1mm tolerance
            self.get_logger().warn(
                f'⚠️  关节1角度超出范围: {joint1_angle:.4f} rad ({np.degrees(joint1_angle):.2f}°), '
                f'限制为 {joint1_clamped:.4f} rad ({np.degrees(joint1_clamped):.2f}°)'
            )
        
        # 使用多项式计算关节2角度
        joint2_angle = float(self.poly_model(joint1_clamped))
        
        return joint2_angle
    
    def excel_to_urdf_angle(self, excel_angle, is_joint2=False):
        """
        将Excel角度转换为URDF角度
        Excel: 大角度 = 伸直, 小角度 = 弯曲
        URDF: 0 rad = 伸直, 1.44 rad = 弯曲
        
        转换公式: urdf_angle = (excel_max - excel_angle) / (excel_max - excel_min) * urdf_max
        """
        if is_joint2:
            # Joint2 Excel范围
            excel_min = self.joint2_min  # 1.29 rad (弯曲)
            excel_max = self.joint2_max  # 3.17 rad (伸直)
        else:
            # Joint1 Excel范围
            excel_min = self.joint1_min  # 1.52 rad (弯曲)
            excel_max = self.joint1_max  # 3.14 rad (伸直)
        
        # URDF范围 (从URDF文件中的limit,两个关节相同)
        urdf_min = 0.0      # 伸直
        urdf_max = 1.4381   # 弯曲
        
        # 限制Excel角度在有效范围内
        excel_angle_clamped = np.clip(excel_angle, excel_min, excel_max)
        
        # 反转并缩放
        # Excel角度越大(接近180°)越伸直 -> URDF角度越小(接近0)越伸直
        urdf_angle = (excel_max - excel_angle_clamped) / (excel_max - excel_min) * urdf_max
        
        # 确保URDF角度也在有效范围内
        urdf_angle = np.clip(urdf_angle, urdf_min, urdf_max)
        
        return urdf_angle
    
    def joint1_callback(self, msg, hand, finger):
        """处理关节1角度命令"""
        excel_joint1_angle = msg.data
        
        # 使用Excel角度计算映射的Excel关节2角度
        excel_joint2_angle = self.map_joint1_to_joint2(excel_joint1_angle)
        
        # 转换为URDF角度
        urdf_joint1_angle = self.excel_to_urdf_angle(excel_joint1_angle, is_joint2=False)
        urdf_joint2_angle = self.excel_to_urdf_angle(excel_joint2_angle, is_joint2=True)
        
        # 更新目标位置(存储URDF角度,用于实际控制)
        key = f'{hand}_{finger}'
        self.current_joint1_targets[key] = urdf_joint1_angle
        self.current_joint2_targets[key] = urdf_joint2_angle
        
        self.get_logger().info(
            f'🎯 {hand} {finger}: Excel J1={excel_joint1_angle:.4f} rad ({np.degrees(excel_joint1_angle):.2f}°) '
            f'-> J2={excel_joint2_angle:.4f} rad ({np.degrees(excel_joint2_angle):.2f}°)'
        )
        self.get_logger().info(
            f'   URDF J1={urdf_joint1_angle:.4f} rad -> J2={urdf_joint2_angle:.4f} rad'
        )
    
    def excel_to_urdf_thumb(self, excel_angle, joint_num):
        """
        将Excel大拇指角度转换为URDF角度
        
        Args:
            excel_angle: Excel角度(弧度)
            joint_num: 关节编号 1=thumb_1, 2=thumb_2, 3=thumb_3, 4=thumb_4
        
        Returns:
            urdf_angle: URDF角度(弧度)
        """
        # 根据关节选择范围
        if joint_num == 1:
            # thumb_1: 不映射,直接传递(但仍需转换角度方向)
            # 假设Excel thumb_1范围与URDF一致(0~1.16 rad)
            urdf_angle = excel_angle
            urdf_min, urdf_max = 0.0, 1.1641
        elif joint_num == 2:
            # thumb_2: Excel C列范围
            excel_min, excel_max = self.thumb2_min, self.thumb2_max
            urdf_min, urdf_max = 0.0, 0.5864
            excel_angle_clamped = np.clip(excel_angle, excel_min, excel_max)
            urdf_angle = (excel_max - excel_angle_clamped) / (excel_max - excel_min) * urdf_max
        elif joint_num == 3:
            # thumb_3: Excel D列范围
            excel_min, excel_max = self.thumb3_min, self.thumb3_max
            urdf_min, urdf_max = 0.0, 0.5
            excel_angle_clamped = np.clip(excel_angle, excel_min, excel_max)
            urdf_angle = (excel_max - excel_angle_clamped) / (excel_max - excel_min) * urdf_max
        elif joint_num == 4:
            # thumb_4: Excel E列范围
            excel_min, excel_max = self.thumb4_min, self.thumb4_max
            urdf_min, urdf_max = 0.0, 3.14
            excel_angle_clamped = np.clip(excel_angle, excel_min, excel_max)
            urdf_angle = (excel_max - excel_angle_clamped) / (excel_max - excel_min) * urdf_max
        else:
            self.get_logger().error(f'❌ 无效的大拇指关节编号: {joint_num}')
            return 0.0
        
        # 确保URDF角度在有效范围内
        urdf_angle = np.clip(urdf_angle, urdf_min, urdf_max)
        
        return urdf_angle
    
    def thumb1_callback(self, msg, hand):
        """处理thumb_1角度命令(直接控制,无映射)"""
        excel_angle = msg.data
        urdf_angle = self.excel_to_urdf_thumb(excel_angle, joint_num=1)
        
        self.current_thumb1_targets[hand] = urdf_angle
        
        self.get_logger().info(
            f'🎯 {hand} thumb_1: Excel={excel_angle:.4f} rad ({np.degrees(excel_angle):.2f}°) '
            f'-> URDF={urdf_angle:.4f} rad'
        )
    
    def thumb2_callback(self, msg, hand):
        """处理thumb_2角度命令(映射输入,计算thumb_3和thumb_4)"""
        excel_thumb2 = msg.data
        
        # 限制在有效范围内
        excel_thumb2_clamped = np.clip(excel_thumb2, self.thumb2_min, self.thumb2_max)
        
        if abs(excel_thumb2_clamped - excel_thumb2) > 0.001:
            self.get_logger().warn(
                f'⚠️  thumb_2角度超出范围: {excel_thumb2:.4f} rad, '
                f'限制为 {excel_thumb2_clamped:.4f} rad'
            )
        
        # 使用多项式计算thumb_3和thumb_4的Excel角度
        excel_thumb3 = float(self.thumb_cd_model(excel_thumb2_clamped))
        excel_thumb4 = float(self.thumb_ce_model(excel_thumb2_clamped))
        
        # 转换为URDF角度
        urdf_thumb2 = self.excel_to_urdf_thumb(excel_thumb2_clamped, joint_num=2)
        urdf_thumb3 = self.excel_to_urdf_thumb(excel_thumb3, joint_num=3)
        urdf_thumb4 = self.excel_to_urdf_thumb(excel_thumb4, joint_num=4)
        
        # 更新目标位置
        self.current_thumb2_targets[hand] = urdf_thumb2
        self.current_thumb3_targets[hand] = urdf_thumb3
        self.current_thumb4_targets[hand] = urdf_thumb4
        
        self.get_logger().info(
            f'🎯 {hand} thumb: Excel T2={excel_thumb2_clamped:.4f} rad ({np.degrees(excel_thumb2_clamped):.2f}°) '
            f'-> T3={excel_thumb3:.4f} rad ({np.degrees(excel_thumb3):.2f}°), '
            f'T4={excel_thumb4:.4f} rad ({np.degrees(excel_thumb4):.2f}°)'
        )
        self.get_logger().info(
            f'   URDF T2={urdf_thumb2:.4f} rad, T3={urdf_thumb3:.4f} rad, T4={urdf_thumb4:.4f} rad'
        )
    
    def publish_targets(self):
        """定时发布速度指令,通过PD控制逼近目标位置"""
        current_time = self.get_clock().now()
        dt = 0.1  # 10Hz控制频率
        
        # 初始化打印时间戳(第一次调用时)
        if not hasattr(self, 'last_print_time'):
            self.last_print_time = current_time
        
        for key in self.current_joint1_targets:
            hand, finger = key.split('_')
            
            # 计算位置误差
            error_j1 = self.current_joint1_targets[key] - self.current_joint1_positions[key]
            error_j2 = self.current_joint2_targets[key] - self.current_joint2_positions[key]
            
            # 计算速度指令(比例控制)
            vel_j1 = self.Kp * error_j1
            vel_j2 = self.Kp * error_j2
            
            # 限制最大速度
            vel_j1 = np.clip(vel_j1, -self.max_velocity, self.max_velocity)
            vel_j2 = np.clip(vel_j2, -self.max_velocity, self.max_velocity)
            
            # 更新位置估计(积分)
            self.current_joint1_positions[key] += vel_j1 * dt
            self.current_joint2_positions[key] += vel_j2 * dt
            
            # 发布速度指令
            j1_msg = Float64()
            j1_msg.data = vel_j1
            self.joint1_pubs[key].publish(j1_msg)
            
            j2_msg = Float64()
            j2_msg.data = vel_j2
            self.joint2_pubs[key].publish(j2_msg)
        
        # ==== 大拇指控制循环 ====
        for hand in ['right', 'left']:
            # thumb_1
            if hand in self.current_thumb1_targets:
                error = self.current_thumb1_targets[hand] - self.current_thumb1_positions[hand]
                vel = np.clip(self.Kp * error, -self.max_velocity, self.max_velocity)
                self.current_thumb1_positions[hand] += vel * dt
                
                msg = Float64()
                msg.data = vel
                self.thumb1_pubs[hand].publish(msg)
            
            # thumb_2
            if hand in self.current_thumb2_targets:
                error = self.current_thumb2_targets[hand] - self.current_thumb2_positions[hand]
                vel = np.clip(self.Kp * error, -self.max_velocity, self.max_velocity)
                self.current_thumb2_positions[hand] += vel * dt
                
                msg = Float64()
                msg.data = vel
                self.thumb2_pubs[hand].publish(msg)
            
            # thumb_3
            if hand in self.current_thumb3_targets:
                error = self.current_thumb3_targets[hand] - self.current_thumb3_positions[hand]
                vel = np.clip(self.Kp * error, -self.max_velocity, self.max_velocity)
                self.current_thumb3_positions[hand] += vel * dt
                
                msg = Float64()
                msg.data = vel
                self.thumb3_pubs[hand].publish(msg)
            
            # thumb_4
            if hand in self.current_thumb4_targets:
                error = self.current_thumb4_targets[hand] - self.current_thumb4_positions[hand]
                vel = np.clip(self.Kp * error, -self.max_velocity, self.max_velocity)
                self.current_thumb4_positions[hand] += vel * dt
                
                msg = Float64()
                msg.data = vel
                self.thumb4_pubs[hand].publish(msg)
        
        # 打印当前状态 (每秒一次)
        time_diff = (current_time - self.last_print_time).nanoseconds / 1e9
        if time_diff >= 1.0:
            self.get_logger().info('当前状态:')
            for key in sorted(self.current_joint1_targets.keys()):
                hand, finger = key.split('_')
                target_j1 = self.current_joint1_targets[key]
                target_j2 = self.current_joint2_targets[key]
                pos_j1 = self.current_joint1_positions[key]
                pos_j2 = self.current_joint2_positions[key]
                self.get_logger().info(
                    f'  {hand} {finger}: '
                    f'J1: {pos_j1:.4f}/{target_j1:.4f} rad, '
                    f'J2: {pos_j2:.4f}/{target_j2:.4f} rad'
                )
            
            # 打印大拇指状态
            for hand in ['right', 'left']:
                if hand in self.current_thumb1_targets:
                    self.get_logger().info(
                        f'  {hand} thumb: '
                        f'T1: {self.current_thumb1_positions[hand]:.4f}/{self.current_thumb1_targets[hand]:.4f} rad, '
                        f'T2: {self.current_thumb2_positions[hand]:.4f}/{self.current_thumb2_targets[hand]:.4f} rad, '
                        f'T3: {self.current_thumb3_positions[hand]:.4f}/{self.current_thumb3_targets[hand]:.4f} rad, '
                        f'T4: {self.current_thumb4_positions[hand]:.4f}/{self.current_thumb4_targets[hand]:.4f} rad'
                    )
            
            self.last_print_time = current_time


def main(args=None):
    rclpy.init(args=args)
    
    try:
        controller = Joint12MappingController()
        rclpy.spin(controller)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'❌ 错误: {e}')
        import traceback
        traceback.print_exc()
    finally:
        if 'controller' in locals():
            controller.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
