#!/usr/bin/python3
# Code for the dashboard window that graphs the last 24 hours of readings from every sensor that is turned on
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import datetime, sys, wx
sys.path.insert(0, '/home/pi/3d_paws/scripts/')
import wx.lib.scrolledpanel as scrolled
from dashboard_data import HOURS, REFRESH_SECONDS, collectTiles, formatValue, ago

# Chart colors: one series color on a light surface, text in neutral inks
SURFACE = wx.Colour(252, 252, 251)
BACKGROUND = wx.Colour(240, 240, 237)
TEXT_PRIMARY = wx.Colour(11, 11, 11)
TEXT_SECONDARY = wx.Colour(82, 81, 78)
GRID = wx.Colour(225, 224, 219)
SERIES = wx.Colour(42, 120, 214)
WARNING = wx.Colour(138, 90, 0)


_fonts = {}

# Fonts can only be made once the app is running, so build them on first use
def font(name):
    if not _fonts:
        _fonts["tiny"] = wx.Font(wx.FontInfo(8))
        _fonts["small"] = wx.Font(wx.FontInfo(9))
        _fonts["unit"] = wx.Font(wx.FontInfo(11))
        _fonts["big"] = wx.Font(wx.FontInfo(20).Bold())
        _fonts["heading"] = wx.Font(wx.FontInfo(11).Bold())
    return _fonts[name]


# Break text into lines no wider than width pixels
def wrapText(window, text, font, width):
    lines = []
    line = ""
    for word in text.split():
        candidate = (line + " " + word).strip()
        if line and window.GetFullTextExtent(candidate, font)[0] > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    return lines


# One measurement: label, latest value, and a chart of the last 24 hours
class Tile(wx.Panel):
    MIN_WIDTH = 230
    CHART_HEIGHT = 60
    CHART_BOTTOM = 26
    SIDE = 12
    GUTTER = 44

    def __init__(self, parent, tile, width):
        super(Tile, self).__init__(parent)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.tile = tile
        self.width = width
        self.hover = None
        self.Measure()
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMotion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)


    def SetTile(self, tile):
        self.tile = tile
        self.Measure()
        self.Refresh()


    def SetWidth(self, width):
        if width != self.width:
            self.width = width
            self.Measure()
            self.Refresh()


    # Work out where each piece of text goes at the current width, wrapping anything that doesn't fit
    def Measure(self):
        small = font("small")
        line_height = self.GetFullTextExtent("Ag", small)[1] + 3
        inner = self.width - 2 * self.SIDE
        self.texts = []
        y = 10
        status = None
        if not self.tile.get("waiting"):
            when = self.tile["points"][-1][0]
            if self.tile["stale"]:
                status = ("⚠ Last reading " + ago(when), WARNING)
            else:
                status = (when.strftime("%H:%M UTC"), TEXT_SECONDARY)
        # Status goes beside the label when there is room, otherwise on its own line under it
        status_width = self.GetFullTextExtent(status[0], small)[0] if status else 0
        beside = status and inner - status_width - 8 >= 90
        if beside:
            self.texts.append((status[0], self.width - self.SIDE - status_width, y, small, status[1]))
            label_lines = wrapText(self, self.tile["label"], small, inner - status_width - 8)
        else:
            label_lines = wrapText(self, self.tile["label"], small, inner)
        for line in label_lines:
            self.texts.append((line, self.SIDE, y, small, TEXT_SECONDARY))
            y += line_height
        if status and not beside:
            for line in wrapText(self, status[0], small, inner):
                self.texts.append((line, self.SIDE, y, small, status[1]))
                y += line_height
        if self.tile.get("waiting"):
            y += 6
            for line in wrapText(self, "This sensor is on, but nothing has been recorded in the last %d hours." % HOURS, small, inner):
                self.texts.append((line, self.SIDE, y, small, TEXT_SECONDARY))
                y += line_height
            height = y + 12
        else:
            self.value_y = y + 4
            value_height = self.GetFullTextExtent("0", font("big"))[1]
            # Leave room above the chart for the hover readout
            self.chart_top = self.value_y + value_height + 22
            height = self.chart_top + self.CHART_HEIGHT + self.CHART_BOTTOM
        self.SetMinSize((self.width, height))
        self.SetSize((self.width, height))


    def ChartBox(self):
        w, h = self.GetClientSize()
        return self.SIDE + self.GUTTER, self.chart_top, w - 2 * self.SIDE - self.GUTTER, self.CHART_HEIGHT


    def Scale(self):
        points = self.tile["points"]
        if self.tile["kind"] == "direction":
            low, high = 0.0, 360.0
        else:
            values = [v for _, v in points]
            low, high = min(values), max(values)
            if self.tile["kind"] == "rain":
                low = 0.0
            if high - low < 1e-9:
                pad = max(abs(high) * 0.05, 1.0)
                low, high = low - pad, high + pad
        end = datetime.datetime.utcnow()
        start = end - datetime.timedelta(hours=HOURS)
        x, y, w, h = self.ChartBox()
        def toX(when):
            return x + w * (when - start).total_seconds() / (end - start).total_seconds()
        def toY(value):
            return y + h - h * (value - low) / (high - low)
        return toX, toY, low, high, start


    def OnPaint(self, e):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(SURFACE))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        gc.SetPen(wx.Pen(GRID, 1))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRoundedRectangle(0, 0, w - 1, h - 1, 8)
        for text, x, y, f, colour in self.texts:
            gc.SetFont(f, colour)
            gc.DrawText(text, x, y)
        if self.tile.get("waiting"):
            return
        # Latest value and units
        value = self.tile["points"][-1][1]
        gc.SetFont(font("big"), TEXT_PRIMARY)
        text = formatValue(self.tile, value)
        tw, th = gc.GetTextExtent(text)
        gc.DrawText(text, self.SIDE, self.value_y)
        if self.tile["unit"] and self.tile["kind"] != "direction":
            gc.SetFont(font("unit"), TEXT_SECONDARY)
            uw, uh = gc.GetTextExtent(self.tile["unit"])
            gc.DrawText(self.tile["unit"], self.SIDE + tw + 5, self.value_y + th - uh - 2)
        self.DrawChart(gc)


    def DrawChart(self, gc):
        points = self.tile["points"]
        toX, toY, low, high, start = self.Scale()
        x, y, cw, ch = self.ChartBox()
        tiny = font("tiny")
        # Recessive gridlines at the top and bottom of the range, labeled in the left margin
        gc.SetPen(wx.Pen(GRID, 1))
        gc.SetFont(tiny, TEXT_SECONDARY)
        for v in (low, high):
            gc.StrokeLine(x, toY(v), x + cw, toY(v))
            text = formatValue(self.tile, v, axis=True)
            tw, th = gc.GetTextExtent(text)
            gc.DrawText(text, x - tw - 6, toY(v) - th / 2)
        # Time axis: 24 hours ago on the left, now on the right
        gc.DrawText("%d h ago" % HOURS, x, y + ch + 6)
        label = "now"
        lw, lh = gc.GetTextExtent(label)
        gc.DrawText(label, x + cw - lw, y + ch + 6)
        # The series: dots for wind direction, otherwise a line that breaks where readings are missing
        gc.SetPen(wx.Pen(SERIES, 2))
        gc.SetBrush(wx.Brush(SERIES))
        if self.tile["kind"] == "direction":
            gc.SetPen(wx.TRANSPARENT_PEN)
            for when, v in points:
                gc.DrawEllipse(toX(when) - 2, toY(v) - 2, 4, 4)
        else:
            gap = self.tile["gap"]
            path = gc.CreatePath()
            previous = None
            for when, v in points:
                if previous is None or when - previous > gap:
                    path.MoveToPoint(toX(when), toY(v))
                else:
                    path.AddLineToPoint(toX(when), toY(v))
                previous = when
            gc.StrokePath(path)
        # Latest reading: a marker with a surface ring
        when, v = points[-1]
        self.DrawMarker(gc, toX(when), toY(v))
        # Hover / touch readout
        if self.hover is not None:
            when, v = points[self.hover]
            px, py = toX(when), toY(v)
            gc.SetPen(wx.Pen(TEXT_SECONDARY, 1))
            gc.StrokeLine(px, y, px, y + ch)
            self.DrawMarker(gc, px, py)
            text = "%s  %s %s" % (when.strftime("%H:%M"), formatValue(self.tile, v), self.tile["unit"] if self.tile["kind"] != "direction" else "")
            gc.SetFont(tiny, TEXT_PRIMARY)
            tw, th = gc.GetTextExtent(text.strip())
            bx = min(max(px - tw / 2 - 4, x), x + cw - tw - 8)
            gc.SetPen(wx.Pen(GRID, 1))
            gc.SetBrush(wx.Brush(SURFACE))
            gc.DrawRoundedRectangle(bx, y - 20, tw + 8, th + 4, 4)
            gc.DrawText(text.strip(), bx + 4, y - 18)


    def DrawMarker(self, gc, px, py):
        gc.SetPen(wx.Pen(SURFACE, 2))
        gc.SetBrush(wx.Brush(SERIES))
        gc.DrawEllipse(px - 5, py - 5, 10, 10)


    def OnMotion(self, e):
        if self.tile.get("waiting"):
            return
        toX, toY, low, high, start = self.Scale()
        mx = e.GetPosition()[0]
        xs = [toX(when) for when, _ in self.tile["points"]]
        nearest = min(range(len(xs)), key=lambda i: abs(xs[i] - mx))
        if nearest != self.hover:
            self.hover = nearest
            self.Refresh()


    def OnLeave(self, e):
        if self.hover is not None:
            self.hover = None
            self.Refresh()


class Dashboard(wx.Frame):
    def __init__(self, parent):
        super(Dashboard, self).__init__(parent, title="3D-PAWS Dashboard")
        self.SetBackgroundColour(BACKGROUND)
        self.tiles = {}
        self.layout = None
        self.tile_width = Tile.MIN_WIDTH
        self.summary_text = ""
        self.message = None
        # Open at most of the screen so the tiles have room, whatever the screen size
        area = wx.Display(0).GetClientArea()
        self.SetSize((min(1100, int(area.width * 0.9)), int(area.height * 0.85)))
        self.SetMinSize((320, 300))
        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(BACKGROUND)
        outer = wx.BoxSizer(wx.VERTICAL)
        # Top bar: what is shown, when it was updated, and a refresh button
        top = wx.BoxSizer(wx.HORIZONTAL)
        self.summary = wx.StaticText(self.panel, label="")
        self.summary.SetForegroundColour(TEXT_SECONDARY)
        top.Add(self.summary, 1, wx.ALIGN_CENTER_VERTICAL)
        self.refresh = wx.Button(self.panel, label="Refresh", size=(90, 36))
        self.refresh.Bind(wx.EVT_BUTTON, lambda e: self.Reload())
        top.Add(self.refresh, 0, wx.LEFT, 8)
        outer.Add(top, 0, wx.EXPAND | wx.ALL, 12)
        self.scroll = scrolled.ScrolledPanel(self.panel)
        self.scroll.SetBackgroundColour(BACKGROUND)
        outer.Add(self.scroll, 1, wx.EXPAND)
        self.panel.SetSizer(outer)
        self.panel.Bind(wx.EVT_SIZE, self.OnSize)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda e: self.Reload(), self.timer)
        self.timer.Start(REFRESH_SECONDS * 1000)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Reload()
        self.Centre()


    def Reload(self):
        groups, test_mode = collectTiles()
        mode = "Test mode: showing test readings" if test_mode else "Sensors that are turned on, last 24 hours"
        self.summary_text = "%s  ·  updated %s UTC" % (mode, datetime.datetime.utcnow().strftime("%H:%M:%S"))
        layout = [(name, [t["label"] for t in tiles]) for name, tiles in groups]
        if layout == self.layout:
            # Same sensors and measurements: just redraw with the new readings
            for name, tiles in groups:
                for t in tiles:
                    self.tiles[(name, t["label"])].SetTile(t)
            self.FitContent()
            return
        self.layout = layout
        view = self.scroll.GetViewStart()
        self.scroll.Freeze()
        self.scroll.DestroyChildren()
        self.tiles = {}
        self.message = None
        sizer = wx.BoxSizer(wx.VERTICAL)
        if not groups:
            self.message = wx.StaticText(self.scroll, label="")
            sizer.Add(self.message, 0, wx.ALL, 16)
        for name, tiles in groups:
            heading = wx.StaticText(self.scroll, label=name.replace(" sensor", ""))
            heading.SetFont(font("heading"))
            heading.SetForegroundColour(TEXT_PRIMARY)
            sizer.Add(heading, 0, wx.LEFT | wx.TOP, 12)
            row = wx.WrapSizer(wx.HORIZONTAL)
            for t in tiles:
                tile = Tile(self.scroll, t, self.tile_width)
                self.tiles[(name, t["label"])] = tile
                row.Add(tile, 0, wx.ALL, 6)
            sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        sizer.AddSpacer(12)
        self.scroll.SetSizer(sizer)
        self.scroll.SetupScrolling(scroll_x=False)
        self.FitContent()
        self.scroll.Scroll(view)
        self.scroll.Thaw()


    # Size the tiles to fill the window width and wrap the text to fit
    def FitContent(self):
        if not self:
            return  # window was closed before a queued resize ran
        width = self.panel.GetClientSize()[0]
        self.summary.SetLabel(self.summary_text)
        self.summary.Wrap(max(100, width - self.refresh.GetSize()[0] - 32))
        if self.message:
            self.message.SetLabel("No sensors are turned on. Turn sensors on in the 3D-PAWS Controller to see their readings here.")
            self.message.Wrap(max(100, width - 48))
        # Each tile takes its width plus a 6 px border on both sides; the rows have 6 px on both sides
        scrollbar = wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)
        available = width - scrollbar - 12
        columns = max(1, available // (Tile.MIN_WIDTH + 12))
        self.tile_width = max(160, available // columns - 12)
        for tile in self.tiles.values():
            tile.SetWidth(self.tile_width)
        self.panel.Layout()
        self.scroll.Layout()
        self.scroll.FitInside()


    def OnSize(self, e):
        e.Skip()
        wx.CallAfter(self.FitContent)


    def OnClose(self, e):
        self.timer.Stop()
        self.Destroy()


# Open the dashboard on its own, e.g. over "ssh -X": sudo -E python3 /home/pi/3d_paws/scripts/gui/dashboard.py
if __name__ == '__main__':
    app = wx.App()
    Dashboard(None).Show()
    app.MainLoop()
