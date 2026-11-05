
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

# ROI plugin: select a spatial region from the RGB image
#NDROIConfigure("ROI1", 2, 0, "STDARRAYS", 0, 0, 0, 0, 0, 1)

# Statistics plugin: calculate intensity statistics
# from the single-channel ROI1 output
#NDStatsConfigure("STATS1", 2, 0, "ROI1", 0, 0, 0, 0, 0, 1)

# Custom RGB image-analysis plugin
NDRGBConfigure("RGB1", 2, 0, "STDARRAYS", 0, 0, 0, 0, 0, 1)


# ==========================================
# Load areaDetector database templates
# ==========================================

# Search path for templates referenced by include directives
epicsEnvSet("EPICS_DB_INCLUDE_PATH", "../../db")

# Input driver records
dbLoadRecords("../../db/NDDriverStdArrays.template", "P=AD:,R=Input:,PORT=STDARRAYS,ADDR=0,TIMEOUT=1,TYPE=Int8,FTVL=CHAR,NELEMENTS=230400")

# Output plugin records
dbLoadRecords("../../db/NDStdArrays.template", "P=AD:,R=Image1:,PORT=IMAGE1,NDARRAY_PORT=STDARRAYS,ADDR=0,TIMEOUT=1,TYPE=Int8,FTVL=CHAR,NELEMENTS=230400")

# ROI plugin records
#dbLoadRecords("../../db/NDROI.template", "P=AD:,R=ROI1:,PORT=ROI1,NDARRAY_PORT=STDARRAYS,ADDR=0,TIMEOUT=1")

# Statistics plugin records

#dbLoadRecords("../../db/NDStats.template", "P=AD:,R=Stats1:,PORT=STATS1,NDARRAY_PORT=ROI1,ADDR=0,TIMEOUT=1")

# Custom RGB plugin records
dbLoadRecords("../../db/NDPluginRGB.template", "P=AD:,R=RGB1:,PORT=RGB1,NDARRAY_PORT=STDARRAYS,ADDR=0,TIMEOUT=1")

# Vision processing records
dbLoadRecords("../../db/vision.db")

epicsEnvSet("EPICS_CA_MAX_ARRAY_BYTES", "1000000")

# ==========================================
# Initialize IOC
# ==========================================

iocInit()


