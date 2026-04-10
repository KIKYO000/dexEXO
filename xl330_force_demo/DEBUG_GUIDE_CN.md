DexEXO XL330 force-demo 调试指南（中文）

说明
----
此文档用于调试和验证 `xl330_force_demo` 固件（单舵机力控/触摸模式）。包含从上电检查、标定、自由跟随、主动寻触（SEEK）、触摸（TOUCH）到调参和常见问题的排查步骤。

前提
----
- Arduino Mega（或兼容）已连接到 XL330，舵机 ID=1。
- 串口工具（例如串口监视、平台IO串口监视器等）连接到主机，波特率 115200（用于 DEBUG 输出）。
- Dynamixel 总线 TX/RX 与电源连接正确，波特率 57600（固件 init 使用）。
- 在操作前确认机械安全，避免移动到限位或碰撞人手与其它设备。

快速检查清单
----
- 上电并打开串口：应看到日志包含：
  - PING ID 1 : OK
  - Operating Mode: 5
  - Torque Enable: 1
  - "DexEXO XL330 single-servo demo ready."
- 运行 TEST：确认舵机能正/反向移动，回到初始位置。
 - 说明：如果在编辑器里见到 “Serial1 未定义” 的提示，这是静态分析假警告；使用 Arduino 环境编译/烧录不会受影响。

启动与自检步骤
----
1) 打开串口并观察启动日志
   - 期望："PING ID 1 : OK"、Operating Mode 与 Torque Enable 为合理值。
2) 运行 TEST 命令：
   - 发送：TEST
   - 期望：正向 500 脉冲、负向 500 脉冲、回到起始；日志打印各步骤当前位置信息。
   - 如果移动异常：检查电源、ID、波特率；用 dxl_bridge 作为参照验证硬件。

标定(CAL)
----
目标：获取合理的 `kN_per_mA`（N = mA * kN_per_mA）

步骤：
1) 先看当前读数
   - 命令：STATUS
   - 期望：打印 present_cur(mA)、估算力 estN（用初始系数）
2) 如果施力较小，降低标定阈值
   - 命令：CALMIN:2（或 1）
3) 施力并在施力瞬间执行 STATUS(可多次观察)，确认 mA 的幅值和方向（正=被推，负=被拉）
4) 在施力保持时立即执行标定
   - 命令：CAL:1（假设当前施力为 +1N）或 CAL:-1（拉力）
   - 期望：提示检测到电流 X mA，并输出新的 kN_per_mA

常见问题：
- 标定失败提示电流太小：增大 CALMIN 或加大施力

自由跟随
----
模式 A（软自由）：
- 命令：N:0
- 行为：代码会使 GOAL 紧贴 PRESENT（阈值 2 tick），舵机会较轻地跟随外力，但仍有基本保持力。
- 验收：轻推舵盘能随外力移动，松手后舵机不会自发快速回跑。

模式 B（极轻、断电）：
- 命令：FREE:ON
- 行为：关闭扭矩（完全无源），适合感受最低阻力；恢复时用 FREE:OFF 或 N:非零/TOUCH:ON。
- 风险：FREE 状态下没有保持力，可能导致快速自由转动或坠落，使用前务必机械安全保障。

力追随基本规则验证
----
- 设定 N:1
- 观察 500ms 的周期打印
- 验证：
  - 当 estN < 1N：打印“力<目标,正转(逆负载)”并 goal_pos += stepPulse
  - 当 estN > 1N：打印“力>目标,反转(顺负载)”并 goal_pos -= stepPulse
  - 当 |estN - target| < HYS：打印“力≈目标,保持”
- 若在无载（|estN| < NLT）下无响应为预期（默认不主动寻触），可启用 SEEK

主动寻触（SEEK）
----
目的：当设定目标力但当前检测不到载荷（无力），SEEK 模式会主动小步前进尝试寻找接触并生成力。

使用场景：当你期望设备在没有外力时自动尝试驱动到接触点（例如靠近物体进行接触检测）。

命令：
- SEEK:ON / SEEK:OFF
 - SEEKMAX:<n> (默认 30，建议初次试验设 20~50)
- STEP:<p> 控制每步脉冲数

行为说明：
- 在 targetForceN != 0 且 |estN| < NLT 的情况下，如果 SEEK=ON 会按 err 的方向（estN - targetForceN）做小步进，每步计数 +1；达到 SEEKMAX 停止；产生可测电流（|estN| >= NLT）后清零计数并正常进入力控逻辑。

安全：SEEK 会主动移动，请先设置 SEEKMAX 小值并确保无障碍。

触摸模式（TOUCH）
----
- 基本命令：TOUCH:ON / TOUCH:OFF（进入/退出触摸）
- 两种增力模式及参数：
   - TMODE:RAMP（按时间线性增力，默认）
      - TRATE:<n> 线性增力速率（N/s），默认 0.5
      - TMAX:<N>  触摸上限，默认 10N
      - 用法示例：
         - N:0 → TMODE:RAMP → TRATE:0.5 → TMAX:10 → TOUCH:ON
   - TMODE:DISP（按位移线性增力）
      - TGAIN:<k> 位移-力增益（N/脉冲），默认 0.05
      - TMAX:<N>  触摸上限（建议 10N 起）
      - 用法示例：
         - N:0 → TMODE:DISP → TGAIN:0.05 → TMAX:10 → TOUCH:ON

行为：
- 进入 TOUCH 时会记录 position 与 baseN；默认 RAMP：target 会随时间线性增加直至 TMAX。
- DISP 模式下：沿触摸方向的位移正向投影增加目标力：target = baseN + disp * TGAIN，直至 TMAX。
- 触摸方向由当前电流方向或最近非零方向推断；进入 TOUCH 时会自动开启 SEEK（受 SEEKMAX 限制）。

调参与验证：
- 先设置 N:0 或 N:小正值
- TOUCH:ON，按方向推舵机，观察 targetForceN 随位移增加并受到 TMAX 限制

常见问题与排查
----
1) 串口日志乱码/中文乱码
   - 检查终端编码为 UTF-8，波特率 115200。
2) 无法 ping 舵机
   - 检查电源、通讯线、舵机 ID、波特率是否一致；用 `dxl_bridge` 验证硬件。
3) 标定后 estN 与直观不符
   - 确认 mA 的符号（STATUS 提示 正=被推，负=被拉）；如果方向反了，可手动 KN:<coef> 设负值。
4) SEEK 导致撞击或超出行程
   - 立即发送 SEEK:OFF；如必要发送 FREE:ON 并断电检查机械限位
5) 忽略小幅噪声导致的抖动
   - 提高 NLT（NLT:0.05~0.1）、增 HYS 或减小 STEP
 6) 编辑器报 “Serial1 未定义”
    - 这是静态分析假警告；用 Arduino IDE/CLI 或平台实际编译/烧录不会报错。
 7) 命令行后带注释导致 "Unknown cmd"
    - 目前解析器不支持行内注释；请将注释放到单独一行，命令行只保留指令本体。

方向校准（DIRREV / DIR）
----
目的：当你发现“力>目标”时的实际运动方向与“顺负载”的直觉不一致（可能因机械装配方向不同），可快速切换控制方向。

命令：
- DIRREV:ON / DIRREV:OFF   （开启/关闭方向反转）
- DIR:<+1|-1>               （直接设置控制方向；+1 默认，-1 反向）
- INFO                      （查看 controlDir 当前值）

说明：
- 控制律判断：err = estN - target；
  - err > HYS → 力>目标 → 沿“顺负载”方向走一步
  - err < -HYS → 力<目标 → 沿“逆负载”方向走一步
- 实际位置步进会乘以 controlDir（默认 +1）；若感觉与实际相反，请用 DIRREV:ON 切换。

建议的调参表（起始点）
----
- stepPulse = 2
- hysteresisN = 0.15
- noLoadThreshN (NLT) = 0.08
- calMin_mA = 2
- currentLimit_mA = 150
- touchGain_N_per_tick = 0.05
- TMODE = RAMP, TRATE = 0.5 N/s
- touchMaxN = 10
- seekMaxSteps = 30
- AUTOFREE = ON（N=0 且未触摸时自动扭矩关闭）
- controlDir = +1（若方向不合适，用 DIRREV 切换）

日志示例（关键片段）
----
[CAL] 检测到电流: 2 mA (被推)
[OK] kN_per_mA: 0.001000 -> 0.500000
    即: 2 mA = 1.00 N
[FREE] 扭矩关闭，自由跟随(完全无电)
[FREE] 扭矩开启，恢复控制
POS=18389 GOAL=18389 | CUR=0mA | estN=0.00N | target=1.0N | NEAR | err=-1.00N -> 无力,保持
SEEK:ON -> 会看见 GOAL 每次小幅变化，直至产生电流

安全与注意事项
----
- SEEK 与 FREE 两个命令会改变舵机对外力的响应，使用前请确保机械与人员安全。
- 标定时请避免短时峰值引入误标（尽量稳态下记录电流）。
- 如果长期运行（高频移动/大力），注意电机/驱动与供电发热和电流限制。

接下来
----
- 我可以把这份文件改为 README_CN.md（或 README_DEBUG.md）并提交到仓库，方便长期保存。
- 若你想，把具体运行时的串口日志（你贴的内容）发我，我可以针对那些输出给出更具体的参数调整建议。 
