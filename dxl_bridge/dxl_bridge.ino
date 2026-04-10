#include <Arduino.h>
#include <Dynamixel2Arduino.h>

// ====== 根据你的硬件修改这些常量 ======
#define DXL_ID        1        // 舵机ID（默认 1）
#define DXL_BAUD      57600    // XL330 默认 57600
#define DXL_PROTOCOL  2.0      // X系列使用协议 2.0
#define DXL_DIR_PIN   -1       // ★ 自动方向的TTL转接板，用 -1
// Mega2560 使用 Serial1（18/19）
Dynamixel2Arduino dxl(Serial1, DXL_DIR_PIN);

// 简单的打印工具
void print_state(const char* tag) {
  int pos = dxl.getPresentPosition(DXL_ID); // 0~4095 ≈ 0~360°
  int cur = dxl.getPresentCurrent(DXL_ID);  // mA
  Serial.print(tag);
  Serial.print(" | POS=");
  Serial.print(pos);
  Serial.print(" | CUR(mA)=");
  Serial.println(cur);
}

void move_to(int goal, uint16_t wait_ms_each = 20) {
  dxl.setGoalPosition(DXL_ID, goal);
  // 简单等待：边等边读状态（约 1 秒）
  for (int i = 0; i < 50; ++i) {
    print_state("POS_MODE");
    delay(wait_ms_each);
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) {}
  delay(200);

  Serial.println("== DXL simple test (auto-direction) ==");

  // 初始化串口到 DXL
  dxl.begin(DXL_BAUD);
  dxl.setPortProtocolVersion(DXL_PROTOCOL);

  // 试 ping
  bool ok = dxl.ping(DXL_ID);
  Serial.print("PING ID ");
  Serial.print(DXL_ID);
  Serial.println(ok ? " : OK" : " : FAIL");
  if (!ok) {
    Serial.println("!!! 没 ping 通：检查供电/共地/接线/ID/波特率/转接板类型。");
  }

  // 位置模式：来回两次
  dxl.torqueOff(DXL_ID);
  dxl.setOperatingMode(DXL_ID, OP_POSITION);
  dxl.torqueOn(DXL_ID);

  Serial.println("== Position mode: sweep ==");
  move_to(1024);
  move_to(3072);
  move_to(1024);
  move_to(2048); // 回到中间

  // 电流模式：给一点小电流让你感受阻力（先从小值开始）
  dxl.torqueOff(DXL_ID);
  dxl.setOperatingMode(DXL_ID, OP_CURRENT);
  dxl.torqueOn(DXL_ID);

  Serial.println("== Current mode: hold 200 mA for ~1s ==");
  dxl.setGoalCurrent(DXL_ID, 200);  // mA，必要时调小/调大
  for (int i = 0; i < 50; ++i) {
    print_state("CUR_MODE");
    delay(20);
  }
  dxl.setGoalCurrent(DXL_ID, 0);
  Serial.println("== Test done ==");
}

void loop() {
  // 保持空闲；你也可以在这里继续加自己的测试逻辑
  delay(1000);
}
