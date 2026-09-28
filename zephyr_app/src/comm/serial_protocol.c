/**
 * Serial Protocol - Host-to-target communication protocol
 */

#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <string.h>
#include <stdio.h>

#include "serial_protocol.h"

#define CMD_BUFFER_SIZE 256

static const struct device *g_uart_dev = NULL;
static uint8_t cmd_buffer[CMD_BUFFER_SIZE];
static size_t cmd_pos = 0;
static void (*g_cmd_callback)(const char *cmd) = NULL;

/* Command opcodes */
#define CMD_PING           0x01
#define CMD_RUN_TEST       0x02
#define CMD_LIST_TESTS     0x03
#define CMD_GET_REPORT     0x04
#define CMD_GET_DEVICE_ID  0x05
#define CMD_RESET          0x06
#define CMD_ECHO           0xFE

/* Response codes */
#define RESP_OK            0x00
#define RESP_ERROR         0xFF
#define RESP_NOT_FOUND     0xFE
#define RESP_BUSY          0xFD

struct __packed serial_packet {
    uint8_t start;      /* 0xAA */
    uint8_t cmd;
    uint16_t length;
    uint8_t data[0];
    /* uint16_t crc16; */
};

void serial_protocol_init(const struct device *uart_dev, void (*cmd_callback)(const char *cmd))
{
    g_uart_dev = uart_dev;
    g_cmd_callback = cmd_callback;
    cmd_pos = 0;

    /* Enable UART RX interrupt */
    uart_irq_rx_enable(uart_dev);
}

/* UART interrupt handler */
void serial_uart_isr(const struct device *dev, void *user_data)
{
    ARG_UNUSED(user_data);

    while (uart_irq_update(dev) && uart_irq_rx_ready(dev)) {
        uint8_t byte;
        uart_fifo_read(dev, &byte, 1);

        /* Simple line-based protocol for shell compatibility */
        if (byte == '\n' || byte == '\r') {
            if (cmd_pos > 0) {
                cmd_buffer[cmd_pos] = '\0';
                if (g_cmd_callback) {
                    g_cmd_callback((char *)cmd_buffer);
                }
                cmd_pos = 0;
            }
        } else if (cmd_pos < CMD_BUFFER_SIZE - 1) {
            cmd_buffer[cmd_pos++] = byte;
        }
    }
}

void serial_send_response(uint8_t status, const char *data, size_t len)
{
    if (!g_uart_dev) return;

    char response[256];
    int resp_len = snprintf(response, sizeof(response), "> %02X ", status);
    if (data && len > 0) {
        memcpy(response + resp_len, data, len);
        resp_len += len;
    }
    response[resp_len++] = '\n';

    for (int i = 0; i < resp_len; i++) {
        uart_poll_out(g_uart_dev, response[i]);
    }
}

/* Binary protocol functions (for automated host) */
void serial_send_binary_packet(uint8_t cmd, const uint8_t *data, uint16_t length)
{
    if (!g_uart_dev) return;

    struct serial_packet pkt;
    pkt.start = 0xAA;
    pkt.cmd = cmd;
    pkt.length = length;

    /* Send header */
    uart_poll_out(g_uart_dev, pkt.start);
    uart_poll_out(g_uart_dev, pkt.cmd);
    uart_poll_out(g_uart_dev, pkt.length & 0xFF);
    uart_poll_out(g_uart_dev, (pkt.length >> 8) & 0xFF);

    /* Send data */
    for (uint16_t i = 0; i < length; i++) {
        uart_poll_out(g_uart_dev, data[i]);
    }

    /* TODO: Add CRC16 */
}