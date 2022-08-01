#!/usr/bin/python3
# Code for the sensor-controlling UI
# Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

logs = '/home/pi/3d_paws/logs/'
scripts = '/home/pi/3d_paws/scripts/'

import sys
sys.path.insert(0, scripts)
from crontab import CronTab
import wx.lib.scrolledpanel as scrolled
import helper_functions, wx, barometric_menu, interval_menu, backup_menu, data_modal, os

# Used to give each start/stop toggle button a referenceable id
SENSOR_IDS = {
    "BMP/BME":wx.Window.NewControlId(),
    "HTU21D":wx.Window.NewControlId(),
    "MCP9808":wx.Window.NewControlId(),
    "SI1145":wx.Window.NewControlId(),
    "Tipping Bucket":wx.Window.NewControlId(),
    "Wind Direction":wx.Window.NewControlId(),
    "Wind Speed":wx.Window.NewControlId()
}
    #"Remote Stations":wx.Window.NewControlId()

# Used to give each data button a referenceable id
DATA_IDS = {
    "BMP/BME":wx.Window.NewControlId(),
    "HTU21D":wx.Window.NewControlId(),
    "MCP9808":wx.Window.NewControlId(),
    "SI1145":wx.Window.NewControlId(),
    "Tipping Bucket":wx.Window.NewControlId(),
    "Wind Direction":wx.Window.NewControlId(),
    "Wind Speed":wx.Window.NewControlId()
}
    #"Remote Stations":wx.Window.NewControlId()

# List of sensors that require a restart to toggle on/off
RESTART_REQUIRED = [
    "Tipping Bucket",
    "Wind Direction",
    "Wind Speed"
]

# Create UI
class Window(wx.Frame):
    def __init__(self, *args, **kwargs):
        super(Window, self).__init__(*args, **kwargs)
        self.restart = False
        self.remote_station = False
        self.restart_list = []
        self.active_sensors = []
        self.InitMenu()
        self.InitUI()
        self.Centre()
        self.SetTitle('3D-PAWS Controller')


    def SetStatusBar(self):
        # Get user vairables from file and show them in status bar
        self.inputs = helper_functions.getArguments()
        self.status_bar.SetStatusText(str(self.inputs[7]) + " m", 1)
        # Handle interval
        time = "min"
        if self.inputs[6] == "true":
            time = "sec"
        self.status_bar.SetStatusText("Record: " + str(self.inputs[0]) + " " + time, 2)
        # Handle chords
        if self.inputs[2] == "true":
            self.status_bar.SetStatusText("CHORDS: " + str(self.inputs[1]) + " min (on)", 3)
        else:
            self.status_bar.SetStatusText("CHORDS: " + str(self.inputs[1]) + " min (off)", 3)
        self.status_bar.SetStatusText("ID: " + str(self.inputs[3]), 4)


    def InitMenu(self):
        # Create a Settings menu
        menubar = wx.MenuBar()
        settingsMenu = wx.Menu()
        # Create Barometric menu option
        barometric_item = settingsMenu.Append(wx.Window.NewControlId(), 'Barometric Values')
        self.Bind(wx.EVT_MENU, self.OpenBarometricOptions, barometric_item)
        # Create Interval menu option
        interval_item = settingsMenu.Append(wx.Window.NewControlId(), 'Intervals')
        self.Bind(wx.EVT_MENU, self.OpenIntervalOptions, interval_item)
        # Create CHORDS menu option
        chords_item = settingsMenu.Append(wx.Window.NewControlId(), 'Backup Menu')
        self.Bind(wx.EVT_MENU, self.OpenBackupOptions, chords_item)
        # Add finished Settings menu to the menu bar
        menubar.Append(settingsMenu, 'Settings')
        self.SetMenuBar(menubar)


    def InitUI(self):
        # Bind onQuit function to when the window is closed
        self.Bind(wx.EVT_CLOSE, self.OnQuit)
        # Setup the window
        panel = wx.Panel(self)
        # Setup the scrolling panel
        scrolled_panel = scrolled.ScrolledPanel(panel, -1, style = wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER, name="panel1")
        scrolled_panel.SetAutoLayout(1)
        scrolled_panel.SetupScrolling()
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(5)
        # Sort SENSOR_IDS dictionary, then create a row of options for each one
        sorted_sensors = sorted(SENSOR_IDS.items(), key=lambda x: x[1], reverse=True)
        for sensor in sorted_sensors:
            self.AddRow(scrolled_panel, sizer, sensor[0])
        # Set alert if the system needs to be restarted
        self.restart_alert = wx.StaticText(scrolled_panel, label="")
        self.restart_alert.SetForegroundColour(wx.Colour(255,0,0))
        sizer.Add(self.restart_alert, flag=wx.LEFT, border=60)
        # Create button area
        button_area = wx.BoxSizer(wx.HORIZONTAL)
        # Create Start All button
        start_all_button = wx.Button(scrolled_panel, label="Start All")
        button_area.Add(start_all_button, flag=wx.LEFT, border=20)
        self.Bind(wx.EVT_BUTTON, self.StartAllSensors, id=start_all_button.GetId())
        # Create Stop All button
        stop_all_button = wx.Button(scrolled_panel, label="Stop All")
        button_area.Add(stop_all_button, flag=wx.LEFT, border=10)
        self.Bind(wx.EVT_BUTTON, self.StopAllSensors, id=stop_all_button.GetId())
        # Create Restart button
        restart_button = wx.Button(scrolled_panel, label="Restart")
        button_area.Add(restart_button, flag=wx.LEFT, border=215)
        self.Bind(wx.EVT_BUTTON, self.ConfirmRestart, id=restart_button.GetId())
        # Add space to the right of the buttons
        button_area.AddSpacer(25)
        # Add button area to window
        sizer.Add(button_area, flag=wx.TOP, border=10)
        # Initialize the status bar
        self.status_bar = self.CreateStatusBar(5)
        self.status_bar.SetStatusWidths([0, -3, -3, -5, -2])
        self.SetStatusBar()
        # Finalize
        scrolled_panel.SetSizer(sizer)
        sizer.Fit(self)
        panelSizer = wx.BoxSizer(wx.VERTICAL)
        panelSizer.Add(scrolled_panel, 1, wx.EXPAND)
        panel.SetSizer(panelSizer)
        panel.SendSizeEvent()


    def AddRow(self, panel, sizer, text):
        row = wx.BoxSizer(wx.HORIZONTAL)
        # Add text
        sensor_name = wx.StaticText(panel, label=text)
        sensor_name.SetFont(wx.Font(12, wx.DECORATIVE, wx.NORMAL, wx.NORMAL))
        row.Add(sensor_name, 2, flag=wx.ALL, border=20)
        # Create button area
        button_area = wx.BoxSizer(wx.HORIZONTAL)
        # Add data button
        data_button = wx.Button(panel, DATA_IDS[text], label="Data", size=((80, 40)))
        button_area.Add(data_button, flag=wx.RIGHT, border=10)
        self.Bind(wx.EVT_BUTTON, self.OpenData, id=DATA_IDS[text])
        # Check if this sensor is already enabled in the cron
        status = False
        label = "Off"
        cron = CronTab(user='root')
        for job in cron:
            if job.comment == text:
                status = job.is_enabled()
                if status:
                    label = "On"
                    self.active_sensors.append(text)
                break
        # Add On/Off toggle button
        toggle = wx.ToggleButton(panel, SENSOR_IDS[text], label=label, size=((80, 40)))
        toggle.SetValue(status)
        button_area.Add(toggle, flag=wx.RIGHT)
        self.Bind(wx.EVT_TOGGLEBUTTON, self.ToggleSensor, id=SENSOR_IDS[text])
        # Add button area to row
        row.Add(button_area, 1, flag=wx.TOP|wx.BOTTOM|wx.ALIGN_RIGHT, border=10)
        # Add row to window
        sizer.Add(row)
        # Make a horizontal line
        sizer.Add(wx.StaticLine(panel), flag=wx.ALL|wx.EXPAND, border=5)


    def OpenBarometricOptions(self, e):
        cdDialog = barometric_menu.ChangeBarometric(None)
        cdDialog.ShowModal()
        self.SetStatusBar()
        cdDialog.Destroy()


    def OpenIntervalOptions(self, e):
        cdDialog = interval_menu.ChangeInterval(None)
        cdDialog.ShowModal()
        self.SetStatusBar()
        cdDialog.Destroy()


    def OpenBackupOptions(self, e):
        cdDialog = backup_menu.ChangeChords(None)
        cdDialog.ShowModal()
        self.SetStatusBar()
        cdDialog.Destroy()


    def OpenData(self, e):
        sensor = [key for (key, value) in DATA_IDS.items() if value == e.GetId()][0]
        cdDialog = data_modal.ShowData(None, sensor)
        cdDialog.ShowModal()
        cdDialog.Destroy()
    

    def ToggleSensor(self, e):
        # Find the sensor in the cron and toggle its enabled status
        button = e.GetEventObject()
        sensor = [key for (key, value) in SENSOR_IDS.items() if value == e.GetId()][0]
        cron = CronTab(user='root')
        for job in cron:
            if job.comment == sensor:
                if button.GetValue() == True:
                    button.SetLabel("On")
                    job.enable()
                    self.active_sensors.append(sensor)
                    if sensor == "Remote Stations":
                        f = open(logs + 'remote_stations_check',"w+")
                        f.close()
                        os.system('sudo ' + scripts + 'comms/rf95/remote_stations_server -d') #start the remote bucket daemon
                        self.remote_station = True                 
                else:
                    button.SetLabel("Off")
                    job.enable(False)
                    self.active_sensors.remove(sensor)
                    if sensor == "Remote Stations":
                        if os.path.exists(logs + 'remote_stations_check'):
                            os.remove(logs + 'remote_stations_check')
                        os.system('sudo pkill -f remote_stations_server') #stop the remote bucket daemon
                        self.remote_station = False
                cron.write()
                break
        self.RestartCheck(sensor)

    
    def StartAllSensors(self, e):
        cron = CronTab(user='root')
        # Enable all sensors in cron
        for job in cron:
            if job.comment in SENSOR_IDS:
                job.enable()
        # Toggle all buttons to On and start the remote bucket daemon
        for sensor, id in SENSOR_IDS.items():
            button = self.FindWindowById(id) 
            button.SetLabel("On")
            button.SetValue(True)
            if sensor not in self.active_sensors:
                self.active_sensors.append(sensor)
                if sensor == "Remote Stations":
                    f = open(logs + 'remote_stations_check',"w+")
                    f.close()
                    os.system('sudo ' + scripts + 'comms/rf95/remote_stations_server -d')
                self.RestartCheck(sensor)
        cron.write()
        self.remote_station = True


    def StopAllSensors(self, e):
        cron = CronTab(user='root')
        # Disable all sensors in cron
        for job in cron:
            if job.comment in SENSOR_IDS:
                job.enable(False)
        # Toggle all buttons to Off and stop the remote bucket daemon
        for sensor, id in SENSOR_IDS.items():
            button = self.FindWindowById(id) 
            button.SetLabel("Off")
            button.SetValue(False)
            if sensor in self.active_sensors:
                self.active_sensors.remove(sensor)
                if sensor == "Remote Stations":
                    if os.path.exists(logs + 'remote_stations_check'):
                        os.remove(logs + 'remote_stations_check')
                    os.system('sudo pkill -f remote_stations_server')
                self.RestartCheck(sensor)
        cron.write()
        self.remote_station = False


    def RestartCheck(self, sensor):
        # If a sensor that requires a restart is turned on/off, tell the user
        if sensor in RESTART_REQUIRED:
            if sensor in self.restart_list:
                # If the sensor is returning to its original state, remove note
                self.restart_list.remove(sensor)
                if len(self.restart_list) == 0:
                    self.restart = False
                    self.restart_alert.SetLabel("")
            else:
                # Otherwise, let user know
                self.restart_list.append(sensor)
                self.restart = True
                self.restart_alert.SetLabel("You need to restart in order for the changes to take effect.")


    def ConfirmRestart(self, e):
        if not self.restart:
            dial = wx.MessageDialog(None, 'Are you sure you want to restart the pi? None of the selected sensors require it.', 'Confirm Restart', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
            ret = dial.ShowModal()
            if ret == wx.ID_YES:
                if self.remote_station:
                    self.Reminder()
                else:
                    os.system('sudo shutdown -r now')
        else:
            if self.remote_station:
                self.Reminder()
            else:
                os.system('sudo shutdown -r now')
    

    def OnQuit(self, e):
        if self.restart:
            # If the user is trying to quit but a restart is required
            dial = wx.MessageDialog(None, "Some of your selected sensors require a restart. Would you like to do so now? (Otherwise, those sensors won't be activated.)", 'Restart Recommended', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
            ret = dial.ShowModal()
            if ret == wx.ID_YES:
                if self.remote_station:
                    self.Reminder()
                else:
                    os.system('sudo shutdown -r now')
            else:
                # If the UI is closed without restarting, sensors that require a restart will be turned off.
                cron = CronTab(user='root')
                for job in cron:
                    if job.comment in RESTART_REQUIRED:
                        job.enable(False)
                cron.write()
                self.Destroy()
        else:
            self.Destroy()


    def Reminder(self):
        dial = wx.MessageDialog(None, 'Remember to relaunch this program to make sure everything launched successfully!', 'Alert', wx.OK | wx.CANCEL)
        ret = dial.ShowModal()
        print(ret)
        if ret == wx.ID_OK:
            os.system('sudo shutdown -r now')


def main():
    # Initialize application object
    app = wx.App() 
    # Create basic window
    window = Window(None)
    window.Show()
    # Show app
    app.MainLoop()

if __name__ == '__main__':
    main()