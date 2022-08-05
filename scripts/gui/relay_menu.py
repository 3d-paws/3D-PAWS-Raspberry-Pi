#!/usr/bin/python3
# Code for the relay menu
# Joseph Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import wx, os
from crontab import CronTab

class ChangeRelay(wx.Dialog):
    def __init__(self, parent):
        super(ChangeRelay, self).__init__(parent)
        self.relay = 'false'
        cron = CronTab(user='root')
        for job in cron:
            if job.comment == 'relay':
                if job.is_enabled():
                    self.relay = 'true'
                break
        self.InitUI()
        self.SetTitle("Relay Menu")


    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        # Add explanation text
        vbox.Add(wx.StaticText(panel, label="Here you can control the relay, which resets the i2c"), flag=wx.LEFT|wx.TOP|wx.RIGHT, border=15)
        vbox.Add(wx.StaticText(panel, label="sensors every midnight. You can also activate the"), flag=wx.LEFT|wx.RIGHT, border=15)
        vbox.Add(wx.StaticText(panel, label="relay now if you need a quick reset."), flag=wx.LEFT|wx.BOTTOM|wx.RIGHT, border=15)
        # Make a horizontal line
        line = wx.StaticLine(panel)
        vbox.Add(line, flag=wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND, border=7)
        # Add Relay option
        relay_section = wx.BoxSizer(wx.HORIZONTAL)
        relay_section.Add(wx.StaticText(panel, label=""), flag=wx.RIGHT, border=40)
        relay_section.Add(wx.StaticText(panel, label="Relay"), flag=wx.ALL, border=10)
        self.relay_toggle = wx.ToggleButton(panel, label="")
        self.relay_toggle.SetToolTip("Turns on the relay to reset i2c sensors daily.") 
        if self.relay.lower() == "true":
            self.relay_toggle.SetLabel("On")
            self.relay_toggle.SetValue(True)
        else:
            self.relay_toggle.SetLabel("Off")
        relay_section.Add(self.relay_toggle, flag=wx.ALIGN_CENTER|wx.ALL, border=8)
        self.relay_toggle.Bind(wx.EVT_TOGGLEBUTTON, self.OnRelayToggle)
        vbox.Add(relay_section, flag=wx.LEFT, border=75)
        # Add Reset Now button
        reset_section = wx.BoxSizer(wx.HORIZONTAL)
        reset_section.Add(wx.StaticText(panel, label=""), flag=wx.RIGHT, border=40)
        self.reset = wx.Button(panel, label="Reset Now", size=(140,35))
        self.reset.SetToolTip("Activate the relay for 5 seconds, resetting i2c sensors.") 
        reset_section.Add(self.reset, flag=wx.ALIGN_CENTER|wx.ALL, border=8)
        self.reset.Bind(wx.EVT_BUTTON, self.OnReset)
        vbox.Add(reset_section, flag=wx.LEFT, border=75)
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


    def OnRelayToggle(self, e):
        if self.relay == "false":
            self.relay = "true"
            self.relay_toggle.SetLabel("On")
        else:
            self.relay = "false"
            self.relay_toggle.SetLabel("Off")


    def OnReset(self, e):
        self.reset.SetLabel("Resetting...")
        self.reset.Disable()
        os.system("sudo python3 /home/pi/3d_paws/scripts/upkeep/relay.py")
        self.reset.SetLabel("Reset!")


    def OnSave(self, e):
        cron = CronTab(user='root')
        for job in cron:
            if job.comment == "relay":
                if self.relay == "true":
                    job.enable()              
                else:
                    job.enable(False)
                cron.write()
                break
        self.Destroy()


    def OnCancel(self, e):
        self.Destroy()
