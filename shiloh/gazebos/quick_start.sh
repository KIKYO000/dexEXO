#!/bin/bash
# FTP双手灵巧手快速启动脚本

cd "$(dirname "$0")"

echo "=========================================="
echo "  FTP双手灵巧手快速启动"
echo "=========================================="
echo ""
echo "请选择操作:"
echo "  1) 启动完整系统 (Gazebo + Bridge + Controller)"
echo "  2) 运行测试 (test_hands.sh)"
echo "  3) 重置手指 (reset_hands.sh)"
echo "  4) 查看日志"
echo "  5) 停止所有进程"
echo ""
read -p "请输入选项 [1-5]: " choice

case $choice in
    1)
        echo "正在启动系统..."
        ./restart_system.sh
        ;;
    2)
        echo "正在运行测试..."
        ./test_hands.sh --delay 1.5
        ;;
    3)
        echo "正在重置手指..."
        ./reset_hands.sh
        ;;
    4)
        echo "查看控制器日志 (Ctrl+C 退出)..."
        tail -f /tmp/joint12_controller.log
        ;;
    5)
        echo "停止所有进程..."
        pkill -9 -f "ign gazebo" 2>/dev/null || true
        pkill -9 -f "ros_gz_bridge" 2>/dev/null || true
        pkill -9 -f "joint12_mapping_controller" 2>/dev/null || true
        echo "✅ 已停止所有进程"
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac
