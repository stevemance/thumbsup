#include "diagnostic_mode.h"
#include "config.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <pico/stdlib.h>
#include <pico/cyw43_arch.h>
#include <lwip/tcp.h>

// Web server state
static struct tcp_pcb* web_server_pcb = NULL;
static web_control_t pending_control = {0};
static bool control_pending = false;

// Minimal compact dashboard - ~2KB total
static const char dashboard_html[] =
"<!DOCTYPE html>"
"<html>"
"<head>"
"<title>ThumbsUp</title>"
"<style>"
"body{font-family:Arial;background:#2a5298;color:white;margin:20px}"
"h1{text-align:center}"
".g{display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:600px;margin:auto}"
".c{background:rgba(255,255,255,0.1);padding:10px;border-radius:5px}"
"h2{color:#ffd700;margin:0 0 10px}"
".s{display:flex;justify-content:space-between;padding:5px;background:rgba(0,0,0,0.2);margin:2px 0}"
".v{font-weight:bold}"
"button{padding:8px 15px;margin:2px;border:none;border-radius:3px;background:#4CAF50;color:white;cursor:pointer}"
"button:hover{background:#45a049}"
".d{background:#f44336}"
"</style>"
"</head>"
"<body>"
"<h1>ThumbsUp Diagnostic</h1>"
"<div class='g'>"
"<div class='c'>"
"<h2>Status</h2>"
"<div class='s'>Armed:<span class='v' id='a'>NO</span></div>"
"<div class='s'>Battery:<span class='v' id='b'>0V</span></div>"
"<div class='s'>Uptime:<span class='v' id='u'>0s</span></div>"
"</div>"
"<div class='c'>"
"<h2>Motors</h2>"
"<div class='s'>Left:<span class='v' id='l'>0%</span></div>"
"<div class='s'>Right:<span class='v' id='r'>0%</span></div>"
"<div class='s'>Weapon:<span class='v' id='w'>0%</span></div>"
"</div>"
"<div class='c'>"
"<h2>Control</h2>"
"<button onclick=\"c('arm')\">Arm</button>"
"<button onclick=\"c('disarm')\">Disarm</button>"
"<button class='d' onclick=\"c('stop')\">E-STOP</button>"
"</div>"
"<div class='c'>"
"<h2>Info</h2>"
"<div id='i'>Loading...</div>"
"</div>"
"</div>"
"<script>"
"function c(a){fetch('/control',{method:'POST',body:'{\"action\":\"'+a+'\"}'}).catch(e=>console.log(e))}"
"function u(){fetch('/telemetry').then(r=>r.json()).then(d=>{"
"document.getElementById('a').textContent=d.armed?'YES':'NO';"
"document.getElementById('a').style.color=d.armed?'red':'lime';"
"document.getElementById('b').textContent=(d.battery_voltage_mv/1000).toFixed(1)+'V';"
"document.getElementById('u').textContent=Math.floor(d.uptime_ms/1000)+'s';"
"document.getElementById('l').textContent=d.left_drive_speed+'%';"
"document.getElementById('r').textContent=d.right_drive_speed+'%';"
"document.getElementById('w').textContent=d.weapon_speed+'%';"
"document.getElementById('i').textContent='CPU:'+d.cpu_usage_percent+'% Loop:'+d.loop_time_us+'us';"
"}).catch(e=>console.log(e))}"
"setInterval(u,1000);u();"
"</script>"
"</body>"
"</html>";

// Connection state
typedef struct {
    struct tcp_pcb *pcb;
    bool close_after_send;
} web_conn_state_t;

// Build telemetry JSON
static void build_telemetry_json(char* buffer, size_t max_len) {
    telemetry_data_t* data = telemetry_get_data();

    snprintf(buffer, max_len,
        "{"
        "\"armed\":%s,"
        "\"battery_voltage_mv\":%u,"
        "\"uptime_ms\":%lu,"
        "\"left_drive_speed\":%d,"
        "\"right_drive_speed\":%d,"
        "\"weapon_speed\":%d,"
        "\"cpu_usage_percent\":%u,"
        "\"loop_time_us\":%lu"
        "}",
        data->armed ? "true" : "false",
        data->battery_voltage_mv,
        data->uptime_ms,
        data->left_drive_speed,
        data->right_drive_speed,
        data->weapon_speed,
        data->cpu_usage_percent,
        data->loop_time_us
    );
}

// Parse control JSON
static bool parse_control_json(const char* json, web_control_t* control) {
    memset(control, 0, sizeof(web_control_t));

    // Simple action parser
    if (strstr(json, "\"arm\"")) control->arm_weapon = true;
    if (strstr(json, "\"disarm\"")) control->disarm_weapon = true;
    if (strstr(json, "\"stop\"")) control->emergency_stop = true;
    if (strstr(json, "\"test\"")) control->run_safety_tests = true;

    return true;
}

// TCP sent callback - called when data has been sent
static err_t web_sent_callback(void *arg, struct tcp_pcb *tpcb, u16_t len) {
    web_conn_state_t *state = (web_conn_state_t *)arg;
    printf("WEB: Sent %d bytes\n", len);

    if (state && state->close_after_send) {
        tcp_close(tpcb);
        free(state);
    }
    return ERR_OK;
}

// TCP receive callback
static err_t web_recv_callback(void* arg, struct tcp_pcb* pcb, struct pbuf* p, err_t err) {
    if (!p) {
        if (arg) free(arg);
        tcp_close(pcb);
        return ERR_OK;
    }

    printf("WEB: Received HTTP request (%d bytes)\n", p->tot_len);

    // Copy request to a buffer for safe access
    char request[256];
    size_t copy_len = (p->tot_len < sizeof(request)-1) ? p->tot_len : sizeof(request)-1;
    pbuf_copy_partial(p, request, copy_len, 0);
    request[copy_len] = '\0';

    printf("WEB: Request: %.60s...\n", request);  // Print first 60 chars

    // Create state for this connection
    web_conn_state_t *state = calloc(1, sizeof(web_conn_state_t));
    if (state) {
        state->pcb = pcb;
        state->close_after_send = true;
        tcp_arg(pcb, state);
    }

    // Set sent callback to know when data is actually sent
    tcp_sent(pcb, web_sent_callback);

    // Check request type
    if (strncmp(request, "GET / ", 6) == 0 || strncmp(request, "GET /index.html", 15) == 0) {
        size_t html_len = strlen(dashboard_html);
        printf("WEB: Serving dashboard (size: %d bytes)\n", html_len);

        // Build header with Content-Length
        char header[256];
        int header_len = snprintf(header, sizeof(header),
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            "Content-Length: %d\r\n"
            "Connection: close\r\n"
            "\r\n", html_len);

        // Send header
        err_t err1 = tcp_write(pcb, header, header_len, TCP_WRITE_FLAG_COPY);

        // Send HTML body
        err_t err2 = tcp_write(pcb, dashboard_html, html_len, TCP_WRITE_FLAG_COPY);

        printf("WEB: Send results: header=%d, html=%d\n", err1, err2);

        if (err1 == ERR_OK && err2 == ERR_OK) {
            tcp_output(pcb);
        } else {
            printf("WEB: Failed to send response\n");
            if (state) free(state);
            tcp_close(pcb);
        }
    }
    else if (strncmp(request, "GET /telemetry", 14) == 0) {
        printf("WEB: Serving telemetry data\n");

        // Build telemetry JSON
        char json_buffer[256];
        build_telemetry_json(json_buffer, sizeof(json_buffer));

        // Build complete response
        char response[512];
        int len = snprintf(response, sizeof(response),
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Connection: close\r\n"
            "\r\n"
            "%s", json_buffer);

        err_t err = tcp_write(pcb, response, len, TCP_WRITE_FLAG_COPY);
        if (err == ERR_OK) {
            tcp_output(pcb);
        }
    }
    else if (strncmp(request, "POST /control", 13) == 0) {
        printf("WEB: Received control command\n");

        // Parse control command from body
        char* body = strstr(request, "\r\n\r\n");
        if (body) {
            body += 4;
            parse_control_json(body, &pending_control);
            control_pending = true;
        }

        // Send OK response
        const char* ok_response = "HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
        err_t err = tcp_write(pcb, ok_response, strlen(ok_response), TCP_WRITE_FLAG_COPY);
        if (err == ERR_OK) {
            tcp_output(pcb);
        }
    }
    else {
        // 404 response
        const char* not_found = "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
        tcp_write(pcb, not_found, strlen(not_found), TCP_WRITE_FLAG_COPY);
        tcp_output(pcb);
    }

    pbuf_free(p);

    // Don't close immediately - wait for sent callback
    return ERR_OK;
}

// TCP accept callback
static err_t web_accept_callback(void* arg, struct tcp_pcb* newpcb, err_t err) {
    printf("WEB: New client connected\n");

    // Set priority for accepted connection
    tcp_setprio(newpcb, TCP_PRIO_MIN);

    // Set up callbacks
    tcp_recv(newpcb, web_recv_callback);
    tcp_err(newpcb, NULL);
    tcp_poll(newpcb, NULL, 4);

    // Keep connection alive
    tcp_nagle_disable(newpcb);

    return ERR_OK;
}

// Initialize web server
bool web_server_init(void) {
    web_server_pcb = tcp_new();
    if (!web_server_pcb) {
        return false;
    }

    err_t err = tcp_bind(web_server_pcb, IP_ADDR_ANY, HTTP_PORT);
    if (err != ERR_OK) {
        tcp_close(web_server_pcb);
        return false;
    }

    web_server_pcb = tcp_listen(web_server_pcb);
    if (!web_server_pcb) {
        return false;
    }

    tcp_accept(web_server_pcb, web_accept_callback);

    printf("Web server initialized on port %d\n", HTTP_PORT);
    return true;
}

// Update web server (process lwIP)
void web_server_update(void) {
    // Process any pending network events
    cyw43_arch_poll();
}

// Shutdown web server
void web_server_shutdown(void) {
    if (web_server_pcb) {
        tcp_close(web_server_pcb);
        web_server_pcb = NULL;
    }
}

// Get pending control command
bool web_get_control(web_control_t* control) {
    if (!control_pending) {
        return false;
    }

    memcpy(control, &pending_control, sizeof(web_control_t));
    control_pending = false;
    return true;
}