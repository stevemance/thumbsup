#ifndef DHCP_SERVER_H
#define DHCP_SERVER_H

#include <stdbool.h>
#include <lwip/ip4_addr.h>

bool dhcp_server_init(ip4_addr_t *ip, ip4_addr_t *mask);
void dhcp_server_deinit(void);

#endif // DHCP_SERVER_H