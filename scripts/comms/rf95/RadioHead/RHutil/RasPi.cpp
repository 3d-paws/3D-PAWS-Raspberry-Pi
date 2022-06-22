// RasPi.cpp
//
// Routines for implementing RadioHead on Raspberry Pi
// using BCM2835 library for GPIO
//
// Contributed by Mike Poublon and used with permission


#include <RadioHead.h>

#if (RH_PLATFORM == RH_PLATFORM_RASPI)
#include <sys/time.h>
#include <time.h>
#include "RasPi.h"

//Initialize the values for sanity
timeval RHStartTime;

void SPIClass::begin()
{
  //Set SPI Defaults
  uint16_t divider = BCM2835_SPI_CLOCK_DIVIDER_256;
  uint8_t bitorder = BCM2835_SPI_BIT_ORDER_MSBFIRST;
  uint8_t datamode = BCM2835_SPI_MODE0;

  begin(divider, bitorder, datamode);
}

void SPIClass::begin(uint16_t divider, uint8_t bitOrder, uint8_t dataMode)
{
  setClockDivider(divider);
  setBitOrder(bitOrder);
  setDataMode(dataMode);

// RH Library code control CS line
  bcm2835_spi_chipSelect(BCM2835_SPI_CS_NONE);

  //
  //  void bcm2835_spi_chipSelect(uint8_t cs)
  //  {
  //      volatile uint32_t* paddr = bcm2835_spi0 + BCM2835_SPI0_CS/4;
  //      bcm2835_peri_set_bits(paddr, cs, BCM2835_SPI0_CS_CS);
  //  }


  //=======SPI0 to SPI1 ==========================
  // bcm2835_spi_begin();
  bcm2835_aux_spi_begin();
  //===============================================


  //Initialize a timestamp for millis calculation
  gettimeofday(&RHStartTime, NULL);
}

void SPIClass::end()
{
  //End the SPI

  //=======SPI0 to SPI1 ==========================
  // bcm2835_spi_end();
  bcm2835_aux_spi_end();
  //===============================================
}

void SPIClass::setBitOrder(uint8_t bitOrder)
{
  //Set the SPI bit Order
  bcm2835_spi_setBitOrder(bitOrder);

  /* Library Function
    void bcm2835_spi_setBitOrder(uint8_t order)
    {
        bcm2835_spi_bit_order = order;
    }
  */ 

}

void SPIClass::setDataMode(uint8_t mode)
{
  //Set SPI data mode
  bcm2835_spi_setDataMode(mode);

  // Library Function
  //  void bcm2835_spi_setDataMode(uint8_t mode)
  //  {
  //    volatile uint32_t* paddr = bcm2835_spi0 + BCM2835_SPI0_CS/4;
  //     /* Mask in the CPO and CPHA bits of CS */
  //     bcm2835_peri_set_bits(paddr, mode << 2, BCM2835_SPI0_CS_CPOL | BCM2835_SPI0_CS_CPHA);
  //  }
}

void SPIClass::setClockDivider(uint16_t rate)
{
  //Set SPI clock divider

  //=======SPI0 to SPI1 ==========================
  // bcm2835_spi_setClockDivider(rate);
  bcm2835_aux_spi_setClockDivider(rate); 
  //===============================================
}

byte SPIClass::transfer(byte _data)
{
  char tbuf[2];
  char rbuf[2];

  //Set which CS pin to use for next transfers
  bcm2835_spi_chipSelect(BCM2835_SPI_CS_NONE);
  //Transfer 1 byte
  
  // printf("\nSPIClass::transfer(%02X)", _data);

  //=======SPI0 to SPI1 ==========================
  // byte data;
  // data = bcm2835_spi_transfer((uint8_t)_data);

  tbuf[0] = _data;
  tbuf[1] = 0;

  bcm2835_aux_spi_transfernb(tbuf, rbuf, 1);
  //===============================================

  // printf("=%02X\n", rbuf[0]);

  return ((byte) rbuf[0]);
}

void pinMode(unsigned char pin, unsigned char mode)
{
  if (pin == NOT_A_PIN)
    return;
  
  if (mode == OUTPUT)
  {
    bcm2835_gpio_fsel(pin,BCM2835_GPIO_FSEL_OUTP);
  }
  else
  {
    bcm2835_gpio_fsel(pin,BCM2835_GPIO_FSEL_INPT);
  }
}

void digitalWrite(unsigned char pin, unsigned char value)
{
  if (pin == NOT_A_PIN)
    return;

  bcm2835_gpio_write(pin,value);
}

unsigned char digitalRead(unsigned char pin) {
  if (pin == NOT_A_PIN)
    return 0;

  return bcm2835_gpio_lev(pin);
}

unsigned long millis()
{
  //Declare a variable to store current time
  struct timeval RHCurrentTime;
  //Get current time
  gettimeofday(&RHCurrentTime,NULL);
  //Calculate the difference between our start time and the end time
  unsigned long difference = ((RHCurrentTime.tv_sec - RHStartTime.tv_sec) * 1000);
  difference += ((RHCurrentTime.tv_usec - RHStartTime.tv_usec)/1000);
  //Return the calculated value
  return difference;
}

void delay (unsigned long ms)
{
  //Implement Delay function
  struct timespec ts;
  ts.tv_sec=0;
  ts.tv_nsec=(ms * 1000);
  nanosleep(&ts,&ts);
}

long random(long min, long max)
{
  long diff = max - min;
  long ret = diff * rand() + min;
  return ret;
}

// Dump a buffer trying to display ASCII or HEX
// depending on contents
void printbuffer(uint8_t buff[], int len)
{
  int i;
  bool ascii = true;
  
  // Check for only printable characters
  for (i = 0; i< len; i++) {
    if ( buff[i]<32 || buff[i]>127) {
      if (buff[i]!=0 || i!=len-1) {
        ascii = false; 
        break;
      }
    }
  }

  // now do real display according to buffer type
  // note each char one by one because we're not sure 
  // string will have \0 on the end
  for (int i = 0; i< len; i++) {
    if (ascii) {
      printf("%c", buff[i]);
    } else {
      printf(" %02X", buff[i]);
    }
  }
}

void SerialSimulator::begin(int baud)
{
  //No implementation neccesary - Serial emulation on Linux = standard console
  //
  //Initialize a timestamp for millis calculation - we do this here as well in case SPI
  //isn't used for some reason
  gettimeofday(&RHStartTime, NULL);
}

size_t SerialSimulator::println(const char* s)
{
  print(s);
  printf("\n");
}

size_t SerialSimulator::print(const char* s)
{
  printf(s);
}

size_t SerialSimulator::print(unsigned int n, int base)
{
  if (base == DEC)
    printf("%d", n);
  else if (base == HEX)
    printf("%02x", n);
  else if (base == OCT)
    printf("%o", n);
  // TODO: BIN
}

size_t SerialSimulator::print(char ch)
{
  printf("%c", ch);
}

size_t SerialSimulator::println(char ch)
{
  printf("%c\n", ch);
}

size_t SerialSimulator::print(unsigned char ch, int base)
{
  return print((unsigned int)ch, base);
}

size_t SerialSimulator::println(unsigned char ch, int base)
{
  print((unsigned int)ch, base);
  printf("\n");
}

#endif
