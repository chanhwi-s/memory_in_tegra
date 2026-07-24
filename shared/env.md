# Environment Log

Append-only reproducibility record. Each run below is its own timestamped block;
earlier blocks are never edited or removed.

## Run: 2026-07-24T07:46:00Z
- phase: 01_single_kernel_size
- device: NVIDIA Jetson AGX Orin Developer Kit
- L4T/JetPack: # R39 (release), REVISION: 2.0, GCID: 45755727, BOARD: generic, EABI: aarch64, DATE: Mon Jun  1 09:28:48 PM UTC 2026
# KERNEL_VARIANT: oot
TARGET_USERSPACE_LIB_DIR=nvidia
TARGET_USERSPACE_LIB_DIR_PATH=usr/lib/aarch64-linux-gnu/nvidia
- CUDA (nvcc): release 13.2
- nvpmodel: NV Power Mode: MAXN 0 
- jetson_clocks --show:
```
SOC family:tegra234  Machine:NVIDIA Jetson AGX Orin Developer Kit
Online CPUs: 0-11, Offline CPUs: 
cpu0:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu1:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu2:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu3:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu4:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu5:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu6:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu7:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu8:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu9:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu10: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu11: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
GPU MinFreq=1300500000 MaxFreq=1300500000 CurrentFreq=1300500000
Active GPU TPCs: 8
EMC MinFreq=3199000000 MaxFreq=3199000000 CurrentFreq=3199000000
DLA0_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA0_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
DLA1_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA1_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
PVA0_VPS0: Online=1 MinFreq=0 MaxFreq=1369600000 CurrentFreq=1369600000
PVA0_AXI:  Online=1 MinFreq=0 MaxFreq=985600000 CurrentFreq=985600000
FAN Dynamic Speed Control=nvfancontrol hwmon2_pwm1=66
FAN Dynamic Speed Control=nvfancontrol hwmon2_pwm1_enable=1
NV Power Mode: MAXN
```
- SoC temp (thermal_zone0): 54 C

## Run: 2026-07-24T08:06:49Z
- phase: 02_two_kernel_size
- device: NVIDIA Jetson AGX Orin Developer Kit
- L4T/JetPack: # R39 (release), REVISION: 2.0, GCID: 45755727, BOARD: generic, EABI: aarch64, DATE: Mon Jun  1 09:28:48 PM UTC 2026
# KERNEL_VARIANT: oot
TARGET_USERSPACE_LIB_DIR=nvidia
TARGET_USERSPACE_LIB_DIR_PATH=usr/lib/aarch64-linux-gnu/nvidia
- CUDA (nvcc): release 13.2
- nvpmodel: NV Power Mode: MAXN 0 
- jetson_clocks --show:
```
SOC family:tegra234  Machine:NVIDIA Jetson AGX Orin Developer Kit
Online CPUs: 0-11, Offline CPUs: 
cpu0:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu1:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu2:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu3:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu4:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu5:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu6:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu7:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu8:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu9:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu10: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu11: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
GPU MinFreq=1300500000 MaxFreq=1300500000 CurrentFreq=1300500000
Active GPU TPCs: 8
EMC MinFreq=3199000000 MaxFreq=3199000000 CurrentFreq=3199000000
DLA0_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA0_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
DLA1_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA1_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
PVA0_VPS0: Online=1 MinFreq=0 MaxFreq=1369600000 CurrentFreq=1369600000
PVA0_AXI:  Online=1 MinFreq=0 MaxFreq=985600000 CurrentFreq=985600000
FAN Dynamic Speed Control=nvfancontrol hwmon2_pwm1=58
FAN Dynamic Speed Control=nvfancontrol hwmon2_pwm1_enable=1
NV Power Mode: MAXN
```
- SoC temp (thermal_zone0): 52 C

## Run: 2026-07-24T08:31:27Z
- phase: 02_two_kernel_size
- device: NVIDIA Jetson AGX Orin Developer Kit
- L4T/JetPack: # R39 (release), REVISION: 2.0, GCID: 45755727, BOARD: generic, EABI: aarch64, DATE: Mon Jun  1 09:28:48 PM UTC 2026
# KERNEL_VARIANT: oot
TARGET_USERSPACE_LIB_DIR=nvidia
TARGET_USERSPACE_LIB_DIR_PATH=usr/lib/aarch64-linux-gnu/nvidia
- CUDA (nvcc): release 13.2
- nvpmodel: NV Power Mode: MAXN 0 
- jetson_clocks --show:
```
SOC family:tegra234  Machine:NVIDIA Jetson AGX Orin Developer Kit
Online CPUs: 0-11, Offline CPUs: 
cpu0:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu1:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu2:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu3:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu4:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu5:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu6:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu7:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu8:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu9:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu10: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu11: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
GPU MinFreq=1300500000 MaxFreq=1300500000 CurrentFreq=1300500000
Active GPU TPCs: 8
EMC MinFreq=3199000000 MaxFreq=3199000000 CurrentFreq=3199000000
DLA0_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA0_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
DLA1_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA1_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
PVA0_VPS0: Online=1 MinFreq=0 MaxFreq=1369600000 CurrentFreq=1369600000
PVA0_AXI:  Online=1 MinFreq=0 MaxFreq=985600000 CurrentFreq=985600000
FAN Dynamic Speed Control=nvfancontrol hwmon2_pwm1=58
FAN Dynamic Speed Control=nvfancontrol hwmon2_pwm1_enable=1
NV Power Mode: MAXN
```
- SoC temp (thermal_zone0): 52 C

## Run: 2026-07-24T08:57:30Z
- phase: 03_green_context
- device: NVIDIA Jetson AGX Orin Developer Kit
- L4T/JetPack: # R39 (release), REVISION: 2.0, GCID: 45755727, BOARD: generic, EABI: aarch64, DATE: Mon Jun  1 09:28:48 PM UTC 2026
# KERNEL_VARIANT: oot
TARGET_USERSPACE_LIB_DIR=nvidia
TARGET_USERSPACE_LIB_DIR_PATH=usr/lib/aarch64-linux-gnu/nvidia
- CUDA (nvcc): release 13.2
- nvpmodel: NV Power Mode: MAXN 0 
- jetson_clocks --show:
```
SOC family:tegra234  Machine:NVIDIA Jetson AGX Orin Developer Kit
Online CPUs: 0-11, Offline CPUs: 
cpu0:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu1:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu2:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu3:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu4:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu5:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu6:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu7:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu8:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu9:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu10: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu11: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
GPU MinFreq=1300500000 MaxFreq=1300500000 CurrentFreq=1300500000
Active GPU TPCs: 8
EMC MinFreq=3199000000 MaxFreq=3199000000 CurrentFreq=3199000000
DLA0_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA0_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
DLA1_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA1_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
PVA0_VPS0: Online=1 MinFreq=0 MaxFreq=1369600000 CurrentFreq=1369600000
PVA0_AXI:  Online=1 MinFreq=0 MaxFreq=985600000 CurrentFreq=985600000
FAN Dynamic Speed Control=nvfancontrol hwmon2_pwm1=58
FAN Dynamic Speed Control=nvfancontrol hwmon2_pwm1_enable=1
NV Power Mode: MAXN
```
- SoC temp (thermal_zone0): 52 C

## Run: 2026-07-24T08:58:21Z
- phase: 04_zero_copy
- device: NVIDIA Jetson AGX Orin Developer Kit
- L4T/JetPack: # R39 (release), REVISION: 2.0, GCID: 45755727, BOARD: generic, EABI: aarch64, DATE: Mon Jun  1 09:28:48 PM UTC 2026
# KERNEL_VARIANT: oot
TARGET_USERSPACE_LIB_DIR=nvidia
TARGET_USERSPACE_LIB_DIR_PATH=usr/lib/aarch64-linux-gnu/nvidia
- CUDA (nvcc): release 13.2
- nvpmodel: NV Power Mode: MAXN 0 
- jetson_clocks --show:
```
SOC family:tegra234  Machine:NVIDIA Jetson AGX Orin Developer Kit
Online CPUs: 0-11, Offline CPUs: 
cpu0:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu1:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu2:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu3:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu4:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu5:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu6:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu7:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu8:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu9:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu10: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu11: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
GPU MinFreq=1300500000 MaxFreq=1300500000 CurrentFreq=1300500000
Active GPU TPCs: 8
EMC MinFreq=3199000000 MaxFreq=3199000000 CurrentFreq=3199000000
DLA0_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA0_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
DLA1_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA1_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
PVA0_VPS0: Online=1 MinFreq=0 MaxFreq=1369600000 CurrentFreq=1369600000
PVA0_AXI:  Online=1 MinFreq=0 MaxFreq=985600000 CurrentFreq=985600000
FAN Dynamic Speed Control=nvfancontrol hwmon2_pwm1=58
FAN Dynamic Speed Control=nvfancontrol hwmon2_pwm1_enable=1
NV Power Mode: MAXN
```
- SoC temp (thermal_zone0): 52 C

## Run: 2026-07-24T12:24:06Z
- phase: 01_single_kernel_size
- device: NVIDIA Jetson AGX Orin Developer Kit
- L4T/JetPack: # R39 (release), REVISION: 2.0, GCID: 45755727, BOARD: generic, EABI: aarch64, DATE: Mon Jun  1 09:28:48 PM UTC 2026
# KERNEL_VARIANT: oot
TARGET_USERSPACE_LIB_DIR=nvidia
TARGET_USERSPACE_LIB_DIR_PATH=usr/lib/aarch64-linux-gnu/nvidia
- CUDA (nvcc): release 13.2
- nvpmodel: NV Power Mode: MAXN 0 
- jetson_clocks --show:
```
SOC family:tegra234  Machine:NVIDIA Jetson AGX Orin Developer Kit
Online CPUs: 0-11, Offline CPUs: 
cpu0:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu1:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu2:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu3:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu4:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu5:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu6:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu7:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu8:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu9:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu10: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu11: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
GPU MinFreq=1300500000 MaxFreq=1300500000 CurrentFreq=1300500000
Active GPU TPCs: 8
EMC MinFreq=3199000000 MaxFreq=3199000000 CurrentFreq=3199000000
DLA0_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA0_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
DLA1_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA1_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
PVA0_VPS0: Online=1 MinFreq=0 MaxFreq=1369600000 CurrentFreq=1369600000
PVA0_AXI:  Online=1 MinFreq=0 MaxFreq=985600000 CurrentFreq=985600000
FAN Dynamic Speed Control=disabled hwmon2_pwm1=255
FAN Dynamic Speed Control=disabled hwmon2_pwm1_enable=1
NV Power Mode: MAXN
```
- SoC temp (thermal_zone0): 52 C

## Run: 2026-07-24T12:24:15Z
- phase: 02_two_kernel_size
- device: NVIDIA Jetson AGX Orin Developer Kit
- L4T/JetPack: # R39 (release), REVISION: 2.0, GCID: 45755727, BOARD: generic, EABI: aarch64, DATE: Mon Jun  1 09:28:48 PM UTC 2026
# KERNEL_VARIANT: oot
TARGET_USERSPACE_LIB_DIR=nvidia
TARGET_USERSPACE_LIB_DIR_PATH=usr/lib/aarch64-linux-gnu/nvidia
- CUDA (nvcc): release 13.2
- nvpmodel: NV Power Mode: MAXN 0 
- jetson_clocks --show:
```
SOC family:tegra234  Machine:NVIDIA Jetson AGX Orin Developer Kit
Online CPUs: 0-11, Offline CPUs: 
cpu0:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu1:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu2:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu3:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu4:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu5:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu6:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu7:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu8:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu9:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu10: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu11: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
GPU MinFreq=1300500000 MaxFreq=1300500000 CurrentFreq=1300500000
Active GPU TPCs: 8
EMC MinFreq=3199000000 MaxFreq=3199000000 CurrentFreq=3199000000
DLA0_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA0_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
DLA1_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA1_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
PVA0_VPS0: Online=1 MinFreq=0 MaxFreq=1369600000 CurrentFreq=1369600000
PVA0_AXI:  Online=1 MinFreq=0 MaxFreq=985600000 CurrentFreq=985600000
FAN Dynamic Speed Control=disabled hwmon2_pwm1=255
FAN Dynamic Speed Control=disabled hwmon2_pwm1_enable=1
NV Power Mode: MAXN
```
- SoC temp (thermal_zone0): 52 C

## Run: 2026-07-24T12:24:38Z
- phase: 03_green_context
- device: NVIDIA Jetson AGX Orin Developer Kit
- L4T/JetPack: # R39 (release), REVISION: 2.0, GCID: 45755727, BOARD: generic, EABI: aarch64, DATE: Mon Jun  1 09:28:48 PM UTC 2026
# KERNEL_VARIANT: oot
TARGET_USERSPACE_LIB_DIR=nvidia
TARGET_USERSPACE_LIB_DIR_PATH=usr/lib/aarch64-linux-gnu/nvidia
- CUDA (nvcc): release 13.2
- nvpmodel: NV Power Mode: MAXN 0 
- jetson_clocks --show:
```
SOC family:tegra234  Machine:NVIDIA Jetson AGX Orin Developer Kit
Online CPUs: 0-11, Offline CPUs: 
cpu0:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu1:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu2:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu3:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu4:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu5:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu6:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu7:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu8:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu9:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu10: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu11: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
GPU MinFreq=1300500000 MaxFreq=1300500000 CurrentFreq=1300500000
Active GPU TPCs: 8
EMC MinFreq=3199000000 MaxFreq=3199000000 CurrentFreq=3199000000
DLA0_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA0_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
DLA1_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA1_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
PVA0_VPS0: Online=1 MinFreq=0 MaxFreq=1369600000 CurrentFreq=1369600000
PVA0_AXI:  Online=1 MinFreq=0 MaxFreq=985600000 CurrentFreq=985600000
FAN Dynamic Speed Control=disabled hwmon2_pwm1=255
FAN Dynamic Speed Control=disabled hwmon2_pwm1_enable=1
NV Power Mode: MAXN
```
- SoC temp (thermal_zone0): 50 C

## Run: 2026-07-24T12:24:49Z
- phase: 04_zero_copy
- device: NVIDIA Jetson AGX Orin Developer Kit
- L4T/JetPack: # R39 (release), REVISION: 2.0, GCID: 45755727, BOARD: generic, EABI: aarch64, DATE: Mon Jun  1 09:28:48 PM UTC 2026
# KERNEL_VARIANT: oot
TARGET_USERSPACE_LIB_DIR=nvidia
TARGET_USERSPACE_LIB_DIR_PATH=usr/lib/aarch64-linux-gnu/nvidia
- CUDA (nvcc): release 13.2
- nvpmodel: NV Power Mode: MAXN 0 
- jetson_clocks --show:
```
SOC family:tegra234  Machine:NVIDIA Jetson AGX Orin Developer Kit
Online CPUs: 0-11, Offline CPUs: 
cpu0:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu1:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu2:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu3:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu4:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu5:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu6:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu7:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu8:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu9:  Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu10: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
cpu11: Governor=schedutil MinFreq=2201600 MaxFreq=2201600 CurrentFreq=2201600 IdleStates: WFI=0 c7=0 
GPU MinFreq=1300500000 MaxFreq=1300500000 CurrentFreq=1300500000
Active GPU TPCs: 8
EMC MinFreq=3199000000 MaxFreq=3199000000 CurrentFreq=3199000000
DLA0_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA0_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
DLA1_CORE:   Online=1 MinFreq=0 MaxFreq=1600000000 CurrentFreq=1600000000
DLA1_FALCON: Online=1 MinFreq=0 MaxFreq=844800000 CurrentFreq=844800000
PVA0_VPS0: Online=1 MinFreq=0 MaxFreq=1369600000 CurrentFreq=1369600000
PVA0_AXI:  Online=1 MinFreq=0 MaxFreq=985600000 CurrentFreq=985600000
FAN Dynamic Speed Control=disabled hwmon2_pwm1=255
FAN Dynamic Speed Control=disabled hwmon2_pwm1_enable=1
NV Power Mode: MAXN
```
- SoC temp (thermal_zone0): 50 C
