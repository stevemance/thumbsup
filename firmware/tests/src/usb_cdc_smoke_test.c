#include <stdio.h>

#include "pico/stdlib.h"

int main(void) {
    stdio_init_all();
    sleep_ms(2000);

    while (true) {
        printf("USB CDC smoke test\n");
        sleep_ms(1000);
    }
}
