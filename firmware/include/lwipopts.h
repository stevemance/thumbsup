#ifndef _LWIPOPTS_H
#define _LWIPOPTS_H

// Common lwIP options for ThumbsUp firmware
// Supports both WiFi (diagnostic mode) and minimal config for Bluetooth mode

// OS mode
#define NO_SYS                      1
#define MEM_ALIGNMENT               4

// Protocols
#define LWIP_RAW                    1
#define LWIP_UDP                    1
#define LWIP_TCP                    1
#define LWIP_ICMP                   1
#define LWIP_DHCP                   1
#define LWIP_DNS                    1
#define LWIP_IPV4                   1
#define LWIP_IPV6                   0

// Network interfaces
#define LWIP_NETIF_HOSTNAME         1
#define LWIP_NETIF_STATUS_CALLBACK  1
#define LWIP_NETIF_LINK_CALLBACK    1

// Socket/Netconn API (not needed, we use raw API)
#define LWIP_SOCKET                 0
#define LWIP_NETCONN                0

// Memory options
#define MEM_SIZE                    (16 * 1024)
#define MEMP_NUM_TCP_PCB           10
#define MEMP_NUM_TCP_PCB_LISTEN     5
#define MEMP_NUM_TCP_SEG           32
#define MEMP_NUM_PBUF              32

// Pbuf options
#define PBUF_POOL_SIZE             24
#define PBUF_POOL_BUFSIZE          1540

// TCP options
#define TCP_MSS                    1460
#define TCP_WND                    (4 * TCP_MSS)
#define TCP_SND_BUF                (4 * TCP_MSS)
#define TCP_SND_QUEUELEN           ((4 * TCP_SND_BUF) / TCP_MSS)
#define LWIP_TCP_KEEPALIVE         1

// DHCP options
#define LWIP_DHCP_CHECK_LINK_UP    1

// HTTP server support (for diagnostic mode)
#define LWIP_HTTPD                  1
#define LWIP_HTTPD_SUPPORT_POST     1
#define LWIP_HTTPD_SSI              1
#define LWIP_HTTPD_CGI              1
#define LWIP_HTTPD_DYNAMIC_HEADERS  1
#define HTTPD_MAX_RETRIES          10

// Checksum options (hardware offload on Pico W)
#define LWIP_CHECKSUM_CTRL_PER_NETIF 1

// Statistics options
#if defined(DEBUG_MODE) && DEBUG_MODE
#define LWIP_STATS                  1
#define LWIP_STATS_DISPLAY          1
#else
#define LWIP_STATS                  0
#endif

// Debug options
#if defined(DEBUG_MODE) && DEBUG_MODE
#define LWIP_DEBUG                  1
#define TCP_DEBUG                   LWIP_DBG_OFF
#define ETHARP_DEBUG                LWIP_DBG_OFF
#define PBUF_DEBUG                  LWIP_DBG_OFF
#define IP_DEBUG                    LWIP_DBG_OFF
#define TCPIP_DEBUG                 LWIP_DBG_OFF
#define DHCP_DEBUG                  LWIP_DBG_OFF
#define UDP_DEBUG                   LWIP_DBG_OFF
#endif

// Additional options for Pico W
#define LWIP_SINGLE_NETIF           0
#define LWIP_MULTICAST_PING         1
#define LWIP_BROADCAST_PING         1

// ARP options
#define LWIP_ARP                    1
#define ARP_TABLE_SIZE              10
#define ARP_QUEUEING                1
#define ETHARP_SUPPORT_STATIC_ENTRIES 1

#endif /* _LWIPOPTS_H */