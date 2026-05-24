# SoundBoard

This directory contains a collection of soundboard images.

## Files

| File | Description |
|------|-------------|
| ![1.png](Schem/1.png) | Root Page |
| ![2.png](Schem/2.png) | Power Page |
| ![3.png](Schem/3.png) | MCU Page |
| ![4.png](Schem/4.png) | Motor Page |
| ![5.png](Schem/5.png) | Audio Page |
| ![6.png](Schem/6.png) | Communication Page |
| ![7.png](Schem/7.png) | Stator Page |

## Usage

These PNG files are used as visual triggers for the soundboard system. Each image (1-7) corresponds to a specific sound or action in the audio processing pipeline.

## Firmware Build Instructions

### Using PlatformIO

The SoundBoard firmware for the ESP32-S3 (stator) and STM32 (rotor) is managed using PlatformIO.

#### Build Commands

To build the firmware using PlatformIO:

- **Build both stator and rotor:**
  ```bash
  ~/.platformio/penv/bin/pio run
  ```

- **Build only stator (ESP32-S3):**
  ```bash
  ~/.platformio/penv/bin/pio run --env stator
  ```

- **Build only rotor (STM32):**
  ```bash
  ~/.platformio/penv/bin/pio run --env rotor
  ```

#### Build Locations

After running `pio run`, the built firmware will be located in:
- `Scripts/stator/.pio/build/` - ESP32-S3 stator firmware
- `Scripts/rotor/.pio/build/` - STM32 rotor firmware

## Related Files

- `coilmaker.py` - Coils maker for KiCAD
- `images/` - Memories
- `Scripts/` - PlatformIO project files for stator and rotor firmware
