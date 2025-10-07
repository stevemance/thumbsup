#ifndef WEB_SERVER_H
#define WEB_SERVER_H

#include <stdbool.h>
#include <stdint.h>

// Web server functions only - types are defined in diagnostic_mode.h
bool web_server_init(void);
void web_server_update(void);
void web_server_shutdown(void);

// Note: web_control_t and web_get_control are defined in diagnostic_mode.h

#endif // WEB_SERVER_H