
#!../../bin/linux-arm/areadetector_camera

#- SPDX-FileCopyrightText: 2005 Argonne National Laboratory
#-
#- SPDX-License-Identifier: EPICS

# ==========================================
# Register IOC support
# ==========================================

dbLoadDatabase("../../dbd/areadetector_camera.dbd")
areadetector_camera_registerRecordDeviceDriver(pdbbase)

# ==========================================
# Configure areaDetector driver
# ==========================================

# Input driver: receives image arrays from EPICS clients
NDDriverStdArraysConfig("STDARRAYS", 10, 20000000, 0, 0)

# Output plugin: converts NDArrays to EPICS waveforms
NDStdArraysConfigure("IMAGE1", 2, 0, "STDARRAYS", 0, 0, 0, 0, 0, 1)

# ==========================================
# Load areaDetector database templates
# ==========================================

# Search path for templates referenced by include directives
epicsEnvSet("EPICS_DB_INCLUDE_PATH", "../../db")

# Input driver records
dbLoadRecords("../../db/NDDriverStdArrays.template", "P=AD:,R=Input:,PORT=STDARRAYS,ADDR=0,TIMEOUT=1,TYPE=Int8,FTVL=CHAR,NELEMENTS=230400")

# Output plugin records
dbLoadRecords("../../db/NDStdArrays.template", "P=AD:,R=Image1:,PORT=IMAGE1,NDARRAY_PORT=STDARRAYS,ADDR=0,TIMEOUT=1,TYPE=Int8,FTVL=CHAR,NELEMENTS=230400")



epicsEnvSet("EPICS_CA_MAX_ARRAY_BYTES", "1000000")

# ==========================================
# Initialize IOC
# ==========================================

iocInit()
