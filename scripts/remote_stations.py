#!/usr/bin/python3
# Code to move remote station data from buffer to main log every minute and send to chords if turned on
# Joseph E. Rener
# UCAR
# Boulder, CO USA
# Email: jrener@ucar.edu
# Copyright (c) 2022 UCAR
# Developed at COMET at University Corporation for Atmospheric Research and the Research Applications Laboratory at the National Center for Atmospheric Research (NCAR)

import helper_functions, datetime, os

#set to true if the antenna needs to be restarted
restart = False 

# Get script arguments
arguments = helper_functions.getArguments()
record_interval = arguments[0]
chords_interval = arguments[1]
chords_toggle = arguments[2]
chords_id = arguments[3]
chords_link = arguments[4]

# Get data
file = open('/home/pi/data/remote_stations/remote_stations_buffer.log', 'r+')
data = file.readlines()
file.truncate(0) #clear file
file.close() 

# Initialize container variables
rg1 = {}
rg2 = {}
rg3 = {}
rg4 = {}
rg5 = {}
sg1 = {}
sg2 = {}
sg3 = {}
paws = {}
message_counts = {}

# Format and send most recent data
if len(data) > 0:
    for line in data:
        #lines will either look something like  Match Len[32] #3 => #1 -48dB : Msg[RG1,3,0,1,4.19] CS[728]  or  Match Len[96] #2 => #1 -48dB : Msg[3DP1,2,0,25.02,83818.67,1609.79,24.17,45.44,24.06,262.00,266.00,0.03,10574,0,10576,0,18,5.12] CS[4574]
        if line[:5] == "Match":
            target = line.split(" => #")[1]
            target = int(target.split(" ")[0])
            if target == chords_id: #is the LoRa sending to us?
                line = line.split("Msg[")[1]
                payload = line.split("] CS")[0].split(",")
                msg_type = payload[0]
                station_id = payload[1]
                #used for averaging values later
                if station_id in message_counts:
                    message_counts[station_id] = message_counts[station_id] + 1
                else:
                    message_counts[station_id] = 1
                # Determine what kind of sensor is reporting to us
                #remote rain gauge battery: RS1,ID,TC,POWERON,F,U
                if msg_type == "RG1":
                    status = payload[3]
                    rg1[station_id] = status
                #remote rain gauge data: RS2,ID,TC, tips, time
                elif msg_type == "RG2":
                    tips = payload[3]
                    if station_id in rg2:
                        rg2[station_id] = rg2[station_id] + float(tips)*.2
                    else:
                        rg2[station_id] = float(tips)*.2
                #remote rain gauge battery: RS3,ID,TC, tips, time, temp1, mois1, temp2, mois2, temp3, mois3
                elif msg_type == "RG3":
                    tips = payload[3]
                    temp1 = payload[5]
                    mois1 = payload[6]
                    temp2 = payload[7]
                    mois2 = payload[8]
                    temp3 = payload[9]
                    mois3 = payload[10]
                    if station_id in rg3:
                        rg3[station_id]['rain'] = rg3[station_id]['rain'] + float(tips)*.2
                        rg3[station_id]['temp1'] = rg3[station_id]['temp1'] + temp1
                        rg3[station_id]['mois1'] = rg3[station_id]['mois1'] + mois1
                        rg3[station_id]['temp2'] = rg3[station_id]['temp2'] + temp2
                        rg3[station_id]['mois2'] = rg3[station_id]['mois2'] + mois2
                        rg3[station_id]['temp3'] = rg3[station_id]['temp3'] + temp3
                        rg3[station_id]['mois3'] = rg3[station_id]['mois3'] + mois3
                    else:
                        rg3[station_id]['rain'] = float(tips)*.2
                        rg3[station_id]['temp1'] = temp1
                        rg3[station_id]['mois1'] = mois1
                        rg3[station_id]['temp2'] = temp2
                        rg3[station_id]['mois2'] = mois2
                        rg3[station_id]['temp3'] = temp3
                        rg3[station_id]['mois3'] = mois3
                #remote rain gauge battery: RS4,ID,TC, tips, time, pres1, temp1, hum1, pres2, temp2, hum2
                elif msg_type == "RG4":
                    tips = payload[3]
                    pres1 = payload[5]
                    temp1 = payload[6]
                    hum1 = payload[7]
                    pres2 = payload[8]
                    temp2 = payload[9]
                    hum2 = payload[10]
                    if station_id in rg4:
                        rg4[station_id]['rain'] = rg4[station_id]['rain'] + float(tips)*.2
                        rg4[station_id]['pres1'] = rg4[station_id]['pres1'] + pres1
                        rg4[station_id]['temp1'] = rg4[station_id]['temp1'] + temp1
                        rg4[station_id]['hum1'] = rg4[station_id]['hum1'] + hum1
                        rg4[station_id]['pres2'] = rg4[station_id]['pres2'] + pres2
                        rg4[station_id]['temp2'] = rg4[station_id]['temp2'] + temp2
                        rg4[station_id]['hum2'] = rg4[station_id]['hum2'] + hum2
                    else:
                        rg4[station_id]['rain'] = float(tips)*.2
                        rg4[station_id]['pres1'] = pres1
                        rg4[station_id]['temp1'] = temp1
                        rg4[station_id]['hum1'] = hum1
                        rg4[station_id]['pres2'] = pres2
                        rg4[station_id]['temp2'] = temp2
                        rg4[station_id]['hum2'] = hum2
                #remote rain gauge battery: RS5,ID,TC, tips, time, temp1, mois1, temp2, mois2, temp3, mois3, pres1, btemp1, hum1, pres2, btemp2, hum2
                elif msg_type == "RG5":
                    tips = payload[3]
                    soil_temp1 = payload[5]
                    mois1 = payload[6]
                    soil_temp2 = payload[7]
                    mois2 = payload[8]
                    soil_temp3 = payload[9]
                    mois3 = payload[10]
                    pres1 = payload[11]
                    temp1 = payload[12]
                    hum1 = payload[13]
                    pres2 = payload[14]
                    temp2 = payload[15]
                    hum2 = payload[16]
                    if station_id in rg5:
                        rg5[station_id]['rain'] = rg5[station_id]['rain'] + float(tips)*.2
                        rg5[station_id]['soil_temp1'] = rg5[station_id]['soil_temp1'] + soil_temp1
                        rg5[station_id]['mois1'] = rg5[station_id]['mois1'] + mois1
                        rg5[station_id]['soil_temp2'] = rg5[station_id]['soil_temp2'] + soil_temp2
                        rg5[station_id]['mois2'] = rg5[station_id]['mois2'] + mois2
                        rg5[station_id]['soil_temp3'] = rg5[station_id]['soil_temp3'] + soil_temp3
                        rg5[station_id]['mois3'] = rg5[station_id]['mois3'] + mois3
                        rg5[station_id]['pres1'] = rg5[station_id]['pres1'] + pres1
                        rg5[station_id]['temp1'] = rg5[station_id]['temp1'] + temp1
                        rg5[station_id]['hum1'] = rg5[station_id]['hum1'] + hum1
                        rg5[station_id]['pres2'] = rg5[station_id]['pres2'] + pres2
                        rg5[station_id]['temp2'] = rg5[station_id]['temp2'] + temp2
                        rg5[station_id]['hum2'] = rg5[station_id]['hum2'] + hum2
                    else:
                        rg5[station_id]['rain'] = float(tips)*.2
                        rg5[station_id]['soil_temp1'] = temp1
                        rg5[station_id]['mois1'] = mois1
                        rg5[station_id]['soil_temp2'] = temp2
                        rg5[station_id]['mois2'] = mois2
                        rg5[station_id]['soil_temp3'] = temp3
                        rg5[station_id]['mois3'] = mois3
                        rg5[station_id]['pres1'] = pres1
                        rg5[station_id]['temp1'] = temp1
                        rg5[station_id]['hum1'] = hum1
                        rg5[station_id]['pres2'] = pres2
                        rg5[station_id]['temp2'] = temp2
                        rg5[station_id]['hum2'] = hum2
                #remote stream gauge: SG1,ID,TC,POWERON,F,U
                elif msg_type == "SG1":
                    status = payload[3]
                    sg1[station_id] = status
                #remote stream gauge: SG2,ID,TC,I,F,U, value
                elif msg_type == "SG2":
                    value = payload[3]
                    if station_id in sg2:
                        sg2[station_id] = sg2[station_id] + value
                    else:
                        sg2[station_id] = value
                #remote stream gauge: SG3,ID,TC,I,F,F,F,F,F,F,F,I
                elif msg_type == "SG3":
                    value = payload[3]
                    pres1 = payload[4]
                    temp1 = payload[5]
                    hum1 = payload[6]
                    pres2 = payload[7]
                    temp2 = payload[8]
                    hum2 = payload[9]
                    if station_id in sg3:
                        sg3[station_id]['gauge'] = sg3[station_id]['gauge'] + value
                        sg3[station_id]['pres1'] = sg3[station_id]['pres1'] + pres1
                        sg3[station_id]['temp1'] = sg3[station_id]['temp1'] + temp1
                        sg3[station_id]['hum1'] = sg3[station_id]['hum1'] + hum1
                        sg3[station_id]['pres2'] = sg3[station_id]['pres2'] + pres2
                        sg3[station_id]['temp2'] = sg3[station_id]['temp2'] + temp2
                        sg3[station_id]['hum2'] = sg3[station_id]['hum2'] + hum2
                    else:
                        sg3[station_id]['gauge'] = value
                        sg3[station_id]['pres1'] = pres1
                        sg3[station_id]['temp1'] = temp1
                        sg3[station_id]['hum1'] = hum1
                        sg3[station_id]['pres2'] = pres2
                        sg3[station_id]['temp2'] = temp2
                        sg3[station_id]['hum2'] = hum2
                #3DP1, id, count, bmp-temp, bmp-pres, bmp-alt, htu-temp, htu-hum, mcp-temp, sil-vis, sil-ir, sil-uv, windspd-time, windspd-rev, windspd, rain-time, rain, winddir, battery
                elif msg_type == "3DP1": 
                    bmp_tmp = 0 if payload[3] == "NA" else float(payload[3]) #0
                    bmp_pre = 0 if payload[4] == "NA" else float(payload[4]) #1
                    bmp_alt = 0 if payload[5] == "NA" else float(payload[5]) #2
                    htu_tmp = 0 if payload[6] == "NA" else float(payload[6]) #3
                    htu_hum = 0 if payload[7] == "NA" else float(payload[7]) #4
                    mcp_tmp = 0 if payload[8] == "NA" else float(payload[8]) #5
                    sil_vis = 0 if payload[9] == "NA" else float(payload[9]) #6
                    sil_ir = 0 if payload[10] == "NA" else float(payload[10]) #7
                    sil_uv = 0 if payload[11] == "NA" else float(payload[11]) #8
                    windspd = 0 if payload[12] == "NA" else float(payload[12]) #9
                    winddir = 0 if payload[13] == "NA" else float(payload[13]) #10
                    wind_gust = 0 if payload[14] == "NA" else float(payload[14]) #11
                    wind_gust_dir = 0 if payload[15] == "NA" else float(payload[15]) #12
                    rain = 0 if payload[17] == "NA" else float(payload[17]) #13
                    battery = 0 if payload[18] == "NA" else float(payload[18]) #14
                    if station_id in paws:
                        paws[station_id].append([bmp_tmp, bmp_pre, bmp_alt, htu_tmp, htu_hum, mcp_tmp, sil_vis, sil_ir, sil_uv, windspd, winddir, wind_gust, wind_gust_dir, rain, battery])
                    else:
                        paws[station_id] = [[bmp_tmp, bmp_pre, bmp_alt, htu_tmp, htu_hum, mcp_tmp, sil_vis, sil_ir, sil_uv, windspd, winddir, wind_gust, wind_gust_dir, rain, battery]]
        #if the line indicates that there was a short in the antenna hardware, restart it
        elif line[:22] == "Unknwn Len[7] #0 => #0":
            restart = True
    #record data now that it's compiled
    now = datetime.datetime.utcnow() - datetime.timedelta(minutes=1)
    month = now.month
    day = now.day
    year = now.year
    hour = now.hour
    minute = now.minute
    for station in rg1:
        url = "http://%s/measurements/url_create?instrument_id=%d&r_status%s=%.2f&key=21DE6A8A" % (chords_link, chords_id, station, rg1[station])
        helper_functions.reportCHORDS(chords_toggle, minute, 1, url)
    for station in rg2:
        line = "%s %.2f" % (station, rg2[station])
        helper_functions.output(False, line, "rain", True)
        url = "http://%s/measurements/url_create?instrument_id=%d&r_rain%s=%.2f&key=21DE6A8A" % (chords_link, chords_id, station, rg2[station])
        helper_functions.reportCHORDS(chords_toggle, minute, chords_interval, url)	
    for station in rg3:
        count = message_counts[station]
        rain = rg3[station]['rain']
        temp1 = rg3[station]['temp1']/count
        mois1 = rg3[station]['mois1']/count
        temp2 = rg3[station]['temp2']/count
        mois2 = rg3[station]['mois2']/count
        temp3 = rg3[station]['temp3']/count
        mois3 = rg3[station]['mois3']/count
        line = "%s %.2f %.2f %.2f %.2f %.2f %.2f %.2f" % (station, rain, temp1, mois1, temp2, mois2, temp3, mois3)
        helper_functions.output(False, line, "rain_and_soil", True)
        url = "http://%s/measurements/url_create?instrument_id=%d&r_rain=%.2f&r_temp1=%.2f&r_mois1=%.2f&r_temp2=%.2f&r_mois2=%.2f&r_temp3=%.2f&r_mois3=%.2f&key=21DE6A8A" % (chords_link, station, rain, temp1, mois1, temp2, mois2, temp3, mois3)
        helper_functions.reportCHORDS(chords_toggle, minute, chords_interval, url)
    for station in rg4:
        count = message_counts[station]
        rain = rg3[station]['rain']
        temp1 = rg3[station]['temp1']/count
        pres1 = rg3[station]['pres1']/count
        hum1 = rg3[station]['hum1']/count
        temp2 = rg3[station]['temp2']/count
        pres2 = rg3[station]['pres2']/count
        hum2 = rg3[station]['hum2']/count
        line = "%s %.2f %.2f %.2f %.2f %.2f %.2f %.2f" % (station, rain, temp1, pres1, hum1, temp2, pres2, hum2)
        helper_functions.output(False, line, "rain_and_air", True)
        url = "http://%s/measurements/url_create?instrument_id=%d&r_rain=%.2f&r_temp1=%.2f&r_pres1=%.2f&r_hum1=%.2f&r_temp2=%.2f&r_pres2=%.2f&r_hum2=%.2f&key=21DE6A8A" % (chords_link, station, rain, temp1, pres1, hum1, temp2, pres2, hum2)
        helper_functions.reportCHORDS(chords_toggle, minute, chords_interval, url)
    for station in rg5:
        count = message_counts[station]
        rain = rg3[station]['rain']
        soil_temp1 = rg3[station]['soil_temp1']/count
        mois1 = rg3[station]['mois1']/count
        soil_temp2 = rg3[station]['soil_temp2']/count
        mois2 = rg3[station]['mois2']/count
        soil_temp3 = rg3[station]['soil_temp3']/count
        mois3 = rg3[station]['mois3']/count
        temp1 = rg3[station]['temp1']/count
        mois1 = rg3[station]['pres1']/count
        temp2 = rg3[station]['hum1']/count
        mois2 = rg3[station]['temp2']/count
        temp3 = rg3[station]['pres2']/count
        mois3 = rg3[station]['hum2']/count
        line = "%s %.2f %.2f %.2f %.2f %.2f %.2f %.2f %.2f %.2f %.2f %.2f %.2f %.2f" % (station, rain, soil_temp1, mois1, soil_temp2, mois2, soil_temp3, mois3, temp1, pres1, hum1, temp2, pres2, hum2)
        helper_functions.output(False, line, "rain_soil_air", True)
        url = "http://%s/measurements/url_create?instrument_id=%d&r_rain=%.2f&r_soil_temp1=%.2f&r_mois1=%.2f&r_soil_temp2=%.2f&r_mois2=%.2f&r_soil_temp3=%.2f&r_mois3=%.2f&r_temp1=%.2f&r_pres1=%.2f&r_hum1=%.2f&r_temp2=%.2f&r_pres2=%.2f&r_hum2=%.2f&key=21DE6A8A" % (chords_link, station, rain, soil_temp1, mois1, soil_temp2, mois2, soil_temp3, mois3, temp1, pres1, hum1, temp2, pres2, hum2)
        helper_functions.reportCHORDS(chords_toggle, minute, chords_interval, url)
    for station in sg1:
        url = "http://%s/measurements/url_create?instrument_id=%d&r_status%s=%.2f&key=21DE6A8A" % (chords_link, chords_id, station, sg1[station])
        helper_functions.reportCHORDS(chords_toggle, minute, 1, url)
    for station in sg2:
        line = "%s %.2f" % (station, sg2[station]/message_counts[station])
        helper_functions.output(False, line, "stream", True)
        url = "http://%s/measurements/url_create?instrument_id=%d&r_rain%s=%.2f&key=21DE6A8A" % (chords_link, chords_id, station, sg2[station])
        helper_functions.reportCHORDS(chords_toggle, minute, chords_interval, url)
    for station in sg3:
        count = message_counts[station]
        value = sg3[station]['rain']/count
        pres1 = sg3[station]['soil_temp1']/count
        temp1 = sg3[station]['soil_temp2']/count
        hum1 = sg3[station]['mois2']/count
        pres2 = sg3[station]['soil_temp3']/count
        temp2 = sg3[station]['mois3']/count
        hum2 = sg3[station]['temp1']/count
        line = "%s %.2f %.2f %.2f %.2f %.2f %.2f %.2f" % (station, value, temp1, pres1, hum1, temp2, pres2, hum2)
        helper_functions.output(False, line, "stream_air", True)
        url = "http://%s/measurements/url_create?instrument_id=%d&r_stream=%.2f&r_temp1=%.2f&r_pres1=%.2f&r_hum1=%.2f&r_temp2=%.2f&r_pres2=%.2f&r_hum2=%.2f&key=21DE6A8A" % (chords_link, station, value, temp1, pres1, hum1, temp2, pres2, hum2)
        helper_functions.reportCHORDS(chords_toggle, minute, chords_interval, url)
    for station in paws:
        pass

#if there are no recordings, or we've noticed a problem with the antenna, restart the script
if len(data) == 0 or restart:
    f = open('/home/pi/3d-paws/logs/remote_stations_check',"w+")
    f.close()
    os.system('sudo pkill -f remote_stations_server')
    os.system('sudo /home/pi/3d-paws/scripts/comms/rf95/remote_stations_server -d')