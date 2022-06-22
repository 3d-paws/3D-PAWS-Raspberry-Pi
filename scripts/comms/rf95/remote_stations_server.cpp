#include <dirent.h>
#include <iterator>
#include <cstdlib>
#include <cstring>
#include <sstream>
#include <iostream>
#include <stdlib.h>
#include <string>
#include <sys/stat.h>
#include <syslog.h>
#include <unistd.h>
#include <vector>
#include <fstream>
#include <bcm2835.h>
#include <stdio.h>
#include <signal.h>
#include <unistd.h>
#include <RH_RF95.h>
#include "/usr/local/include/AES/AES.h"
using namespace std;


// Our RFM95 Configuration 
#define RF_FREQUENCY  915.0
#define RF_NODE_ID    1

// Below setup for spi1
#define RF_CS_PIN  RPI_V2_GPIO_P1_36 // Slave Select on CE0 so P1 connector pin #36 (SPI1 CS0)
#define RF_RST_PIN RPI_V2_GPIO_P1_37 // IRQ on GPIO26 so P1 connector pin #37

// Create an instance of a driver
RH_RF95 rf95(RF_CS_PIN);

// AES Instance
AES aes;

// Daemon bool
bool daemonized = false;

// Private Key
byte key[] = "FEEDCODEBEEF4242";

// Initialization Vector must be and always will be 128 bits (16 bytes.)
// The real iv is actually my_iv repeated twice EX: 01234567 = 0123456701234567
unsigned long long int my_iv = 56495141;
byte msgbuf[RH_RF95_MAX_MESSAGE_LEN+1]; // 255 - 4(Header) + 1(Null) = 252


/*
 * ==================================================================================
 *  log() either records data to log files if daemonized or simply prints to screen
 * ==================================================================================
 */
void log(string message){
	// if running in test mode
	if (!daemonized){ 
		cout << message << "\n";
	}
	// Get date (used for name of log file)
	time_t now = time(0);
	tm *ltm = localtime(&now);
	auto year = 1900 + ltm->tm_year;
	auto month = to_string(1 + ltm->tm_mon);
	if (month.length() == 1){
		month = "0" + month;
	}
	auto day = ltm->tm_mday;
	string date = to_string(year) + month + to_string(day);
	// Log to temporary buffer file (which will be processed by remote_stations.py)
	ofstream data_file;
	data_file.open("/home/pi/3d-paws/data/remote_stations/remote_stations_buffer.log", fstream::in | fstream::out | fstream::app);
	data_file << message + "\n";
	data_file.close();
}


/*
 * ==================================================================================
 *  sig_handler()
 * ==================================================================================
 */
volatile sig_atomic_t force_exit = false;		//Flag for Ctrl-C
void sig_handler(int sig){
  	log("remote_data_server break received; exiting!");
	force_exit=true;
}


/*
 * ==================================================================================
 *  Primary functionality - logs incoming data if daemon, prints to screen if not
 * ==================================================================================
 */
int rf95_server(){
	uint8_t data[] = "And hello back to you";
	byte iv [N_BLOCK];

	signal(SIGINT, sig_handler);

	log("Starting remote_data_server");

	if (!bcm2835_init()) {
		if (!daemonized){
			fprintf(stderr, "%s bcm2835_init() Failed\n\n", __BASEFILE__);
		}
		else{
			log("remote_data_server bcm2835_init() Failed");
		}
		return 1;
	}
  
	log("RF95 CS=GPIO" + to_string(RF_CS_PIN) + ", RST=GPIO" + to_string(RF_RST_PIN));

	// Pulse a reset on module
	pinMode(RF_RST_PIN, OUTPUT);
	digitalWrite(RF_RST_PIN, LOW );
	bcm2835_delay(150);
	digitalWrite(RF_RST_PIN, HIGH );
	bcm2835_delay(100);

	if (!rf95.init()) {
		if (!daemonized){
			fprintf(stderr, "\nRF95 module init failed, Please verify wiring/module\n");
		}
		else{
			log("RF95 module init failed, Please verify wiring/module\n");
		}
	} 
	else {
		// Defaults after init are 434.0MHz, 13dBm, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on

		// The default transmitter power is 13dBm, using PA_BOOST.
		// If you are using RFM95/96/97/98 modules which uses the PA_BOOST transmitter pin, then 
		// you can set transmitter powers from 5 to 23 dBm:
		// RF95 Modules don't have RFO pin connected, so just use PA_BOOST
		// Set useRFO to false
		rf95.setTxPower(23, false);

		// You can optionally require this module to wait until Channel Activity
		// Detection shows no activity on the channel before transmitting by setting
		// the CAD timeout to non-zero:
		rf95.setCADTimeout(10000);

		// Adjust Frequency
		rf95.setFrequency(RF_FREQUENCY);
		
		// If we need to send something
		rf95.setThisAddress(RF_NODE_ID);
		rf95.setHeaderFrom(RF_NODE_ID);
		
		// Be sure to grab all node packet 
		// we're sniffing to display, it's a demo
		rf95.setPromiscuous(true);

		// We're ready to listen for incoming message
		rf95.setModeRx();

		log(" OK NodeID=" + to_string(RF_NODE_ID) + " @ " + to_string(RF_FREQUENCY) + "MHz");
		log("Listening packet...");

		//Begin the main body of code
		while (!force_exit) {
			if (rf95.available()) { 
				// Should be a message for us now
				uint8_t buf[RH_RF95_MAX_MESSAGE_LEN];
				uint8_t len  = sizeof(buf);
				uint8_t from = rf95.headerFrom();
				uint8_t to   = rf95.headerTo();
				uint8_t id   = rf95.headerId();
				uint8_t flags= rf95.headerFlags();;
				int8_t rssi  = rf95.lastRssi();
				uint8_t msglen = 0;
				uint16_t checksum = 0;
				uint8_t byte1;
				uint8_t byte2;
				uint8_t i;

				memset(buf, 0, RH_RF95_MAX_MESSAGE_LEN);
				memset(msgbuf, 0, RH_RF95_MAX_MESSAGE_LEN+1);
			
				if (rf95.recv(buf, &len)) {
					aes.iv_inc();
					aes.set_IV(my_iv);
					aes.get_IV(iv);
					aes.do_aes_decrypt(buf, len, msgbuf, key, 128, iv);
					if ((msgbuf[3] == '3' && msgbuf[4] == 'D' && msgbuf[5] == 'P' && (msgbuf[6] == '1' || msgbuf[6] == '2')) ||
                            (msgbuf[3] == 'R' && msgbuf[4] == 'G' && (msgbuf[5] == '1' || msgbuf[5] == '2')) ||
                            (msgbuf[3] == 'S' && msgbuf[4] == 'G' && (msgbuf[5] == '1' || msgbuf[5] == '2')) ||
							(msgbuf[3] == 'S' && msgbuf[4] == 'M' && (msgbuf[5] == '1' || msgbuf[5] == '2'))
						){
						// Message from a 3DPAWS or Arduino
						msglen = msgbuf[0];  // Get length of what follows
						checksum=0;
						for (i=3; i<msglen; i++) {
							checksum += msgbuf[i];
						}
						byte1 = checksum>>8;
						byte2 = checksum%256;
						// Good Message
						if ((byte1 == msgbuf[1]) && (byte2 == msgbuf[2])) {
							//The following is either:
							//remote rain data: Match Len[32] #1 => #1 -48dB : Msg[RG1,1,0,1,4.19] CS[728]
							//or remote stream gauge: Match Len[32] #2 => #1 -48dB : Msg[SG1,1,0,242,4.19] CS[728]
							//or full remote station: Match Len[112] #3 => #1 -22dB : Msg[3DP1,1,-7552,23.15,84107.58,1575.82,22.35,15.70,22.13,0.00,0.00,0.00,10574,0,10574,0,379,4.29] CS[4622]
							msgbuf[msglen]=0;    // Make what follows a string
							string payload = (const char*)(msgbuf+3);
							log("Match Len[" + to_string(len) + "] #" + to_string(from) + " => #" + to_string(to) + " " + to_string(rssi) + "dB : Msg[" + payload + "] CS[" + to_string(checksum) + "]");
						}
						// Bad Message
						else {
							if (daemonized){
								log("CKSUM Len[" + to_string(len) + "] #" + to_string(from) + " => #" + to_string(to) + " " + to_string(rssi) + "dB");
							}
							else{
								printf ("CKSUM Len[%02d] #%d => #%d %ddB : ", len, from, to, rssi);
								printbuffer(buf, len);
								printf ("\n");
							}
						}
					} 
					else { 
						// Message form unknown origin
						if (daemonized){
							log("Unknwn Len[" + to_string(len) + "] #" + to_string(from) + " => #" + to_string(to) + " " + to_string(rssi) + "dB");
						}
						else{
							printf ("Unknwn Len[%02d] #%d => #%d %ddB : ", len, from, to, rssi);
							printbuffer(buf, len);
							printf ("\n");
						} 
					}
				}
				else {
					if (daemonized){
						log("receive failed");
					}
					else{
						Serial.print("receive failed");
					}	
				}
			}
			// Let OS doing other tasks
			// For timed critical appliation you can reduce or delete
			// this delay, but this will charge CPU usage, take care and monitor
			bcm2835_delay(5);
		}
	}
	log("Stopping remote_stations_server");
	bcm2835_close();
	return 0;
}


// For security purposes, we don't allow any arguments to be passed into the daemon
int main(int argc, char *argv[]){
	// Check if this should be ran as a daemon
	if (argc > 1){
		ifstream fin("/home/pi/3d-paws/logs/remote_stations_check");
		if ((strcmp(argv[1], "-d") == 0 || strcmp(argv[1], "-D") == 0) && fin){
			// Define variables
			pid_t pid, sid;
			// Fork the current process
			pid = fork();
			// The parent process continues with a process ID greater than 0
			if(pid > 0){
				exit(EXIT_SUCCESS);
			}
			// A process ID lower than 0 indicates a failure in either process
			else if(pid < 0){
				exit(EXIT_FAILURE);
			}
			// The parent process has now terminated, and the forked child process will continue (the pid of the child process was 0)
			// Since the child process is a daemon, the umask needs to be set so files and logs can be written
			umask(0);
			// Open system logs for the child process
			openlog("remote_stations_server", LOG_NOWAIT | LOG_PID, LOG_USER);
			syslog(LOG_NOTICE, "Successfully started remote_stations_server");
			// Generate a session ID for the child process
			sid = setsid();
			// Ensure a valid SID for the child process
			if(sid < 0){
				// Log failure and exit
				syslog(LOG_ERR, "Could not generate session ID for child process");
				// If a new session ID could not be generated, we must terminate the child process
				// or it will be orphaned
				exit(EXIT_FAILURE);
			}
			// Change the current working directory to a directory guaranteed to exist
			if((chdir("/")) < 0){
				// Log failure and exit
				syslog(LOG_ERR, "Could not change working directory to /");
				// If our guaranteed directory does not exist, terminate the child process to ensure
				// the daemon has not been hijacked
				exit(EXIT_FAILURE);
			}
			// A daemon cannot use the terminal, so close standard file descriptors for security reasons
			close(STDIN_FILENO);
			close(STDOUT_FILENO);
			close(STDERR_FILENO);
			// Enter daemon loop
			daemonized = true;
			rf95_server();
			// Close system logs for the child process
			syslog(LOG_NOTICE, "Stopping remote_stations_server");
			closelog();
			// Terminate the child process when the daemon completes
			exit(EXIT_SUCCESS);
		}
		else{
			// Arguments are incorrect
			printf ("To test this script, make sure to not use any arguments (or -d if you want it to run as a daemon.)\n");
		}
	}
	else{
		// Not running as a daemon
		rf95_server();
	}
	return 0;
}
