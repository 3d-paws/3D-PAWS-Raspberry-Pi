#!/usr/bin/python
# Code for the chords menu
# Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import wx, helper_functions
from crontab import CronTab

class ChangeChords(wx.Dialog):
    def __init__(self, parent):
        super(ChangeChords, self).__init__(parent)
        inputs = helper_functions.getArguments()
        self.record_interval = str(inputs[0])
        self.chords_interval = str(inputs[1])
        self.chords_toggle = str(inputs[2])
        self.chords_id = str(inputs[3])
        self.chords_link = str(inputs[4])
        self.pressure_level = str(inputs[5])
        self.test_toggle = str(inputs[6])
        self.altitude = str(inputs[7])
        self.ral = 'false'
        cron = CronTab(user='root')
        for job in cron:
            if job.comment == 'RAL FTP':
                if job.is_enabled():
                    self.ral = 'true'
                break
        self.InitUI()
        self.SetTitle("CHORDS Menu")


    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        # Initialize alert and save button (but don't place them yet; this is so they can be referenced when id_input is made)
        self.alert = wx.StaticText(panel, label="")
        self.alert.SetForegroundColour(wx.Colour(255,0,0))
        self.saveButton = wx.Button(panel, label='Save')
        # Add explanation text
        vbox.Add(wx.StaticText(panel, label="By turning this on, you'll send data to the"), flag=wx.LEFT|wx.TOP|wx.RIGHT, border=15)
        vbox.Add(wx.StaticText(panel, label="Chords website if there is a connection."), flag=wx.LEFT|wx.RIGHT, border=15)
        vbox.Add(wx.StaticText(panel, label="Please email Paul Kucera (pkucera@ucar.edu)"), flag=wx.LEFT|wx.RIGHT, border=15)
        vbox.Add(wx.StaticText(panel, label="to obtain an ID."), flag=wx.LEFT|wx.BOTTOM|wx.RIGHT, border=15)
        # Make a horizontal line
        line = wx.StaticLine(panel)
        vbox.Add(line, flag=wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND, border=7)
        # Add toggle
        toggle_section = wx.BoxSizer(wx.HORIZONTAL)
        toggle_section.Add(wx.StaticText(panel, label="CHORDS"), flag=wx.ALL, border=10)
        toggle_section.Add(wx.StaticText(panel, label=""), flag=wx.RIGHT, border=20)
        self.toggle = wx.ToggleButton(panel, label="")
        if self.chords_toggle.lower() == "true":
            self.toggle.SetLabel("On")
            self.toggle.SetValue(True)
        else:
            self.toggle.SetLabel("Off")
            if self.test_toggle == "true":
                self.toggle.Enable(False)
                self.toggle.SetToolTip("CHORDS cannot be turned on while test mode is active; disable test mode in the Change Intervals menu.")
        toggle_section.Add(self.toggle, flag=wx.TOP, border=3)
        self.toggle.Bind(wx.EVT_TOGGLEBUTTON, self.OnChordsToggle)
        vbox.Add(toggle_section, flag=wx.LEFT, border=15)
        # Add ID input
        id_section = wx.BoxSizer(wx.HORIZONTAL)
        id_section.Add(wx.StaticText(panel, label="3D-PAWS ID"), flag=wx.ALIGN_LEFT|wx.ALL, border=10)
        self.id_input = wx.TextCtrl(panel, -1, style=wx.ALIGN_LEFT)
        self.Bind(wx.EVT_TEXT, self.OnEdit, self.id_input)
        self.id_input.SetValue(self.chords_id)
        id_section.Add(self.id_input, flag=wx.TOP, border=2)
        vbox.Add(id_section, flag=wx.LEFT, border=15)
        # Add link input
        link_section = wx.BoxSizer(wx.HORIZONTAL)
        link_section.Add(wx.StaticText(panel, label="http://"), flag=wx.ALIGN_LEFT|wx.ALL, border=8)
        self.link_input = wx.TextCtrl(panel, -1, size=(150, -1), style=wx.ALIGN_LEFT)
        self.Bind(wx.EVT_TEXT, self.OnLinkEdit, self.link_input)
        self.link_input.SetValue(self.chords_link)
        link_section.Add(self.link_input, flag=wx.TOP, border=2)
        link_section.Add(wx.StaticText(panel, label="/measurements/..."), flag=wx.ALIGN_LEFT|wx.ALL, border=8)
        vbox.Add(link_section, flag=wx.LEFT, border=15)

        """
        # Add RAL toggle
        toggle_section2 = wx.BoxSizer(wx.HORIZONTAL)
        toggle_section2.Add(wx.StaticText(panel, label="RAL FTP"), flag=wx.ALL, border=10)
        toggle_section2.Add(wx.StaticText(panel, label=""), flag=wx.RIGHT, border=20)
        self.toggle2 = wx.ToggleButton(panel, label="")
        if self.ral == "true":
            self.toggle2.SetLabel("On")
            self.toggle2.SetValue(True)
        else:
            self.toggle2.SetLabel("Off")
        toggle_section2.Add(self.toggle2, flag=wx.TOP, border=3)
        self.toggle2.Bind(wx.EVT_TOGGLEBUTTON, self.OnRalToggle)
        vbox.Add(toggle_section2, flag=wx.LEFT, border=15)
        """

        # Make a horizontal line
        line = wx.StaticLine(panel)
        vbox.Add(line, flag=wx.LEFT|wx.TOP|wx.RIGHT|wx.EXPAND, border=7)
        # Place alert
        vbox.Add(self.alert, flag=wx.ALIGN_CENTER)
        # Add save and cancel buttons
        button_area = wx.BoxSizer(wx.HORIZONTAL)
        self.saveButton.Bind(wx.EVT_BUTTON, self.OnSave)
        button_area.Add(self.saveButton, flag=wx.RIGHT, border=5)
        self.cancelButton = wx.Button(panel, label='Cancel')
        self.cancelButton.Bind(wx.EVT_BUTTON, self.OnCancel)
        button_area.Add(self.cancelButton)
        vbox.Add(button_area, flag=wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, border=10)
        # Adjust window size to fit content
        panel.SetSizer(vbox)
        vbox.Fit(self)


    def OnChordsToggle(self, e):
        if self.chords_toggle == "false":
            self.chords_toggle = "true"
            self.toggle.SetLabel("On")
        else:
            self.chords_toggle = "false"
            self.toggle.SetLabel("Off")


    def OnEdit(self, e):
        value = self.id_input.GetValue()
        try:
            int(value)
            self.chords_id = value
            self.alert.SetLabel("")
            self.saveButton.Enable(True)
        except (ValueError, TypeError):
            self.alert.SetLabel("ID must be an integer")
            self.saveButton.Enable(False)

    
    def OnLinkEdit(self, e):
        value = self.link_input.GetValue()
        if ".com" in value or ".gov" in value or ".org" in value:
            if value[-1] == "/":
                value = value[:-1]
            self.chords_link = value
            self.alert.SetLabel("")
            self.saveButton.Enable(True)
        else:
            self.alert.SetLabel("Link needs to end in .com, .gov, or .org")
            self.saveButton.Enable(False)

    
    def OnRalToggle(self, e):
        cron = CronTab(user='root')
        for job in cron:
            if job.comment == "RAL FTP":
                if self.ral == "false":
                    self.ral = "true"
                    self.toggle2.SetLabel("On")
                    job.enable()              
                else:
                    self.ral = "false"
                    self.toggle2.SetLabel("Off")
                    job.enable(False)
                cron.write()
                break


    def OnSave(self, e):
        with open("/home/pi/Desktop/variables.txt", 'w') as file:
            file.write(self.record_interval + "," + self.chords_interval + "," + self.chords_toggle + "," + str(int(self.chords_id)) + "," + self.chords_link + "," + self.pressure_level + "," + self.test_toggle + "," + str(self.altitude))
        self.Destroy()


    def OnCancel(self, e):
        self.Destroy()
