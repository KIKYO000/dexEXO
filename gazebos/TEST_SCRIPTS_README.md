# 双手灵巧手测试脚本 - 快速参考

## 📦 可用脚本

| 脚本名称 | 功能 | 用法 |
|---------|------|------|
| `test_hands.sh` | 完整运动测试 | `./test_hands.sh [选项]` |
| `reset_hands.sh` | 重置到初始状态 | `./reset_hands.sh` |
| `restart_system.sh` | 重启整个系统 | `./restart_system.sh` |
| `test_thumb_mapping.py` | 大拇指映射测试 | `python3 test_thumb_mapping.py` |

---

## 🚀 快速测试

### 1. 测试双手所有手指 (完整测试)
```bash
./test_hands.sh
# 耗时: ~2分钟 (60步)
```

### 2. 快速测试单手
```bash
# 右手快速测试 (1秒/步)
./test_hands.sh --hand right --delay 1.0

# 左手快速测试
./test_hands.sh --hand left --delay 1.0
```

### 3. 测试特定手指
```bash
# 只测试食指
./test_hands.sh --fingers index

# 只测试大拇指
./test_hands.sh --fingers thumb

# 测试食指和中指
./test_hands.sh --fingers index,middle
```

### 4. 重置手指
```bash
./reset_hands.sh
```

---

## 📋 测试内容

### 四指 (index, middle, ring, little)
✅ **3步弯曲**: 180° → 150° → 120° → 87°
✅ **3步伸直**: 87° → 120° → 150° → 180°

### 大拇指侧摆 (thumb_1)
✅ **3步外展**: 0 → 0.4 → 0.8 → 1.16 rad
✅ **3步复原**: 1.16 → 0.8 → 0.4 → 0 rad

### 大拇指弯曲 (thumb_2)
✅ **3步弯曲**: 101° → 115° → 127° → 140°
✅ **3步伸直**: 140° → 127° → 115° → 101°

---

## 🎮 命令行选项

```bash
./test_hands.sh [选项]

选项:
  --hand <right|left|both>    选择测试的手 (默认: both)
  --fingers <list>            选择测试的手指 (默认: all)
                              可选: index, middle, ring, little, thumb
  --delay <seconds>           每步延迟时间 (默认: 2.0)

示例:
  ./test_hands.sh --hand right --fingers index --delay 1.0
  ./test_hands.sh --fingers thumb --delay 3.0
  ./test_hands.sh --hand left --delay 1.5
```

---

## 📊 测试时间估算

| 配置 | 延迟 | 耗时 |
|------|------|------|
| 双手全部手指 | 2.0秒 | ~2.0分钟 |
| 单手全部手指 | 2.0秒 | ~1.0分钟 |
| 双手快速测试 | 1.0秒 | ~1.0分钟 |
| 只测试大拇指 | 2.0秒 | ~0.4分钟 |
| 只测试单个手指 | 2.0秒 | ~0.2分钟 |

---

## 🔍 监控测试

### 实时查看日志
```bash
tail -f /tmp/joint12_controller.log
```

### 只看映射计算
```bash
tail -f /tmp/joint12_controller.log | grep "🎯"
```

### 只看当前状态
```bash
tail -f /tmp/joint12_controller.log | grep "当前状态" -A 10
```

---

## ✅ 测试验收

测试通过标准:
- [x] 所有手指完成3步弯曲
- [x] 所有手指完成3步伸直
- [x] 大拇指完成3步外展+复原
- [x] 大拇指完成3步弯曲+伸直
- [x] 运动平滑无卡顿
- [x] 无错误或警告日志
- [x] 双手独立运动

---

## 🐛 故障排查

### 系统未运行
```bash
# 检查进程
ps aux | grep -E "gz|bridge|joint12"

# 启动系统
./restart_system.sh
sleep 5

# 再次测试
./test_hands.sh
```

### 重置失败
```bash
# 手动重置
./reset_hands.sh

# 或重启系统
./restart_system.sh
```

### 测试中断
```bash
# 使用 Ctrl+C 中断测试
# 然后运行重置
./reset_hands.sh
```

---

## 📚 详细文档

- **完整使用指南**: `TEST_HANDS_MOTION_GUIDE.md`
- **大拇指控制**: `THUMB_MAPPING_CONTROL.md`
- **实现总结**: `THUMB_IMPLEMENTATION_SUMMARY.md`
- **大拇指分析**: `THUMB_JOINTS_ANALYSIS.md`

---

## 🎯 常用测试场景

### 场景1: 每日快速检查
```bash
./test_hands.sh --delay 1.0
# 1分钟快速验证所有功能
```

### 场景2: 详细验证测试
```bash
./test_hands.sh --delay 3.0
# 3分钟详细观察每个动作
```

### 场景3: 单手调试
```bash
./test_hands.sh --hand right
./test_hands.sh --hand left
# 分别测试左右手
```

### 场景4: 重点测试大拇指
```bash
./test_hands.sh --fingers thumb --delay 2.5
# 重点验证大拇指映射功能
```

### 场景5: 对比测试
```bash
# 测试右手
./test_hands.sh --hand right --fingers index --delay 2.0

# 重置
./reset_hands.sh

# 测试左手
./test_hands.sh --hand left --fingers index --delay 2.0

# 对比运动是否一致
```

---

## 💡 提示

1. **测试前**: 确保Gazebo窗口可见,方便观察运动
2. **测试中**: 可随时按Ctrl+C中断
3. **测试后**: 使用`reset_hands.sh`恢复初始状态
4. **并行监控**: 开两个终端,一个运行测试,一个查看日志

---

## 📞 技术支持

- 控制器日志: `/tmp/joint12_controller.log`
- 系统检查: `ps aux | grep -E "gz|bridge|joint12"`
- 话题列表: `ros2 topic list | grep cmd`
- 重启系统: `./restart_system.sh`

---

**创建日期**: 2025年11月3日  
**版本**: v1.0  
**状态**: ✅ 完全可用
