# Firmware for LMS Line Sensor

Two versions of the firmware are available. 

* I2C version
  
    This version is recognised by scanning of the 8 NeoPixels in three different colors (red, green, blue). Use the QWIIC connectors to connect the sensor to a i2C master (such as the QWIIC port on the LMS-ESP32v2)
* uRemote version
  
    This version is recognised by 3 times scanning of the Neopixels in blue. Use the 2x3 header to connect the Line Sensor board to your EV3 hub (using the LMS-EV3-BREAKOUT board) ot to your Spike Prime hub.



## How to flash firmware on the Line Sensor board?

* connect the Line Sensor Board with USB to your PC.
* Press the RESET button twice in quick succession.
* A UF2 Mass storage device with name **CH32V UF2** device should appear in the File Manager of your PC.
* Select the I2C or uRemote UF2 firmware file and drag it into the UF2.
* This will flash the UF2 file into the flash memory. Wait until the firmware is flashed to the board. The UF2 Mass Storage device will disappear.
* When the neopixels are not scaning, disconnect and reconnect the USB.





