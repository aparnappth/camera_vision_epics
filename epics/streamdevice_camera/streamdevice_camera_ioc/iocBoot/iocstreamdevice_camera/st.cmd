#!../../bin/linux-arm/streamdevice_camera

#- SPDX-FileCopyrightText: 2005 Argonne National Laboratory
#-
#- SPDX-License-Identifier: EPICS

#- You may have to change streamdevice_camera to something else
#- everywhere it appears in this file

#< envPaths

## Register all support components
dbLoadDatabase "../../dbd/streamdevice_camera.dbd"
streamdevice_camera_registerRecordDeviceDriver(pdbbase) 


# Configure asyn TCP/IP connection to Python server
drvAsynIPPortConfigure("CAM_PORT", "127.0.0.1:5000", 0, 0, 0)


# Tell StreamDevice where to find protocol files
epicsEnvSet("STREAM_PROTOCOL_PATH", "../../db")

# Load camera records with macros
dbLoadRecords("../../db/camera.db", "P=CAM:,R=,PORT=CAM_PORT,SCAN=1 second")

## Load record instances
#dbLoadRecords("../../db/streamdevice_camera.db","user=aparna")

iocInit()

## Start any sequence programs
#seq sncstreamdevice_camera,"user=aparna"

