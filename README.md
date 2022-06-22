# 3D-PAWS

3D-PAWS is a Python3 library used to run the various sensors of a 3D-PAWS station. This library supports the following sensors: BMP280, BME280, HTU21d, MCP9808, AS5600, 55300-00-02-A, and SS451A.

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install 3D-PAWS. First, check which syntax is correct for your system by typing the following in the command line:

```bash
python --version
```

If the result is version 3 or higher, install using 
```bash
sudo pip install 3d-paws
```
Otherwise, use
```bash
sudo pip3 install 3d-paws
```

## Setup
### Step 1 - Edit Crontab
Once the 3D-PAWS library is installed, run the following commands:
```bash
cd /home/pi/3d-paws/
sudo python3 update_cron.py
```

### Step 2 - Create a Shortcut
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
Icon=/home/pi/3d_paws/3d_paws_icon.png
Exec=sudo python3 /home/pi/3d_paws/scripts/main.py
Terminal=false
Categories=Graphics
```

### Step 3 - Install Teamviewer
In order for us to debug future issues, we recommend installing [Teamviewer](https://www.teamviewer.com/en-us/?utm_source=google&utm_medium=cpc&utm_campaign=us|b|pr|19|jul|Brand-TeamViewer-Exact|free|t0|0|dl|g&utm_content=TeamViewer_Exact&utm_term=teamviewer&gclid=CjwKCAjwqauVBhBGEiwAXOepkaUDmfKPy7NqY8tIiuxn6tcV3Q-74NOweONXAebWNg_R0GERunuaYxoCKhkQAvD_BwE). This can be done on their site, or by executing the following commands:
```bash
sudo apt-get update
sudo apt-get upgrade
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

## License
[MIT](https://choosealicense.com/licenses/mit/)
