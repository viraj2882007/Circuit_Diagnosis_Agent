/**
 * Serial Protocol - Host-to-target communication protocol
 */

#ifndef SERIAL_PROTOCOL_H
#define SERIAL_PROTOCOL_H

#include <zephyr/kernel.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Initialize serial protocol handler */
void serial_protocol_init(const struct device *uart_dev,
                          void (*cmd_callback)(const char *cmd));

/* UART ISR - must be called from UART interrupt */
void serial_uart_isr(const struct device *dev, void *user_data);

/* Send response to host */
void serial_send_response(uint8_t status, const char *data, size_t len);

/* Binary protocol functions (for automated host) */
void serial_send_binary_packet(uint8_t cmd, const uint8_t *data, uint16_t length);

#ifdef __cplusplus
}
#endif

#endif /* SERIAL_PROTOCOL_H */