/*
 * FreeRTOS V202212.00
 * [License text truncated...]
 *
 * https://www.FreeRTOS.org
 * https://github.com/FreeRTOS
 */

/******************************************************************************
 * Modified main.c: Integrated concurrency tasks (SensorTask & SecureNetworkTask)
 * plus real-time performance checks.
 * 
 * Threat Model (Condensed):
 *  1) Buffer Overflow: Use boundary checks in SecureNetworkTask.
 *  2) Race Condition: Use a mutex in SensorTask for shared data.
 *  3) DoS (CPU hog / RT violation): Keep tasks short, use priorities/timeouts,
 *     and now measure ticks to detect missed deadlines.
 *  4) Unauthorized Access: Not fully shown here; typically restrict debug or config.
 *****************************************************************************/

/* FreeRTOS includes. */
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

/* Standard includes. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>

/* TraceRecorder includes (if used). */
#include <trcRecorder.h>

/* Hardware setup for QEMU UART prints. */
#define UART0_ADDRESS         ( 0x40004000UL )
#define UART0_DATA            ( *( ( volatile uint32_t * ) ( UART0_ADDRESS + 0UL ) ) )
#define UART0_STATE           ( *( ( volatile uint32_t * ) ( UART0_ADDRESS + 4UL ) ) )
#define UART0_CTRL            ( *( ( volatile uint32_t * ) ( UART0_ADDRESS + 8UL ) ) )
#define UART0_BAUDDIV         ( *( ( volatile uint32_t * ) ( UART0_ADDRESS + 16UL ) ) )
#define TX_BUFFER_MASK        ( 1UL )

/* Forward declarations for local functions. */
static void prvUARTInit( void );
static void vSensorTask( void *pvParameters );
static void vSecureNetworkTask( void *pvParameters );

/* Shared resource for concurrency example. */
static uint16_t sSensorData = 0;
static SemaphoreHandle_t xSensorMutex = NULL;

/*-----------------------------------------------------------*/

int main( void )
{
#if ( configUSE_TRACE_FACILITY == 1 )
    xTraceInitialize();
    xTraceEnable( TRC_START );
    xTraceTimestampSetPeriod(configCPU_CLOCK_HZ / configTICK_RATE_HZ);
#endif

    /* Basic hardware init for UART so printf() goes to QEMU stdio. */
    prvUARTInit();

    printf("Starting FreeRTOS with integrated Sensor & Network tasks in main.c (with RT checks)\n");

    /* Create the SensorTask (lower priority). */
    xTaskCreate(vSensorTask, "SensorTask", configMINIMAL_STACK_SIZE + 100, NULL, 1, NULL);

    /* Create the SecureNetworkTask (higher priority). */
    xTaskCreate(vSecureNetworkTask, "NetTask", configMINIMAL_STACK_SIZE + 200, NULL, 2, NULL);

    /* Start the FreeRTOS scheduler. Should never return. */
    vTaskStartScheduler();

    /* If we ever break out of the scheduler, handle it here. */
    for( ;; );
    return 0;
}
/*-----------------------------------------------------------*
 *  Task & Function Definitions
 *-----------------------------------------------------------*/

/* Simulated hardware read for sensor. */
static uint16_t getSensorReadingFromHardware(void)
{
    static uint16_t fakeValue = 0;
    return fakeValue++;
}

/* SensorTask: concurrency (mutex) + real-time check. */
static void vSensorTask( void *pvParameters )
{
    (void) pvParameters;

    if (xSensorMutex == NULL)
    {
        xSensorMutex = xSemaphoreCreateMutex();
        if (xSensorMutex == NULL)
        {
            printf("Failed to create sensor mutex!\n");
            vTaskDelete(NULL);
            return;
        }
    }

    /* Let's run this task periodically every 100ms */
    const TickType_t xPeriod = pdMS_TO_TICKS(100);
    TickType_t xNextWakeTime = xTaskGetTickCount();

    for (;;)
    {
        /* Wait until the next cycle (100ms). */
        vTaskDelayUntil(&xNextWakeTime, xPeriod);

        /* Start timing for real-time check. */
        TickType_t startTime = xTaskGetTickCount();

        /* Lock shared data before updating. */
        if (xSemaphoreTake(xSensorMutex, pdMS_TO_TICKS(50)) == pdTRUE)
        {
            sSensorData = getSensorReadingFromHardware();
            xSemaphoreGive(xSensorMutex);
        }

        printf("SensorTask: sSensorData=%u\n", sSensorData);

        /* End timing and compute the difference. */
        TickType_t endTime = xTaskGetTickCount();
        TickType_t diff = endTime - startTime;

        /* If we took more than 5 ticks, consider that a missed 'soft deadline'. */
        if (diff > 5)
        {
            printf("SensorTask: MISSED DEADLINE (took %u ticks)\n", (unsigned)diff);
        }
        else
        {
            printf("SensorTask: took %u ticks\n", (unsigned)diff);
        }
    }
}

/* A mock function simulating network driver input. */
static int getIncomingPacket(uint8_t *buffer, size_t bufferSize)
{
    /* For demonstration, we might do:
       1) Zero bytes => no data
       2) Some random or test pattern
       In real code, read from a queue or QEMU-based UART, etc.
    */
    return 0;
}

/* Basic boundary checks + real-time measure in "SecureNetworkTask". */
static void handlePacket(const uint8_t *data, size_t length)
{
    if (length < 2) {
        return;
    }

    uint8_t packetType = data[0];
    uint8_t payloadLen = data[1];

    if (payloadLen > (length - 2)) {
        /* Avoid buffer overflow scenario. */
        return;
    }

    printf("NetTask: Got packetType=%u, payloadLen=%u\n", packetType, payloadLen);
}

static void vSecureNetworkTask( void *pvParameters )
{
    (void) pvParameters;

    static uint8_t netBuffer[256];

    /* Suppose NetTask runs every 10ms. */
    const TickType_t xPeriod = pdMS_TO_TICKS(10);
    TickType_t xNextWakeTime = xTaskGetTickCount();

    for (;;)
    {
        vTaskDelayUntil(&xNextWakeTime, xPeriod);

        /* Start timing. */
        TickType_t startTime = xTaskGetTickCount();

        int bytesRead = getIncomingPacket(netBuffer, sizeof(netBuffer));
        if (bytesRead > 0)
        {
            if ((size_t)bytesRead < sizeof(netBuffer))
                netBuffer[bytesRead] = '\0';
            else
                netBuffer[sizeof(netBuffer) - 1] = '\0';

            handlePacket(netBuffer, bytesRead);
        }

        /* End timing. */
        TickType_t endTime = xTaskGetTickCount();
        TickType_t diff = endTime - startTime;

        /* If we took > 5 ticks for a 10ms task, log a missed deadline. */
        if (diff > 5)
        {
            printf("NetTask: MISSED DEADLINE (took %u ticks)\n", (unsigned)diff);
        }
        else
        {
            printf("NetTask: took %u ticks\n", (unsigned)diff);
        }
    }
}

/*-----------------------------------------------------------*
 *  FreeRTOS Hook Implementations (same as before)
 *-----------------------------------------------------------*/
void vApplicationMallocFailedHook( void )
{
    printf( "\r\n\r\nMalloc failed\r\n" );
    portDISABLE_INTERRUPTS();
    for( ; ; );
}

void vApplicationIdleHook( void ) { }

void vApplicationStackOverflowHook( TaskHandle_t pxTask, char * pcTaskName )
{
    (void) pcTaskName;
    (void) pxTask;
    printf( "\r\n\r\nStack overflow in %s\r\n", pcTaskName );
    portDISABLE_INTERRUPTS();
    for( ; ; );
}

void vApplicationTickHook( void ) { }

void vApplicationDaemonTaskStartupHook( void )
{
#if ( configUSE_TRACE_FACILITY == 1 )
    xTraceEnable( TRC_START );
#endif
}

void vAssertCalled( const char * pcFileName, uint32_t ulLine )
{
    volatile uint32_t ulSetToNonZeroInDebuggerToContinue = 0;
    printf( "ASSERT! Line %d, file %s\r\n", ( int ) ulLine, pcFileName );
    taskENTER_CRITICAL();
    {
        while( ulSetToNonZeroInDebuggerToContinue == 0 )
        {
            __asm volatile ( "NOP" );
            __asm volatile ( "NOP" );
        }
    }
    taskEXIT_CRITICAL();
}

void vApplicationGetIdleTaskMemory( StaticTask_t ** ppxIdleTaskTCBBuffer,
                                    StackType_t ** ppxIdleTaskStackBuffer,
                                    uint32_t * pulIdleTaskStackSize )
{
    static StaticTask_t xIdleTaskTCB;
    static StackType_t uxIdleTaskStack[ configMINIMAL_STACK_SIZE ];

    *ppxIdleTaskTCBBuffer = &xIdleTaskTCB;
    *ppxIdleTaskStackBuffer = uxIdleTaskStack;
    *pulIdleTaskStackSize = configMINIMAL_STACK_SIZE;
}

void vApplicationGetTimerTaskMemory( StaticTask_t ** ppxTimerTaskTCBBuffer,
                                     StackType_t ** ppxTimerTaskStackBuffer,
                                     uint32_t * pulTimerTaskStackSize )
{
    static StaticTask_t xTimerTaskTCB;
    static StackType_t uxTimerTaskStack[ configTIMER_TASK_STACK_DEPTH ];

    *ppxTimerTaskTCBBuffer = &xTimerTaskTCB;
    *ppxTimerTaskStackBuffer = uxTimerTaskStack;
    *pulTimerTaskStackSize = configTIMER_TASK_STACK_DEPTH;
}

/* Basic UART init for QEMU stdio. */
static void prvUARTInit( void )
{
    UART0_BAUDDIV = 16;
    UART0_CTRL = 1;
}

int __write( int iFile, char * pcString, int iStringLength )
{
    (void) iFile;

    for( int iNextChar = 0; iNextChar < iStringLength; iNextChar++ )
    {
        while( ( UART0_STATE & TX_BUFFER_MASK ) != 0 ) { }
        UART0_DATA = *pcString++;
    }
    return iStringLength;
}

/* We do not expect calls to malloc() from the C library, so guard them. */
void * malloc( size_t size )
{
    ( void ) size;
    printf( "\r\n\r\nUnexpected call to malloc() - use pvPortMalloc()\r\n" );
    portDISABLE_INTERRUPTS();
    for( ; ; );
}
