# Direct I2C drivers for 3D-PAWS sensors, one module per model, no Adafruit libraries.
# Each class takes (smbus2 bus, address), checks the chip is there (IOError if not), and read() returns a
# dict with some of temp_c, rh_pct, pressure_hpa. Used by shield_test.py; the station scripts can move
# to these later (replacing humidity.py and bmp_bme.py, which guess the model).
# UCAR
# Boulder, CO USA
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

from .sht45 import SHT45
from .sht31 import SHT31
from .bmp390 import BMP390
from .bmp581 import BMP581
from .mcp9808 import MCP9808

MODELS = {"sht45": SHT45, "sht31": SHT31, "bmp390": BMP390, "bmp581": BMP581, "mcp9808": MCP9808}
