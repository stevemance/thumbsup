// Simple DHCP server for Pico W AP mode
#include <stdio.h>
#include <string.h>
#include <lwip/udp.h>
#include <lwip/dhcp.h>

#define DHCP_SERVER_PORT 67
#define DHCP_CLIENT_PORT 68

// DHCP message types
#define DHCP_DISCOVER 1
#define DHCP_OFFER    2
#define DHCP_REQUEST  3
#define DHCP_ACK      5
#define DHCP_NAK      6

// DHCP options
#define DHCP_OPTION_MESSAGE_TYPE 53
#define DHCP_OPTION_SERVER_ID    54
#define DHCP_OPTION_LEASE_TIME   51
#define DHCP_OPTION_SUBNET_MASK  1
#define DHCP_OPTION_ROUTER       3
#define DHCP_OPTION_DNS_SERVER   6
#define DHCP_OPTION_END          255

typedef struct {
    uint8_t op;
    uint8_t htype;
    uint8_t hlen;
    uint8_t hops;
    uint32_t xid;
    uint16_t secs;
    uint16_t flags;
    uint32_t ciaddr;
    uint32_t yiaddr;
    uint32_t siaddr;
    uint32_t giaddr;
    uint8_t chaddr[16];
    uint8_t sname[64];
    uint8_t file[128];
    uint32_t magic_cookie;
    uint8_t options[312];
} dhcp_msg_t;

static struct udp_pcb *dhcp_pcb = NULL;
static ip4_addr_t server_ip;
static ip4_addr_t subnet_mask;
static uint8_t next_client_ip = 2;  // Start at .2

// Simple lease table (MAC -> IP mapping)
#define MAX_LEASES 10
typedef struct {
    uint8_t mac[6];
    uint8_t ip;
    bool active;
} dhcp_lease_t;
static dhcp_lease_t leases[MAX_LEASES] = {0};

static void dhcp_server_recv(void *arg, struct udp_pcb *pcb, struct pbuf *p,
                            const ip_addr_t *addr, u16_t port) {
    printf("\n=== DHCP PACKET RECEIVED ===\n");
    printf("  From port: %d\n", port);
    printf("  Size: %d bytes\n", p->len);
    printf("  pbuf tot_len: %d\n", p->tot_len);

    // Minimum DHCP message size (without options)
    const size_t min_dhcp_size = 236;  // Fixed header without options
    if (p->tot_len < min_dhcp_size) {
        printf("DHCP: ERROR - Packet too small (%d bytes, need at least %d)\n", p->tot_len, min_dhcp_size);
        pbuf_free(p);
        return;
    }

    // Make sure payload is accessible
    if (!p->payload) {
        printf("DHCP: ERROR - No payload pointer!\n");
        pbuf_free(p);
        return;
    }

    printf("  Payload ptr: %p\n", p->payload);

    // Copy packet data to a local buffer to avoid direct memory access issues
    uint8_t packet_buffer[600];  // Max DHCP packet is usually ~550 bytes
    size_t copy_len = (p->tot_len < sizeof(packet_buffer)) ? p->tot_len : sizeof(packet_buffer);

    // Use pbuf_copy_partial to safely copy data from pbuf chain
    uint16_t copied = pbuf_copy_partial(p, packet_buffer, copy_len, 0);
    if (copied < min_dhcp_size) {
        printf("DHCP: ERROR - Failed to copy packet data (copied=%d)\n", copied);
        pbuf_free(p);
        return;
    }

    printf("  Copied %d bytes to local buffer\n", copied);

    // Now work with the local buffer instead of direct pbuf access
    // Check magic cookie at offset 236
    printf("  Checking magic cookie at offset 236...\n");
    if (copied < 240) {
        printf("DHCP: ERROR - Packet too short for magic cookie (len=%d)\n", copied);
        pbuf_free(p);
        return;
    }

    // Read magic cookie byte by byte to avoid alignment issues
    uint32_t magic = (packet_buffer[236] << 24) |
                     (packet_buffer[237] << 16) |
                     (packet_buffer[238] << 8) |
                     packet_buffer[239];
    printf("  Magic cookie: 0x%08x (expected 0x63825363)\n", magic);

    if (magic != 0x63825363) {
        printf("DHCP: ERROR - Invalid magic cookie\n");
        pbuf_free(p);
        return;
    }

    // Find message type - options start at offset 240
    uint8_t msg_type = 0;
    size_t opt_idx = 240;  // Start of options

    printf("DHCP: Parsing options (start offset 240, packet size %d)\n", copied);

    while (opt_idx < copied - 2) {  // Need at least 2 bytes for option type and length
        uint8_t opt_type = packet_buffer[opt_idx];

        if (opt_type == DHCP_OPTION_END) {
            break;
        }

        if (opt_type == DHCP_OPTION_MESSAGE_TYPE && opt_idx + 2 < copied) {
            msg_type = packet_buffer[opt_idx + 2];
            break;
        }

        // Move to next option
        uint8_t opt_len = packet_buffer[opt_idx + 1];
        if (opt_idx + 2 + opt_len > copied) {
            printf("DHCP: Option extends beyond packet\n");
            break;
        }
        opt_idx += 2 + opt_len;
    }

    printf("DHCP: Message type %d (1=DISCOVER, 3=REQUEST)\n", msg_type);

    // Extract transaction ID (XID) at offset 4
    uint32_t xid = (packet_buffer[4] << 24) |
                   (packet_buffer[5] << 16) |
                   (packet_buffer[6] << 8) |
                   packet_buffer[7];
    printf("DHCP: Transaction ID: 0x%08x\n", xid);

    // Extract MAC address at offset 28
    printf("DHCP: Client MAC: %02x:%02x:%02x:%02x:%02x:%02x\n",
           packet_buffer[28], packet_buffer[29], packet_buffer[30],
           packet_buffer[31], packet_buffer[32], packet_buffer[33]);

    // Handle DISCOVER and REQUEST
    if (msg_type == DHCP_DISCOVER || msg_type == DHCP_REQUEST) {
        // Create response (standard size is 300-350 bytes typically)
        const size_t response_size = 350;
        struct pbuf *resp = pbuf_alloc(PBUF_TRANSPORT, response_size, PBUF_RAM);
        if (!resp) {
            printf("DHCP: Failed to allocate response buffer\n");
            pbuf_free(p);
            return;
        }

        // Build response in a local buffer first
        uint8_t response_buffer[350];
        memset(response_buffer, 0, sizeof(response_buffer));

        // Fill basic fields
        printf("DHCP: Building response...\n");
        response_buffer[0] = 2;  // op: BOOTREPLY
        response_buffer[1] = 1;  // htype: Ethernet
        response_buffer[2] = 6;  // hlen: MAC address length

        // Copy XID from original message (offset 4)
        response_buffer[4] = packet_buffer[4];
        response_buffer[5] = packet_buffer[5];
        response_buffer[6] = packet_buffer[6];
        response_buffer[7] = packet_buffer[7];

        // Copy MAC address to chaddr field (offset 28)
        memcpy(&response_buffer[28], &packet_buffer[28], 6);
        // chaddr is 16 bytes total, rest is already zeroed

        // Find or assign IP address based on MAC
        uint8_t assigned_ip = 0;

        // Check if this MAC already has a lease
        for (int i = 0; i < MAX_LEASES; i++) {
            if (leases[i].active && memcmp(leases[i].mac, &packet_buffer[28], 6) == 0) {
                assigned_ip = leases[i].ip;
                printf("DHCP: Found existing lease for IP 192.168.4.%d\n", assigned_ip);
                break;
            }
        }

        // If no existing lease, assign a new one
        if (assigned_ip == 0) {
            assigned_ip = next_client_ip++;
            if (next_client_ip > 254) next_client_ip = 2;

            // Store the lease
            for (int i = 0; i < MAX_LEASES; i++) {
                if (!leases[i].active) {
                    memcpy(leases[i].mac, &packet_buffer[28], 6);
                    leases[i].ip = assigned_ip;
                    leases[i].active = true;
                    printf("DHCP: Assigned new IP 192.168.4.%d (lease slot %d)\n", assigned_ip, i);
                    break;
                }
            }
        }

        // Set yiaddr (your IP address) at offset 16
        response_buffer[16] = 192;
        response_buffer[17] = 168;
        response_buffer[18] = 4;
        response_buffer[19] = assigned_ip;

        // Set siaddr (server IP address) at offset 20
        response_buffer[20] = 192;
        response_buffer[21] = 168;
        response_buffer[22] = 4;
        response_buffer[23] = 1;

        // Set magic cookie at offset 236
        response_buffer[236] = 0x63;
        response_buffer[237] = 0x82;
        response_buffer[238] = 0x53;
        response_buffer[239] = 0x63;

        // Add options starting at offset 240
        size_t opt_offset = 240;

        // Message type
        response_buffer[opt_offset++] = DHCP_OPTION_MESSAGE_TYPE;
        response_buffer[opt_offset++] = 1;
        response_buffer[opt_offset++] = (msg_type == DHCP_DISCOVER) ? DHCP_OFFER : DHCP_ACK;

        // Server ID
        response_buffer[opt_offset++] = DHCP_OPTION_SERVER_ID;
        response_buffer[opt_offset++] = 4;
        response_buffer[opt_offset++] = 192;
        response_buffer[opt_offset++] = 168;
        response_buffer[opt_offset++] = 4;
        response_buffer[opt_offset++] = 1;

        // Lease time (1 hour = 3600 seconds)
        response_buffer[opt_offset++] = DHCP_OPTION_LEASE_TIME;
        response_buffer[opt_offset++] = 4;
        response_buffer[opt_offset++] = 0;
        response_buffer[opt_offset++] = 0;
        response_buffer[opt_offset++] = 0x0E;  // 3600 >> 8
        response_buffer[opt_offset++] = 0x10;  // 3600 & 0xFF

        // Subnet mask
        response_buffer[opt_offset++] = DHCP_OPTION_SUBNET_MASK;
        response_buffer[opt_offset++] = 4;
        response_buffer[opt_offset++] = 255;
        response_buffer[opt_offset++] = 255;
        response_buffer[opt_offset++] = 255;
        response_buffer[opt_offset++] = 0;

        // Router
        response_buffer[opt_offset++] = DHCP_OPTION_ROUTER;
        response_buffer[opt_offset++] = 4;
        response_buffer[opt_offset++] = 192;
        response_buffer[opt_offset++] = 168;
        response_buffer[opt_offset++] = 4;
        response_buffer[opt_offset++] = 1;

        // DNS server
        response_buffer[opt_offset++] = DHCP_OPTION_DNS_SERVER;
        response_buffer[opt_offset++] = 4;
        response_buffer[opt_offset++] = 192;
        response_buffer[opt_offset++] = 168;
        response_buffer[opt_offset++] = 4;
        response_buffer[opt_offset++] = 1;

        // End
        response_buffer[opt_offset++] = DHCP_OPTION_END;

        // Copy the buffer to the pbuf
        memcpy(resp->payload, response_buffer, response_size);

        // Send response
        ip4_addr_t broadcast;
        IP4_ADDR(&broadcast, 255, 255, 255, 255);
        err_t err = udp_sendto(pcb, resp, (ip_addr_t *)&broadcast, DHCP_CLIENT_PORT);

        if (err == ERR_OK) {
            printf("DHCP: Sent %s for IP 192.168.4.%d\n",
                   (msg_type == DHCP_DISCOVER) ? "OFFER" : "ACK", assigned_ip);
        } else {
            printf("DHCP: Failed to send response (error %d)\n", err);
        }

        pbuf_free(resp);
    } else {
        printf("DHCP: Ignoring message type %d\n", msg_type);
    }

    pbuf_free(p);
}

bool dhcp_server_init(ip4_addr_t *ip, ip4_addr_t *mask) {
    if (dhcp_pcb) return false;  // Already initialized

    server_ip = *ip;
    subnet_mask = *mask;

    dhcp_pcb = udp_new();
    if (!dhcp_pcb) return false;

    udp_bind(dhcp_pcb, IP_ADDR_ANY, DHCP_SERVER_PORT);
    udp_recv(dhcp_pcb, dhcp_server_recv, NULL);

    return true;
}

void dhcp_server_deinit(void) {
    if (dhcp_pcb) {
        udp_remove(dhcp_pcb);
        dhcp_pcb = NULL;
    }
}