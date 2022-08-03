# 3D PAWS

3D PAWS is a Python3 library used to run the various sensors of a 3D-PAWS station. This library supports the following sensors: BMP280, BME280, HTU21d, MCP9808, AS5600, 55300-00-02-A, and SS451A. Note that you need to install this software on a raspberry pi in order for it to work.

## Installation
If you're using our OS image (contact Paul Kucera at pkucera@ucar.edu for more information) then all you need to do in order to update to the latest software version is open a command terminal (make sure you're in /home/pi, which is the default when opening a terminal) and type

```bash
update_3d_paws.py
```

Once that's done, move on to Set Variables. If you want to update manually, continue to Manual Installation. 

### Manual Installation
You'll need to download and unpack the software by using the following commands in order. If 3d-paws is already installed on your system, refer to the Update section instead.

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

## Set Variables
You'll want to change your station vairables in order for accurate readings, specific recording intervals, and to activate CHORDS. There are two ways of doing this.

Recommended Way: Launch the GUI (it has a shortcut on the desktop). In the GUI, there is a Settings button in the top left, containing 3 options. Click through each of them, changing any variables you need to. Descriptions for these variables are noted in the GUI.  

Other Way: Update the variables.txt file directly, which is on located your Desktop (/home/pi/Desktop). It is formatted as follows: recording_interval,chords_interval,chords_on/off,station_id,chords_site,pressure_level,test_mode,altitude.

In either case, the software will run without any changes made during this step. However, we recommend at least changing pressure level and altitude to ensure the data is accurate. 

## Usage
You can either launch the GUI from the desktop by double clicking the icon, or from the terminal.
```bash
sudo python3 /home/pi/3d_paws/scripts/gui/main.py
```

If for some reason you don't have a desktop shortcut, you can make one. First, in the File manager, select Edit -> Preferences -> General -> "Do not ask option on executable launch"

Then right click the desktop, and make a file called 3d_paws.desktop
Open it, and paste the following in:
```bash
[Desktop Entry]
Version=1.1
Type=Application
Encoding=UTF-8
Name=3D_PAWS
Comment=3d paws gui
Icon=/home/pi/3d_paws/3d_paws_icon.png
Exec=sudo python3 /home/pi/3d_paws/scripts/gui/main.py
Terminal=false
Categories=Graphics
```

## Update
The software will update itself every Monday morning at midnight UTC. To force an update sooner, open a terminal (make sure you're in /home/pi, which is the default when opening a terminal) and type 

```bash
update_3d_paws.py
```

## License
[MIT](https://choosealicense.com/licenses/mit/)