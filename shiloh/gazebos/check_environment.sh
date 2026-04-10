#!/bin/bash
# 环境检查脚本

echo "=========================================="
echo "  环境检查"
echo "=========================================="
echo ""

# 检查ROS 2
if command -v ros2 &> /dev/null; then
    echo "✅ ROS 2 已安装"
    ros2 --version
else
    echo "❌ ROS 2 未安装"
    exit 1
fi

# 检查Gazebo
if command -v gz &> /dev/null; then
    echo "✅ Gazebo 已安装"
    gz sim --version
else
    echo "❌ Gazebo 未安装"
    exit 1
fi

# 检查Python依赖
echo ""
echo "检查Python依赖..."
/usr/bin/python3 -c "import pandas, numpy, scipy" 2>/dev/null && echo "✅ Python依赖完整" || {
    echo "❌ Python依赖缺失"
    echo "请运行: /usr/bin/python3 -m pip install pandas numpy scipy openpyxl --user"
    exit 1
}

# 检查Excel文件
if [ -f "驱动器行程与角度关系表.xls" ]; then
    echo "✅ Excel映射文件存在"
else
    echo "❌ Excel映射文件缺失"
    exit 1
fi

# 检查关键目录
DIRS=("urdf" "models" "worlds" "meshes" "scripts")
for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo "✅ 目录存在: $dir"
    else
        echo "❌ 目录缺失: $dir"
    fi
done

echo ""
echo "=========================================="
echo "✅ 环境检查完成"
echo "=========================================="
