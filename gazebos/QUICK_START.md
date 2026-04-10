# FTP双手灵巧手 - 快速启动指南

## 📍 当前路径
本项目位于: `/home/wxc/projects/dexEXO/gazebos`

## 🚀 快速开始

### 1. 检查环境
```bash
./check_environment.sh
```

### 2. 启动系统
```bash
./restart_system.sh
```

### 3. 运行测试
```bash
# 等待系统就绪约5秒
sleep 5

# 运行完整测试
./test_hands.sh --delay 1.5
```

### 4. 重置手指
```bash
./reset_hands.sh
```

## 🎯 使用快速启动菜单
```bash
./quick_start.sh
```

## 📝 手动控制命令

### 四指控制
```bash
# 右手食指弯曲
ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 1.52}'

# 右手食指伸直
ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 3.14}'
```

### 大拇指控制
```bash
# 大拇指外展
ros2 topic pub -1 /ftp/right_hand/thumb/joint1/cmd std_msgs/Float64 '{data: 0.8}'

# 大拇指弯曲
ros2 topic pub -1 /ftp/right_hand/thumb/joint2/cmd std_msgs/Float64 '{data: 2.0944}'
```

## 🔍 查看日志
```bash
tail -f /tmp/joint12_controller.log
```

## 📚 详细文档
查看完整文档: `README.md`
