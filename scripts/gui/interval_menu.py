#!/usr/bin/python3
# Code for the interval menu
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import wx, helper_functions
from crontab import CronTab

class ChangeInterval(wx.Dialog):
    def __init__(self, parent):
        super(ChangeInterval, self).__init__(parent)
        inputs = helper_functions.getVariables()
        self.test_toggle = str(inputs[0]).lower()
        self.chords_id = str(inputs[1])
        self.chords_link = str(inputs[2])
        self.pressure_level = str(inputs[3])
        self.altitude = str(inputs[4])
        cron = helper_functions.getCron()
        self.record_interval = cron[0]
        self.chords_interval = cron[1]
        self.chords_toggle = cron[2]
        self.InitUI()
        self.SetTitle("Interval Menu")


    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        # Add explanation text
        vbox.Add(wx.StaticText(panel, label="Here you can change how often sensors record locally"), flag=wx.LEFT|wx.TOP|wx.RIGHT, border=15)
        vbox.Add(wx.StaticText(panel, label="and to CHORDS. They should be between 1 and 59 minutes."), flag=wx.LEFT|wx.RIGHT, border=15)
        vbox.Add(wx.StaticText(panel, label="Test mode changes this from minutes to seconds."), flag=wx.LEFT|wx.BOTTOM|wx.RIGHT, border=15)
        # Make a horizontal line
        line = wx.StaticLine(panel)
        vbox.Add(line, flag=wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND, border=7)
        # Add Test Mode option
        test_section = wx.BoxSizer(wx.HORIZONTAL)
        test_section.Add(wx.StaticText(panel, label="Test Mode"), flag=wx.ALL, border=10)
        test_section.Add(wx.StaticText(panel, label=""), flag=wx.RIGHT, border=45)
        self.toggle = wx.ToggleButton(panel, label="")
        self.toggle.SetToolTip("Test mode changes Record Interval to seconds and deactivates CHORDS.") 
        if self.test_toggle == "true":
            self.toggle.SetLabel("On")
            self.toggle.SetValue(True)
        else:
            self.toggle.SetLabel("Off")
        test_section.Add(self.toggle, flag=wx.ALIGN_CENTER|wx.ALL, border=8)
        self.toggle.Bind(wx.EVT_TOGGLEBUTTON, self.OnTestToggle)
        vbox.Add(test_section, flag=wx.LEFT, border=75)
        # Add RECORD input
        record_section = wx.BoxSizer(wx.HORIZONTAL)
        record_section.Add(wx.StaticText(panel, label="Record Interval"), flag=wx.ALL, border=10)
        record_section.Add(wx.StaticText(panel, label=""), flag=wx.RIGHT, border=13)
        record_section.Add(wx.StaticText(panel, label=""), flag=wx.RIGHT, border=6)
        self.record_interval_input = wx.SpinCtrl(panel, value=str(self.record_interval), min=1, max=59)
        record_section.Add(self.record_interval_input, flag=wx.TOP, border=3)
        vbox.Add(record_section, flag=wx.LEFT, border=75)
        # Add CHORDS input
        chords_section = wx.BoxSizer(wx.HORIZONTAL)
        chords_section.Add(wx.StaticText(panel, label="CHORDS Interval"), flag=wx.ALL, border=10)
        self.chords_interval_input = wx.SpinCtrl(panel, value=str(self.chords_interval), min=1, max=59)
        chords_section.Add(self.chords_interval_input, flag=wx.ALIGN_CENTER|wx.ALL, border=7)
        if self.test_toggle == "true":
            self.chords_interval_input.Enable(False)
        vbox.Add(chords_section, flag=wx.LEFT, border=75)
        # Make a horizontal line
        line = wx.StaticLine(panel)
        vbox.Add(line, flag=wx.LEFT|wx.TOP|wx.RIGHT|wx.EXPAND, border=7)
        # Add save and cancel buttons
        button_area = wx.BoxSizer(wx.HORIZONTAL)
        self.save_button = wx.Button(panel, label='Save')
        self.save_button.Bind(wx.EVT_BUTTON, self.OnSave)
        button_area.Add(self.save_button, flag=wx.RIGHT, border=5)
        self.cancel_button = wx.Button(panel, label='Cancel')
        self.cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)
        button_area.Add(self.cancel_button)
        vbox.Add(button_area, flag=wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, border=15)
        # Adjust window size to fit content
        panel.SetSizer(vbox)
        vbox.Fit(self)


    def OnTestToggle(self, e):
        if self.test_toggle == "false":
            self.test_toggle = "true"
            self.toggle.SetLabel("On")
            self.chords_interval_input.Enable(False)
            self.chords_toggle = False
            self.record_interval_input.Enable(False)
            self.save_button.SetToolTip("Make sure to restart the sensors so they'll run in Test Mode.") 
        else:
            self.test_toggle = "false"
            self.toggle.SetLabel("Off")
            self.chords_interval_input.Enable(True)
            self.save_button.SetToolTip(None)
            self.record_interval_input.Enable(True)


    def OnSave(self, e):
        chords_interval = self.chords_interval_input.GetValue()
        # Sanity Check
        if self.test_toggle == "true":
            record_interval = 1
        else:
            record_interval = int(self.record_interval_input.GetValue())
            if chords_interval < record_interval:
                chords_interval = record_interval
        # Set cron
        cron = CronTab(user='root')
        for job in cron:
            if "report" in job.comment or "sensor" in job.comment:
                job.minute.every(record_interval)
            elif "chords" in job.comment:
                job.minute.every(chords_interval)
                job.enable(self.chords_toggle)
        cron.write()
        # Write file
        with open("/home/pi/Desktop/variables.txt", 'w') as file:
            file.write(self.test_toggle + "," + self.chords_id + "," + self.chords_link + "," + str(self.pressure_level) + "," + str(self.altitude))
        self.Destroy()


    def OnCancel(self, e):
        self.Destroy()
