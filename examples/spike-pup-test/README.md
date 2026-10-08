\# Simple Line test



\## setup

* Connect line sensor module using i2c to LMS-ESP32 using the QWIIC cable
* connect LMS-ESP32 to Spike prime on Port A



\## Load programs

\### LMS-ESP32

* start https://viper-ide.org/
* connect to lms-esp32
* create new program: `line\_sensor.py` 
* paste program from `Micropython/line\_sensor.py` and save
* create new program `main.py`.
* paste content of `examples/spike-pup-test/line\_esp32\_main.py` and save



\### Pybricks

* open `code.pybricks.com`
* create new program, name it `line\_sensor\_pybricks.py`
* paste content of `Micropython/line\_sensor\_pybricks.py`
* create new program, name it `line\_pybricks`
* paste prigram from `examples/spike-pup-test/line\_pybricks.py`



\## Running

* reset LMS-ESP32, so that `main.py` starts
* run `line\_pybricks.py` on Pybricks
* A count down counter is shown on the prime display.
* Press left button to calibrate the line sensor.

