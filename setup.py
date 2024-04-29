from setuptools import setup, find_packages

VERSION = '3.6.0' 
DESCRIPTION = 'A python library used to run a 3D PAWS weather station. For more information, go to https://github.com/3d-paws/3d_paws'

setup(
        name="3d-paws", 
        version=VERSION,
        author="Joey Rener",
        author_email="jrener@ucar.edu",
        description=DESCRIPTION,
        url = "https://www.icdp.ucar.edu/core-programs-1/3dpaws/",

        packages=find_packages(
            where='scripts'
        ),

        install_requires=[
            "Adafruit_Blinka==4.8.1",
            "adafruit_bme280==1.0.1",
            "adafruit_circuitpython_bme280==2.4.3",
            "adafruit_circuitpython_bmp3xx",
            "adafruit_circuitpython_bmp280==3.2.3",
            "adafruit_circuitpython_HTU21D==0.10.2",
            "adafruit_circuitpython_sht31d==2.3.0",
            "adafruit_circuitpython_mcp9808==3.3.2",
            "adafruit_mcp9808==1.5.6",
            "board==1.0",
            "gps==3.19",
            "python_crontab==2.6.0",
            "requests==2.28.0",
            "setuptools==40.8.0",
            "SI1145==1.0.2",
            "smbus==1.1.post2",
            "spidev==3.5",
            "wxPython==4.0.4"
        ], 

        python_requires='>=3.8',
        
        keywords=['3d', 'paws'],

        classifiers= [
            "Intended Audience :: Education",
            "Programming Language :: Python :: 3",
        ]
)