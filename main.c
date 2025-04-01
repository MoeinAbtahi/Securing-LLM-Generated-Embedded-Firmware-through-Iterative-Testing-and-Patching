/*
 * FreeRTOS V202212.00
 * [License text truncated...]
 *
 * https://www.FreeRTOS.org
 * https://github.com/FreeRTOS
 */

#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"

#include <stdio.h>
#include <string.h>
#include <stdint.h>

/* Added for random delay logic. */
#include <stdlib.h>

/* TraceRecorder includes (if used). */
#include <trcRecorder.h>

/* Hardware setup for QEMU UART prints. */
#define UART0_ADDRESS         ( 0x40004000UL )
#define UART0_DATA            ( *( ( volatile uint32_t * ) ( UART0_ADDRESS + 0UL ) ) )
#define UART0_STATE           ( *( ( volatile uint32_t * ) ( UART0_ADDRESS + 4UL ) ) )
#define UART0_CTRL            ( *( ( volatile uint32_t * ) ( UART0_ADDRESS + 8UL ) ) )
#define UART0_BAUDDIV         ( *( ( volatile uint32_t * ) ( UART0_ADDRESS + 16UL ) ) )
#define TX_BUFFER_MASK        ( 1UL )

static void prvUARTInit( void );
static void vSensorTask( void *pvParameters );
static void vSecureNetworkTask( void *pvParameters );

/* Shared resource for concurrency example. */
static uint16_t sSensorData = 0;
static SemaphoreHandle_t xSensorMutex = NULL;

int main( void )
{
#if ( configUSE_TRACE_FACILITY == 1 )
    xTraceInitialize();
    xTraceEnable( TRC_START );
    xTraceTimestampSetPeriod(configCPU_CLOCK_HZ / configTICK_RATE_HZ);
#endif

    /* Initialize random seed (if desired). In real embedded code, you might do a fixed seed. */
    srand(1);  /* or srand(time(NULL)); if you have time() available */

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

/* Minimal check to see if a packet looks like MQTT. */
static int isMqttPacket(const uint8_t *data, size_t length)
{
    /* A valid MQTT Control Packet has at least 2 bytes:
       - byte[0] = Control Packet type/flags
       - byte[1..n] = Remaining length (using variable-length encoding).
     */
    if (length < 2)
    {
        return 0;
    }

    /* Extract control packet type from bits 7..4.  MQTT valid range is 1..14. */
    uint8_t controlPacketType = (data[0] & 0xF0) >> 4;
    if (controlPacketType < 1 || controlPacketType > 14)
    {
        return 0; /* Not a valid MQTT type. */
    }

    /* Now parse the variable-length "Remaining Length" field. */
    size_t offset = 1;        /* Start after the first byte (Control Packet type). */
    size_t remainingLength = 0;
    int shift = 0;

    while (1)
    {
        /* If we've run out of buffer before finishing "Remaining Length", it's invalid. */
        if (offset >= length)
        {
            return 0; 
        }

        uint8_t encodedByte = data[offset++];
        remainingLength += (encodedByte & 0x7F) << shift;
        shift += 7;

        /* If MSB is 0, we finished reading the Remaining Length. */
        if ((encodedByte & 0x80) == 0)
        {
            break;
        }

        /* MQTT spec says Remaining Length can be up to 4 bytes. If we exceed that, error out. */
        if (shift > 28)
        {
            return 0;  /* Malformed (very large) Remaining Length. */
        }
    }

    /* We’ve parsed the "Remaining Length". Check if the buffer has enough data. */
    if (remainingLength > (length - offset))
    {
        return 0;  /* The stated Remaining Length doesn't fit in the provided packet data. */
    }

    /* If we got here, it’s minimally valid for MQTT. */
    return 1;
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

    /* Periodic task: every 100ms => 10 times/second => ~50 times in 5 seconds. */
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

        /* -------------------------------
         *  Randomly force extra delay ~1/50 chance
         *  => ~once every 5 seconds for SensorTask
         * ------------------------------- */
        if ((rand() % 50) == 0)
        {
            /* Enough delay to exceed a 5-tick threshold. */
            vTaskDelay(pdMS_TO_TICKS(60));  // ~6 ticks at 10 ms/tick
        }

        /* End timing and compute the difference. */
        TickType_t endTime = xTaskGetTickCount();
        TickType_t diff = endTime - startTime;

        /* If we took more than 5 ticks, consider that a missed deadline. */
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
    // Example: Fake an MQTT CONNECT packet of length 14 just for testing
    // (Control packet type = 1 (CONNECT), Remaining Length = 12)
    if (bufferSize >= 14)
    {
        buffer[0] = 0x10; // bits 7..4 = 1 (CONNECT)
        buffer[1] = 12;   // Remaining length
        // Fill the rest with dummy payload...
        for (int i = 2; i < 14; i++)
        {
            buffer[i] = (uint8_t)i;
        }
        return 14; // bytes read
    }
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

    /* Existing logging. */
    printf("NetTask: Got packetType=%u, payloadLen=%u\n", packetType, payloadLen);

    /* --- MQTT MINIMAL CHECK ADDITION --- */
    if (isMqttPacket(data, length))
    {
        printf("NetTask: Detected a minimal valid MQTT packet!\n");
        /* Optionally do deeper MQTT processing here... */
    }
    else
    {
        /* Non-MQTT or invalid structure. Handle as usual or ignore. */
    }
}


static void vSecureNetworkTask( void *pvParameters )
{
    (void) pvParameters;

    static uint8_t netBuffer[256];

    /* NetTask runs every 10ms => 100 times/second => ~500 times in 5 seconds. */
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
            {
                netBuffer[bytesRead] = '\0';
            }
            else
            {
                netBuffer[sizeof(netBuffer) - 1] = '\0';
            }

            handlePacket(netBuffer, bytesRead);
        }

        /* Random delay to simulate missed-deadline scenario. */
        if ((rand() % 500) == 0)
        {
            vTaskDelay(pdMS_TO_TICKS(60)); // ~6 ticks
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
 *  FreeRTOS Hook Implementations
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

void SampleOverflowIssue(int x) // Unused function to detect
{
    (void)x;
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

void *malloc(size_t size)
{
    /* Wrap library malloc to FreeRTOS allocation. */
    return pvPortMalloc(size);
}

void free(void *ptr)
{
    /* Likewise wrap free to FreeRTOS deallocation. */
    vPortFree(ptr);
}
