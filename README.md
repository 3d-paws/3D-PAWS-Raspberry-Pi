# 3D PAWS

3D PAWS is a Python3 library used to run the various sensors of a [3D-PAWS station](https://sites.google.com/ucar.edu/3dpaws/home), including the BMP280, BME280, HTU21d, MCP9808, AS5600, 55300-00-02-A, SS451A, and STH31D sensors. The software must be installed on a Raspberry Pi 3b, 3b+, or 4, which will control the sensors, data acquisition, archiving, data processing, and communication to remote data servers. Remote communications can be achieved through a wireless or cell-modem network.

## Step 1) Installation
### Using an OS Image
The 3D-PAWS OS and software are burned into a disk image. We recommend using this to setup your Raspberry Pi. Follow these steps to do so:

1. On any computer, download the [OS image](https://drive.google.com/file/d/1ck8N7d2CWNkj50k7m8lLqwNjnUSTWsCz/view?usp=sharing) and [Balena Etcher](https://etcher.balena.io/#download-etcher).

2. Unzip the OS image. 

3. Insert a micro-SD card to your computer that is at least 32 GB large (this will likely require a micro-SD to USB adapter).

4. Open Etcher, selecting "Flash from File". Navigate to your unzipped image; within that folder, you'll find the .img file (you may need to select "All files" instead of "Image files" in the bottom of the search window in order to see this) and select the SD card as the target. Note that you need at least a 32 GB micro-SD card.

5. Flash! 

6. Once complete, you'll want to update to the latest software version. Insert the SD card into a Raspberry Pi and turn it on. If it is connected to a monitor, keyboard, and mouse, it will boot into a desktop environment. Open a command terminal (make sure you're in /home/pi, which is the default when opening a terminal) and type

```bash
sudo python3 update_3d_paws.py
```

### Not Using OS Image
If you already have a fully functioning Raspberry Pi that you'd like to install the software on, you'll need to download and unpack it by using the following commands in order. If 3d-paws is already installed on your system, refer to the Update section instead.

```bash
cd /home/pi/
sudo apt-get install git
sudo git clone https://github.com/3d-paws/3d_paws
cd 3d_paws/
sudo python3 setup.py install
```

Once the 3D PAWS library is successfully installed, run the following command:

```bash
sudo python3 environment.py
```

Note: this will delete anything already in the cron (this is to ensure no issues occur when updating the 3D-PAWS software). If the pi is only used for 3d-paws (which is recommended) then this won't be an issue. 

## Step 2) Set Variables
The software will run without any changes made during this step. However, we recommend at least changing pressure level and altitude to ensure the data is accurate. You'll also want to activate CHORDS so the data is sent to the database. There are two ways of doing this.

Recommended Way: Launch the GUI (it has a shortcut on the desktop). In the GUI, there is a Settings button in the top left, containing 3 options. Click through each of them, changing any variables you need to. Descriptions for these variables are noted in the GUI.  

Other Way: Update the variables.txt file directly, which is located on your Desktop (/home/pi/Desktop). It is formatted as follows: 

    1. Toggle (either true or false) if you want to report to CHORDS.
    2. The station ID.
    3. Link to the correct CHORDS site
    4. The station's pressure level.
    5. Toggle (true or false) to determine if the station is in test mode, which will record data in second intervals based on the Recording interval (instead of in minute intervals)
    6. The station's altitude. This is set to a massive number by default; make sure to set this one correctly!

The list must remain comma-separated, with no spaces. 

## Step 3) Teamviewer
Teamviewer is used to connect remotely to your pi. If you run into trouble and need assistance, this is usually the way we can help, so it's important to get it setup. All you need to do is open a command terminal and run 

```bash
sudo python3 teamviewer.py
```

Once done, open Teamviewer by clicking the blue icon near the bottom right of the desktop. Go into Settings by clicking the gear icon (if the "Set easy access" popup is up, clicking the button there will also bring you to Settings). Go to the Advanced tab and scroll down to Personal Password. After entering the pi password (Wrf2Pi8!), type in whatever you choose, then hit Apply, then OK. 

You're all set! Make note of your Teamviewer ID so you'll be able to connect.

## Step 4) Operating the Station
### Activating Sensors
Open the GUI from the desktop, and simply toggle "on" each sensor that you wish to activate. If a restart is required, the GUI will alert you.

### Remote Viewing
If you need to remote into the pi, there are multiple ways to do so. Our recommended way is Teamviewer, which you hopefully just setup. But there are two other ways:

1. SSH (requires pi's ip address)
```bash
username: pi
password: Wrf2Pi8!
```

2. AnyDesk (requires pi's AnyDesk id)
```bash
password: 3d_paws!
```

### Running Tests
Open a terminal, and navigate to where the scripts are located.
```bash
cd /3d-paws/scripts/sensors
```

This folder contains all sensor scripts. You can run any of them by typing "sudo python3" followed by the name of the script. For example: 
```bash
sudo python3 bmp_bme.py
```

Note that the rain and two wind sensors show data every minute while doing this. You can add a number after the command to have the code instead run after that many seconds. For example, if you want to test the tipping bucket every 5 seconds, type
```bash
sudo python3 rain.py 5
```

If instead, you would like all sensors to run in sub-minute intervals, you can activate test mode. While in test mode, the station will not report to CHORDS, the interval value will be interpreted in seconds instead of minutes, and all data recorded are stored in the tests/ subfolder of data/.

You can activate test mode by toggling it on in the Intervals Menu of the GUI, or by switching the 7th value in variables.txt to true. You may need to restart the Raspberry Pi in order for the changes to take effect (this is true for deactivating test mode as well).

### Finding the Data
If the option is activated, the pi will report to CHORDS and/or backup data to the RAL server. If you want to locate your data locally, you can find it in /home/pi/data/. Data gathered over a 24-hour period are stored into a single file.

## Update
The software will update itself every Monday morning at midnight UTC. To force an update sooner, open a terminal (make sure you're in /home/pi, which is the default when opening a terminal) and type 
```bash
sudo python3 update_3d_paws.py
```

## Troubleshooting
If a sensor isn't recording data, try the following steps:

1. Run a software update (as shown above).

2. Check if the sensor is connected. Open the command line and type
```bash
i2cdetect -y 0
```

If the sensor's address isn't listed, it isn't plugged in correctly. Check the connections. Below are the sensors' addresses. If it isn't listed, the sensor isn't I2C and can't be detected in this way.
MCP9808: 0x18 
HTU21D: 0x40 
SHT31d: 0x44 or 0x45
SI1145: 0x60
BMP/BME 280: 0x77

3. Check if it's recording data.
```bash
cd /home/pi/3d_paws/scripts/sensors/
```

Run the script for that sensor. For example, 
```bash
sudo python3 mcp9808.py
```

Note that doing so will double up on reporting; you should consider switching off the sensor in the GUI. If there's an error, email it to Joey Rener at jrener@ucar.edu

4. Check if there is an issue with the reporting script.
```bash
cd /home/pi/3d_paws/scripts/upkeep/
sudo python3 report.py
```

5. Any errors that happen will be logged in the files in /tmp. For example, to look at the log file for the HTU21d sensor:
```bash
cd /tmp
more htu21d.log
```

6. If all else fails, please email both Paul Kucera (pkucera@ucar.edu) and Joey Rener (jrener@ucar.edu) for assistance.

## License
[MIT](https://choosealicense.com/licenses/mit/)
