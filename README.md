# 3D-PAWS

3D-PAWS is a Python3 library used to run the various sensors of a 3D-PAWS station. This library supports the following sensors: BMP280, BME280, HTU21d, MCP9808, AS5600, 55300-00-02-A, and SS451A. Note that you need to install this software on a raspberry pi in order for it to work.

## Installation

Use [github](https://github.com/) to install 3D-PAWS. Install git with the following in the command line:

```bash
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install git
```

Once that's done, install 3D-PAWS and its dependancies with:
```bash
cd /home/pi/
git clone https://github.com/3d-paws/3d-paws
cd 3d-paws/
sudo python3 setup.py install
```

## Setup
### Step 1 - Setup the Environment (edit crontab and create variables file)
Once the 3D-PAWS library is installed, run the following commands:
```bash
sudo python3 environment.py
```
Note: this step will delete anything already in the cron (this is to ensure no issues occur when updating the 3D-PAWS software). 

### Step 3 - Create a Shortcut
If you would like to make a desktop shortcut:

In the File manager -> Edit -> Preferences -> General -> "Do not ask option on executable launch"

Make a file called 3d_paws.desktop on your Desktop (/home/pi/Desktop)
Open it, and paste the following in:
```bash
[Desktop Entry]
Version=1.1
Type=Application
Encoding=UTF-8
Name=3D-PAWS
Comment=OpenGL demotool
Icon=/home/pi/3d-paws/3d_paws_icon.png
Exec=sudo python3 /home/pi/3d-paws/scripts/main.py
Terminal=false
Categories=Graphics
```

### Step 3 - Set Vairables
You'll want to change your station vairables in order for accurate readings, specific recording intervals, and to activate CHORDS. There are two ways of doing this: 

The first is the recommended way. Launch the GUI (see the Usage header in this document for instructions on that). In the GUI, there is a Settings button in the top left. It contains 3 options. Click through each of them, changing any variables you need to. Descriptions for these variables are noted in the GUI.  

The second option is to update the variables.txt file directly, which is on located your Desktop (/home/pi/Desktop). It is formatted as follows: recording_interval,chords_interval,chords_on/off,chords_id,chords_site,pressure_level,test_mode,altitude.

In either case, the software will run without any changes made during this step. However, we recommend changing pressure level and altitude to ensure the data is accurate. 

### Step 4 - Install Teamviewer
In order for us to debug future issues, we recommend installing [Teamviewer](https://www.teamviewer.com/en-us/?utm_source=google&utm_medium=cpc&utm_campaign=us|b|pr|19|jul|Brand-TeamViewer-Exact|free|t0|0|dl|g&utm_content=TeamViewer_Exact&utm_term=teamviewer&gclid=CjwKCAjwqauVBhBGEiwAXOepkaUDmfKPy7NqY8tIiuxn6tcV3Q-74NOweONXAebWNg_R0GERunuaYxoCKhkQAvD_BwE). This can be done on their site, or by executing the following commands:
```bash
wget https://download.teamviewer.com/download/linux/teamviewer-host_armhf.deb
sudo dpkg -i teamviewer-host_armhf.deb
sudo apt --fix-broken install
```

## Usage
You can either launch the GUI from the desktop if you made a shortcut, or from the terminal.
```python
cd /home/pi/3d-paws/scripts
sudo python3 main.py
```

## Updates
To update the software, you'll need to delete the 3d-paws/ folder and reclone it by following the below steps. This will not change your variables.txt file.
```python
cd /home/pi/
sudo rm -rf 3d-paws
git clone https://github.com/3d-paws/3d-paws
cd 3d-paws/
sudo python3 setup.py install
```

## License
[MIT](https://choosealicense.com/licenses/mit/)