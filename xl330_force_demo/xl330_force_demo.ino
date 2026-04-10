#include <Dynamixel2Arduino.h>
using namespace ControlTableItem;   // 直接使用控制表项符号名（如 PRESENT_CURRENT 等）

// ===== 硬件串口 & 舵机参数 =====
#define DXL_SERIAL   Serial1       // Mega2560 Pro: TX1=18, RX1=19
#define DEBUG_SERIAL Serial
const int    DXL_DIR_PIN = -1;      // 自动方向板不接此脚也可；库仍会切换该引脚，不影响
const uint8_t DXL_ID = 1;
const float   DXL_PROTOCOL = 2.0;

// ===== 目标 & 控制参数（可串口指令修改）=====
float  targetForceN = 0.0f;        // 目标力(N)，由 "N:10" 指令设置
float  kN_per_mA    = 0.25f;      // 力换算系数：N = |mA| * kN_per_mA ——建议用CAL命令标定！
float  hysteresisN  = 0.15f;       // 力迟滞带，避免抖动（默认 0.15N）
int    stepPulse    = 2;           // 每次调整的脉冲步进（默认 2）
uint16_t currentLimit_mA = 150;    // 电流（力矩）上限（默认 150mA）

// ===== 触摸(touch)模式相关 =====
bool   touchMode = false;          // 是否处于触摸模式（接触物体）
float  touchGain_N_per_tick = 0.05f;// N 增益 = 位移tick * 此系数（默认 0.05N/脉冲，建议按需调整）
float  touchMaxN = 5.0f;          // 触摸模式下 N 的上限，默认 10N（可通过 TMAX 调整）
int32_t touchStartPos = 0;         // 触摸开始时的位置（tick）
float  touchBaseN = 0.0f;          // 触摸开始时的基准 N（通常为 0）
int    touchDirSign = 0;           // 负载方向（+1/-1），触摸时确定
int    lastNonZeroSign = 0;        // 最近一次非零电流方向，用于方向丢失时回退
uint32_t touchStartMs = 0;         // 触摸开始时间戳
bool   touchRampMode = true;       // 触摸模式：true=时间线性增力(RAMP)，false=位移增力(DISP)
float  touchRampRateNPerSec = 0.5f;// RAMP：线性增力速率 N/s（默认 0.5），直到触摸上限

// ===== 运行配置 =====
int8_t g_opMode = OP_CURRENT_BASED_POSITION; // 缓存当前工作模式
int    calMin_mA = 2;              // CAL 标定所需的最小电流阈值（绝对值），默认 2mA
bool   freeModeActive = false;     // N=0 自由模式（扭矩关闭）
float  noLoadThreshN = 0.08f;      // 无载阈值 N，可配置
bool   seekMode = false;           // 当无载时，是否主动寻觸以达到目标力
int    seekMaxSteps = 30;          // 主动寻触的最大步数（默认 30，用于安全防护，防止无限移动）
int    seekStepCounter = 0;
bool   autoFree = true;            // 自动自由模式：N=0 且非触摸时自动 torque-off
bool   holdMode = false;           // 标定/测试固定模式：固定当前位置，关闭自动自由/跟随/寻触
int    controlDir = +1;            // 控制方向：+1=默认映射，-1=反向映射（用于机械装配方向不一致时）

int32_t home_pos = 0;              // 零位（上电后记录当前为Home，或通过 HOME 指令重置）
int32_t goal_pos = 0;

Dynamixel2Arduino dxl(DXL_SERIAL, DXL_DIR_PIN);

static inline int32_t stepToward(int32_t from, int32_t to, int32_t step){
  if(from < to) return (from + step > to) ? to : from + step;
  if(from > to) return (from - step < to) ? to : from - step;
  return from;
}

void setup(){
  DEBUG_SERIAL.begin(115200);
  while(!DEBUG_SERIAL){;}

  dxl.begin(57600);                       // XL330 缺省 57600 - 必须先 begin()
  dxl.setPortProtocolVersion(DXL_PROTOCOL);
  delay(50);
  
  // 测试连接
  bool pingOk = dxl.ping(DXL_ID);
  DEBUG_SERIAL.print(F("PING ID "));
  DEBUG_SERIAL.print(DXL_ID);
  DEBUG_SERIAL.println(pingOk ? F(" : OK") : F(" : FAIL - 检查接线/ID/波特率"));

  // 安全初始化
  dxl.torqueOff(DXL_ID);
  dxl.setOperatingMode(DXL_ID, OP_CURRENT_BASED_POSITION); // 电流基位置模式
  dxl.writeControlTableItem(CURRENT_LIMIT,      DXL_ID, currentLimit_mA);
  dxl.writeControlTableItem(PROFILE_VELOCITY,   DXL_ID, 200);   // 增大速度 (0=无限制)
  dxl.writeControlTableItem(PROFILE_ACCELERATION, DXL_ID, 100); // 增大加速度
  dxl.torqueOn(DXL_ID);
  delay(100);
  freeModeActive = false;
  
  DEBUG_SERIAL.print(F("Operating Mode: "));
  DEBUG_SERIAL.println(dxl.readControlTableItem(OPERATING_MODE, DXL_ID));
  DEBUG_SERIAL.print(F("Torque Enable: "));
  DEBUG_SERIAL.println(dxl.readControlTableItem(TORQUE_ENABLE, DXL_ID));

  home_pos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
  goal_pos = home_pos;
  dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);

  DEBUG_SERIAL.println(F("DexEXO XL330 single-servo demo ready."));
  DEBUG_SERIAL.println(F(""));
  DEBUG_SERIAL.println(F("=== 快速开始 ==="));
  DEBUG_SERIAL.println(F("1. 发送: STATUS (查看当前电流)"));
  DEBUG_SERIAL.println(F("2. 用手推舵机，再发送 STATUS"));
  DEBUG_SERIAL.println(F("3. 发送: CAL:1 (假设刚才用了1N力)"));
  DEBUG_SERIAL.println(F("4. 发送: N:0 (自由跟随)"));
  DEBUG_SERIAL.println(F("5. 发送: TOUCH 或 TOUCH:ON 开启触摸模式"));
  DEBUG_SERIAL.println(F("6. 触摸期间: N 会随位移增加，新N = 基准N + 位移tick * TGAIN"));
  DEBUG_SERIAL.println(F("7. 可用 TGAIN:<k> 和 TMAX:<N> 调整增益和上限"));
  DEBUG_SERIAL.println(F(""));
  DEBUG_SERIAL.println(F("=== 力追随模式说明 ==="));
  DEBUG_SERIAL.println(F("力带有方向(正/负):"));
  DEBUG_SERIAL.println(F("  正力(+): 舵机被推的力"));
  DEBUG_SERIAL.println(F("  负力(-): 舵机被拉的力"));
  DEBUG_SERIAL.println(F(""));
  DEBUG_SERIAL.println(F("控制规则（设置N:1为例）:"));
  DEBUG_SERIAL.println(F("  检测力 < 1N  → 舵机正转(position+)"));
  DEBUG_SERIAL.println(F("  检测力 > 1N  → 舵机反转(position-)"));
  DEBUG_SERIAL.println(F("  检测力 = 1N  → 舵机不动"));
  DEBUG_SERIAL.println(F(""));
  DEBUG_SERIAL.println(F("实际效果:"));
  DEBUG_SERIAL.println(F("  - 用手推舵机: 力变大→舵机反转减小阻力→维持1N"));
  DEBUG_SERIAL.println(F("  - 松手不推: 力变0→舵机不会自己动！"));
  DEBUG_SERIAL.println(F("  - 用手拉舵机: 力变负→舵机正转抵抗→维持1N"));
  DEBUG_SERIAL.println(F(""));
  DEBUG_SERIAL.println(F("=== 所有命令 ==="));
  DEBUG_SERIAL.println(F("STATUS     - 查看实时电流(标定前先用这个!)"));
  DEBUG_SERIAL.println(F("N:<val>    - 设置目标力(N)"));
  DEBUG_SERIAL.println(F("TOUCH[:ON|:OFF] - 进入/退出触摸模式，ON时N随位移增加"));
  DEBUG_SERIAL.println(F("TGAIN:<k>  - 位移-力增益(N/脉冲)，默认0.05"));
  DEBUG_SERIAL.println(F("TMAX:<N>   - 触摸模式下N的上限，默认10N"));
  DEBUG_SERIAL.println(F("TMODE:<RAMP|DISP> - 触摸增力模式：RAMP=按时间线性递增，DISP=按位移递增(默认RAMP)"));
  DEBUG_SERIAL.println(F("TRATE:<n>  - RAMP模式下线性增力速率(N/s)，默认0.5"));
  DEBUG_SERIAL.println(F("SEEK[:ON|:OFF] - 在无载时主动移动以寻找目标力(危险：注意限位)"));
  DEBUG_SERIAL.println(F("SEEKMAX:<n> - 设置主动寻触最多步数，默认30"));
  DEBUG_SERIAL.println(F("FREE[:ON|:OFF] - 手动进入/退出自由模式(扭矩关闭)"));
  DEBUG_SERIAL.println(F("AUTOFREE[:ON|:OFF] - 自动自由模式：N=0 且未触摸时自动扭矩关闭(默认ON)"));
  DEBUG_SERIAL.println(F("HOLD[:ON|:OFF] - 标定/用力测试固定当前位置，关闭自动自由/跟随/寻触"));
  DEBUG_SERIAL.println(F("CALMIN:<mA> - 设置CAL最小电流阈值, 默认2mA (噪声大可调大)"));
  DEBUG_SERIAL.println(F("HOME       - 重置零位"));
  DEBUG_SERIAL.println(F("CAL:<N>    - 标定: 当前受力为<N>牛"));
  DEBUG_SERIAL.println(F("KN:<coef>  - 直接设置换算系数"));
  DEBUG_SERIAL.println(F("HYS:<h>    - 设置迟滞带(N)"));
  DEBUG_SERIAL.println(F("STEP:<p>   - 设置步进量"));
  DEBUG_SERIAL.println(F("ILIM:<mA>  - 设置电流限制"));
  DEBUG_SERIAL.println(F("NLT:<N>    - 设置无载阈值(避免噪声动作)，默认0.08N"));
  DEBUG_SERIAL.println(F("DIRREV[:ON|:OFF] - 控制方向反转开关(机械装配相反时使用)"));
  DEBUG_SERIAL.println(F("DIR:<+1|-1> - 直接设置控制方向(+1=默认,-1=反向)"));
  DEBUG_SERIAL.println(F("INFO       - 显示所有参数"));
  DEBUG_SERIAL.println(F("TEST       - 测试移动"));
  DEBUG_SERIAL.println(F("POS:<p>    - 移动到位置"));
  DEBUG_SERIAL.println(F(""));
  DEBUG_SERIAL.print(F("初始 Home=")); DEBUG_SERIAL.print(home_pos);
  DEBUG_SERIAL.print(F(", kN_per_mA=")); DEBUG_SERIAL.print(kN_per_mA, 6);
  DEBUG_SERIAL.println(F(" (未标定!)"));
}

// 自由模式切换
static inline void enterFreeMode(){
  dxl.torqueOff(DXL_ID);
  freeModeActive = true;
  DEBUG_SERIAL.println(F("[FREE] 扭矩关闭，自由跟随(完全无电)"));
}

static inline void exitFreeMode(){
  int32_t ppos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
  dxl.torqueOn(DXL_ID);
  // 为避免跳变，先把目标对齐到当前位置
  goal_pos = ppos;
  dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);
  freeModeActive = false;
  DEBUG_SERIAL.println(F("[FREE] 扭矩开启，恢复控制"));
}

void handleSerial(){
  static String buf;
  while(DEBUG_SERIAL.available()){
    char c = DEBUG_SERIAL.read();
    if(c=='\n' || c=='\r'){
      buf.trim();
      
      // 调试：显示接收到的命令
      if(buf.length() > 0){
        DEBUG_SERIAL.print(F("[RCV] '")); 
        DEBUG_SERIAL.print(buf); 
        DEBUG_SERIAL.print(F("' (len=")); 
        DEBUG_SERIAL.print(buf.length());
        DEBUG_SERIAL.println(F(")"));
      }
      
      // 支持中英文冒号
      buf.replace("：", ":");
      
      if(buf.startsWith("N:")){
        targetForceN = buf.substring(2).toFloat();
        DEBUG_SERIAL.print(F("[OK] targetForceN=")); DEBUG_SERIAL.println(targetForceN,3);
        if(targetForceN == 0){
          // N=0 表示自由跟随模式
          touchMode = false; // 退出触摸模式
          // 不自动关闭扭矩，若需要完全自由由 FREE:ON 决定
        }else{
          // 非零目标力，确保扭矩开启
          if(freeModeActive) exitFreeMode();
          if(holdMode){ holdMode = false; DEBUG_SERIAL.println(F("[HOLD] 自动退出(检测到N!=0)")); }
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
        DEBUG_SERIAL.print(F("[OK] TOUCH ON. baseN=")); DEBUG_SERIAL.print(touchBaseN,2);
        DEBUG_SERIAL.print(F(" startPos=")); DEBUG_SERIAL.print(touchStartPos);
        DEBUG_SERIAL.print(F(" dir=")); DEBUG_SERIAL.println(touchDirSign);
        DEBUG_SERIAL.print(F("[INFO] SEEK 自动开启, seekMaxSteps=")); DEBUG_SERIAL.println(seekMaxSteps);
        if(holdMode){ holdMode = false; DEBUG_SERIAL.println(F("[HOLD] 自动退出(进入TOUCH)")); }
      }else if(buf=="TOUCH:OFF"){
        touchMode = false;
        DEBUG_SERIAL.println(F("[OK] TOUCH OFF"));
      }else if(buf=="FREE" || buf=="FREE:ON"){
        if(!freeModeActive) enterFreeMode();
        else DEBUG_SERIAL.println(F("[FREE] 已在自由模式"));
      }else if(buf=="FREE:OFF"){
        if(freeModeActive) exitFreeMode();
        else DEBUG_SERIAL.println(F("[FREE] 已经退出自由模式"));
      }else if(buf=="AUTOFREE" || buf=="AUTOFREE:ON"){
        autoFree = true;
        DEBUG_SERIAL.println(F("[OK] AUTOFREE=ON (N=0 且未触摸时自动 torque-off)"));
      }else if(buf=="AUTOFREE:OFF"){
        autoFree = false;
        DEBUG_SERIAL.println(F("[OK] AUTOFREE=OFF"));
      }else if(buf=="HOLD" || buf=="HOLD:ON"){
        // 进入标定固定模式：固定当前位置，关闭自动行为
        if(freeModeActive) exitFreeMode();
        seekMode = false;
        touchMode = false;
        int32_t ppos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        goal_pos = ppos;
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);
        holdMode = true;
        DEBUG_SERIAL.println(F("[HOLD] ON - 固定当前位置，关闭自动自由/跟随/寻触"));
      }else if(buf=="HOLD:OFF"){
        holdMode = false;
        DEBUG_SERIAL.println(F("[HOLD] OFF"));
      }else if(buf.startsWith("TGAIN:")){
        touchGain_N_per_tick = buf.substring(6).toFloat();
        DEBUG_SERIAL.print(F("[OK] touchGain_N_per_tick=")); DEBUG_SERIAL.println(touchGain_N_per_tick,4);
      }else if(buf.startsWith("TMAX:")){
        touchMaxN = buf.substring(5).toFloat();
        DEBUG_SERIAL.print(F("[OK] touchMaxN=")); DEBUG_SERIAL.println(touchMaxN,2);
      }else if(buf.startsWith("TMODE:")){
        String m = buf.substring(6);
        m.toUpperCase();
        if(m=="RAMP"){ touchRampMode = true; DEBUG_SERIAL.println(F("[OK] TMODE=RAMP (按时间线性增力)")); }
        else if(m=="DISP"){ touchRampMode = false; DEBUG_SERIAL.println(F("[OK] TMODE=DISP (按位移增力)")); }
        else { DEBUG_SERIAL.println(F("[ERR] TMODE 仅支持 RAMP 或 DISP")); }
      }else if(buf.startsWith("TRATE:")){
        touchRampRateNPerSec = buf.substring(6).toFloat();
        if(touchRampRateNPerSec < 0) touchRampRateNPerSec = 0;
        DEBUG_SERIAL.print(F("[OK] touchRampRateNPerSec=")); DEBUG_SERIAL.println(touchRampRateNPerSec,2);
      }else if(buf=="SEEK" || buf=="SEEK:ON"){
        seekMode = true;
        seekStepCounter = 0;
        DEBUG_SERIAL.print(F("[OK] SEEK ON. seekMaxSteps=")); DEBUG_SERIAL.println(seekMaxSteps);
      }else if(buf=="SEEK:OFF"){
        seekMode = false;
        DEBUG_SERIAL.println(F("[OK] SEEK OFF"));
      }else if(buf.startsWith("SEEKMAX:")){
        seekMaxSteps = buf.substring(8).toInt();
        if(seekMaxSteps < 1) seekMaxSteps = 1;
        DEBUG_SERIAL.print(F("[OK] seekMaxSteps=")); DEBUG_SERIAL.println(seekMaxSteps);
      }else if(buf.startsWith("CALMIN:")){
        calMin_mA = buf.substring(7).toInt();
        if(calMin_mA < 1) calMin_mA = 1;
        DEBUG_SERIAL.print(F("[OK] calMin_mA=")); DEBUG_SERIAL.print(calMin_mA); DEBUG_SERIAL.println(F(" mA"));
      }else if(buf=="HOME"){
        int32_t old_home = home_pos;
        home_pos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        goal_pos = home_pos;
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, goal_pos);
        DEBUG_SERIAL.print(F("[OK] Home reset: ")); 
        DEBUG_SERIAL.print(old_home);
        DEBUG_SERIAL.print(F(" -> "));
        DEBUG_SERIAL.println(home_pos);
      }else if(buf.startsWith("CAL:")){
        float knownN = buf.substring(4).toFloat();
        int16_t mA = (int16_t)dxl.readControlTableItem(PRESENT_CURRENT, DXL_ID);
        DEBUG_SERIAL.print(F("[CAL] 检测到电流: ")); 
        DEBUG_SERIAL.print(mA); 
        DEBUG_SERIAL.print(F(" mA "));
        DEBUG_SERIAL.println(mA > 0 ? F("(被推)") : (mA < 0 ? F("(被拉)") : F("")));
        
        if(abs(mA) >= calMin_mA){  // 至少要有阈值电流才有意义
          float old_kN = kN_per_mA;
          kN_per_mA = knownN / (float)mA;  // 不再取绝对值，保留符号
          DEBUG_SERIAL.print(F("[OK] kN_per_mA: "));
          DEBUG_SERIAL.print(old_kN, 6);
          DEBUG_SERIAL.print(F(" -> "));
          DEBUG_SERIAL.println(kN_per_mA, 6);
          DEBUG_SERIAL.print(F("     即: ")); 
          DEBUG_SERIAL.print(mA); 
          DEBUG_SERIAL.print(F(" mA = ")); 
          DEBUG_SERIAL.print(knownN, 2); 
          DEBUG_SERIAL.println(F(" N"));
        }else{
          DEBUG_SERIAL.print(F("[WARN] 电流太小(<")); DEBUG_SERIAL.print(calMin_mA); DEBUG_SERIAL.println(F("mA)! 请加大外力后再标定。"));
          DEBUG_SERIAL.println(F("       提示: 用手用力推(正力)或拉(负力)舵机"));
          DEBUG_SERIAL.println(F("             然后立即发送 CAL:1 或 CAL:-1"));
        }
      }else if(buf.startsWith("STEP:")){
        stepPulse = buf.substring(5).toInt();
        DEBUG_SERIAL.print(F("[OK] stepPulse=")); DEBUG_SERIAL.println(stepPulse);
      }else if(buf.startsWith("HYS:")){
        hysteresisN = buf.substring(4).toFloat();
        DEBUG_SERIAL.print(F("[OK] hysteresisN=")); DEBUG_SERIAL.println(hysteresisN, 2);
      }else if(buf.startsWith("ILIM:")){
        currentLimit_mA = (uint16_t)buf.substring(5).toInt();
        dxl.writeControlTableItem(CURRENT_LIMIT, DXL_ID, currentLimit_mA);
        DEBUG_SERIAL.print(F("[OK] CURRENT_LIMIT=")); DEBUG_SERIAL.println(currentLimit_mA);
      }else if(buf.startsWith("NLT:")){
        noLoadThreshN = buf.substring(4).toFloat();
        if(noLoadThreshN < 0) noLoadThreshN = 0;
        DEBUG_SERIAL.print(F("[OK] noLoadThreshN=")); DEBUG_SERIAL.println(noLoadThreshN,3);
      }else if(buf=="DIRREV" || buf=="DIRREV:ON"){
        controlDir = -1;
        DEBUG_SERIAL.println(F("[OK] DIRREV=ON (控制方向反转)"));
      }else if(buf=="DIRREV:OFF"){
        controlDir = +1;
        DEBUG_SERIAL.println(F("[OK] DIRREV=OFF (控制方向默认)"));
      }else if(buf.startsWith("DIR:")){
        int v = buf.substring(4).toInt();
        controlDir = (v>=0)? +1 : -1;
        DEBUG_SERIAL.print(F("[OK] controlDir=")); DEBUG_SERIAL.println(controlDir);
      }else if(buf.startsWith("KN:")){
        kN_per_mA = buf.substring(3).toFloat();
        DEBUG_SERIAL.print(F("[OK] kN_per_mA=")); DEBUG_SERIAL.println(kN_per_mA, 6);
      }else if(buf.startsWith("POS:")){
        int32_t target_pos = buf.substring(4).toInt();
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, target_pos);
        goal_pos = target_pos;
        DEBUG_SERIAL.print(F("[OK] Moving to position: ")); DEBUG_SERIAL.println(target_pos);
      }else if(buf=="STATUS"){
        int32_t ppos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        int16_t pcur = (int16_t)dxl.readControlTableItem(PRESENT_CURRENT, DXL_ID);
        float estN = pcur * kN_per_mA;  // 带符号的力
        DEBUG_SERIAL.println(F("=== 实时状态 ==="));
        DEBUG_SERIAL.print(F("位置: ")); DEBUG_SERIAL.println(ppos);
        DEBUG_SERIAL.print(F("电流: ")); DEBUG_SERIAL.print(pcur); DEBUG_SERIAL.println(F(" mA"));
        DEBUG_SERIAL.print(F("估算力: ")); DEBUG_SERIAL.print(estN, 2); 
        DEBUG_SERIAL.print(F(" N ")); 
        DEBUG_SERIAL.println(estN > 0 ? F("(被推)") : (estN < 0 ? F("(被拉)") : F("(无力)")));
        DEBUG_SERIAL.println(F("提示: 用手推/拉舵机，然后发送 STATUS 查看电流"));
        DEBUG_SERIAL.println(F("      正电流=被推, 负电流=被拉"));
        DEBUG_SERIAL.println(F("      如果电流显示正常，发送 CAL:<实际力> 来标定"));
      }else if(buf=="INFO"){
        DEBUG_SERIAL.println(F("=== 当前参数 ==="));
        DEBUG_SERIAL.print(F("targetForceN = ")); DEBUG_SERIAL.println(targetForceN, 3);
        DEBUG_SERIAL.print(F("kN_per_mA = ")); DEBUG_SERIAL.println(kN_per_mA, 6);
        DEBUG_SERIAL.print(F("hysteresisN = ")); DEBUG_SERIAL.println(hysteresisN, 2);
        DEBUG_SERIAL.print(F("noLoadThreshN = ")); DEBUG_SERIAL.println(noLoadThreshN, 3);
        DEBUG_SERIAL.print(F("stepPulse = ")); DEBUG_SERIAL.println(stepPulse);
        DEBUG_SERIAL.print(F("currentLimit_mA = ")); DEBUG_SERIAL.println(currentLimit_mA);
        DEBUG_SERIAL.print(F("calMin_mA = ")); DEBUG_SERIAL.print(calMin_mA); DEBUG_SERIAL.println(F(" mA"));
        DEBUG_SERIAL.print(F("freeMode = ")); DEBUG_SERIAL.println(freeModeActive ? F("ON") : F("OFF"));
        DEBUG_SERIAL.print(F("autoFree = ")); DEBUG_SERIAL.println(autoFree ? F("ON") : F("OFF"));
  DEBUG_SERIAL.print(F("holdMode = ")); DEBUG_SERIAL.println(holdMode ? F("ON") : F("OFF"));
        DEBUG_SERIAL.print(F("touchMode = ")); DEBUG_SERIAL.println(touchMode ? F("ON") : F("OFF"));
        DEBUG_SERIAL.print(F("touchGain_N_per_tick = ")); DEBUG_SERIAL.println(touchGain_N_per_tick,4);
        DEBUG_SERIAL.print(F("touchMaxN = ")); DEBUG_SERIAL.println(touchMaxN,2);
  DEBUG_SERIAL.print(F("touchModeType = ")); DEBUG_SERIAL.println(touchRampMode ? F("RAMP") : F("DISP"));
  DEBUG_SERIAL.print(F("touchRampRateNPerSec = ")); DEBUG_SERIAL.println(touchRampRateNPerSec,2);
        DEBUG_SERIAL.print(F("touchStartPos = ")); DEBUG_SERIAL.println(touchStartPos);
        DEBUG_SERIAL.print(F("touchBaseN = ")); DEBUG_SERIAL.println(touchBaseN,2);
        DEBUG_SERIAL.print(F("touchDirSign = ")); DEBUG_SERIAL.println(touchDirSign);
        DEBUG_SERIAL.print(F("seekMode = ")); DEBUG_SERIAL.println(seekMode ? F("ON") : F("OFF"));
        DEBUG_SERIAL.print(F("seekMaxSteps = ")); DEBUG_SERIAL.println(seekMaxSteps);
        DEBUG_SERIAL.print(F("home_pos = ")); DEBUG_SERIAL.println(home_pos);
        DEBUG_SERIAL.print(F("goal_pos = ")); DEBUG_SERIAL.println(goal_pos);
  DEBUG_SERIAL.print(F("controlDir = ")); DEBUG_SERIAL.println(controlDir);
        int32_t ppos = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        int16_t pcur = (int16_t)dxl.readControlTableItem(PRESENT_CURRENT, DXL_ID);
        DEBUG_SERIAL.print(F("present_pos = ")); DEBUG_SERIAL.println(ppos);
        DEBUG_SERIAL.print(F("present_cur(mA) = ")); DEBUG_SERIAL.println(pcur);
      }else if(buf=="TEST"){
        DEBUG_SERIAL.println(F("[TEST] 移动测试开始..."));
        int32_t test_home = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        DEBUG_SERIAL.print(F("  起始位置: ")); DEBUG_SERIAL.println(test_home);
        
        DEBUG_SERIAL.println(F("  -> 向正方向移动 500 脉冲"));
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, test_home + 500);
        delay(1500);
        int32_t pos1 = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        DEBUG_SERIAL.print(F("  当前位置: ")); DEBUG_SERIAL.println(pos1);
        
        DEBUG_SERIAL.println(F("  -> 向负方向移动 500 脉冲"));
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, test_home - 500);
        delay(1500);
        int32_t pos2 = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        DEBUG_SERIAL.print(F("  当前位置: ")); DEBUG_SERIAL.println(pos2);
        
        DEBUG_SERIAL.println(F("  -> 回到起始位置"));
        dxl.writeControlTableItem(GOAL_POSITION, DXL_ID, test_home);
        delay(1000);
        int32_t pos3 = dxl.readControlTableItem(PRESENT_POSITION, DXL_ID);
        DEBUG_SERIAL.print(F("  最终位置: ")); DEBUG_SERIAL.println(pos3);
        
        goal_pos = test_home;
        DEBUG_SERIAL.print(F("[TEST] 完成 - 移动范围: "));
        DEBUG_SERIAL.print(pos1 - pos2);
        DEBUG_SERIAL.println(F(" 脉冲"));
      }else{
        if(buf.length()) DEBUG_SERIAL.println(F("[ERR] Unknown cmd."));
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
  float   estN = present_mA * kN_per_mA;  // 不再取绝对值！

  // 检查是否接近目标位置（在20个脉冲以内认为已到达）
  // 注意：为满足“有力才动，无力不动”的需求，我们不再强依赖 nearGoal 才执行控制
  bool nearGoal = abs(present_pos - goal_pos) < 20;

  // 无载阈值：当力的绝对值小于该阈值时认为“几乎无力”，避免微小噪声引起移动
  // 可通过 NLT 命令设置，默认 0.08N

  // 记录最近一次非零电流方向
  if(present_mA > 1)      lastNonZeroSign = +1;
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
      if(abs(present_mA) >= calMin_mA){
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
    DEBUG_SERIAL.print(F("POS=")); DEBUG_SERIAL.print(present_pos);
    DEBUG_SERIAL.print(F(" GOAL=")); DEBUG_SERIAL.print(goal_pos);
    DEBUG_SERIAL.print(F(" | CUR=")); DEBUG_SERIAL.print(present_mA);
    DEBUG_SERIAL.print(F("mA | estN=")); DEBUG_SERIAL.print(estN,2);
    DEBUG_SERIAL.print(F("N | target=")); DEBUG_SERIAL.print(targetForceN,1);
    DEBUG_SERIAL.print(F("N | ")); 
    DEBUG_SERIAL.print(nearGoal ? F("NEAR") : F("MOVING"));
    // 显示控制决策（带正负方向）
    float err = estN - targetForceN;
    DEBUG_SERIAL.print(F(" | err=")); DEBUG_SERIAL.print(err,2); DEBUG_SERIAL.print(F("N"));
    if(fabs(estN) < noLoadThreshN){
      DEBUG_SERIAL.print(F(" -> 无力,保持"));
    }else if(err < -hysteresisN){
      DEBUG_SERIAL.print(F(" -> 力<目标,正转(逆负载)"));
    }else if(err > hysteresisN){
      DEBUG_SERIAL.print(F(" -> 力>目标,反转(顺负载)"));
    }else{
      DEBUG_SERIAL.print(F(" -> 力≈目标,保持"));
    }
    DEBUG_SERIAL.println();
    lastPrint = millis();
  }

  // N==0: 自由跟随（尽量不产生反力，让位置随外力变化）
  if(holdMode){
    // 标定固定模式：保持 goal_pos 不变，仅用于观测电流
  }
  else if(targetForceN == 0){
    if(abs((int32_t)(goal_pos - present_pos)) > 2){
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
