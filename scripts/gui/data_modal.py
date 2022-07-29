#!/usr/bin/python3
# Code for the modal that displays data per sensor
# Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import glob, os, wx, helper_functions
import wx.lib.scrolledpanel as scrolled

class ShowData(wx.Dialog):
    def __init__(self, parent, sensor):
        super(ShowData, self).__init__(parent)
        self.sensor = sensor
        # Get Arguments
        arguments = helper_functions.getArguments()
        test_toggle = arguments[6]
        # Grab the most recent data file and read its lines into a list
        if test_toggle == "true":
            list_of_files = glob.glob('/home/pi/data/tests/' + self.sensor + '*.dat')
        else:
            list_of_files = glob.glob('/home/pi/data/*.dat')
        if len(list_of_files) > 0:
            self.data = True
            latest_file = max(list_of_files, key=os.path.getctime)
            with open(latest_file) as f:
                self.content = f.readlines()
            # Only use the 5 most recent lines of data
            if len(self.content) > 5:
                self.content = self.content[-5:]
        # If there are no files found
        else:
            self.data = False
            self.content = ["There is no data for this sensor yet."]
        # Initialize the window
        self.InitUI()
        self.SetTitle(self.sensor + " Sensor Data")


    def InitUI(self):
        panel = wx.Panel(self)
        # Setup the scrolling panel
        scrolled_panel = scrolled.ScrolledPanel(panel, -1, style = wx.TAB_TRAVERSAL|wx.SUNKEN_BORDER, name="scroll")
        vbox = wx.BoxSizer(wx.VERTICAL)
        # Add description
        if self.sensor == "Remote Stations":
            sentence = "remote stations."
        else:
            sentence = self.sensor.lower() + " sensor."
        vbox.Add(wx.StaticText(scrolled_panel, label="These are the most recent data entries from the " + sentence + "     "), flag=wx.ALL, border=15)
        # Make a horizontal line
        line = wx.StaticLine(scrolled_panel)
        vbox.Add(line, flag=wx.LEFT|wx.BOTTOM|wx.RIGHT|wx.EXPAND, border=7)
        # Show data for the correct sensor
        if self.data == False:
            vbox.Add(wx.StaticText(scrolled_panel, label=self.content[0]), flag=wx.ALIGN_CENTER|wx.LEFT|wx.RIGHT, border=20)
        else:
            if self.sensor == "BMP/BME":
                start = 5
                end = 13
            elif self.sensor == "HTU21D":
                start = 14
                end = 15
            elif self.sensor == "MCP9808":
                start = 16
                end = 16
            elif self.sensor == "Tipping Bucket":
                start = 17
                end = 17
            elif self.sensor == "SI1145":
                start = 18
                end = 20
            elif self.sensor == "Wind Direction":
                start = 21
                end = 21
            elif self.sensor == "Wind Speed":
                start = 22
                end = 22
            for line in self.content:
                line_parts = (' '.join(line.replace("\n","").split())).split(" ")
                info = (str(line_parts[0 : 5]).replace(", "," ") + "  ->  " + str(line_parts[start : end+1])).replace("'", "").replace("[", "").replace("]", "")
                vbox.Add(wx.StaticText(scrolled_panel, label=info), flag=wx.ALIGN_CENTER|wx.LEFT|wx.RIGHT, border=20)
        # Make a horizontal line
        line = wx.StaticLine(scrolled_panel)
        vbox.Add(line, flag=wx.LEFT|wx.TOP|wx.RIGHT|wx.EXPAND, border=7)
        # Add close button
        self.closeButton = wx.Button(scrolled_panel, label='Close')
        self.closeButton.Bind(wx.EVT_BUTTON, self.OnClose)
        vbox.Add(self.closeButton, flag=wx.ALIGN_CENTER|wx.TOP, border=15)
        vbox.Add(wx.StaticText(scrolled_panel, label=""))
        # Finalize
        vbox.Fit(self)
        scrolled_panel.SetSizer(vbox)
        scrolled_panel.SetAutoLayout(1)
        scrolled_panel.SetupScrolling()
        panelSizer = wx.BoxSizer(wx.VERTICAL)
        panelSizer.Add(scrolled_panel, 1, wx.EXPAND)
        panel.SetSizer(panelSizer)
        panel.SendSizeEvent()


    def OnClose(self, e):
        self.Destroy()