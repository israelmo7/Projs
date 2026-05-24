idf_component_register(
    SRCS "src/main.c" "src/levitation.c" "src/rotation.c" "src/audio.c" "src/safety.c"
    INCLUDE_DIRS "include"
    REQUIRES driver esp_adc
)
