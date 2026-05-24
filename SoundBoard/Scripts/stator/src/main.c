#include "config.h"
#include "levitation.h"

void app_main(void)
{
    (void)levitation_hardware_init;
    (void)levitation_calibrate_halls;
    (void)levitation_start_loop;
}
