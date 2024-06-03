# 3D PAWS

3D PAWS is a Python3 library used to run the various sensors of a [3D-PAWS station](https://sites.google.com/ucar.edu/3dpaws/home). This library supports the following sensors: BMP280, BME280, HTU21d, MCP9808, AS5600, 55300-00-02-A, SS451A, and STH31D. Note that you need to install this software on a Raspberry Pi in order for it to work.

## Step 1) Installation
### Using an OS Image
We recommend using our OS image to setup your Raspberry Pi. Follow these steps to do so:

1. On any computer, download the [OS image](https://drive.google.com/file/d/1ck8N7d2CWNkj50k7m8lLqwNjnUSTWsCz/view?usp=sharing) and [Balena Etcher](https://etcher.balena.io/#download-etcher).

2. Unzip the OS image. 

3. Insert a micro-SD card to your computer that is at least 32 GB large (this will likely require a micro-SD to USB adapter).

4. Open Etcher, selecting "Flash from File". Navigate to your unzipped image; within that folder, you'll find the .img file (you may need to select "All files" instead of "Image files" in the bottom of the search window in order to see this) and select the SD card as the target. 

5. Flash! 

6. Once complete, you'll want to update to the latest software version. Insert the SD card into a Raspberry Pi and turn it on. Open a command terminal (make sure you're in /home/pi, which is the default when opening a terminal) and type

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
The software will run without any changes made during this step. However, we recommend at least changing pressure level and altitude to ensure the data is accurate. You'll also want to activate CHORDS so the data is is sent to the database. There are two ways of doing this.

Recommended Way: Launch the GUI (it has a shortcut on the desktop). In the GUI, there is a Settings button in the top left, containing 3 options. Click through each of them, changing any variables you need to. Descriptions for these variables are noted in the GUI.  

Other Way: Update the variables.txt file directly, which is on located your Desktop (/home/pi/Desktop). It is formatted as follows: recording_interval,chords_interval,chords_on/off,station_id,chords_site,pressure_level,test_mode,altitude. 

## Step 3) Teamviewer
Teamviewer is used to connect remotely to your pi. If you run into trouble and need assistance, this is usually the way we can help, so it's important to get it setup.

First, open a command terminal and run the following commands in sequence. This will generate your Teamviewer ID.

```bash
sudo systemctl stop teamviewerd
sudo rm -rf /etc/teamviewer/global.conf
sudo rm -rf /var/lib/teamviewer/config/global.conf
sudo rm /etc/machine-id
sudo systemd-machine-id-setup
sudo systemctl start teamviewerd
```

Once done, open Teamviewer by clicking the blue icon near the bottom right of the desktop. Go into Settings by clicking the gear icon (if the "Set easy access" popup is up, clicking the button there will also bring you to Settings). Go to the Advanced tab and scroll down to Personal Password. Type in whatever you choose, then hit Apply, then OK. 

You're all set! Make note of your Teamviewer ID so you'll be able to connect.

## Step 4) Usage
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

### Launching the Software
You can either launch the GUI from the desktop by double clicking the icon, or from the terminal.
```bash
sudo python3 /home/pi/3d_paws/scripts/gui/main.py
```

### Finding the Data
If the option is activated, the pi will report to CHORDS and/or backup data to the RAL server. If you want to locate your data locally, you can find it in /home/pi/data/. Data gathered over a 24-hour period are stored into a single file.

## Update
The software will update itself every Monday morning at midnight UTC. To force an update sooner, open a terminal (make sure you're in /home/pi, which is the default when opening a terminal) and type 

```bash
sudo python3 update_3d_paws.py
```

## Help
For any questions or problems you might have, please email both Paul Kucera (pkucera@ucar.edu) and Joey Rener (jrener@ucar.edu).

## License
[MIT](https://choosealicense.com/licenses/mit/)