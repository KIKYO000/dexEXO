# 1 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
# 2 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 2
using namespace ControlTableItem; // 直接使用控制表项符号名（如 PRESENT_CURRENT 等）

// ===== 硬件串口 & 舵机参数 =====


const int DXL_DIR_PIN = -1; // 自动方向板不接此脚也可；库仍会切换该引脚，不影响
const uint8_t DXL_ID = 1;
const float DXL_PROTOCOL = 2.0;

// ===== 目标 & 控制参数（可串口指令修改）=====
float targetForceN = 0.0f; // 目标力(N)，由 "N:10" 指令设置
float kN_per_mA = 0.25f; // 力换算系数：N = |mA| * kN_per_mA ——建议用CAL命令标定！
float hysteresisN = 0.15f; // 力迟滞带，避免抖动（默认 0.15N）
int stepPulse = 2; // 每次调整的脉冲步进（默认 2）
uint16_t currentLimit_mA = 150; // 电流（力矩）上限（默认 150mA）

// ===== 触摸(touch)模式相关 =====
bool touchMode = false; // 是否处于触摸模式（接触物体）
float touchGain_N_per_tick = 0.05f;// N 增益 = 位移tick * 此系数（默认 0.05N/脉冲，建议按需调整）
float touchMaxN = 5.0f; // 触摸模式下 N 的上限，默认 10N（可通过 TMAX 调整）
int32_t touchStartPos = 0; // 触摸开始时的位置（tick）
float touchBaseN = 0.0f; // 触摸开始时的基准 N（通常为 0）
int touchDirSign = 0; // 负载方向（+1/-1），触摸时确定
int lastNonZeroSign = 0; // 最近一次非零电流方向，用于方向丢失时回退
uint32_t touchStartMs = 0; // 触摸开始时间戳
bool touchRampMode = true; // 触摸模式：true=时间线性增力(RAMP)，false=位移增力(DISP)
float touchRampRateNPerSec = 0.5f;// RAMP：线性增力速率 N/s（默认 0.5），直到触摸上限

// ===== 运行配置 =====
int8_t g_opMode = OP_CURRENT_BASED_POSITION; // 缓存当前工作模式
int calMin_mA = 2; // CAL 标定所需的最小电流阈值（绝对值），默认 2mA
bool freeModeActive = false; // N=0 自由模式（扭矩关闭）
float noLoadThreshN = 0.08f; // 无载阈值 N，可配置
bool seekMode = false; // 当无载时，是否主动寻觸以达到目标力
int seekMaxSteps = 30; // 主动寻触的最大步数（默认 30，用于安全防护，防止无限移动）
int seekStepCounter = 0;
bool autoFree = true; // 自动自由模式：N=0 且非触摸时自动 torque-off
bool holdMode = false; // 标定/测试固定模式：固定当前位置，关闭自动自由/跟随/寻触
int controlDir = +1; // 控制方向：+1=默认映射，-1=反向映射（用于机械装配方向不一致时）

int32_t home_pos = 0; // 零位（上电后记录当前为Home，或通过 HOME 指令重置）
int32_t goal_pos = 0;

Dynamixel2Arduino dxl(Serial1 /* Mega2560 Pro: TX1=18, RX1=19*/, DXL_DIR_PIN);

static inline int32_t stepToward(int32_t from, int32_t to, int32_t step){
  if(from < to) return (from + step > to) ? to : from + step;
  if(from > to) return (from - step < to) ? to : from - step;
  return from;
}

void setup(){
  Serial.begin(115200);
  while(!Serial){;}

  dxl.begin(57600); // XL330 缺省 57600 - 必须先 begin()
  dxl.setPortProtocolVersion(DXL_PROTOCOL);
  delay(50);

  // 测试连接
  bool pingOk = dxl.ping(DXL_ID);
  Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 63 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 63 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    "PING ID "
# 63 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    ); &__c[0];}))
# 63 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    )));
  Serial.print(DXL_ID);
  Serial.println(pingOk ? (reinterpret_cast<const __FlashStringHelper *>(
# 65 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                               (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 65 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                               " : OK"
# 65 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                               ); &__c[0];}))
# 65 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                               )) : (reinterpret_cast<const __FlashStringHelper *>(
# 65 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 65 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                            " : FAIL - 检查接线/ID/波特率"
# 65 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                            ); &__c[0];}))
# 65 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                            )));

  // 安全初始化
  dxl.torqueOff(DXL_ID);
  dxl.setOperatingMode(DXL_ID, OP_CURRENT_BASED_POSITION); // 电流基位置模式
  dxl.writeControlTableItem(CURRENT_LIMIT, DXL_ID, currentLimit_mA);
  dxl.writeControlTableItem(PROFILE_VELOCITY, DXL_ID, 200); // 增大速度 (0=无限制)
  dxl.writeControlTableItem(PROFILE_ACCELERATION, DXL_ID, 100); // 增大加速度
  dxl.torqueOn(DXL_ID);
  delay(100);
  freeModeActive = false;

  Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 77 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 77 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    "Operating Mode: "
# 77 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    ); &__c[0];}))
# 77 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    )));
  Serial.println(dxl.readControlTableItem(OPERATING_MODE, DXL_ID));
  Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 79 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 79 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    "Torque Enable: "
# 79 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    ); &__c[0];}))
# 79 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    )));
  Serial.println(dxl.readControlTableItem(TORQUE_ENABLE, DXL_ID));

  home_pos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
  goal_pos = home_pos;
  dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);

  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 86 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 86 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "DexEXO XL330 single-servo demo ready."
# 86 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 86 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 87 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 87 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ""
# 87 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 87 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 88 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 88 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "=== 快速开始 ==="
# 88 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 88 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 89 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 89 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "1. 发送: STATUS (查看当前电流)"
# 89 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 89 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 90 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 90 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "2. 用手推舵机，再发送 STATUS"
# 90 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 90 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 91 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 91 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "3. 发送: CAL:1 (假设刚才用了1N力)"
# 91 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 91 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 92 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 92 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "4. 发送: N:0 (自由跟随)"
# 92 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 92 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 93 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 93 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "5. 发送: TOUCH 或 TOUCH:ON 开启触摸模式"
# 93 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 93 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 94 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 94 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "6. 触摸期间: N 会随位移增加，新N = 基准N + 位移tick * TGAIN"
# 94 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 94 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 95 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 95 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "7. 可用 TGAIN:<k> 和 TMAX:<N> 调整增益和上限"
# 95 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 95 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 96 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 96 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ""
# 96 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 96 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 97 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 97 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "=== 力追随模式说明 ==="
# 97 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 97 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 98 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 98 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "力带有方向(正/负):"
# 98 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 98 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 99 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 99 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "  正力(+): 舵机被推的力"
# 99 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 99 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 100 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 100 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "  负力(-): 舵机被拉的力"
# 100 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 100 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 101 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 101 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ""
# 101 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 101 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 102 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 102 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "控制规则（设置N:1为例）:"
# 102 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 102 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 103 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 103 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "  检测力 < 1N  → 舵机正转(position+)"
# 103 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 103 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 104 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 104 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "  检测力 > 1N  → 舵机反转(position-)"
# 104 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 104 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 105 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 105 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "  检测力 = 1N  → 舵机不动"
# 105 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 105 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 106 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 106 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ""
# 106 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 106 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 107 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 107 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "实际效果:"
# 107 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 107 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 108 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 108 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "  - 用手推舵机: 力变大→舵机反转减小阻力→维持1N"
# 108 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 108 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 109 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 109 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "  - 松手不推: 力变0→舵机不会自己动！"
# 109 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 109 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 110 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 110 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "  - 用手拉舵机: 力变负→舵机正转抵抗→维持1N"
# 110 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 110 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 111 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 111 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ""
# 111 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 111 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 112 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 112 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "=== 所有命令 ==="
# 112 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 112 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 113 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 113 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "STATUS     - 查看实时电流(标定前先用这个!)"
# 113 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 113 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 114 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 114 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "N:<val>    - 设置目标力(N)"
# 114 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 114 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 115 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 115 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "TOUCH[:ON|:OFF] - 进入/退出触摸模式，ON时N随位移增加"
# 115 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 115 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 116 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 116 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "TGAIN:<k>  - 位移-力增益(N/脉冲)，默认0.05"
# 116 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 116 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 117 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 117 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "TMAX:<N>   - 触摸模式下N的上限，默认10N"
# 117 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 117 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 118 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 118 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "TMODE:<RAMP|DISP> - 触摸增力模式：RAMP=按时间线性递增，DISP=按位移递增(默认RAMP)"
# 118 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 118 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 119 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 119 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "TRATE:<n>  - RAMP模式下线性增力速率(N/s)，默认0.5"
# 119 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 119 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 120 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 120 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "SEEK[:ON|:OFF] - 在无载时主动移动以寻找目标力(危险：注意限位)"
# 120 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 120 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 121 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 121 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "SEEKMAX:<n> - 设置主动寻触最多步数，默认30"
# 121 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 121 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 122 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 122 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "FREE[:ON|:OFF] - 手动进入/退出自由模式(扭矩关闭)"
# 122 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 122 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 123 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 123 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "AUTOFREE[:ON|:OFF] - 自动自由模式：N=0 且未触摸时自动扭矩关闭(默认ON)"
# 123 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 123 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 124 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 124 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "HOLD[:ON|:OFF] - 标定/用力测试固定当前位置，关闭自动自由/跟随/寻触"
# 124 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 124 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 125 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 125 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "CALMIN:<mA> - 设置CAL最小电流阈值, 默认2mA (噪声大可调大)"
# 125 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 125 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 126 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 126 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "HOME       - 重置零位"
# 126 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 126 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 127 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 127 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "CAL:<N>    - 标定: 当前受力为<N>牛"
# 127 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 127 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 128 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 128 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "KN:<coef>  - 直接设置换算系数"
# 128 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 128 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 129 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 129 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "HYS:<h>    - 设置迟滞带(N)"
# 129 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 129 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 130 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 130 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "STEP:<p>   - 设置步进量"
# 130 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 130 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 131 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 131 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "ILIM:<mA>  - 设置电流限制"
# 131 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 131 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 132 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 132 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "NLT:<N>    - 设置无载阈值(避免噪声动作)，默认0.08N"
# 132 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 132 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 133 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 133 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "DIRREV[:ON|:OFF] - 控制方向反转开关(机械装配相反时使用)"
# 133 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 133 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 134 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 134 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "DIR:<+1|-1> - 直接设置控制方向(+1=默认,-1=反向)"
# 134 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 134 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 135 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 135 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "INFO       - 显示所有参数"
# 135 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 135 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 136 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 136 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "TEST       - 测试移动"
# 136 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 136 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 137 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 137 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "POS:<p>    - 移动到位置"
# 137 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 137 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 138 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 138 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ""
# 138 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 138 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
  Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 139 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 139 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    "初始 Home="
# 139 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    ); &__c[0];}))
# 139 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    ))); Serial.print(home_pos);
  Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 140 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 140 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    ", kN_per_mA="
# 140 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    ); &__c[0];}))
# 140 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    ))); Serial.print(kN_per_mA, 6);
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 141 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 141 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      " (未标定!)"
# 141 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 141 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
}

// 自由模式切换
static inline void enterFreeMode(){
  dxl.torqueOff(DXL_ID);
  freeModeActive = true;
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 148 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 148 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "[FREE] 扭矩关闭，自由跟随(完全无电)"
# 148 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 148 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
}

static inline void exitFreeMode(){
  int32_t ppos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
  dxl.torqueOn(DXL_ID);
  // 为避免跳变，先把目标对齐到当前位置
  goal_pos = ppos;
  dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);
  freeModeActive = false;
  Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 158 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 158 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "[FREE] 扭矩开启，恢复控制"
# 158 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 158 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
}

void handleSerial(){
  static String buf;
  while(Serial.available()){
    char c = Serial.read();
    if(c=='\n' || c=='\r'){
      buf.trim();

      // 调试：显示接收到的命令
      if(buf.length() > 0){
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 170 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 170 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[RCV] '"
# 170 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 170 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          )));
        Serial.print(buf);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 172 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 172 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "' (len="
# 172 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 172 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          )));
        Serial.print(buf.length());
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 174 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 174 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            ")"
# 174 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 174 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }

      // 支持中英文冒号
      buf.replace("：", ":");

      if(buf.startsWith("N:")){
        targetForceN = buf.substring(2).toFloat();
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 182 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 182 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] targetForceN="
# 182 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 182 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(targetForceN,3);
        if(targetForceN == 0){
          // N=0 表示自由跟随模式
          touchMode = false; // 退出触摸模式
          // 不自动关闭扭矩，若需要完全自由由 FREE:ON 决定
        }else{
          // 非零目标力，确保扭矩开启
          if(freeModeActive) exitFreeMode();
          if(holdMode){ holdMode = false; Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 190 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                              (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 190 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                              "[HOLD] 自动退出(检测到N!=0)"
# 190 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                              ); &__c[0];}))
# 190 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                              ))); }
        }
      }else if(buf=="TOUCH" || buf=="TOUCH:ON"){
        // 进入触摸模式：记录基准
        touchMode = true;
        if(freeModeActive) exitFreeMode(); // 触摸模式需要扭矩
        int32_t ppos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        int16_t pcur = (int16_t)dxl.readControlTableItem(PRESENT_CURRENT, DXL_ID);
        touchStartPos = ppos;
        touchBaseN = targetForceN; // 当前N作为基准
        // 负载方向：优先现有电流方向，否则用最近一次非零方向
        int s = (pcur > 0) ? +1 : (pcur < 0 ? -1 : (lastNonZeroSign==0? +1 : lastNonZeroSign));
        touchDirSign = s;
        touchStartMs = millis();
        // 进入触摸时自动开启寻触（更快建立接触力）
        seekMode = true;
        seekStepCounter = 0;
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 207 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 207 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] TOUCH ON. baseN="
# 207 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 207 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.print(touchBaseN,2);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 208 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 208 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          " startPos="
# 208 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 208 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.print(touchStartPos);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 209 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 209 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          " dir="
# 209 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 209 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(touchDirSign);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 210 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 210 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[INFO] SEEK 自动开启, seekMaxSteps="
# 210 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 210 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(seekMaxSteps);
        if(holdMode){ holdMode = false; Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 211 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 211 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                            "[HOLD] 自动退出(进入TOUCH)"
# 211 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                            ); &__c[0];}))
# 211 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                            ))); }
      }else if(buf=="TOUCH:OFF"){
        touchMode = false;
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 214 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 214 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[OK] TOUCH OFF"
# 214 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 214 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }else if(buf=="FREE" || buf=="FREE:ON"){
        if(!freeModeActive) enterFreeMode();
        else Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 217 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                 (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 217 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                 "[FREE] 已在自由模式"
# 217 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                 ); &__c[0];}))
# 217 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                 )));
      }else if(buf=="FREE:OFF"){
        if(freeModeActive) exitFreeMode();
        else Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 220 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                 (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 220 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                 "[FREE] 已经退出自由模式"
# 220 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                 ); &__c[0];}))
# 220 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                 )));
      }else if(buf=="AUTOFREE" || buf=="AUTOFREE:ON"){
        autoFree = true;
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 223 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 223 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[OK] AUTOFREE=ON (N=0 且未触摸时自动 torque-off)"
# 223 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 223 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }else if(buf=="AUTOFREE:OFF"){
        autoFree = false;
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 226 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 226 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[OK] AUTOFREE=OFF"
# 226 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 226 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }else if(buf=="HOLD" || buf=="HOLD:ON"){
        // 进入标定固定模式：固定当前位置，关闭自动行为
        if(freeModeActive) exitFreeMode();
        seekMode = false;
        touchMode = false;
        int32_t ppos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        goal_pos = ppos;
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);
        holdMode = true;
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 236 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 236 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[HOLD] ON - 固定当前位置，关闭自动自由/跟随/寻触"
# 236 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 236 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }else if(buf=="HOLD:OFF"){
        holdMode = false;
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 239 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 239 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[HOLD] OFF"
# 239 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 239 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }else if(buf.startsWith("TGAIN:")){
        touchGain_N_per_tick = buf.substring(6).toFloat();
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 242 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 242 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] touchGain_N_per_tick="
# 242 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 242 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(touchGain_N_per_tick,4);
      }else if(buf.startsWith("TMAX:")){
        touchMaxN = buf.substring(5).toFloat();
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 245 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 245 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] touchMaxN="
# 245 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 245 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(touchMaxN,2);
      }else if(buf.startsWith("TMODE:")){
        String m = buf.substring(6);
        m.toUpperCase();
        if(m=="RAMP"){ touchRampMode = true; Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 249 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                 (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 249 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                 "[OK] TMODE=RAMP (按时间线性增力)"
# 249 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                 ); &__c[0];}))
# 249 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                 ))); }
        else if(m=="DISP"){ touchRampMode = false; Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 250 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                       (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 250 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                       "[OK] TMODE=DISP (按位移增力)"
# 250 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                       ); &__c[0];}))
# 250 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                       ))); }
        else { Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 251 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                   (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 251 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                   "[ERR] TMODE 仅支持 RAMP 或 DISP"
# 251 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                   ); &__c[0];}))
# 251 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                   ))); }
      }else if(buf.startsWith("TRATE:")){
        touchRampRateNPerSec = buf.substring(6).toFloat();
        if(touchRampRateNPerSec < 0) touchRampRateNPerSec = 0;
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 255 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 255 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] touchRampRateNPerSec="
# 255 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 255 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(touchRampRateNPerSec,2);
      }else if(buf=="SEEK" || buf=="SEEK:ON"){
        seekMode = true;
        seekStepCounter = 0;
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 259 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 259 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] SEEK ON. seekMaxSteps="
# 259 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 259 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(seekMaxSteps);
      }else if(buf=="SEEK:OFF"){
        seekMode = false;
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 262 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 262 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[OK] SEEK OFF"
# 262 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 262 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }else if(buf.startsWith("SEEKMAX:")){
        seekMaxSteps = buf.substring(8).toInt();
        if(seekMaxSteps < 1) seekMaxSteps = 1;
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 266 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 266 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] seekMaxSteps="
# 266 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 266 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(seekMaxSteps);
      }else if(buf.startsWith("CALMIN:")){
        calMin_mA = buf.substring(7).toInt();
        if(calMin_mA < 1) calMin_mA = 1;
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 270 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 270 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] calMin_mA="
# 270 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 270 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.print(calMin_mA); Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 270 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                                     (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 270 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                                     " mA"
# 270 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                                     ); &__c[0];}))
# 270 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                                     )));
      }else if(buf=="HOME"){
        int32_t old_home = home_pos;
        home_pos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        goal_pos = home_pos;
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 276 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 276 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] Home reset: "
# 276 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 276 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          )));
        Serial.print(old_home);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 278 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 278 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          " -> "
# 278 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 278 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          )));
        Serial.println(home_pos);
      }else if(buf.startsWith("CAL:")){
        float knownN = buf.substring(4).toFloat();
        int16_t mA = (int16_t)dxl.readControlTableItem(PRESENT_CURRENT, DXL_ID);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 283 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 283 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[CAL] 检测到电流: "
# 283 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 283 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          )));
        Serial.print(mA);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 285 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 285 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          " mA "
# 285 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 285 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          )));
        Serial.println(mA > 0 ? (reinterpret_cast<const __FlashStringHelper *>(
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                     (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                     "(被推)"
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                     ); &__c[0];}))
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                     )) : (mA < 0 ? (reinterpret_cast<const __FlashStringHelper *>(
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                               (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                               "(被拉)"
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                               ); &__c[0];}))
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                               )) : (reinterpret_cast<const __FlashStringHelper *>(
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                               (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                               ""
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                               ); &__c[0];}))
# 286 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                               ))));

        if(((mA)>0?(mA):-(mA)) >= calMin_mA){ // 至少要有阈值电流才有意义
          float old_kN = kN_per_mA;
          kN_per_mA = knownN / (float)mA; // 不再取绝对值，保留符号
          Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 291 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 291 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[OK] kN_per_mA: "
# 291 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 291 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
          Serial.print(old_kN, 6);
          Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 293 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 293 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            " -> "
# 293 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 293 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
          Serial.println(kN_per_mA, 6);
          Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 295 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 295 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "     即: "
# 295 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 295 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
          Serial.print(mA);
          Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 297 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 297 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            " mA = "
# 297 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 297 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
          Serial.print(knownN, 2);
          Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 299 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                              (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 299 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                              " N"
# 299 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                              ); &__c[0];}))
# 299 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                              )));
        }else{
          Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 301 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 301 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[WARN] 电流太小(<"
# 301 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 301 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            ))); Serial.print(calMin_mA); Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 301 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                                             (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 301 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                                             "mA)! 请加大外力后再标定。"
# 301 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                                             ); &__c[0];}))
# 301 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                                             )));
          Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 302 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                              (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 302 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                              "       提示: 用手用力推(正力)或拉(负力)舵机"
# 302 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                              ); &__c[0];}))
# 302 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                              )));
          Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 303 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                              (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 303 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                              "             然后立即发送 CAL:1 或 CAL:-1"
# 303 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                              ); &__c[0];}))
# 303 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                              )));
        }
      }else if(buf.startsWith("STEP:")){
        stepPulse = buf.substring(5).toInt();
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 307 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 307 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] stepPulse="
# 307 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 307 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(stepPulse);
      }else if(buf.startsWith("HYS:")){
        hysteresisN = buf.substring(4).toFloat();
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 310 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 310 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] hysteresisN="
# 310 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 310 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(hysteresisN, 2);
      }else if(buf.startsWith("ILIM:")){
        currentLimit_mA = (uint16_t)buf.substring(5).toInt();
        dxl.writeControlTableItem(CURRENT_LIMIT, DXL_ID, currentLimit_mA);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 314 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 314 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] CURRENT_LIMIT="
# 314 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 314 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(currentLimit_mA);
      }else if(buf.startsWith("NLT:")){
        noLoadThreshN = buf.substring(4).toFloat();
        if(noLoadThreshN < 0) noLoadThreshN = 0;
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 318 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 318 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] noLoadThreshN="
# 318 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 318 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(noLoadThreshN,3);
      }else if(buf=="DIRREV" || buf=="DIRREV:ON"){
        controlDir = -1;
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 321 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 321 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[OK] DIRREV=ON (控制方向反转)"
# 321 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 321 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }else if(buf=="DIRREV:OFF"){
        controlDir = +1;
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 324 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 324 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[OK] DIRREV=OFF (控制方向默认)"
# 324 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 324 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }else if(buf.startsWith("DIR:")){
        int v = buf.substring(4).toInt();
        controlDir = (v>=0)? +1 : -1;
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 328 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 328 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] controlDir="
# 328 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 328 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(controlDir);
      }else if(buf.startsWith("KN:")){
        kN_per_mA = buf.substring(3).toFloat();
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 331 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 331 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] kN_per_mA="
# 331 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 331 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(kN_per_mA, 6);
      }else if(buf.startsWith("POS:")){
        int32_t target_pos = buf.substring(4).toInt();
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, target_pos);
        goal_pos = target_pos;
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 336 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 336 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[OK] Moving to position: "
# 336 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 336 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(target_pos);
      }else if(buf=="STATUS"){
        int32_t ppos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        int16_t pcur = (int16_t)dxl.readControlTableItem(PRESENT_CURRENT, DXL_ID);
        float estN = pcur * kN_per_mA; // 带符号的力
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 341 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 341 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "=== 实时状态 ==="
# 341 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 341 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 342 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 342 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "位置: "
# 342 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 342 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(ppos);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 343 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 343 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "电流: "
# 343 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 343 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.print(pcur); Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 343 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                         (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 343 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                         " mA"
# 343 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                         ); &__c[0];}))
# 343 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                         )));
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 344 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 344 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "估算力: "
# 344 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 344 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.print(estN, 2);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 345 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 345 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          " N "
# 345 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 345 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          )));
        Serial.println(estN > 0 ? (reinterpret_cast<const __FlashStringHelper *>(
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                       (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                       "(被推)"
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                       ); &__c[0];}))
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                       )) : (estN < 0 ? (reinterpret_cast<const __FlashStringHelper *>(
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                   (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                   "(被拉)"
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                   ); &__c[0];}))
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                   )) : (reinterpret_cast<const __FlashStringHelper *>(
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                   (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                   "(无力)"
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                   ); &__c[0];}))
# 346 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                   ))));
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 347 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 347 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "提示: 用手推/拉舵机，然后发送 STATUS 查看电流"
# 347 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 347 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 348 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 348 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "      正电流=被推, 负电流=被拉"
# 348 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 348 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 349 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 349 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "      如果电流显示正常，发送 CAL:<实际力> 来标定"
# 349 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 349 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }else if(buf=="INFO"){
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 351 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 351 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "=== 当前参数 ==="
# 351 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 351 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 352 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 352 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "targetForceN = "
# 352 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 352 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(targetForceN, 3);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 353 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 353 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "kN_per_mA = "
# 353 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 353 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(kN_per_mA, 6);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 354 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 354 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "hysteresisN = "
# 354 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 354 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(hysteresisN, 2);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 355 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 355 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "noLoadThreshN = "
# 355 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 355 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(noLoadThreshN, 3);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 356 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 356 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "stepPulse = "
# 356 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 356 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(stepPulse);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 357 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 357 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "currentLimit_mA = "
# 357 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 357 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(currentLimit_mA);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 358 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 358 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "calMin_mA = "
# 358 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 358 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.print(calMin_mA); Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 358 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                                  (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 358 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                                  " mA"
# 358 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                                  ); &__c[0];}))
# 358 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                                  )));
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "freeMode = "
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(freeModeActive ? (reinterpret_cast<const __FlashStringHelper *>(
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                   (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                   "ON"
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                   ); &__c[0];}))
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                   )) : (reinterpret_cast<const __FlashStringHelper *>(
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                             (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                             "OFF"
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                             ); &__c[0];}))
# 359 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                             )));
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "autoFree = "
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(autoFree ? (reinterpret_cast<const __FlashStringHelper *>(
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                             (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                             "ON"
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                             ); &__c[0];}))
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                             )) : (reinterpret_cast<const __FlashStringHelper *>(
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                       (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                       "OFF"
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                       ); &__c[0];}))
# 360 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                       )));
  Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    "holdMode = "
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    ); &__c[0];}))
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    ))); Serial.println(holdMode ? (reinterpret_cast<const __FlashStringHelper *>(
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                       (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                       "ON"
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                       ); &__c[0];}))
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                       )) : (reinterpret_cast<const __FlashStringHelper *>(
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                 (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                 "OFF"
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                 ); &__c[0];}))
# 361 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                 )));
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "touchMode = "
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(touchMode ? (reinterpret_cast<const __FlashStringHelper *>(
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                               (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                               "ON"
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                               ); &__c[0];}))
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                               )) : (reinterpret_cast<const __FlashStringHelper *>(
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                         (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                         "OFF"
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                         ); &__c[0];}))
# 362 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                         )));
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 363 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 363 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "touchGain_N_per_tick = "
# 363 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 363 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(touchGain_N_per_tick,4);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 364 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 364 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "touchMaxN = "
# 364 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 364 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(touchMaxN,2);
  Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    "touchModeType = "
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    ); &__c[0];}))
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    ))); Serial.println(touchRampMode ? (reinterpret_cast<const __FlashStringHelper *>(
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                 (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                 "RAMP"
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                 ); &__c[0];}))
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                 )) : (reinterpret_cast<const __FlashStringHelper *>(
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                             (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                             "DISP"
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                             ); &__c[0];}))
# 365 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                             )));
  Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 366 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 366 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    "touchRampRateNPerSec = "
# 366 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    ); &__c[0];}))
# 366 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    ))); Serial.println(touchRampRateNPerSec,2);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 367 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 367 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "touchStartPos = "
# 367 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 367 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(touchStartPos);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 368 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 368 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "touchBaseN = "
# 368 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 368 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(touchBaseN,2);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 369 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 369 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "touchDirSign = "
# 369 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 369 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(touchDirSign);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "seekMode = "
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(seekMode ? (reinterpret_cast<const __FlashStringHelper *>(
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                             (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                             "ON"
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                             ); &__c[0];}))
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                             )) : (reinterpret_cast<const __FlashStringHelper *>(
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                       (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                       "OFF"
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                       ); &__c[0];}))
# 370 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                       )));
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 371 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 371 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "seekMaxSteps = "
# 371 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 371 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(seekMaxSteps);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 372 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 372 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "home_pos = "
# 372 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 372 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(home_pos);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 373 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 373 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "goal_pos = "
# 373 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 373 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(goal_pos);
  Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 374 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 374 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    "controlDir = "
# 374 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                    ); &__c[0];}))
# 374 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                    ))); Serial.println(controlDir);
        int32_t ppos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        int16_t pcur = (int16_t)dxl.readControlTableItem(PRESENT_CURRENT, DXL_ID);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 377 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 377 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "present_pos = "
# 377 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 377 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(ppos);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 378 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 378 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "present_cur(mA) = "
# 378 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 378 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(pcur);
      }else if(buf=="TEST"){
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 380 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 380 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "[TEST] 移动测试开始..."
# 380 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 380 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
        int32_t test_home = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 382 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 382 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "  起始位置: "
# 382 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 382 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(test_home);

        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 384 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 384 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "  -> 向正方向移动 500 脉冲"
# 384 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 384 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, test_home + 500);
        delay(1500);
        int32_t pos1 = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 388 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 388 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "  当前位置: "
# 388 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 388 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(pos1);

        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 390 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 390 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "  -> 向负方向移动 500 脉冲"
# 390 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 390 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, test_home - 500);
        delay(1500);
        int32_t pos2 = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 394 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 394 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "  当前位置: "
# 394 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 394 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(pos2);

        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 396 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 396 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            "  -> 回到起始位置"
# 396 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 396 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, test_home);
        delay(1000);
        int32_t pos3 = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 400 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 400 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "  最终位置: "
# 400 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 400 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          ))); Serial.println(pos3);

        goal_pos = test_home;
        Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 403 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 403 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          "[TEST] 完成 - 移动范围: "
# 403 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                          ); &__c[0];}))
# 403 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                          )));
        Serial.print(pos1 - pos2);
        Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 405 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 405 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            " 脉冲"
# 405 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                            ); &__c[0];}))
# 405 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                            )));
      }else{
        if(buf.length()) Serial.println((reinterpret_cast<const __FlashStringHelper *>(
# 407 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                             (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 407 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                             "[ERR] Unknown cmd."
# 407 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                             ); &__c[0];}))
# 407 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                             )));
      }
      buf="";
    }else{
      buf+=c;
    }
  }
}

void loop(){
  static uint32_t lastPrint = 0;
  handleSerial();

  // 读取位置和电流
  int32_t present_pos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
  int16_t present_mA = (int16_t)dxl.readControlTableItem(PRESENT_CURRENT, DXL_ID);

  // ★★★ 关键改变：保留电流符号，力也带符号 ★★★
  float estN = present_mA * kN_per_mA; // 不再取绝对值！

  // 检查是否接近目标位置（在20个脉冲以内认为已到达）
  // 注意：为满足“有力才动，无力不动”的需求，我们不再强依赖 nearGoal 才执行控制
  bool nearGoal = ((present_pos - goal_pos)>0?(present_pos - goal_pos):-(present_pos - goal_pos)) < 20;

  // 无载阈值：当力的绝对值小于该阈值时认为“几乎无力”，避免微小噪声引起移动
  // 可通过 NLT 命令设置，默认 0.08N

  // 记录最近一次非零电流方向
  if(present_mA > 1) lastNonZeroSign = +1;
  else if(present_mA < -1) lastNonZeroSign = -1;

  // 自动自由：N=0 且未触摸时自动关闭扭矩；但在 HOLD 模式下强制扭矩开启并忽略自动自由
  if(autoFree){
    if(holdMode){
      if(freeModeActive) exitFreeMode();
    }else if(!touchMode && targetForceN == 0){
      if(!freeModeActive) enterFreeMode();
    }else{
      if(freeModeActive) exitFreeMode();
    }
  }

  // 触摸模式：按模式更新 N
  if(touchMode){
    float newN = targetForceN;
    if(touchRampMode){
      // 按时间线性增力：N = baseN + rate * dt，直到触摸上限
      float dt = (millis() - touchStartMs) / 1000.0f;
      newN = touchBaseN + touchRampRateNPerSec * dt;
    }else{
      // 按位移线性增力（仅沿负载方向投影的位移增加 N）
      int32_t disp = present_pos - touchStartPos; // 当前位置相对触摸开始的位移（tick）
      // 若当前电流达到可感知阈值，动态刷新触摸方向
      if(((present_mA)>0?(present_mA):-(present_mA)) >= calMin_mA){
        touchDirSign = (present_mA > 0) ? +1 : -1;
      }
      int dispAlong = disp * (touchDirSign == 0 ? 1 : touchDirSign);
      float addN = (dispAlong > 0) ? (dispAlong * touchGain_N_per_tick) : 0.0f;
      newN = touchBaseN + addN;
    }
    // 限幅
    if(newN > touchMaxN) newN = touchMaxN;
    if(newN < -touchMaxN) newN = -touchMaxN;
    targetForceN = newN;
  }

  // 每500ms打印一次状态（仅当目标力!=0时）
  if(targetForceN != 0 && (millis() - lastPrint > 500)){
    Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 475 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 475 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "POS="
# 475 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 475 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ))); Serial.print(present_pos);
    Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 476 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 476 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      " GOAL="
# 476 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 476 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ))); Serial.print(goal_pos);
    Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 477 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 477 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      " | CUR="
# 477 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 477 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ))); Serial.print(present_mA);
    Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 478 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 478 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "mA | estN="
# 478 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 478 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ))); Serial.print(estN,2);
    Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 479 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 479 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "N | target="
# 479 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 479 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ))); Serial.print(targetForceN,1);
    Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 480 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 480 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      "N | "
# 480 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 480 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      )));
    Serial.print(nearGoal ? (reinterpret_cast<const __FlashStringHelper *>(
# 481 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                 (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 481 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                 "NEAR"
# 481 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                 ); &__c[0];}))
# 481 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                 )) : (reinterpret_cast<const __FlashStringHelper *>(
# 481 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                             (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 481 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                             "MOVING"
# 481 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                             ); &__c[0];}))
# 481 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                             )));
    // 显示控制决策（带正负方向）
    float err = estN - targetForceN;
    Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 484 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 484 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      " | err="
# 484 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                      ); &__c[0];}))
# 484 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                      ))); Serial.print(err,2); Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 484 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                   (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 484 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                   "N"
# 484 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                                                                                   ); &__c[0];}))
# 484 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                                                                                   )));
    if(fabs(estN) < noLoadThreshN){
      Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 486 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                        (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 486 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                        " -> 无力,保持"
# 486 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                        ); &__c[0];}))
# 486 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                        )));
    }else if(err < -hysteresisN){
      Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 488 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                        (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 488 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                        " -> 力<目标,正转(逆负载)"
# 488 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                        ); &__c[0];}))
# 488 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                        )));
    }else if(err > hysteresisN){
      Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 490 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                        (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 490 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                        " -> 力>目标,反转(顺负载)"
# 490 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                        ); &__c[0];}))
# 490 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                        )));
    }else{
      Serial.print((reinterpret_cast<const __FlashStringHelper *>(
# 492 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                        (__extension__({static const char __c[] __attribute__((__progmem__)) = (
# 492 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                        " -> 力≈目标,保持"
# 492 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino" 3
                        ); &__c[0];}))
# 492 "/home/wxc/projects/dexEXO/xl330_force_demo/xl330_force_demo.ino"
                        )));
    }
    Serial.println();
    lastPrint = millis();
  }

  // N==0: 自由跟随（尽量不产生反力，让位置随外力变化）
  if(holdMode){
    // 标定固定模式：保持 goal_pos 不变，仅用于观测电流
  }
  else if(targetForceN == 0){
    if((((int32_t)(goal_pos - present_pos))>0?((int32_t)(goal_pos - present_pos)):-((int32_t)(goal_pos - present_pos))) > 2){
      goal_pos = present_pos; // 追随当前位置，产生近似“自由”手感
      dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);
    }
  }

  // 控制律：满足你的规则
  // - 负载(力) 大于 目标(例如 1N) -> 舵机朝负载方向运动（顺负载，反转）
  // - 负载(力) 小于 目标 -> 舵机朝负载反方向运动（逆负载，正转）
  // - 等于 目标 -> 不动
  else if(targetForceN != 0 && !holdMode){
    if(freeModeActive) exitFreeMode(); // 有目标力时应使能扭矩
    float err = estN - targetForceN; // 正表示力偏大
    if(fabs(estN) < noLoadThreshN){
      // 无力：根据 seekMode 决定是否主动寻触
      if(seekMode && seekStepCounter < seekMaxSteps){
        // 按 err 的方向执行与迟滞区一致的步进
        if(err < 0){
          goal_pos += controlDir * stepPulse;
        }else if(err > 0){
          goal_pos -= controlDir * stepPulse;
        }
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);
        seekStepCounter++;
      }else{
        // 无力且不寻触：不响应，避免空跑
      }
    }else if(err < -hysteresisN){
      // 力 < 目标：逆负载（position 方向与负载相反）
      goal_pos += controlDir * stepPulse;
      dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);
      // 成功开始产生力，重置 seek 计数
      seekStepCounter = 0;
    }else if(err > hysteresisN){
      // 力 > 目标：顺负载（position 沿负载方向）
      goal_pos -= controlDir * stepPulse;
      dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);
      // 成功开始产生力，重置 seek 计数
      seekStepCounter = 0;
    } // 处于迟滞区：保持不动
  }

  delay(5); // ~200 Hz 循环
}
