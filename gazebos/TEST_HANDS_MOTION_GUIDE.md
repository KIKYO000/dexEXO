# 双手灵巧手运动测试文档

## 📋 测试脚本说明

**文件名**: `test_dual_hands_motion.py` / `test_hands.sh`

**功能**: 自动化测试双手所有手指的完整运动范围

**测试内容**:
1. **四指测试** (食指/中指/无名指/小指)
   - 3步弯曲: 180° → 150° → 120° → 87°
   - 3步伸直: 87° → 120° → 150° → 180°

2. **大拇指侧摆测试** (thumb_1)
   - 3步外展: 0 → 0.4 → 0.8 → 1.16 rad
   - 3步复原: 1.16 → 0.8 → 0.4 → 0 rad

3. **大拇指弯曲测试** (thumb_2)
   - 3步弯曲: 101° → 115° → 127° → 140°
   - 3步伸直: 140° → 127° → 115° → 101°

---

## 🚀 快速开始

### 方法1: 使用Shell脚本 (推荐)

```bash
# 测试双手所有手指 (默认)
cd /home/wxc/dexhandsim
./test_hands.sh
```

### 方法2: 直接运行Python脚本

```bash
source /opt/ros/humble/setup.bash
cd /home/wxc/dexhandsim
python3 test_dual_hands_motion.py
```

---

## 🎮 使用选项

### 选择测试的手

```bash
# 只测试右手
./test_hands.sh --hand right

# 只测试左手
./test_hands.sh --hand left

# 测试双手 (默认)
./test_hands.sh --hand both
```

### 选择测试的手指

```bash
# 只测试食指
./test_hands.sh --fingers index

# 测试食指和中指
./test_hands.sh --fingers index,middle

# 只测试大拇指
./test_hands.sh --fingers thumb

# 测试所有手指 (默认)
./test_hands.sh --fingers all
```

### 调整延迟时间

```bash
# 每步延迟1秒 (快速测试)
./test_hands.sh --delay 1.0

# 每步延迟3秒 (慢速观察)
./test_hands.sh --delay 3.0

# 默认2秒
./test_hands.sh --delay 2.0
```

### 组合使用

```bash
# 快速测试右手食指
./test_hands.sh --hand right --fingers index --delay 1.0

# 慢速测试双手大拇指
./test_hands.sh --fingers thumb --delay 3.0

# 测试左手食指和中指,每步1.5秒
./test_hands.sh --hand left --fingers index,middle --delay 1.5
```

---

## 📊 测试输出示例

### 启动输出
```
======================================================================
  双手灵巧手运动测试
======================================================================
测试手: RIGHT, LEFT
测试手指: index, middle, ring, little, thumb
延迟时间: 2.0 秒/步
======================================================================
```

### 运行过程输出
```
======================================================================
  RIGHT手 - 四指运动测试
======================================================================

🔽 right index - 开始弯曲 (3步)
  第0步: 初始位置 180.0°
  📤 right index: 180.0° (3.1416 rad)
  第1步: 弯曲至 150.0°
  📤 right index: 150.0° (2.6180 rad)
  第2步: 弯曲至 120.0°
  📤 right index: 120.0° (2.0944 rad)
  第3步: 弯曲至 87.0°
  📤 right index: 87.0° (1.5184 rad)
  ⏸️  保持弯曲状态...

🔼 right index - 开始伸直 (3步)
  第0步: 初始位置 87.0°
  📤 right index: 87.0° (1.5184 rad)
  第1步: 伸直至 120.0°
  📤 right index: 120.0° (2.0944 rad)
  第2步: 伸直至 150.0°
  📤 right index: 150.0° (2.6180 rad)
  第3步: 伸直至 180.0°
  📤 right index: 180.0° (3.1416 rad)
  ✅ right index 测试完成
```

### 完成输出
```
======================================================================
  ✅ 所有测试完成!
======================================================================

测试摘要:
  - 测试手数: 2
  - 测试手指: 5
  - 总步数: 60
  - 总耗时: 约 2.0 分钟

📊 查看详细日志:
    tail -f /tmp/joint12_controller.log
```

---

## ⏱️ 预计测试时间

### 默认配置 (delay=2.0秒)

| 测试项目 | 手数 | 手指数 | 步数 | 耗时 |
|---------|------|--------|------|------|
| 四指测试 | 2 | 4 | 48 | ~1.6分钟 |
| 大拇指侧摆 | 2 | 1 | 6 | ~0.2分钟 |
| 大拇指弯曲 | 2 | 1 | 6 | ~0.2分钟 |
| **总计** | **2** | **5** | **60** | **~2.0分钟** |

### 快速测试 (delay=1.0秒)
- **总耗时**: ~1.0 分钟

### 慢速测试 (delay=3.0秒)
- **总耗时**: ~3.0 分钟

### 单手测试
- **耗时**: 约为双手测试的一半

---

## 🔍 监控测试过程

### 实时查看控制器日志
```bash
# 新开一个终端
tail -f /tmp/joint12_controller.log

# 只看状态更新
tail -f /tmp/joint12_controller.log | grep "当前状态"

# 只看映射计算
tail -f /tmp/joint12_controller.log | grep "🎯"
```

### 在Gazebo中观察
1. 打开Gazebo窗口
2. 运行测试脚本
3. 观察手指实时运动

### 查看ROS话题
```bash
# 查看所有控制话题
ros2 topic list | grep cmd

# 监听某个手指的命令
ros2 topic echo /ftp/right_hand/index/joint1/cmd
```

---

## 📋 完整测试序列

### 右手测试顺序
1. 食指弯曲 (3步) + 伸直 (3步)
2. 中指弯曲 (3步) + 伸直 (3步)
3. 无名指弯曲 (3步) + 伸直 (3步)
4. 小指弯曲 (3步) + 伸直 (3步)
5. 大拇指外展 (3步) + 复原 (3步)
6. 大拇指弯曲 (3步) + 伸直 (3步)

### 左手测试顺序
与右手相同

---

## 🎯 测试验证标准

### 四指 (index/middle/ring/little)
- ✅ 能完成180°到87°的弯曲
- ✅ 能完成87°到180°的伸直
- ✅ joint2能自动跟随joint1映射
- ✅ 运动平滑无卡顿

### 大拇指侧摆 (thumb_1)
- ✅ 能完成0到1.16 rad的外展
- ✅ 能完成1.16到0 rad的复原
- ✅ 直接控制,无映射延迟

### 大拇指弯曲 (thumb_2)
- ✅ 能完成101°到140°的弯曲
- ✅ 能完成140°到101°的伸直
- ✅ thumb_3和thumb_4能自动跟随映射
- ✅ 映射精度高 (RMSE < 0.02°)

---

## 🐛 故障排查

### 问题1: 脚本无反应
```bash
# 检查系统是否运行
ps aux | grep -E "gz|bridge|joint12"

# 如果没有运行,启动系统
./restart_system.sh

# 等待5秒后再运行测试
sleep 5
./test_hands.sh
```

### 问题2: 话题连接失败
```bash
# 检查话题是否存在
ros2 topic list | grep cmd

# 检查订阅者
ros2 topic info /ftp/right_hand/index/joint1/cmd
```

### 问题3: 手指运动异常
```bash
# 查看控制器日志错误
grep -E "ERROR|WARN" /tmp/joint12_controller.log

# 检查URDF是否正确
grep "mimic" urdf/FTP_right_hand.urdf
# 应该没有mimic输出(已移除)
```

### 问题4: 测试中断
```bash
# 使用Ctrl+C可以随时中断测试
# 手指会保持在当前位置

# 重置所有手指到伸直状态
./reset_hands.sh  # (需要创建此脚本)
```

---

## 💡 使用技巧

### 1. 快速测试单个手指
```bash
# 只测试右手食指,1秒延迟
./test_hands.sh --hand right --fingers index --delay 1.0
```

### 2. 重点测试大拇指
```bash
# 大拇指有两个运动测试(侧摆+弯曲)
./test_hands.sh --fingers thumb --delay 2.5
```

### 3. 对比左右手
```bash
# 先测试右手
./test_hands.sh --hand right --delay 1.5

# 再测试左手
./test_hands.sh --hand left --delay 1.5
```

### 4. 并行监控
```bash
# 终端1: 运行测试
./test_hands.sh

# 终端2: 监控日志
tail -f /tmp/joint12_controller.log | grep thumb

# 终端3: 监控话题
watch -n 0.5 'ros2 topic list | wc -l'
```

---

## 🔄 测试后重置

### 手动重置到初始状态
```bash
# 所有手指伸直
source /opt/ros/humble/setup.bash

for hand in right left; do
  for finger in index middle ring little; do
    ros2 topic pub -1 /ftp/${hand}_hand/${finger}/joint1/cmd std_msgs/Float64 '{data: 3.14}'
  done
  
  # 大拇指复原
  ros2 topic pub -1 /ftp/${hand}_hand/thumb/joint1/cmd std_msgs/Float64 '{data: 0.0}'
  ros2 topic pub -1 /ftp/${hand}_hand/thumb/joint2/cmd std_msgs/Float64 '{data: 1.76}'
done
```

### 创建重置脚本 (可选)
将上述命令保存为 `reset_hands.sh`,方便快速重置。

---

## 📝 测试记录模板

### 测试日期: ________

| 项目 | 右手 | 左手 | 备注 |
|------|------|------|------|
| 食指弯曲 | ☐ | ☐ | |
| 食指伸直 | ☐ | ☐ | |
| 中指弯曲 | ☐ | ☐ | |
| 中指伸直 | ☐ | ☐ | |
| 无名指弯曲 | ☐ | ☐ | |
| 无名指伸直 | ☐ | ☐ | |
| 小指弯曲 | ☐ | ☐ | |
| 小指伸直 | ☐ | ☐ | |
| 大拇指外展 | ☐ | ☐ | |
| 大拇指复原 | ☐ | ☐ | |
| 大拇指弯曲 | ☐ | ☐ | |
| 大拇指伸直 | ☐ | ☐ | |

**测试结果**: ☐ 全部通过  ☐ 部分通过  ☐ 失败

**问题描述**: _________________________

---

## 📚 相关文件

- **测试脚本**: `test_dual_hands_motion.py`
- **包装脚本**: `test_hands.sh`
- **控制器**: `scripts/joint12_mapping_controller.py`
- **启动脚本**: `restart_system.sh`
- **日志文件**: `/tmp/joint12_controller.log`
- **使用文档**: `THUMB_MAPPING_CONTROL.md`

---

## ✅ 验收标准

测试通过需要满足:
1. ✅ 所有手指能完成3步弯曲
2. ✅ 所有手指能完成3步伸直
3. ✅ 大拇指能完成3步外展+复原
4. ✅ 大拇指能完成3步弯曲+伸直
5. ✅ 运动平滑,无异常卡顿
6. ✅ 映射计算正确(查看日志)
7. ✅ 双手独立运动,无干扰
8. ✅ 无错误或警告日志

**总测试步数**: 60步 (5手指 × 2手 × 6步)
**预计总耗时**: 2分钟 (delay=2.0秒)
