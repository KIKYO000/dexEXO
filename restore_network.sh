#!/bin/bash
# 树莓派网络恢复脚本 - 恢复原始网络配置

echo "=========================================="
echo "树莓派网络恢复脚本"
echo "=========================================="

# 1. 恢复 rc.local
echo "[1] 恢复原始 rc.local..."
if [ -f /etc/rc.local.bak ]; then
    sudo cp /etc/rc.local.bak /etc/rc.local
    echo "✓ 已从备份恢复"
else
    echo "! 未找到备份文件，创建默认 rc.local..."
    sudo bash -c 'cat > /etc/rc.local << '\''EOF'\''
#!/bin/sh -e
# This script is executed at the end of each multiuser runlevel.
exit 0
EOF'
fi

sudo chmod +x /etc/rc.local

# 2. 重启网络
echo "[2] 重启网络接口..."
sudo ip addr flush dev eth0 2>/dev/null || true
sleep 1

# 3. 使用 DHCP 获取 IP
echo "[3] 重新启用 DHCP..."
sudo systemctl restart networking 2>/dev/null || true
sleep 3

# 4. 显示最终状态
echo ""
echo "=========================================="
echo "恢复完成！当前状态："
echo "=========================================="
ip addr show eth0
echo ""
echo "✓ 网络应已恢复到原始状态"
echo "=========================================="
