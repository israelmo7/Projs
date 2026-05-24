#ifndef PROTOCOL_H
#define PROTOCOL_H

/**
 * @file protocol.h
 * @brief Shared communication protocol definitions for the inductive link
 */

#include <stdint.h>

/* ============================================================
 * PROTOCOL CONSTANTS
 * ============================================================ */

/**
 * @brief Total strict size for a command packet (Stator -> Rotor)
 * Optimized for low-bandwidth, high-noise inductive Downlink.
 */
#define COMMAND_PACKET_TOTAL_SIZE   8

/**
 * @brief Maximum payload size for compressed Opus audio packets (Rotor -> Stator)
 * 64 bytes is ideal for typical 20ms/40ms Opus frames at low-to-medium bitrates.
 */
#define OPUS_PAYLOAD_MAX            64

/* ============================================================
 * PACKET TYPES
 * ============================================================ */

typedef enum {
    CMD_PKT_TYPE_RESERVED     = 0,
    CMD_PKT_TYPE_START_STREAM = 1,  ///< Start audio stream transmission
    CMD_PKT_TYPE_STOP_STREAM  = 2,  ///< Stop audio stream transmission
    CMD_PKT_TYPE_PLAY_NEXT    = 3,  ///< Play next track
    CMD_PKT_TYPE_PLAY_PREV    = 4,  ///< Play previous track
    CMD_PKT_TYPE_PING         = 5,  ///< Keep-alive / Link check
} cmd_packet_type_t;

typedef enum {
    AUDIO_PKT_TYPE_RESERVED   = 0,
    AUDIO_PKT_TYPE_OPUS_FRAME = 1,  ///< Compressed Opus audio frame
    AUDIO_PKT_TYPE_SYNC       = 2,  ///< Stream synchronization packet
    AUDIO_PKT_TYPE_STATUS     = 3,  ///< Rotor status (Battery-less voltage state, etc.)
} audio_packet_type_t;

/* ============================================================
 * SHARED STRUCTURES
 * ============================================================ */

/**
 * @brief Strict 8-Byte Command Packet (Stator -> Rotor)
 * Total size is exactly 8 bytes to minimize transmission time and air errors.
 */
typedef struct {
    uint8_t  preamble;       ///< Sync byte (e.g., 0xA5)
    uint8_t  type;           ///< cmd_packet_type_t
    uint8_t  payload[4];     ///< 4 bytes of raw parameters/data
    uint8_t  crc[2];         ///< CRC-16 Checksum
} __attribute__((packed)) command_packet_t;

/**
 * @brief Audio/Data Packet Structure (Rotor -> Stator)
 * Carries the compressed Opus stream over the Uplink (Load Modulation).
 */
typedef struct {
    uint8_t  preamble;       ///< Sync byte (e.g., 0x5A)
    uint8_t  type;           ///< audio_packet_type_t
    uint8_t  payload_len;    ///< Dynamic length of the Opus frame
    uint8_t  payload[OPUS_PAYLOAD_MAX];
    uint8_t  crc[2];         ///< CRC-16 Checksum
} __attribute__((packed)) audio_packet_t;

#endif /* PROTOCOL_H */