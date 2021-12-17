#!/usr/bin/env python3
"""Copyright (c) 2020 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied."""
from netmiko import ConnectHandler
import json
from details import *

#open the file with the radio configuration information and save the contents to config_info
radio_file_path = config_file_dir + "/simulatedRadios.json"
radio_file = open(radio_file_path)
config_info = json.load(radio_file)
radio_file.close()

#open the file with the access point information and save the contents to ap_info
ap_file_path = config_file_dir + "/accessPoints.json"
ap_file = open(ap_file_path)
ap_info = json.load(ap_file)
ap_file.close()

#open the file with the matrix that maps the power levels in dBm to the Cisco power levels and save it to power_model_channel_matrix
matrix_file = open('powerByModelandChannel.json')
power_model_channel_matrix = json.load(matrix_file)
matrix_file.close()

#these Boolean variables will indicate whether or not to change the channel, change the power, or shut down the access point entirely
change_channel = False
change_power = False
shutdown = False

ap_dict = {} #the ap_dict will map the AP  IDs to the name and model of the AP
channels24 = [1, 6, 11] #these channels indicate that we are configuring the 2.4 GHz radio
matrix_keys = power_model_channel_matrix.keys() #the matrix keys are the AP models

#open connection with WLC through netmiko
with ConnectHandler(ip=ip_addr,
    port=22,
    username=username,
    password=password,
    device_type="cisco_wlc_ssh") as ch:

    #find the AP name, model, and id from the file contents of the access point Ekahau file and save that info the the ap_dict
    for ap in ap_info["accessPoints"]:
        ap_name = ap["name"]
        ap_id = ap["id"]
        ap_model = ap["model"]
        ap_dict[ap_id] = {
            "name": ap_name,
            "model": ap_model
        }

    #find the configuration of the AP (power level and channel) from the simulated radios Ekahau file
    for radio in config_info["simulatedRadios"]:
        #find the AP name and model associated with the AP id given in the simulated radios file
        ap_id = radio["accessPointId"]
        ap_name = ap_dict[ap_id]["name"]
        ap_model = ap_dict[ap_id]["model"]

        #find the power and channels associated with the model of this AP
        for model in matrix_keys:
            if model in ap_model:
                power_channel_matrix = power_model_channel_matrix[model]

        #check if a new channel is given in the Ekahau file
        if "channel" in radio.keys():
            channel = radio["channel"][0] #save channel value from Ekahau file
            change_channel = True #indicate the channel needs to be changed for this AP
            power_matrix = power_channel_matrix[str(channel)] #retrieve the different power levels available for this AP at this channel
            print("CHANNEL VALUE: {}".format(channel))

        #check if a new power level is given in the Ekahau file
        if "transmitPower" in radio.keys():
            power = radio["transmitPower"] #save the power value from the Ekahau file
            if power == 0.0:
                shutdown = True #if the power level is set to 0, the AP should be shutdown
                print("AP will be shutdown")
            else:
                #check which Cisco power level most closely corresponds with the power level given from Ekahau
                min_diff = 100
                #the key represents the Cisco power level and the value represents the power level in dBm
                for key, value in power_matrix.items():
                    diff = abs(int(value) - int(power))
                    if diff < min_diff:
                        min_diff = diff
                        power_value = key #the Cisco level with the closest corresponding power level in dBm is the power value the AP will be configured with
                print("POWER VALUE: {}".format(power_value))

                change_power = True #indicate the power value needs to be changed for this AP

        #now take all the information gathered above and configure the AP
        if change_channel: #channel needs to be changed
            ch.send_command("ap name {} no shut".format(ap_name)) #if channel is being configured, we need to make sure the AP is not shutdown
            if channel in channels24 and "5GHz" in ap_model: #we are configuring a channel in the 2.4 GHz range, but the AP has a 5 GHz radio - thus, it is dual band. This is important for the exact CLI command we want to use.
                channel_command = "ap name {} dot11 dual-band channel {}".format(ap_name, channel)
                ch.send_command(channel_command)

                print(ch.send_command("show ap dot11 dual-band summary")) #print results of this CLI command
            elif channel in channels24: #channel is in 2.4 GHz range, and the AP does not have a 5 GHz radio - plain ole 2.4 GHz
                channel_command = "ap name {} dotll 24ghz channel {}".format(ap_name, channel)
                ch.send_command(channel_command)

                print(ch.send_command("show ap dot11 24ghz summary")) #print results of this CLI command
            else: #channel is not in 2.4 GHz range, so it must be 5 GHz
                channel_command = "ap name {} dot11 5ghz channel {}".format(ap_name, channel)
                ch.send_command(channel_command)

                print(ch.send_command("show ap dot11 5ghz summary")) #print results of this CLI command

        if change_power: #power needs to be changed
            ch.send_command("ap name {} no shut".format(ap_name)) #if power is being configured, we need to make sure the AP is not shutdown
            if channel in channels24 and "5GHz" in ap_model: #the channel was in the 2.4 GHz range, but the AP has a 5 GHz radio - thus it's dual band. This is important for the exact CLI command we want to use.
                power_command = "ap name {} dot11 dual-band txpower {}".format(ap_name, power_value)
                ch.send_command(power_command)

                print(ch.send_command("show ap dot11 dual-band summary")) #print results of this CLI command
            elif channel in channels24: #channel is in 2.4 GHz range, and the AP does not have a 5 GHz radio
                power_command = "ap name {} dot11 24ghz txpower {}".format(ap_name, power_value)
                ch.send_command(power_command)

                print(ch.send_command("show ap dot11 24ghz summary")) #print results of this CLI command
            else: #channel is not in the 2.4 GHz range, so it must be 5 GHz
                power_command = "ap name {} dot11 5ghz txpower {}".format(ap_name, power_value)
                ch.send_command(power_command)

                print(ch.send_command("show ap dot11 5ghz summary")) #print results of this CLI command

        if shutdown: #ap needs to be shutdown
            shutdown_command = "ap name {} shutdown".format(ap_name)
            ch.send_command(shutdown_command)

            print(ch.send_command("show ap status")) #print results of this CLI command

        #reset these values for the next AP checked
        change_channel = False
        change_power = False
        shutdown = False
