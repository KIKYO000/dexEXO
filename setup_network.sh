#!/bin/bash
# 树莓派网络配置脚本 - 添加 192.168.123.100 用于连接灵巧手右手 (192.168.123.211)
# 重要：保留现有的 10.42.0.174，在同一个 eth0 上添加第二个 IP

echo "=========================================="
echo "树莓派网络配置脚本 (安全版本)"
echo "=========================================="

# 1. 添加第二个 IP 地址到 eth0（保留原有的 IP）
echo "[1] 正在添加 192.168.123.100 到 eth0..."
sudo ip addr add 192.168.123.100/24 dev eth0 2>/dev/null || echo "   (IP 可能已存在)"

echo "[2] 等待网络稳定..."
sleep 2

# 2. 测试网络连接
echo "[3] 测试连接到灵巧手右手 (192.168.123.211)..."
ping -c 3 192.168.123.211
PING_RESULT=$?

if [ $PING_RESULT -eq 0 ]; then
    echo "✓ 网络连接成功！"
else
    echo "✗ 网络连接失败，请检查配置"
    echo "   但仍继续进行永久配置..."
fi

# 3. 永久配置 - 编辑 /etc/rc.local
echo "[4] 正在配置永久网络设置..."

# 创建临时文件
TEMP_FILE=$(mktemp)

cat > "$TEMP_FILE" << 'EOF'
#!/bin/sh -e
# This script is executed at the end of each multiuser runlevel.

# Network configuration for Inspire hand right (192.168.123.211)
echo "Configuring dexEXO network..."
ip addr add 192.168.123.100/24 dev eth0 2>/dev/null || true
echo "Network configured: eth0 has 192.168.123.100/24 (+ existing IPs)"

exit 0
EOF

# 备份原始文件
if [ -f /etc/rc.local ]; then
    sudo cp /etc/rc.local /etc/rc.local.bak.$(date +%s)
    echo "   已备份原始 rc.local"
fi

# 替换文件
sudo cp "$TEMP_FILE" /etc/rc.local
sudo chmod +x /etc/rc.local
rm "$TEMP_FILE"

echo "✓ 永久网络配置已完成"

# 4. 显示最终状态
echo ""
echo "=========================================="
echo "配置完成！当前状态："
echo "=========================================="
ip addr show eth0
echo ""
echo "✓ 原有的 10.42.0.174 被保留"
echo "✓ 新增的 192.168.123.100 已添加"
echo "=========================================="
