#!/usr/bin/env bash
###############################################################################
# FTP 灵巧手关节1-2映射控制器启动脚本
###############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "==============================================="
echo "🤖 FTP 关节1-2映射控制器启动"
echo "==============================================="

# 检查依赖 (使用系统 Python,避免 conda 干扰)
echo "📦 检查 Python 依赖..."
/usr/bin/python3 -c "import pandas, scipy, numpy" 2>/dev/null || {
    echo "❌ 缺少 Python 依赖包"
    echo "   请使用系统 Python 安装: /usr/bin/python3 -m pip install pandas scipy numpy openpyxl --user"
    exit 1
}

echo "✅ 依赖检查通过"
echo ""

# 停止现有控制器
pkill -f joint12_mapping_controller 2>/dev/null || true
sleep 1

echo "🚀 启动映射控制器..."
echo "   ⚠️  使用系统 Python (非 conda),避免版本冲突"
echo ""

# 启动控制器 (关键: 使用 env -i 清除 conda 环境变量)
env -i HOME="$HOME" USER="$USER" PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
    bash -c "source /opt/ros/humble/setup.bash && \
    cd ${SCRIPT_DIR} && \
    /usr/bin/python3 scripts/joint12_mapping_controller.py" 2>&1 | tee /tmp/joint12_controller.log &

CONTROLLER_PID=$!
sleep 2

# 检查是否成功启动
if ps -p ${CONTROLLER_PID} > /dev/null 2>&1; then
    echo "✅ 控制器已启动 (PID: ${CONTROLLER_PID})"
    echo "   日志: /tmp/joint12_controller.log"
else
    echo "❌ 控制器启动失败,查看日志:"
    cat /tmp/joint12_controller.log
    exit 1
fi

echo ""
echo "==============================================="
echo "✅ 系统启动完成!"
echo "==============================================="
echo ""
echo "📝 使用方法 (输入Excel G列角度值):"
echo ""
echo "1️⃣  伸直手指 (G≈180°=3.14弧度):"
echo "   bash --login -c \"source /opt/ros/humble/setup.bash && \\"
echo "   ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd \\"
echo "   std_msgs/Float64 '{data: 3.14}'\""
echo ""
echo "2️⃣  轻微弯曲 (G≈150°=2.62弧度):"
echo "   bash --login -c \"source /opt/ros/humble/setup.bash && \\"
echo "   ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd \\"
echo "   std_msgs/Float64 '{data: 2.62}'\""
echo ""
echo "3️⃣  完全弯曲 (G≈87°=1.52弧度):"
echo "   bash --login -c \"source /opt/ros/humble/setup.bash && \\"
echo "   ros2 topic pub -1 /ftp/right_hand/index/joint1/cmd \\"
echo "   std_msgs/Float64 '{data: 1.52}'\""
echo ""
echo "📋 可用手指: index, middle, ring, little"
echo "   可用手: right_hand, left_hand"
echo ""
echo "📐 关节1角度范围: 1.52 ~ 3.14 弧度 (87° ~ 180°, Excel G列)"
echo "   ⚠️  3.14rad(180°)=伸直, 1.52rad(87°)=弯曲"
echo ""
echo "🛑 停止控制器:"
echo "   pkill -f joint12_mapping_controller"
echo ""
echo "💡 提示: 关节2角度通过3次多项式自动计算"
echo ""
echo "==============================================="
