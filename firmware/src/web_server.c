#include "diagnostic_mode.h"
#include "config.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <pico/stdlib.h>
#include <lwip/tcp.h>

// Web server state
static struct tcp_pcb* web_server_pcb = NULL;
static web_control_t pending_control = {0};
static bool control_pending = false;

// HTTP response headers
static const char http_200_header[] =
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: text/html\r\n"
    "Cache-Control: no-cache\r\n"
    "Connection: close\r\n\r\n";

static const char http_200_json[] =
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: application/json\r\n"
    "Cache-Control: no-cache\r\n"
    "Access-Control-Allow-Origin: *\r\n"
    "Connection: close\r\n\r\n";

// Main dashboard HTML page
static const char dashboard_html[] =
"<!DOCTYPE html>\n"
"<html lang='en'>\n"
"<head>\n"
"    <meta charset='UTF-8'>\n"
"    <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n"
"    <title>ThumbsUp Diagnostic Dashboard</title>\n"
"    <style>\n"
"        * { margin: 0; padding: 0; box-sizing: border-box; }\n"
"        body {\n"
"            font-family: 'Segoe UI', Arial, sans-serif;\n"
"            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);\n"
"            color: white;\n"
"            padding: 20px;\n"
"            min-height: 100vh;\n"
"        }\n"
"        .container { max-width: 1400px; margin: 0 auto; }\n"
"        h1 {\n"
"            text-align: center;\n"
"            margin-bottom: 30px;\n"
"            font-size: 2.5em;\n"
"            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);\n"
"        }\n"
"        .grid {\n"
"            display: grid;\n"
"            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));\n"
"            gap: 20px;\n"
"            margin-bottom: 20px;\n"
"        }\n"
"        .card {\n"
"            background: rgba(255,255,255,0.1);\n"
"            backdrop-filter: blur(10px);\n"
"            border-radius: 15px;\n"
"            padding: 20px;\n"
"            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);\n"
"            border: 1px solid rgba(255,255,255,0.18);\n"
"        }\n"
"        .card h2 {\n"
"            margin-bottom: 15px;\n"
"            color: #ffd700;\n"
"            font-size: 1.3em;\n"
"        }\n"
"        .status-grid {\n"
"            display: grid;\n"
"            grid-template-columns: 1fr 1fr;\n"
"            gap: 10px;\n"
"        }\n"
"        .status-item {\n"
"            display: flex;\n"
"            justify-content: space-between;\n"
"            padding: 8px;\n"
"            background: rgba(0,0,0,0.2);\n"
"            border-radius: 5px;\n"
"        }\n"
"        .status-value {\n"
"            font-weight: bold;\n"
"            color: #00ff00;\n"
"        }\n"
"        .status-value.warning { color: #ffff00; }\n"
"        .status-value.danger { color: #ff3333; }\n"
"        .control-panel {\n"
"            display: flex;\n"
"            flex-wrap: wrap;\n"
"            gap: 10px;\n"
"        }\n"
"        button {\n"
"            padding: 12px 24px;\n"
"            border: none;\n"
"            border-radius: 8px;\n"
"            font-size: 16px;\n"
"            font-weight: bold;\n"
"            cursor: pointer;\n"
"            transition: all 0.3s;\n"
"            text-transform: uppercase;\n"
"        }\n"
"        button:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.3); }\n"
"        button:active { transform: translateY(0); }\n"
"        .btn-arm { background: #ff9800; color: white; }\n"
"        .btn-disarm { background: #4caf50; color: white; }\n"
"        .btn-estop { background: #f44336; color: white; font-size: 20px; padding: 15px 30px; }\n"
"        .btn-clear { background: #2196f3; color: white; }\n"
"        .btn-test { background: #9c27b0; color: white; }\n"
"        .joystick-container {\n"
"            position: relative;\n"
"            width: 200px;\n"
"            height: 200px;\n"
"            background: rgba(0,0,0,0.3);\n"
"            border-radius: 50%;\n"
"            margin: 20px auto;\n"
"            touch-action: none;\n"
"        }\n"
"        .joystick {\n"
"            position: absolute;\n"
"            width: 60px;\n"
"            height: 60px;\n"
"            background: radial-gradient(circle, #4caf50, #2e7d32);\n"
"            border-radius: 50%;\n"
"            top: 50%;\n"
"            left: 50%;\n"
"            transform: translate(-50%, -50%);\n"
"            cursor: grab;\n"
"            box-shadow: 0 4px 8px rgba(0,0,0,0.5);\n"
"        }\n"
"        .slider-container {\n"
"            margin: 15px 0;\n"
"        }\n"
"        .slider {\n"
"            width: 100%;\n"
"            height: 40px;\n"
"            -webkit-appearance: none;\n"
"            background: rgba(0,0,0,0.3);\n"
"            border-radius: 20px;\n"
"            outline: none;\n"
"        }\n"
"        .slider::-webkit-slider-thumb {\n"
"            -webkit-appearance: none;\n"
"            width: 35px;\n"
"            height: 35px;\n"
"            background: #ff9800;\n"
"            border-radius: 50%;\n"
"            cursor: pointer;\n"
"        }\n"
"        .event-log {\n"
"            max-height: 300px;\n"
"            overflow-y: auto;\n"
"            background: rgba(0,0,0,0.3);\n"
"            padding: 10px;\n"
"            border-radius: 8px;\n"
"            font-family: monospace;\n"
"            font-size: 12px;\n"
"            line-height: 1.5;\n"
"        }\n"
"        .event-log::-webkit-scrollbar { width: 8px; }\n"
"        .event-log::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); }\n"
"        .event-log::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.3); border-radius: 4px; }\n"
"        .battery-bar {\n"
"            width: 100%;\n"
"            height: 30px;\n"
"            background: rgba(0,0,0,0.3);\n"
"            border-radius: 15px;\n"
"            overflow: hidden;\n"
"            position: relative;\n"
"        }\n"
"        .battery-fill {\n"
"            height: 100%;\n"
"            background: linear-gradient(90deg, #ff3333, #ffff00, #00ff00);\n"
"            transition: width 0.3s;\n"
"        }\n"
"        .battery-text {\n"
"            position: absolute;\n"
"            top: 50%;\n"
"            left: 50%;\n"
"            transform: translate(-50%, -50%);\n"
"            font-weight: bold;\n"
"            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);\n"
"        }\n"
"        .led {\n"
"            display: inline-block;\n"
"            width: 20px;\n"
"            height: 20px;\n"
"            border-radius: 50%;\n"
"            margin: 0 5px;\n"
"            box-shadow: 0 0 10px currentColor;\n"
"        }\n"
"        .led.green { background: #00ff00; color: #00ff00; }\n"
"        .led.yellow { background: #ffff00; color: #ffff00; }\n"
"        .led.red { background: #ff3333; color: #ff3333; }\n"
"        .led.blue { background: #2196f3; color: #2196f3; }\n"
"        .led.off { background: #333; box-shadow: none; }\n"
"    </style>\n"
"</head>\n"
"<body>\n"
"    <div class='container'>\n"
"        <h1>🤖 ThumbsUp Diagnostic Dashboard</h1>\n"
"        \n"
"        <div class='grid'>\n"
"            <!-- System Status Card -->\n"
"            <div class='card'>\n"
"                <h2>📊 System Status</h2>\n"
"                <div class='status-grid'>\n"
"                    <div class='status-item'>\n"
"                        <span>State:</span>\n"
"                        <span class='status-value' id='system-state'>IDLE</span>\n"
"                    </div>\n"
"                    <div class='status-item'>\n"
"                        <span>Uptime:</span>\n"
"                        <span class='status-value' id='uptime'>00:00:00</span>\n"
"                    </div>\n"
"                    <div class='status-item'>\n"
"                        <span>CPU:</span>\n"
"                        <span class='status-value' id='cpu'>0%</span>\n"
"                    </div>\n"
"                    <div class='status-item'>\n"
"                        <span>Memory:</span>\n"
"                        <span class='status-value' id='memory'>0KB</span>\n"
"                    </div>\n"
"                    <div class='status-item'>\n"
"                        <span>Loop Time:</span>\n"
"                        <span class='status-value' id='loop-time'>0μs</span>\n"
"                    </div>\n"
"                    <div class='status-item'>\n"
"                        <span>Temp:</span>\n"
"                        <span class='status-value' id='temperature'>25°C</span>\n"
"                    </div>\n"
"                </div>\n"
"                <div style='margin-top: 15px;'>\n"
"                    <span>LEDs: </span>\n"
"                    <span class='led' id='led-status' title='Status'></span>\n"
"                    <span class='led' id='led-armed' title='Armed'></span>\n"
"                    <span class='led' id='led-battery' title='Battery'></span>\n"
"                </div>\n"
"            </div>\n"
"            \n"
"            <!-- Battery Card -->\n"
"            <div class='card'>\n"
"                <h2>🔋 Battery Status</h2>\n"
"                <div class='battery-bar'>\n"
"                    <div class='battery-fill' id='battery-fill'></div>\n"
"                    <div class='battery-text' id='battery-text'>0.0V (0%)</div>\n"
"                </div>\n"
"                <div class='status-grid' style='margin-top: 15px;'>\n"
"                    <div class='status-item'>\n"
"                        <span>Voltage:</span>\n"
"                        <span class='status-value' id='voltage'>0.0V</span>\n"
"                    </div>\n"
"                    <div class='status-item'>\n"
"                        <span>Current:</span>\n"
"                        <span class='status-value' id='current'>0.0A</span>\n"
"                    </div>\n"
"                </div>\n"
"            </div>\n"
"            \n"
"            <!-- Emergency Controls -->\n"
"            <div class='card'>\n"
"                <h2>⚠️ Emergency Controls</h2>\n"
"                <div class='control-panel'>\n"
"                    <button class='btn-estop' onclick='emergencyStop()'>🛑 E-STOP</button>\n"
"                    <button class='btn-clear' onclick='clearEStop()'>Clear E-Stop</button>\n"
"                    <button class='btn-test' onclick='runTests()'>Run Safety Tests</button>\n"
"                </div>\n"
"            </div>\n"
"            \n"
"            <!-- Weapon Control -->\n"
"            <div class='card'>\n"
"                <h2>⚔️ Weapon Control</h2>\n"
"                <div class='status-grid'>\n"
"                    <div class='status-item'>\n"
"                        <span>Status:</span>\n"
"                        <span class='status-value' id='weapon-status'>DISARMED</span>\n"
"                    </div>\n"
"                    <div class='status-item'>\n"
"                        <span>Speed:</span>\n"
"                        <span class='status-value' id='weapon-speed'>0%</span>\n"
"                    </div>\n"
"                </div>\n"
"                <div class='control-panel' style='margin-top: 15px;'>\n"
"                    <button class='btn-arm' onclick='armWeapon()'>ARM</button>\n"
"                    <button class='btn-disarm' onclick='disarmWeapon()'>DISARM</button>\n"
"                </div>\n"
"                <div class='slider-container'>\n"
"                    <label>Weapon Speed:</label>\n"
"                    <input type='range' class='slider' id='weapon-slider' min='0' max='100' value='0'>\n"
"                    <span id='weapon-slider-value'>0%</span>\n"
"                </div>\n"
"            </div>\n"
"            \n"
"            <!-- Drive Control -->\n"
"            <div class='card'>\n"
"                <h2>🎮 Drive Control</h2>\n"
"                <div class='joystick-container' id='joystick-container'>\n"
"                    <div class='joystick' id='joystick'></div>\n"
"                </div>\n"
"                <div class='status-grid'>\n"
"                    <div class='status-item'>\n"
"                        <span>Forward:</span>\n"
"                        <span class='status-value' id='drive-forward'>0</span>\n"
"                    </div>\n"
"                    <div class='status-item'>\n"
"                        <span>Turn:</span>\n"
"                        <span class='status-value' id='drive-turn'>0</span>\n"
"                    </div>\n"
"                    <div class='status-item'>\n"
"                        <span>Left:</span>\n"
"                        <span class='status-value' id='motor-left'>0%</span>\n"
"                    </div>\n"
"                    <div class='status-item'>\n"
"                        <span>Right:</span>\n"
"                        <span class='status-value' id='motor-right'>0%</span>\n"
"                    </div>\n"
"                </div>\n"
"            </div>\n"
"            \n"
"            <!-- Event Log -->\n"
"            <div class='card'>\n"
"                <h2>📜 Event Log</h2>\n"
"                <div class='event-log' id='event-log'></div>\n"
"            </div>\n"
"        </div>\n"
"    </div>\n"
"    \n"
"    <script>\n"
"        let telemetryData = {};\n"
"        let joystickActive = false;\n"
"        let joystickX = 0;\n"
"        let joystickY = 0;\n"
"        \n"
"        // Update telemetry display\n"
"        function updateDisplay(data) {\n"
"            telemetryData = data;\n"
"            \n"
"            // System status\n"
"            document.getElementById('system-state').textContent = \n"
"                data.emergency_stopped ? 'E-STOPPED' : \n"
"                data.armed ? 'ARMED' : 'IDLE';\n"
"            \n"
"            // Format uptime\n"
"            const uptime_s = Math.floor(data.uptime_ms / 1000);\n"
"            const hours = Math.floor(uptime_s / 3600);\n"
"            const minutes = Math.floor((uptime_s % 3600) / 60);\n"
"            const seconds = uptime_s % 60;\n"
"            document.getElementById('uptime').textContent = \n"
"                `${hours.toString().padStart(2,'0')}:${minutes.toString().padStart(2,'0')}:${seconds.toString().padStart(2,'0')}`;\n"
"            \n"
"            document.getElementById('cpu').textContent = data.cpu_usage_percent + '%';\n"
"            document.getElementById('memory').textContent = Math.floor(data.free_memory_bytes / 1024) + 'KB';\n"
"            document.getElementById('loop-time').textContent = data.loop_time_us + 'μs';\n"
"            document.getElementById('temperature').textContent = data.temperature_c.toFixed(1) + '°C';\n"
"            \n"
"            // Battery\n"
"            const voltage = data.battery_voltage_mv / 1000;\n"
"            document.getElementById('voltage').textContent = voltage.toFixed(2) + 'V';\n"
"            document.getElementById('battery-text').textContent = \n"
"                `${voltage.toFixed(1)}V (${Math.round(data.battery_percentage)}%)`;\n"
"            document.getElementById('battery-fill').style.width = data.battery_percentage + '%';\n"
"            \n"
"            // Update voltage color\n"
"            const voltageElem = document.getElementById('voltage');\n"
"            if (voltage < 10.5) voltageElem.className = 'status-value danger';\n"
"            else if (voltage < 11.1) voltageElem.className = 'status-value warning';\n"
"            else voltageElem.className = 'status-value';\n"
"            \n"
"            // Weapon\n"
"            document.getElementById('weapon-status').textContent = \n"
"                data.armed ? 'ARMED' : 'DISARMED';\n"
"            document.getElementById('weapon-speed').textContent = data.weapon_speed + '%';\n"
"            \n"
"            // Motors\n"
"            document.getElementById('motor-left').textContent = data.left_drive_speed + '%';\n"
"            document.getElementById('motor-right').textContent = data.right_drive_speed + '%';\n"
"            document.getElementById('drive-forward').textContent = data.input_forward;\n"
"            document.getElementById('drive-turn').textContent = data.input_turn;\n"
"            \n"
"            // LEDs\n"
"            updateLED('led-status', data.emergency_stopped ? 'red' : 'blue');\n"
"            updateLED('led-armed', data.armed ? 'red' : 'off');\n"
"            updateLED('led-battery', \n"
"                voltage < 10.5 ? 'red' : voltage < 11.1 ? 'yellow' : 'green');\n"
"            \n"
"            // Event log\n"
"            const logDiv = document.getElementById('event-log');\n"
"            logDiv.innerHTML = data.event_log.join('<br>');\n"
"            logDiv.scrollTop = logDiv.scrollHeight;\n"
"        }\n"
"        \n"
"        function updateLED(id, color) {\n"
"            const led = document.getElementById(id);\n"
"            led.className = 'led ' + color;\n"
"        }\n"
"        \n"
"        // Control functions\n"
"        function sendCommand(cmd) {\n"
"            fetch('/control', {\n"
"                method: 'POST',\n"
"                headers: {'Content-Type': 'application/json'},\n"
"                body: JSON.stringify(cmd)\n"
"            });\n"
"        }\n"
"        \n"
"        function emergencyStop() {\n"
"            if (confirm('Trigger Emergency Stop?')) {\n"
"                sendCommand({emergency_stop: true});\n"
"            }\n"
"        }\n"
"        \n"
"        function clearEStop() {\n"
"            sendCommand({clear_emergency_stop: true});\n"
"        }\n"
"        \n"
"        function armWeapon() {\n"
"            if (confirm('ARM weapon?')) {\n"
"                sendCommand({arm_weapon: true});\n"
"            }\n"
"        }\n"
"        \n"
"        function disarmWeapon() {\n"
"            sendCommand({disarm_weapon: true});\n"
"        }\n"
"        \n"
"        function runTests() {\n"
"            sendCommand({run_safety_tests: true});\n"
"        }\n"
"        \n"
"        // Weapon slider\n"
"        const weaponSlider = document.getElementById('weapon-slider');\n"
"        const weaponValue = document.getElementById('weapon-slider-value');\n"
"        weaponSlider.addEventListener('input', function() {\n"
"            weaponValue.textContent = this.value + '%';\n"
"            sendCommand({weapon_speed: parseInt(this.value)});\n"
"        });\n"
"        \n"
"        // Joystick control\n"
"        const joystick = document.getElementById('joystick');\n"
"        const container = document.getElementById('joystick-container');\n"
"        const containerRect = container.getBoundingClientRect();\n"
"        const radius = containerRect.width / 2;\n"
"        \n"
"        function moveJoystick(x, y) {\n"
"            const centerX = radius;\n"
"            const centerY = radius;\n"
"            const deltaX = x - centerX;\n"
"            const deltaY = y - centerY;\n"
"            const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);\n"
"            \n"
"            if (distance <= radius - 30) {\n"
"                joystick.style.left = x + 'px';\n"
"                joystick.style.top = y + 'px';\n"
"                joystickX = Math.round((deltaX / (radius - 30)) * 127);\n"
"                joystickY = Math.round(-(deltaY / (radius - 30)) * 127);\n"
"            } else {\n"
"                const angle = Math.atan2(deltaY, deltaX);\n"
"                const limitedX = centerX + Math.cos(angle) * (radius - 30);\n"
"                const limitedY = centerY + Math.sin(angle) * (radius - 30);\n"
"                joystick.style.left = limitedX + 'px';\n"
"                joystick.style.top = limitedY + 'px';\n"
"                joystickX = Math.round(Math.cos(angle) * 127);\n"
"                joystickY = Math.round(-Math.sin(angle) * 127);\n"
"            }\n"
"            \n"
"            sendCommand({\n"
"                drive_forward: joystickY,\n"
"                drive_turn: joystickX\n"
"            });\n"
"        }\n"
"        \n"
"        function resetJoystick() {\n"
"            joystick.style.left = '50%';\n"
"            joystick.style.top = '50%';\n"
"            joystick.style.transform = 'translate(-50%, -50%)';\n"
"            joystickX = 0;\n"
"            joystickY = 0;\n"
"            sendCommand({drive_forward: 0, drive_turn: 0});\n"
"        }\n"
"        \n"
"        // Mouse events\n"
"        joystick.addEventListener('mousedown', function(e) {\n"
"            joystickActive = true;\n"
"            joystick.style.transform = 'none';\n"
"        });\n"
"        \n"
"        document.addEventListener('mousemove', function(e) {\n"
"            if (joystickActive) {\n"
"                const rect = container.getBoundingClientRect();\n"
"                moveJoystick(e.clientX - rect.left, e.clientY - rect.top);\n"
"            }\n"
"        });\n"
"        \n"
"        document.addEventListener('mouseup', function() {\n"
"            if (joystickActive) {\n"
"                joystickActive = false;\n"
"                resetJoystick();\n"
"            }\n"
"        });\n"
"        \n"
"        // Touch events\n"
"        joystick.addEventListener('touchstart', function(e) {\n"
"            joystickActive = true;\n"
"            joystick.style.transform = 'none';\n"
"            e.preventDefault();\n"
"        });\n"
"        \n"
"        document.addEventListener('touchmove', function(e) {\n"
"            if (joystickActive) {\n"
"                const rect = container.getBoundingClientRect();\n"
"                const touch = e.touches[0];\n"
"                moveJoystick(touch.clientX - rect.left, touch.clientY - rect.top);\n"
"                e.preventDefault();\n"
"            }\n"
"        });\n"
"        \n"
"        document.addEventListener('touchend', function(e) {\n"
"            if (joystickActive) {\n"
"                joystickActive = false;\n"
"                resetJoystick();\n"
"                e.preventDefault();\n"
"            }\n"
"        });\n"
"        \n"
"        // Poll for telemetry data\n"
"        function fetchTelemetry() {\n"
"            fetch('/telemetry')\n"
"                .then(response => response.json())\n"
"                .then(data => updateDisplay(data))\n"
"                .catch(err => console.error('Telemetry fetch error:', err));\n"
"        }\n"
"        \n"
"        // Start polling\n"
"        setInterval(fetchTelemetry, 250);\n"
"        fetchTelemetry();\n"
"    </script>\n"
"</body>\n"
"</html>\n";

// JSON telemetry response builder
static void build_telemetry_json(char* buffer, size_t max_len) {
    telemetry_data_t* data = telemetry_get_data();

    // Build event log JSON array
    char events_json[2048] = "[";
    for (int i = 0; i < data->event_log_count; i++) {
        int idx = (data->event_log_head - data->event_log_count + i) % EVENT_LOG_SIZE;
        if (idx < 0) idx += EVENT_LOG_SIZE;

        if (i > 0) strcat(events_json, ",");
        strcat(events_json, "\"");
        strcat(events_json, data->event_log[idx]);
        strcat(events_json, "\"");
    }
    strcat(events_json, "]");

    snprintf(buffer, max_len,
        "{"
        "\"uptime_ms\":%lu,"
        "\"armed\":%s,"
        "\"emergency_stopped\":%s,"
        "\"safety_button\":%s,"
        "\"battery_voltage_mv\":%lu,"
        "\"battery_percentage\":%.1f,"
        "\"left_drive_speed\":%d,"
        "\"right_drive_speed\":%d,"
        "\"weapon_speed\":%u,"
        "\"safety_tests_passed\":%s,"
        "\"input_forward\":%d,"
        "\"input_turn\":%d,"
        "\"input_weapon\":%d,"
        "\"loop_time_us\":%lu,"
        "\"cpu_usage_percent\":%lu,"
        "\"free_memory_bytes\":%lu,"
        "\"temperature_c\":%.1f,"
        "\"event_log\":%s"
        "}",
        data->uptime_ms,
        data->armed ? "true" : "false",
        data->emergency_stopped ? "true" : "false",
        data->safety_button ? "true" : "false",
        data->battery_voltage_mv,
        data->battery_percentage,
        data->left_drive_speed,
        data->right_drive_speed,
        data->weapon_speed,
        data->safety_tests_passed ? "true" : "false",
        data->input_forward,
        data->input_turn,
        data->input_weapon,
        data->loop_time_us,
        data->cpu_usage_percent,
        data->free_memory_bytes,
        data->temperature_c,
        events_json
    );
}

// Parse control JSON
static bool parse_control_json(const char* json, web_control_t* control) {
    memset(control, 0, sizeof(web_control_t));

    // Simple JSON parser for control commands
    if (strstr(json, "\"emergency_stop\":true")) control->emergency_stop = true;
    if (strstr(json, "\"clear_emergency_stop\":true")) control->clear_emergency_stop = true;
    if (strstr(json, "\"arm_weapon\":true")) control->arm_weapon = true;
    if (strstr(json, "\"disarm_weapon\":true")) control->disarm_weapon = true;
    if (strstr(json, "\"reboot_system\":true")) control->reboot_system = true;
    if (strstr(json, "\"run_safety_tests\":true")) control->run_safety_tests = true;

    // Parse numeric values
    const char* p;
    if ((p = strstr(json, "\"drive_forward\":"))) {
        control->drive_forward = atoi(p + 16);
    }
    if ((p = strstr(json, "\"drive_turn\":"))) {
        control->drive_turn = atoi(p + 13);
    }
    if ((p = strstr(json, "\"weapon_speed\":"))) {
        control->weapon_speed = atoi(p + 15);
    }

    return true;
}

// TCP receive callback
static err_t web_recv_callback(void* arg, struct tcp_pcb* pcb, struct pbuf* p, err_t err) {
    if (!p) {
        tcp_close(pcb);
        return ERR_OK;
    }

    char* request = (char*)p->payload;

    // Check request type
    if (strncmp(request, "GET / ", 6) == 0) {
        // Send main dashboard
        tcp_write(pcb, http_200_header, strlen(http_200_header), TCP_WRITE_FLAG_COPY);
        tcp_write(pcb, dashboard_html, strlen(dashboard_html), TCP_WRITE_FLAG_COPY);
    }
    else if (strncmp(request, "GET /telemetry ", 15) == 0) {
        // Send telemetry JSON
        char json_buffer[4096];
        build_telemetry_json(json_buffer, sizeof(json_buffer));

        tcp_write(pcb, http_200_json, strlen(http_200_json), TCP_WRITE_FLAG_COPY);
        tcp_write(pcb, json_buffer, strlen(json_buffer), TCP_WRITE_FLAG_COPY);
    }
    else if (strncmp(request, "POST /control ", 14) == 0) {
        // Parse control command
        char* body = strstr(request, "\r\n\r\n");
        if (body) {
            body += 4;
            parse_control_json(body, &pending_control);
            control_pending = true;
        }

        // Send OK response
        const char* ok_response = "HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n";
        tcp_write(pcb, ok_response, strlen(ok_response), TCP_WRITE_FLAG_COPY);
    }

    tcp_output(pcb);
    pbuf_free(p);

    // Close connection after response
    tcp_close(pcb);

    return ERR_OK;
}

// TCP accept callback
static err_t web_accept_callback(void* arg, struct tcp_pcb* newpcb, err_t err) {
    tcp_recv(newpcb, web_recv_callback);
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

// Get pending control commands
bool web_get_control(web_control_t* control) {
    if (control_pending) {
        memcpy(control, &pending_control, sizeof(web_control_t));
        control_pending = false;
        return true;
    }
    return false;
}