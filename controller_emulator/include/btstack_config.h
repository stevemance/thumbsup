#ifndef BTSTACK_CONFIG_H
#define BTSTACK_CONFIG_H

// Port related features
#define HAVE_EMBEDDED_TIME_MS
#define HAVE_MALLOC
#define HAVE_ASSERT

// Enable classic Bluetooth for HID device mode
#ifndef ENABLE_CLASSIC
#define ENABLE_CLASSIC
#endif

// Optional logging
#define ENABLE_LOG_INFO
#define ENABLE_LOG_ERROR
#define ENABLE_PRINTF_HEXDUMP

// BTstack configuration. buffers, sizes, ...
#define HCI_OUTGOING_PRE_BUFFER_SIZE 4
#define HCI_ACL_PAYLOAD_SIZE (1691 + 4)
#define HCI_ACL_CHUNK_SIZE_ALIGNMENT 4

#define MAX_NR_HCI_CONNECTIONS 1
// SDP + HID control + HID interrupt can be open at once when a host connects to us.
#define MAX_NR_L2CAP_CHANNELS 4
// SDP (PSM 0x0001) + HID control (0x11) + HID interrupt (0x13).  With only 2 slots
// the HID control PSM silently fails to register and every host-initiated HID
// connection is refused (L2CAP result 0x0002 PSM not supported), so the robot
// could never reconnect to the emulator on its own.
#define MAX_NR_L2CAP_SERVICES 3
#define MAX_NR_BTSTACK_LINK_KEY_DB_MEMORY_ENTRIES 2

// Limit number of ACL buffers to avoid cyw43 shared bus overrun
#define MAX_NR_CONTROLLER_ACL_BUFFERS 3

// Enable HCI Controller to Host Flow Control
#define ENABLE_HCI_CONTROLLER_TO_HOST_FLOW_CONTROL
#define HCI_HOST_ACL_PACKET_LEN 1024
#define HCI_HOST_ACL_PACKET_NUM 3
#define HCI_HOST_SCO_PACKET_LEN 120
#define HCI_HOST_SCO_PACKET_NUM 3

// Link key storage in RAM
#define NVM_NUM_LINK_KEYS 8
#define NVM_NUM_DEVICE_DB_ENTRIES 2

#endif
