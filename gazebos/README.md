# FTP双手灵巧手仿真系统

完整的ROS 2 + Ignition Gazebo双手灵巧手控制系统，支持基于Excel数据的多项式映射控制。

## 📋 目录

- [环境要求](#环境要求)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [手指控制说明](#手指控制说明)
- [关节限制](#关节限制)
- [测试文档](#测试文档)
- [故障排查](#故障排查)
- [文件结构](#文件结构)

---

## 🔧 环境要求

### 系统环境
- **操作系统**: Ubuntu 22.04 LTS
- **ROS版本**: ROS 2 Humble
- **仿真器**: Ignition Gazebo 6.17.0
- **Python**: 3.10 (系统Python,用于ROS节点)

### 依赖安装

```bash
# 安装ROS 2 Humble
sudo apt update
sudo apt install ros-humble-desktop

# 安装Ignition Gazebo
sudo apt install ros-humble-ros-gz

# 安装Python依赖
sudo apt install python3-pip
pip3 install pandas openpyxl numpy

# Source ROS环境 (添加到~/.bashrc)
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### 验证安装

```bash
# 检查ROS 2
ros2 --version

# 检查Gazebo
gz sim --version

# 检查Python包
python3 -c "import pandas, numpy; print('Python dependencies OK')"
```

---

## 🏗️ 系统架构

### 整体架构图

```
用户命令 (ROS 2 Topics)
    ↓
/ftp/{hand}_hand/{finger}/joint1/cmd
    ↓
joint12_mapping_controller.py
├─ 四指: Excel G→H多项式映射 (joint1 → joint2)
├─ 大拇指: thumb_1直接控制
└─ 大拇指: Excel C→D,E映射 (thumb_2 → thumb_3,4)
    ↓
/model/ftp_{hand}_hand_nested/joint/{joint_name}/cmd_vel
    ↓
ros_gz_bridge (24 topics)
    ↓
Ignition Gazebo (JointController plugins)
    ↓
URDF模型 (无mimic约束,独立控制)
```

### 核心组件

1. **Ignition Gazebo**: 物理仿真环境
2. **ros_gz_bridge**: ROS 2 ↔ Gazebo话题桥接 (24个通道)
3. **joint12_mapping_controller.py**: 映射控制节点
   - PD速度控制器 (Kp=2.0, max_vel=1.0 rad/s)
   - Excel多项式映射 (RMSE < 0.25°)
   - 双向角度转换 (Excel ↔ URDF)

### 话题通信

**输入话题** (用户控制):
```
/ftp/right_hand/index/joint1/cmd      # 右手食指
/ftp/right_hand/middle/joint1/cmd     # 右手中指
/ftp/right_hand/ring/joint1/cmd       # 右手无名指
/ftp/right_hand/little/joint1/cmd     # 右手小指
/ftp/right_hand/thumb/joint1/cmd      # 右手大拇指侧摆
/ftp/right_hand/thumb/joint2/cmd      # 右手大拇指弯曲

# 左手话题同理 (left_hand)
```

**输出话题** (发送到Gazebo):
```
/model/ftp_right_hand_nested/joint/right_{finger}_{1,2}_joint/cmd_vel
/model/ftp_right_hand_nested/joint/right_thumb_{1,2,3,4}_joint/cmd_vel
```

---

## 🚀 快速开始

### 1. 克隆/解压项目

```bash
cd /home/wxc/dexhandsim
```

### 2. 启动完整系统

```bash
# 使用自动启动脚本 (推荐)
./restart_system.sh

# 或手动启动 (分3个终端)
# 终端1: 启动Gazebo
gz sim worlds/ftp_dual_hands.sdf

# 终端2: 启动桥接器 (等待Gazebo加载完成)
source /opt/ros/humble/setup.bash
./start_hand_control.sh

# 终端3: 启动控制器
source /opt/ros/humble/setup.bash
python3 scripts/joint12_mapping_controller.py
```

### 3. 验证系统运行

```bash
# 检查所有进程
ps aux | grep -E "gz sim|bridge|joint12"

# 检查话题
ros2 topic list | grep cmd

# 查看控制器日志
tail -f /tmp/joint12_controller.log
```

### 4. 简单测试

```bash
source /opt/ros/humble/setup.bash

# 测试右手食指弯曲
ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 1.52}'

# 测试右手食指伸直
ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 3.14}'

# 测试大拇指外展
ros2 topic pub -1 /ftp/right_hand/thumb/joint1/cmd std_msgs/Float64 '{data: 0.8}'

# 测试大拇指弯曲 (自动映射thumb_3和thumb_4)
ros2 topic pub -1 /ftp/right_hand/thumb/joint2/cmd std_msgs/Float64 '{data: 2.0944}'
```

---

## 🖐️ 手指控制说明

### 四指控制 (食指/中指/无名指/小指)

#### 控制策略
- **输入**: 发送 joint1 角度 (Excel G列值)
- **输出**: joint2 自动通过多项式映射计算
- **映射模型**: 3次多项式 (RMSE: 0.2474°)

#### 角度范围
| 项目 | Excel角度 | Excel弧度 | 含义 |
|------|----------|----------|------|
| **最伸直** | 180° | 3.14 rad | 手指完全伸直 |
| **中间** | 133° | 2.32 rad | 手指半弯曲 |
| **最弯曲** | 87° | 1.52 rad | 手指最大弯曲 |

#### 控制示例

```bash
# 右手食指
ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 3.14}'   # 伸直
ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 2.32}'   # 半弯
ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 1.52}'   # 弯曲

# 左手中指
ros2 topic pub -1 /ftp/left_hand/middle/joint1/cmd std_msgs/Float64 '{data: 3.14}'

# 右手无名指
ros2 topic pub -1 /ftp/right_hand/ring/joint1/cmd std_msgs/Float64 '{data: 2.0}'

# 左手小指
ros2 topic pub -1 /ftp/left_hand/little/joint1/cmd std_msgs/Float64 '{data: 1.8}'
```

#### 映射计算

控制器会自动计算joint2:
```
用户输入: joint1 = 180° (3.14 rad)
映射计算: joint2 = 182° (3.17 rad)
日志显示: 🎯 right index: Excel J1=3.1416 rad (180.00°) -> J2=3.1803 rad (182.22°)
```

### 大拇指控制

#### thumb_1 (侧摆) - 直接控制

**功能**: 大拇指根部外展/内收运动

**角度范围**:
- 0 rad: 贴合手掌
- 0.58 rad (33°): 中等外展
- 1.16 rad (66°): 最大外展

**控制示例**:
```bash
# 贴合
ros2 topic pub -1 /ftp/right_hand/thumb/joint1/cmd std_msgs/Float64 '{data: 0.0}'

# 中等外展
ros2 topic pub -1 /ftp/right_hand/thumb/joint1/cmd std_msgs/Float64 '{data: 0.58}'

# 最大外展
ros2 topic pub -1 /ftp/right_hand/thumb/joint1/cmd std_msgs/Float64 '{data: 1.16}'
```

#### thumb_2 (弯曲) - 映射控制

**功能**: 大拇指弯曲,自动计算thumb_3和thumb_4

**角度范围** (Excel C列):
- 101.10° (1.76 rad): 最伸直
- 120° (2.09 rad): 中等弯曲
- 140.18° (2.45 rad): 最弯曲

**映射精度**:
- C→D映射: RMSE 0.0140°
- C→E映射: RMSE 0.0019°

**控制示例**:
```bash
# 伸直 (thumb_3和thumb_4自动伸直)
ros2 topic pub -1 /ftp/right_hand/thumb/joint2/cmd std_msgs/Float64 '{data: 1.76}'

# 中等弯曲
ros2 topic pub -1 /ftp/right_hand/thumb/joint2/cmd std_msgs/Float64 '{data: 2.09}'

# 最大弯曲
ros2 topic pub -1 /ftp/right_hand/thumb/joint2/cmd std_msgs/Float64 '{data: 2.45}'
```

**映射计算示例**:
```
用户输入: thumb_2 = 120° (2.0944 rad)
映射计算: thumb_3 = 164.62°, thumb_4 = 157.01°
日志显示: 🎯 right thumb: Excel T2=2.0944 rad (120.00°) 
          -> T3=2.8731 rad (164.62°), T4=2.7404 rad (157.01°)
```

---

## ⚙️ 关节限制

### 四指关节限制 (index/middle/ring/little)

| 关节 | URDF范围 | Excel范围 | 说明 |
|------|---------|----------|------|
| joint1 | 0 ~ 1.4381 rad | 87° ~ 180° (1.52 ~ 3.14 rad) | 第一指节 |
| joint2 | 0 ~ 1.4381 rad | 74° ~ 182° (1.29 ~ 3.17 rad) | 第二指节 |

**重要**:
- Excel: 大角度 = 伸直, 小角度 = 弯曲
- URDF: 0 rad = 伸直, 1.44 rad = 弯曲
- 控制器自动转换角度方向

### 大拇指关节限制

| 关节 | 范围 | 控制方式 | 说明 |
|------|------|---------|------|
| thumb_1 | 0 ~ 1.1641 rad | 直接控制 | 侧摆(外展/内收) |
| thumb_2 | 0 ~ 0.5864 rad | 映射输入 | 第一指节弯曲 |
| thumb_3 | 0 ~ 0.5 rad | 自动映射 | 第二指节(由thumb_2计算) |
| thumb_4 | 0 ~ 3.14 rad | 自动映射 | 指尖(由thumb_2计算) |

### 速度限制

所有关节都使用PD速度控制:
- **最大速度**: 1.0 rad/s
- **控制频率**: 10Hz
- **Kp增益**: 2.0

**运动时间估算**:
- 最大行程 (1.44 rad): 约1.5秒
- 半行程 (0.72 rad): 约0.8秒

---

## 🧪 测试文档

### 自动化测试脚本

项目提供完整的自动化测试工具:

#### 1. 完整运动测试

```bash
# 测试双手所有手指 (默认2秒延迟)
./test_hands.sh

# 快速测试 (1秒延迟)
./test_hands.sh --delay 1.0

# 只测试右手
./test_hands.sh --hand right

# 只测试大拇指
./test_hands.sh --fingers thumb

# 测试特定手指
./test_hands.sh --fingers index,middle
```

**测试内容**:
- 四指: 3步弯曲 (180°→150°→120°→87°) + 3步伸直
- 大拇指侧摆: 3步外展 (0→0.4→0.8→1.16) + 3步复原
- 大拇指弯曲: 3步弯曲 (101°→115°→127°→140°) + 3步伸直

**预计时间**: 约2分钟 (双手5手指×6步)

#### 2. 重置手指

```bash
# 将所有手指恢复到初始伸直状态
./reset_hands.sh
```

#### 3. 大拇指映射测试

```bash
# 交互式测试
python3 test_thumb_mapping.py

# 命令行测试
./test_thumb.sh thumb1 right 0.5      # 测试thumb_1
./test_thumb.sh thumb2 right 120      # 测试thumb_2映射
```

### 手动测试步骤

#### 测试1: 单个手指完整运动

```bash
# 1. 右手食指弯曲
ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 1.52}'

# 2. 等待2秒,观察运动

# 3. 右手食指伸直
ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 3.14}'

# 4. 查看日志确认映射
tail -f /tmp/joint12_controller.log | grep "right index"
```

#### 测试2: 大拇指组合运动

```bash
# 1. 大拇指外展
ros2 topic pub -1 /ftp/right_hand/thumb/joint1/cmd std_msgs/Float64 '{data: 0.8}'

# 2. 大拇指弯曲 (自动映射)
ros2 topic pub -1 /ftp/right_hand/thumb/joint2/cmd std_msgs/Float64 '{data: 2.0944}'

# 3. 观察thumb_3和thumb_4自动跟随

# 4. 查看映射日志
grep "🎯.*thumb" /tmp/joint12_controller.log | tail -5
```

#### 测试3: 双手协同

```bash
# 同时控制双手食指
ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd std_msgs/Float64 '{data: 2.0}' &
ros2 topic pub -1 /ftp/left_hand/index/joint1/cmd std_msgs/Float64 '{data: 2.0}' &
```

### 测试验收标准

- [ ] 所有手指能完成弯曲和伸直
- [ ] 运动平滑,无异常卡顿
- [ ] joint2能自动跟随joint1映射
- [ ] 大拇指thumb_3/4能自动跟随thumb_2映射
- [ ] 日志中无ERROR或WARN
- [ ] 映射精度符合预期 (查看日志中🎯标记)

### 查看测试结果

```bash
# 实时查看控制器日志
tail -f /tmp/joint12_controller.log

# 只看映射计算
tail -f /tmp/joint12_controller.log | grep "🎯"

# 只看当前状态
tail -f /tmp/joint12_controller.log | grep "当前状态" -A 12

# 查看错误
grep -E "ERROR|WARN" /tmp/joint12_controller.log
```

---

## 🐛 故障排查

### 问题1: 系统无响应

**症状**: 发送命令后手指不动

**排查步骤**:
```bash
# 1. 检查所有进程是否运行
ps aux | grep -E "gz sim|bridge|joint12"

# 2. 检查话题是否存在
ros2 topic list | grep cmd

# 3. 重启系统
./restart_system.sh
```

### 问题2: 手指运动异常

**症状**: 手指运动方向错误或幅度不对

**排查步骤**:
```bash
# 1. 查看映射计算日志
grep "🎯" /tmp/joint12_controller.log | tail -10

# 2. 检查角度转换
# Excel: 180° = 伸直, 87° = 弯曲
# URDF: 0 rad = 伸直, 1.44 rad = 弯曲

# 3. 验证URDF是否有mimic约束 (应该没有)
grep "mimic" urdf/FTP_right_hand.urdf
# 无输出 = 正确
```

### 问题3: 映射精度问题

**症状**: joint2位置与预期不符

**排查步骤**:
```bash
# 1. 查看映射模型加载日志
head -20 /tmp/joint12_controller.log | grep "多项式"

# 2. 验证Excel文件存在
ls -lh 驱动器行程与角度关系表.xls

# 3. 检查映射精度
# 四指: RMSE应约为0.25°
# 大拇指: RMSE应小于0.02°
```

### 问题4: 桥接器断开

**症状**: 话题存在但无数据传输

**排查步骤**:
```bash
# 1. 检查桥接器日志
ps aux | grep ros_gz_bridge

# 2. 检查话题连接
ros2 topic info /ftp/right_hand/index/joint1/cmd

# 3. 重启桥接器
pkill -f ros_gz_bridge
./start_hand_control.sh
```

### 问题5: Python环境冲突

**症状**: 运行脚本时ModuleNotFoundError

**解决方法**:
```bash
# 使用系统Python而不是conda
source /opt/ros/humble/setup.bash
/usr/bin/python3 scripts/joint12_mapping_controller.py

# 或使用包装脚本 (自动处理环境)
./test_hands.sh
```

### 常用诊断命令

```bash
# 系统健康检查
ps aux | grep -E "gz|bridge|joint12"     # 检查进程
ros2 topic list | wc -l                  # 话题数量 (应>20)
ros2 node list                           # 节点列表

# 日志查看
tail -f /tmp/joint12_controller.log      # 实时日志
journalctl -f | grep gazebo              # Gazebo日志

# 性能监控
top -p $(pgrep -f "gz sim")              # Gazebo CPU/内存
ros2 topic hz /ftp/right_hand/index/joint1/cmd  # 话题频率
```

---

## 📁 文件结构

```
dexhandsim/
├── README.md                              # 本文档
│
├── 核心文件
│   ├── urdf/
│   │   ├── FTP_right_hand.urdf           # 右手URDF (已移除mimic)
│   │   └── FTP_left_hand.urdf            # 左手URDF (已移除mimic)
│   ├── models/
│   │   ├── FTP_right_hand.sdf            # 右手SDF (含JointController)
│   │   └── FTP_left_hand.sdf             # 左手SDF (含JointController)
│   ├── worlds/
│   │   └── ftp_dual_hands.sdf            # 双手世界文件
│   └── 驱动器行程与角度关系表.xls          # 映射数据源
│
├── 控制脚本
│   ├── scripts/
│   │   └── joint12_mapping_controller.py # 主控制器 (映射+PD控制)
│   ├── start_hand_control.sh             # 桥接器启动脚本
│   └── restart_system.sh                 # 完整系统重启脚本
│
├── 测试脚本
│   ├── test_hands.sh                     # 完整运动测试 (推荐)
│   ├── test_dual_hands_motion.py         # 测试脚本主体
│   ├── reset_hands.sh                    # 重置手指
│   ├── test_thumb_mapping.py             # 大拇指映射测试
│   └── test_thumb.sh                     # 大拇指测试包装器
│
├── 文档
│   ├── TEST_HANDS_MOTION_GUIDE.md        # 测试详细指南
│   ├── TEST_SCRIPTS_README.md            # 测试脚本快速参考
│   ├── TEST_SUMMARY.md                   # 测试完成总结
│   ├── THUMB_MAPPING_CONTROL.md          # 大拇指控制文档
│   ├── THUMB_IMPLEMENTATION_SUMMARY.md   # 大拇指实现总结
│   ├── THUMB_JOINTS_ANALYSIS.md          # 大拇指关节分析
│   └── QUICK_TEST_CARD.txt               # 快速使用卡片
│
└── 日志
    └── /tmp/joint12_controller.log        # 控制器运行日志
```

---

## 📚 详细文档索引

### 入门文档
- **README.md** (本文档): 完整的入门和参考指南
- **QUICK_TEST_CARD.txt**: 一页纸快速参考卡片

### 测试文档
- **TEST_SCRIPTS_README.md**: 所有测试脚本快速参考
- **TEST_HANDS_MOTION_GUIDE.md**: 详细的测试使用指南 (520行)
- **TEST_SUMMARY.md**: 测试实现总结和验收标准

### 技术文档
- **THUMB_MAPPING_CONTROL.md**: 大拇指映射控制完整文档
- **THUMB_IMPLEMENTATION_SUMMARY.md**: 大拇指技术实现细节
- **THUMB_JOINTS_ANALYSIS.md**: 大拇指关节结构分析

---

## 🎯 快速参考

### 启动命令
```bash
./restart_system.sh              # 启动完整系统
./test_hands.sh                  # 自动化测试
./reset_hands.sh                 # 重置手指
```

### 控制命令
```bash
# 四指 (数值: 1.52~3.14 rad)
ros2 topic pub -1 /ftp/{hand}_hand/{finger}/joint1/cmd std_msgs/Float64 '{data: 值}'

# 大拇指侧摆 (数值: 0~1.16 rad)
ros2 topic pub -1 /ftp/{hand}_hand/thumb/joint1/cmd std_msgs/Float64 '{data: 值}'

# 大拇指弯曲 (数值: 1.76~2.45 rad)
ros2 topic pub -1 /ftp/{hand}_hand/thumb/joint2/cmd std_msgs/Float64 '{data: 值}'
```

### 监控命令
```bash
tail -f /tmp/joint12_controller.log           # 实时日志
tail -f /tmp/joint12_controller.log | grep "🎯"  # 映射计算
ps aux | grep -E "gz|bridge|joint12"          # 进程状态
```

---

## 💡 最佳实践

### 1. 启动顺序
始终使用 `./restart_system.sh` 确保正确的启动顺序:
1. 先启动Gazebo (等待5秒加载)
2. 再启动桥接器 (建立话题连接)
3. 最后启动控制器 (订阅话题)

### 2. 角度输入
- **四指**: 使用Excel G列值 (1.52~3.14 rad)
- **大拇指侧摆**: 直接使用物理角度 (0~1.16 rad)
- **大拇指弯曲**: 使用Excel C列值 (1.76~2.45 rad)

### 3. 测试流程
```bash
# 1. 启动系统
./restart_system.sh

# 2. 等待系统就绪 (约5秒)
sleep 5

# 3. 运行测试
./test_hands.sh --delay 1.5

# 4. 测试后重置
./reset_hands.sh
```

### 4. 调试技巧
- 始终查看日志了解系统状态
- 使用 `grep "🎯"` 快速定位映射计算
- 使用 `--delay` 参数调整观察速度
- 出问题先重启系统: `./restart_system.sh`

---

## 🤝 技术支持

### 日志位置
- **控制器日志**: `/tmp/joint12_controller.log`
- **Gazebo日志**: `journalctl -f | grep gazebo`

### 关键参数
- **控制频率**: 10Hz
- **最大速度**: 1.0 rad/s
- **PD增益**: Kp=2.0
- **映射精度**: 四指~0.25°, 大拇指<0.02°

### 常见问题
1. **系统无响应** → 运行 `./restart_system.sh`
2. **角度方向错误** → 检查是否使用Excel范围值
3. **映射不准确** → 查看日志中的RMSE值
4. **Python错误** → 确保使用系统Python (`/usr/bin/python3`)

---

## 📊 系统指标

### 性能指标
- **启动时间**: 约10秒
- **响应延迟**: <100ms
- **映射精度**: RMSE <0.25° (四指), <0.02° (大拇指)
- **运动时间**: 最大行程约1.5秒

### 资源占用
- **Gazebo**: ~500MB内存, ~30% CPU
- **桥接器**: ~50MB内存, ~5% CPU
- **控制器**: ~100MB内存, ~10% CPU

### 话题统计
- **控制话题**: 12个 (6手指×2手)
- **Gazebo话题**: 24个 (12关节×2手)
- **总计**: 36个活跃话题

---

## ✅ 验收清单

系统部署验收:
- [ ] 所有依赖安装完成
- [ ] Gazebo能正常启动
- [ ] 桥接器话题连接正常
- [ ] 控制器无ERROR日志
- [ ] 四指弯曲/伸直正常
- [ ] 大拇指侧摆正常
- [ ] 大拇指弯曲映射正常
- [ ] 自动化测试通过
- [ ] 双手独立控制正常

---

## 📝 更新日志

### v2.0 (2025-11-03)
- ✅ 添加大拇指映射控制
- ✅ 实现C→D,E多项式映射
- ✅ 创建完整测试套件
- ✅ 编写详细文档

### v1.0 (2025-01)
- ✅ 实现四指Excel G→H映射
- ✅ PD速度控制器
- ✅ 双向角度转换
- ✅ 移除URDF mimic约束

---

**项目状态**: ✅ 完全可用  
**最后更新**: 2025年11月3日  
**维护者**: FTP双手灵巧手项目组
