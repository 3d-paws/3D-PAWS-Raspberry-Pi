from setuptools import setup, find_packages

VERSION = '3.0.0' 
DESCRIPTION = 'A python library used to run a 3D-PAWS weather station.'

with open(file="README.md", mode="r") as readme:
    LONG_DESCRIPTION = readme.read()

setup(
        name="3d-paws", 
        version=VERSION,
        author="Joey Rener",
        author_email="jrener@ucar.edu",
        description=DESCRIPTION,
        long_description=LONG_DESCRIPTION,
        long_description_content_type = "text/markdown",
        url = "https://www.icdp.ucar.edu/core-programs-1/3dpaws/",

        packages=find_packages(
            where='scripts'
        ),

        package_data = {
            'input' : ['scripts/input.txt']
        },

        install_requires=[
            "Adafruit_Blinka==4.8.1",
            "adafruit_bme280==1.0.1",
            "adafruit_circuitpython_bme280==2.4.3",
            "adafruit_circuitpython_bmp280==3.2.3",
            "adafruit_circuitpython_HTU21D==0.10.2",
            "adafruit_circuitpython_mcp9808==3.3.2",
            "adafruit_mcp9808==1.5.6",
            "board==1.0",
            "gps==3.19",
            "python_crontab==2.6.0",
            "requests==2.21.0",
            "setuptools==40.8.0",
            "SI1145==1.0.2",
            "smbus==1.1.post2",
            "spidev==3.5",
            "wxPython==4.0.4"
        ], 

        python_requires='>=3.6',
        
        keywords=['3d', 'paws'],

        classifiers= [
            "Intended Audience :: Education",
            "Programming Language :: Python :: 3",
        ]
)