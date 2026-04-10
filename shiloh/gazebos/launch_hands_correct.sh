#!/bin/bash
# FTP 双手灵巧手正确版启动脚本 - 使用完整URDF包含

echo "==============================================="
echo "🤲 FTP 双手灵巧手正确版启动"
echo "==============================================="

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 设置环境变量
export IGN_GAZEBO_RESOURCE_PATH="$SCRIPT_DIR:$SCRIPT_DIR/meshes:$SCRIPT_DIR/urdf"
export GZ_SIM_RESOURCE_PATH="$SCRIPT_DIR:$SCRIPT_DIR/meshes:$SCRIPT_DIR/urdf"

# 检查文件是否存在
if [ ! -f "$SCRIPT_DIR/worlds/ftp_hands_correct.sdf" ]; then
    echo "❌ 错误: 正确版SDF文件不存在"
    exit 1
fi

if [ ! -d "$SCRIPT_DIR/meshes" ]; then
    echo "❌ 错误: meshes文件夹不存在"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/urdf/FTP_left_hand.urdf" ]; then
    echo "❌ 错误: 左手URDF文件不存在"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/urdf/FTP_right_hand.urdf" ]; then
    echo "❌ 错误: 右手URDF文件不存在"
    exit 1
fi

echo "📁 工作目录: $SCRIPT_DIR"
echo "🗂️  资源路径: $IGN_GAZEBO_RESOURCE_PATH"
echo "🎯 使用完整URDF包含方式"
echo ""

# 清理现有进程
echo "🧹 清理现有的Gazebo进程..."
pkill -f "ign.*gazebo" 2>/dev/null || true
pkill -f "gz.*sim" 2>/dev/null || true
pkill -f "gazebo" 2>/dev/null || true
sleep 3

# 检查并启动Gazebo
echo "🚀 启动正确版Gazebo..."
echo "修复内容:"
echo "  ✓ 完整的URDF关节结构"
echo "  ✓ 正确的父子关系"
echo "  ✓ 完整的手指关节链"
echo "  ✓ 正确的mesh路径引用"
echo "  ✓ 保持手掌朝前、手指朝上"
echo ""

cd "$SCRIPT_DIR"

if command -v ign >/dev/null 2>&1; then
    echo "使用Ignition Gazebo..."
    ign gazebo worlds/ftp_hands_correct.sdf -v 3
elif command -v gz >/dev/null 2>&1; then
    echo "使用Gazebo..."
    gz sim worlds/ftp_hands_correct.sdf -v 3
else
    echo "❌ 错误: 未找到Gazebo或Ignition Gazebo"
    echo "请安装:"
    echo "  - Ubuntu 20.04: sudo apt install ignition-gazebo"
    echo "  - Ubuntu 22.04: sudo apt install gz-garden"
    exit 1
fi

echo ""
echo "✅ 正确版Gazebo已退出"