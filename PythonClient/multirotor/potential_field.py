import airsim
import numpy as np
import time

# 定数
TARGET_POS = np.array([10.0, 10.0, -10.0])  # 目標位置
K_ATTRACTIVE = 1.0  # 目標位置のポテンシャルの重み
K_REPULSIVE = 5.0  # 障害物位置のポテンシャルの重み
OBSTACLE_THRESHOLD = 10.0  # 障害物とみなす距離の閾値
DELTA_T = 0.1  # 時間ステップ
FORWARD_VELOCITY = 2.0  # 前進する速度
MIN_ALTITUDE = -5.0  # 地面から5m以上の高度を保つ
LEFT_BIAS = 0.2  # 左方向へのバイアスの強さ

# AirSimクライアントの設定
client = airsim.MultirotorClient(ip='172.23.32.1')
client.confirmConnection()
client.enableApiControl(True)
client.armDisarm(True)
client.takeoffAsync().join()

# ポテンシャル関数の計算
def calculate_potential(current_pos, obstacle_pos, target_pos):
    Po = 1.0 / np.linalg.norm(current_pos - obstacle_pos)**2
    Pd = -1.0 / np.linalg.norm(current_pos - target_pos)**2
    return K_REPULSIVE * Po + K_ATTRACTIVE * Pd

# 勾配の計算
def calculate_gradient(current_pos, obstacles, target_pos):
    grad = np.zeros(3)
    for obstacle in obstacles:
        distance = np.linalg.norm(current_pos - obstacle)
        if distance > 0:  # 距離が0でない場合のみ計算
            Po = 1.0 / distance**2
            grad[:2] += K_REPULSIVE * Po * (current_pos[:2] - obstacle[:2]) / distance**3
    distance = np.linalg.norm(current_pos - target_pos)
    if distance > 0:  # 距離が0でない場合のみ計算
        Pd = 1.0 / distance**2
        grad[:2] += -K_ATTRACTIVE * Pd * (current_pos[:2] - target_pos[:2]) / distance**3
    grad[1] += LEFT_BIAS  # 左方向へのバイアスを追加
    return grad

# メインループ
while True:
    # 現在の位置を取得
    kinematics = client.simGetGroundTruthKinematics().position
    current_pos = np.array([kinematics.x_val, kinematics.y_val, kinematics.z_val])
    
    # LiDARデータの取得
    lidar_data = client.getLidarData()
    if len(lidar_data.point_cloud) < 3:
        continue

    # 障害物位置の計算
    points = np.array(lidar_data.point_cloud).reshape(-1, 3)
    obstacles = [point for point in points if np.linalg.norm(current_pos - point) < OBSTACLE_THRESHOLD]

    # ポテンシャル勾配の計算
    if obstacles:
        grad = calculate_gradient(current_pos, obstacles, TARGET_POS)

        # 勾配ベクトルに基づく新しい速度ベクトルの計算
        if np.linalg.norm(grad) > 0:  # 勾配が0でない場合のみ計算
            velocity = -grad / np.linalg.norm(grad) * FORWARD_VELOCITY
            print("Obstacles detected, potential field method")
            print(f"Current Position: {current_pos}")
        else:
            velocity = np.zeros(3)
    else:
        # 障害物がない場合は前進
        velocity = np.array([FORWARD_VELOCITY, 0, 0])
    
    # 高度を維持するための制御
    if current_pos[2] > MIN_ALTITUDE:
        velocity[2] = max(velocity[2], 0)  # 降下を防ぐ
    else:
        velocity[2] = min(velocity[2], 0)  # 上昇のみ許可

    # 速度の設定
    client.moveByVelocityAsync(velocity[0], velocity[1], velocity[2]-0.059999, DELTA_T).join()

    # 目標位置に到達したかどうかを確認
    if np.linalg.norm(current_pos - TARGET_POS) < 1.0:
        print("Target reached!")
        break

    time.sleep(DELTA_T)

client.landAsync().join()
client.armDisarm(False)
client.enableApiControl(False)
