import socket
import sys
import time

# 树莓派的IP地址 (请根据实际情况修改)
# 如果不知道IP，可以在树莓派上运行 `hostname -I` 查看
RASPBERRY_PI_IP = '10.42.0.174' 
PORT = 8888

def main():
    if len(sys.argv) > 1:
        server_ip = sys.argv[1]
    else:
        server_ip = input(f"请输入树莓派IP地址 [默认 {RASPBERRY_PI_IP}]: ").strip()
        if not server_ip:
            server_ip = RASPBERRY_PI_IP

    print(f"正在连接到 {server_ip}:{PORT} ...")
    
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_ip, PORT))
        print("连接成功！现在可以输入指令控制舵机。")
        print("输入 'EXIT' 退出程序。")
        print("输入 'RAMP' 发送 6-10N 阶梯指令（10秒完成，每0.5秒一次）。")

        while True:
            cmd = input("DexEXO> ").strip()
            if not cmd:
                continue
            
            if cmd.upper() == 'EXIT':
                break

            if cmd.upper() == 'RAMP':
                start_force = 6.0
                end_force = 10.0
                total_time = 10.0
                interval = 0.5
                steps = int(total_time / interval)
                if steps <= 0:
                    steps = 1
                step_force = (end_force - start_force) / steps

                for i in range(steps + 1):
                    value = start_force + step_force * i
                    cmd_str = f"N:2:{value:.2f}"
                    client_socket.sendall(cmd_str.encode('utf-8'))
                    print(f"Sent: {cmd_str}")
                    time.sleep(interval)
                continue
                
            # 发送指令
            client_socket.sendall(cmd.encode('utf-8'))
            
            # 接收反馈 (可选，取决于服务器是否发送反馈)
            try:
                response = client_socket.recv(1024)
                print(f"Server: {response.decode('utf-8').strip()}")
            except socket.timeout:
                pass
                
    except ConnectionRefusedError:
        print("连接失败：目标计算机拒绝连接。请检查IP地址和树莓派程序是否运行。")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        client_socket.close()
        print("连接已关闭。")

if __name__ == '__main__':
    main()
