\# Full firmware



This is the firmware that includes the UF2 bootloader. When the bootloader seems to be broken (pressing twice on the reset button, does not show a UF2 drive), you can restore the bootloader, and the firmware in one go.



\## WCHISPTool



This is a tool provided by WCH to flash the CH32v203 chip that is present in the line sensor module.



* Down the \[WCHISPTool from the WCH website](https://www.wch-ic.com/downloads/WCHISPTool\_Setup\_exe.html).
* Connect the line sensor using USB to you PC
* start the WCHISPTool
* press 'RESET' button while keeping 'BOOT0' pressed
* You should see a USB device with mac address appearing in the WCHISPTool
* Click on 'Remove Protect'
* press 'RESET' button while keeping 'BOOT0' pressed
* Select the firmware file `boot\_firmware\_ch32\_line\_v5\_7.bin` and press Download button
* remove line sensor from USB cable



When you reconnect the line sensor with USB you should see a blue scanning pattern.



\## Check UF2 bootloader



Now you should be able to set the line sensor module in UF2 mode by pressing the 'RESET' button twice with a short interval. A UF2 device should appear in your PC.



