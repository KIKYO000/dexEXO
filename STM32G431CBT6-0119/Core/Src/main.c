/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "adc.h"
#include "dma.h"
#include "spi.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include <string.h>
#include <stdbool.h>

//#include "myiic.h" 

#include "mpu6050.h"
//#include "usmart.h"   
#include "inv_mpu.h"
#include "inv_mpu_dmp_motion_driver.h" 

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */

// ����DMA������ - ����2��ͨ����ÿ��ͨ���ɼ�10��
#define ADC_CHANNELS    4    // ͨ����
#define ADC_SAMPLES    1    // ÿ��ͨ����������
uint32_t ADC_DMA_Buffer[ADC_CHANNELS * ADC_SAMPLES];  // �ܳ��� = 2 * 10 = 20

uint8_t DMA_cov = 1;

uint16_t ADC_arrayBend[18];
uint16_t arrayBend[18];

/* ��ӡ���麯�� */
uint16_t CBD_arrayData1[64];   // ������ݻ�����
uint16_t CBD_arrayData2[64];
uint16_t CBD_arrayData3[64];
uint16_t CBD_arrayData4[64];
uint16_t CBD_arrayData5[64];

char SPI_NSS_flag = 1;

/* ͨ��״̬ */
#define TRIGGER_CMD 0x01
volatile uint8_t spiRxComplete = 0;
volatile uint8_t spiTxComplete = 0;
volatile uint8_t spiError = 0;

/* ���ݻ����� */
uint8_t SPI_RxData[130];
uint8_t txTrigger = TRIGGER_CMD;

/* ��Ч��ӡ������ */
uint8_t Bend_Buffer[640];

int16_t accel[3], gyro[3], angle[3];
float pitch, roll, yaw; 		//ŷ����
int16_t pitch_100, roll_100, yaw_100;

short aacx,aacy,aacz;		//���ٶȴ�����ԭʼ����
short gyrox,gyroy,gyroz;	//������ԭʼ����
short temp;					//�¶�	

const  char footer = 0x55;

int16_t SPI_time = 1000;
int16_t accel_base[3], gyro_base[3];

// ���巢�ͻ�����
#define TX_BUF_SIZE sizeof(accel) + sizeof(gyro) + sizeof(pitch_100) + sizeof(roll_100) + sizeof(yaw_100)  + sizeof(arrayBend) + sizeof(Bend_Buffer) + 4
uint8_t txBuffer[TX_BUF_SIZE]; // 4�ֽ�ͷ�� + ���� + 2�ֽ�CRC(��ѡ)

// ���������ݽṹ��
typedef struct {
    uint16_t  BLE_accel[3];
    uint16_t  BLE_gyro[3];
    uint16_t  BLE_angle[3];
    uint16_t  BLE_arrayBend[18];
    uint16_t BLE_arrayA1[32], BLE_arrayB1[32];
    uint16_t BLE_arrayA2[32], BLE_arrayB2[32];
    uint16_t BLE_arrayA3[32], BLE_arrayB3[32];
    uint16_t BLE_arrayA4[32], BLE_arrayB4[32];
    uint16_t BLE_arrayA5[32], BLE_arrayB5[32];
} SensorData_t;

SensorData_t sensor_data;

// USART2 DMA������ɱ�־
volatile uint8_t usart1TxComplete = 0;

// ��¼��������־״̬
static volatile bool log_active = false;
static uint32_t log_start_ms = 0;
static uint8_t uart_rx_byte = 0;
static char cmd_buf[16];
static uint8_t cmd_idx = 0;
static volatile bool cmd_ready = false;

void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart)
{
    if(huart->Instance == USART1)
    {
        usart1TxComplete = 0;
        HAL_GPIO_TogglePin(TP_SW_GPIO_Port,TP_SW_Pin);
    }
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART2) {
        char c = (char)uart_rx_byte;
        if (c == '\r' || c == '\n') {
            if (cmd_idx > 0) {
                cmd_buf[cmd_idx] = '\0';
                cmd_ready = true;
                cmd_idx = 0;
            }
        } else {
            if (cmd_idx < (sizeof(cmd_buf) - 1)) {
                cmd_buf[cmd_idx++] = c;
            }
        }
        HAL_UART_Receive_IT(&huart2, &uart_rx_byte, 1);
    }
}

/* SPI������ɻص� */
void HAL_SPI_TxCpltCallback(SPI_HandleTypeDef *hspi) {
    if(hspi->Instance == SPI1) {
        spiTxComplete = 1;
    }
}

void HAL_SPI_RxCpltCallback(SPI_HandleTypeDef *hspi) {
    if(hspi->Instance == SPI1) {
        spiRxComplete = 1;
    }
}

void HAL_SPI_ErrorCallback(SPI_HandleTypeDef *hspi) {
    if(hspi->Instance == SPI1) {
        spiError = 1;
    }
}


/* USER CODE BEGIN 4 */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
//    static unsigned char ledState = 0;
    if (htim == (&htim2))
    {
//        HAL_GPIO_TogglePin(TP_SW_GPIO_Port,TP_SW_Pin);
    }
}
/* USER CODE END 4 */

/* USER CODE BEGIN PV */

void Set_Bend_Address(uint8_t addr){
    	switch(addr)
		{
			case 0:  //Bend_X1 0 0Bend_W3 1  Bend_S1 2  0X03
			{
                HAL_GPIO_WritePin(BCT_AB_GPIO_Port, BCT_AB_Pin, GPIO_PIN_SET);  
                HAL_GPIO_WritePin(BCT_BB_GPIO_Port, BCT_BB_Pin, GPIO_PIN_SET);  
                HAL_GPIO_WritePin(BCT_CB_GPIO_Port, BCT_CB_Pin, GPIO_PIN_RESET);
                break;
			}
			case 1:  //Bend_X2 3  Bend_WZC 4  Bend_S2 5  0X00
			{
				HAL_GPIO_WritePin(BCT_AB_GPIO_Port, BCT_AB_Pin, GPIO_PIN_RESET);  
                HAL_GPIO_WritePin(BCT_BB_GPIO_Port, BCT_BB_Pin, GPIO_PIN_RESET);  
                HAL_GPIO_WritePin(BCT_CB_GPIO_Port, BCT_CB_Pin, GPIO_PIN_RESET);
                break;
			}
            case 2:  //Bend_X3 6  Bend_Z1 7  Bend_S3 8  0X01
			{
                HAL_GPIO_WritePin(BCT_AB_GPIO_Port, BCT_AB_Pin, GPIO_PIN_SET);  
                HAL_GPIO_WritePin(BCT_BB_GPIO_Port, BCT_BB_Pin, GPIO_PIN_RESET);  
                HAL_GPIO_WritePin(BCT_CB_GPIO_Port, BCT_CB_Pin, GPIO_PIN_RESET);
                break;
			}
			case 3:  //Bend_XWC 9  Bend_Z2 10  Bend_SDC 11  0X02
			{
				HAL_GPIO_WritePin(BCT_AB_GPIO_Port, BCT_AB_Pin, GPIO_PIN_RESET);  
                HAL_GPIO_WritePin(BCT_BB_GPIO_Port, BCT_BB_Pin, GPIO_PIN_SET);  
                HAL_GPIO_WritePin(BCT_CB_GPIO_Port, BCT_CB_Pin, GPIO_PIN_RESET);
                break;
			}
            case 4:  //Bend_W1 12  Bend_Z3 13  Bend_D1 14  0X04
			{
                HAL_GPIO_WritePin(BCT_AB_GPIO_Port, BCT_AB_Pin, GPIO_PIN_RESET);  
                HAL_GPIO_WritePin(BCT_BB_GPIO_Port, BCT_BB_Pin, GPIO_PIN_RESET);  
                HAL_GPIO_WritePin(BCT_CB_GPIO_Port, BCT_CB_Pin, GPIO_PIN_SET);
                break;
			}
			case 5:  //Bend_W2 15  Bend_ZSC 16  Bend_D2 17  0X06
			{
				HAL_GPIO_WritePin(BCT_AB_GPIO_Port, BCT_AB_Pin, GPIO_PIN_RESET);  
                HAL_GPIO_WritePin(BCT_BB_GPIO_Port, BCT_BB_Pin, GPIO_PIN_SET);  
                HAL_GPIO_WritePin(BCT_CB_GPIO_Port, BCT_CB_Pin, GPIO_PIN_SET);
                break;
			} 
		}
}

// ɨ��״̬
typedef enum {
    SCAN_IDLE,
    SCAN_SETUP,
    SCAN_WAIT_ADC,
    SCAN_COMPLETE
} ScanState_t;

volatile ScanState_t scanState = SCAN_SETUP;
uint8_t current_Bend = 0;
uint8_t current_Bend1 = 0;
uint8_t current_Bend2 = 0;
uint8_t current_Bend3 = 0;

uint16_t ADC_DMA_Buffer1 = 0;
uint16_t ADC_DMA_Buffer2 = 0;
uint16_t ADC_DMA_Buffer3 = 0;
// ɨ��״̬������
void ProcessResistorScan(void) {
    switch (scanState) {
        case SCAN_SETUP:
            // �������е�ַ
            Set_Bend_Address(current_Bend);
            
            // �ɼ�����
            HAL_GPIO_WritePin(BCT_ENB_GPIO_Port, BCT_ENB_Pin, GPIO_PIN_RESET);
            
//            HAL_Delay(1);
//            if(DMA_cov == 1)scanState = SCAN_SETUP;
//            else if(DMA_cov == 0)scanState = SCAN_WAIT_ADC;
        if(DMA_cov == 0)
        {
            DMA_cov = 1;
            scanState = SCAN_WAIT_ADC;
        }
        else scanState = SCAN_SETUP;
            
        break;
        
        case SCAN_WAIT_ADC:
            
            current_Bend1 = current_Bend;
            current_Bend2 = current_Bend + 6;
            current_Bend3 = current_Bend + 12;
        
                
            ADC_arrayBend[current_Bend1] =  ADC_DMA_Buffer[0];
            ADC_arrayBend[current_Bend2] =  ADC_DMA_Buffer[2];
            ADC_arrayBend[current_Bend3] =  ADC_DMA_Buffer[1];
       
            // ��������
            HAL_GPIO_WritePin(BCT_ENB_GPIO_Port, BCT_ENB_Pin, GPIO_PIN_SET); // ����
            
            // �ƶ�����һ����
            current_Bend++;
            
            if (current_Bend >= 6) {
                current_Bend = 0;
                for(int i = 0; i < 18; i ++)
                {
//                    if(ADC_arrayBend[i] < 2700)ADC_arrayBend[i] = 2700;
//                    sensor_data.BLE_arrayBend[i] = (ADC_arrayBend[i] - 2700) / 10;
                    sensor_data.BLE_arrayBend[i] = ADC_arrayBend[i];
                    
                }
//                scanState = SCAN_COMPLETE;
//                print_Bend(arrayBend);
//                scanState = SCAN_SETUP;
            } 
//                Set_Bend_Address(current_Bend);
                scanState = SCAN_SETUP;
            break;
            
        default:
            break;
    }
}

// ����NSS��ַ
void SetNSSAddress(uint8_t addr) {
  HAL_GPIO_WritePin(SPI_S1_GPIO_Port, SPI_S1_Pin, GPIO_PIN_SET); // S1
  HAL_GPIO_WritePin(SPI_S2_GPIO_Port, SPI_S2_Pin, GPIO_PIN_SET); // S2
  HAL_GPIO_WritePin(SPI_S3_GPIO_Port, SPI_S3_Pin, GPIO_PIN_SET); // S3
  HAL_GPIO_WritePin(SPI_S4_GPIO_Port, SPI_S4_Pin, GPIO_PIN_SET); // S4
  HAL_GPIO_WritePin(SPI_S5_GPIO_Port, SPI_S5_Pin, GPIO_PIN_SET); // S5
  switch(addr)
  {
       case 1:
       {
          HAL_GPIO_WritePin(SPI_S1_GPIO_Port, SPI_S1_Pin, GPIO_PIN_RESET); // S1
          break;
       }
       case 2:
       {
          HAL_GPIO_WritePin(SPI_S2_GPIO_Port, SPI_S2_Pin, GPIO_PIN_RESET); // S2
          break;
       }
       case 3:
       {
          HAL_GPIO_WritePin(SPI_S3_GPIO_Port, SPI_S3_Pin, GPIO_PIN_RESET); // S3
          break;
       }
       case 4:
       {
          HAL_GPIO_WritePin(SPI_S4_GPIO_Port, SPI_S4_Pin, GPIO_PIN_RESET); // S4
          break;
       }
       case 5:
       {
          HAL_GPIO_WritePin(SPI_S5_GPIO_Port, SPI_S5_Pin, GPIO_PIN_RESET); // S5
          break;
       }
       default:
          break;
  }
}

void SPI_Communication(void)
{

            SetNSSAddress(SPI_NSS_flag);
            HAL_Delay(100);
            memset(SPI_RxData, 0, sizeof(SPI_RxData));
            HAL_StatusTypeDef status = HAL_SPI_Receive(&hspi1, SPI_RxData, 130, 100);
            
            if (status == HAL_OK) {
                if(SPI_RxData[0] == 0xA1 && SPI_RxData[129] == 0x1A) {
                    memcpy(sensor_data.BLE_arrayA1, SPI_RxData + 1, 64);
                    memcpy(sensor_data.BLE_arrayB1, SPI_RxData + 65, 64);
                }
                if(SPI_RxData[0] == 0xA2 && SPI_RxData[129] == 0x2A) {
                    memcpy(sensor_data.BLE_arrayA2, SPI_RxData + 1, 64);
                    memcpy(sensor_data.BLE_arrayB2, SPI_RxData + 65, 64);
                }
                if(SPI_RxData[0] == 0xA3 && SPI_RxData[129] == 0x3A) {
                    memcpy(sensor_data.BLE_arrayA3, SPI_RxData + 1, 64);
                    memcpy(sensor_data.BLE_arrayB3, SPI_RxData + 65, 64);
                }
                if(SPI_RxData[0] == 0xA4 && SPI_RxData[129] == 0x4A) {
                    memcpy(sensor_data.BLE_arrayA4, SPI_RxData + 1, 64);
                    memcpy(sensor_data.BLE_arrayB4, SPI_RxData + 65, 64);
                }
                if(SPI_RxData[0] == 0xA5 && SPI_RxData[129] == 0x5A) {
                    memcpy(sensor_data.BLE_arrayA5, SPI_RxData + 1, 64);
                    memcpy(sensor_data.BLE_arrayB5, SPI_RxData + 65, 64);
                }
                SPI_NSS_flag ++;
                SetNSSAddress(0);
            }

            if(SPI_NSS_flag == 6)SPI_NSS_flag = 1;

            
            if(spiError) {
                const char *errorMsg = "SPI Error! Reinitializing...\r\n";
                HAL_UART_Transmit(&huart2, (uint8_t*)errorMsg, strlen(errorMsg), 100);
                
                HAL_SPI_DeInit(&hspi1);
                MX_SPI1_Init();
                spiError = 0;
            }
}

#define JSON_BUFFER_SIZE 2048
static char json_buffer[JSON_BUFFER_SIZE];

// ����������������ת��ΪJSON�����ַ���
static int array_to_json(char* buffer, uint16_t* array, int size) {
    int pos = 0;
    pos += sprintf(buffer + pos, "[");
    
    for(int i = 0; i < size; i++) {
        pos += sprintf(buffer + pos, "%u", array[i]);
        if(i < size - 1) {
            pos += sprintf(buffer + pos, ",");
        }
    }
    pos += sprintf(buffer + pos, "]");
    return pos;
}

// ��ADCֵת��Ϊѹ��(N)
// V = AD/4096*3.3
// R = (45.3*V + 7.0215) / (4.795 - V)   (R��λ: K��)
// �ֶ����ԣ�ʹ���̼ұ궨��(1/R �� F)
static const float FORCE_F_KG_TABLE[10] = {
    0.5f, 1.0f, 1.5f, 2.0f, 2.5f, 3.0f, 3.5f, 4.0f, 4.5f, 5.0f
};
static const float INV_R_TABLE[10] = {
    0.011111f, 0.022222f, 0.038462f, 0.058824f, 0.083333f,
    0.111111f, 0.136986f, 0.166667f, 0.192308f, 0.222222f
};

static void ad_to_params(uint16_t ad, float* v, float* r, float* inv_r)
{
    float vv = (float)ad * 3.3f / 4096.0f;
    // �����ĸΪ0��ֵ
    if (vv >= 4.795f) {
        vv = 4.794f;
    }

    float rr = (45.3f * vv + 7.0215f) / (4.795f - vv); // K��
    float inv = 0.0f;
    if (rr > 0.0f) {
        inv = 1.0f / rr;
    }

    if (v) {
        *v = vv;
    }
    if (r) {
        *r = rr;
    }
    if (inv_r) {
        *inv_r = inv;
    }
}

static float force_from_inv_r(float inv_r)
{
    // �ֶ����Բ�ֵ����F(kg)
    float f_kg_raw = FORCE_F_KG_TABLE[0];
    if (inv_r <= INV_R_TABLE[0]) {
        f_kg_raw = FORCE_F_KG_TABLE[0];
    } else if (inv_r >= INV_R_TABLE[9]) {
        f_kg_raw = FORCE_F_KG_TABLE[9];
    } else {
        for (int i = 0; i < 9; i++) {
            float x0 = INV_R_TABLE[i];
            float x1 = INV_R_TABLE[i + 1];
            if (inv_r >= x0 && inv_r <= x1) {
                float y0 = FORCE_F_KG_TABLE[i];
                float y1 = FORCE_F_KG_TABLE[i + 1];
                float t = (inv_r - x0) / (x1 - x0);
                f_kg_raw = y0 + t * (y1 - y0);
                break;
            }
        }
    }

    float f_kg = f_kg_raw;
    float f = f_kg * 9.80665f; // N
    if (f < 0.0f) {
        f = 0.0f;
    }
    return f;
}

// ���ʹ��������ݵ�JSON��ʽ
void send_sensor_data_json(SensorData_t* data) {
    int pos = 0;
    
    // ��ʼ����JSON
    pos += sprintf(json_buffer + pos, "{\n");
    
//    // ����������
//    pos += sprintf(json_buffer + pos, "  \"gyro\": {\n");
//    pos += sprintf(json_buffer + pos, "    \"accel\": [%u, %u, %u],\n", 
//                  data->BLE_accel[0], data->BLE_accel[1], data->BLE_accel[2]);
//    pos += sprintf(json_buffer + pos, "    \"gyro\": [%u, %u, %u],\n", 
//                  data->BLE_gyro[0], data->BLE_gyro[1], data->BLE_gyro[2]);
//    pos += sprintf(json_buffer + pos, "    \"angle\": [%u, %u, %u]\n", 
//                  data->BLE_angle[0], data->BLE_angle[1], data->BLE_angle[2]);
//    pos += sprintf(json_buffer + pos, "  },\n");
//    
    // ��������������(��λ: N) - �����ԭ����һ·
    pos += sprintf(json_buffer + pos, "  \"touch_sensors\": [");
    {
        uint16_t ad = data->BLE_arrayBend[17];
        float v = 0.0f;
        float r = 0.0f;
        float inv_r = 0.0f;
        ad_to_params(ad, &v, &r, &inv_r);
        float force = force_from_inv_r(inv_r);
        pos += sprintf(json_buffer + pos, "%.3f", force);
    }
    pos += sprintf(json_buffer + pos, "],\n");

    // ��ӡAD, V, R, 1/R
    {
        uint16_t ad = data->BLE_arrayBend[17];
        float v = 0.0f;
        float r = 0.0f;
        float inv_r = 0.0f;
        ad_to_params(ad, &v, &r, &inv_r);
        pos += sprintf(json_buffer + pos,
                       "  \"touch_debug\": {\"ad\": %u, \"v\": %.4f, \"r\": %.4f, \"inv_r\": %.6f},\n",
                       ad, v, r, inv_r);
    }
    
//    // ��������������
//    pos += sprintf(json_buffer + pos, "  \"tactile\": {\n");
//    
//    // ��һ�鴥��������
//    pos += sprintf(json_buffer + pos, "    \"group1\": {\n");
//    pos += sprintf(json_buffer + pos, "      \"A1\": ");
//    pos += array_to_json(json_buffer + pos, data->BLE_arrayA1, 32);
//    pos += sprintf(json_buffer + pos, ",\n");
//    pos += sprintf(json_buffer + pos, "      \"B1\": ");
//    pos += array_to_json(json_buffer + pos, data->BLE_arrayB1, 32);
//    pos += sprintf(json_buffer + pos, "\n");
//    pos += sprintf(json_buffer + pos, "    },\n");
//    
//    // �ڶ��鴥��������
//    pos += sprintf(json_buffer + pos, "    \"group2\": {\n");
//    pos += sprintf(json_buffer + pos, "      \"A2\": ");
//    pos += array_to_json(json_buffer + pos, data->BLE_arrayA2, 32);
//    pos += sprintf(json_buffer + pos, ",\n");
//    pos += sprintf(json_buffer + pos, "      \"B2\": ");
//    pos += array_to_json(json_buffer + pos, data->BLE_arrayB2, 32);
//    pos += sprintf(json_buffer + pos, "\n");
//    pos += sprintf(json_buffer + pos, "    },\n");
//    
//    // �����鴥��������
//    pos += sprintf(json_buffer + pos, "    \"group3\": {\n");
//    pos += sprintf(json_buffer + pos, "      \"A3\": ");
//    pos += array_to_json(json_buffer + pos, data->BLE_arrayA3, 32);
//    pos += sprintf(json_buffer + pos, ",\n");
//    pos += sprintf(json_buffer + pos, "      \"B3\": ");
//    pos += array_to_json(json_buffer + pos, data->BLE_arrayB3, 32);
//    pos += sprintf(json_buffer + pos, "\n");
//    pos += sprintf(json_buffer + pos, "    },\n");
//    
//    // �����鴥��������
//    pos += sprintf(json_buffer + pos, "    \"group4\": {\n");
//    pos += sprintf(json_buffer + pos, "      \"A4\": ");
//    pos += array_to_json(json_buffer + pos, data->BLE_arrayA4, 32);
//    pos += sprintf(json_buffer + pos, ",\n");
//    pos += sprintf(json_buffer + pos, "      \"B4\": ");
//    pos += array_to_json(json_buffer + pos, data->BLE_arrayB4, 32);
//    pos += sprintf(json_buffer + pos, "\n");
//    pos += sprintf(json_buffer + pos, "    },\n");
//    
//    // �����鴥��������
//    pos += sprintf(json_buffer + pos, "    \"group5\": {\n");
//    pos += sprintf(json_buffer + pos, "      \"A5\": ");
//    pos += array_to_json(json_buffer + pos, data->BLE_arrayA5, 32);
//    pos += sprintf(json_buffer + pos, ",\n");
//    pos += sprintf(json_buffer + pos, "      \"B5\": ");
//    pos += array_to_json(json_buffer + pos, data->BLE_arrayB5, 32);
//    pos += sprintf(json_buffer + pos, "\n");
//    pos += sprintf(json_buffer + pos, "    }\n");
//    
//    pos += sprintf(json_buffer + pos, "  }\n");
//    pos += sprintf(json_buffer + pos, "}\n");
    
    // ͨ��DMA����JSON���ݣ���������
    HAL_UART_Transmit_DMA(&huart2, (uint8_t*)json_buffer, pos);
    HAL_UART_Transmit_DMA(&huart1, (uint8_t*)json_buffer, pos);
    // ����ʹ��������ʽ���ͣ������ã�
    // HAL_UART_Transmit(&huart1, (uint8_t*)json_buffer, pos, HAL_MAX_DELAY);
}

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
  /* USER CODE BEGIN 1 */
    

  char IMU_valuesstr[1000];
//    float BAT_VEL = 0;

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */
  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_ADC1_Init();
  MX_SPI1_Init();
  MX_USART1_UART_Init();
  MX_USART2_UART_Init();
    HAL_UART_Receive_IT(&huart2, &uart_rx_byte, 1);
//  MX_TIM2_Init();
  /* USER CODE BEGIN 2 */

//    HAL_SPI_TransmitReceive(&hspi1, rxData, rxData, 1, 10);
    
    MPU_Init();						//��ʼ��MPU6050
    while(mpu_dmp_init());
     
    HAL_GPIO_WritePin(BAT_ADC_SW_GPIO_Port, BAT_ADC_SW_Pin, GPIO_PIN_SET);//��ȡ��ص�ѹ����
  
    HAL_GPIO_WritePin(POWER_SW_GPIO_Port, POWER_SW_Pin, GPIO_PIN_SET);//�����Դ����
    
    HAL_ADCEx_Calibration_Start(&hadc1, ADC_SINGLE_ENDED);
    HAL_ADC_Start_DMA(&hadc1, (uint32_t*)ADC_DMA_Buffer, 6);

    SetNSSAddress(0);
//    HAL_TIM_Base_Start_IT(&htim2);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */

//      BAT_VEL = (float)ADC_DMA_Buffer[3]*3.02*2.034/4096;  //��ص�ѹ
//      sprintf(BAT_valuesstr,"%.2f \r\n",BAT_VEL);
//      HAL_UART_Transmit(&huart2, (uint8_t *)BAT_valuesstr, 20, 0xffff);


//        if(mpu_dmp_get_data(&pitch,&roll,&yaw) == 0)
//        {
////            HAL_UART_Transmit(&huart1, (uint8_t *)IMU_valuesstr, sizeof(IMU_valuesstr), 0xffff);
////            sprintf(IMU_valuesstr,"tt: %d\r\n",
////                                mpu_dmp_get_data(&pitch,&roll,&yaw));
//            if(pitch < 0)sensor_data.BLE_angle[0] = (pitch+360)*100 ;
//            else sensor_data.BLE_angle[0] = pitch*100 ;
//            if(roll  < 0)sensor_data.BLE_angle[1] = (roll +360)*100 ;
//            else sensor_data.BLE_angle[1]  = roll*100;
//            if(yaw   < 0)sensor_data.BLE_angle[2] = (yaw  +360)*100 ;
//            else sensor_data.BLE_angle[2]   = yaw*100;
//        }
////        temp=MPU_Get_Temperature();	//�õ��¶�ֵ
//        MPU_Get_Accelerometer(&sensor_data.BLE_accel[0],&sensor_data.BLE_accel[1],&sensor_data.BLE_accel[2]);	//�õ����ٶȴ���������
//        MPU_Get_Gyroscope(&sensor_data.BLE_gyro[0],&sensor_data.BLE_gyro[1],&sensor_data.BLE_gyro[2]);	//�õ�����������

//        sprintf(IMU_valuesstr,"tt:temp��%d aacx:%d aacy:%d aacz:%d gyrox:%d gyroy:%d gyroz:%d pitch:%.2f roll:%.2f yaw:%.2f \r\n",
//                                temp, aacx, aacy, aacz, gyrox, gyroy, gyroz, pitch, roll, yaw);

        if (cmd_ready) {
            cmd_ready = false;
            if (strcmp(cmd_buf, "record") == 0) {
                log_active = true;
                log_start_ms = HAL_GetTick();
                const char *hdr = "time_ms,ad\r\n";
                HAL_UART_Transmit(&huart2, (uint8_t*)hdr, strlen(hdr), 100);
            } else if (strcmp(cmd_buf, "over") == 0) {
                log_active = false;
                const char *end = "OVER\r\n";
                HAL_UART_Transmit(&huart2, (uint8_t*)end, strlen(end), 100);
            }
        }

        if (log_active) {
            uint32_t t_ms = HAL_GetTick() - log_start_ms;
            uint16_t ad = sensor_data.BLE_arrayBend[17];
            char line[32];
            int n = snprintf(line, sizeof(line), "%lu,%u\r\n", (unsigned long)t_ms, ad);
            HAL_UART_Transmit(&huart2, (uint8_t*)line, n, 100);
        } else {
            send_sensor_data_json(&sensor_data);
        }

        ProcessResistorScan();
        
//        SPI_Communication();
//        
//        if(usart1TxComplete == 0)
//        {
////            Send_Combined_Data();
//            usart1TxComplete = 1;
//        }
//        HAL_Delay(1);

  }
 
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = RCC_PLLM_DIV2;
  RCC_OscInitStruct.PLL.PLLN = 28;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
  RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_3) != HAL_OK)
  {
    Error_Handler();
  }
}

///* USER CODE BEGIN 4 */
//void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
//{
////    static unsigned char ledState = 0;
//    if (htim == (&htim2))
//    {
////        HAL_GPIO_TogglePin(TP_SW_GPIO_Port,TP_SW_Pin);
//    }
//}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */