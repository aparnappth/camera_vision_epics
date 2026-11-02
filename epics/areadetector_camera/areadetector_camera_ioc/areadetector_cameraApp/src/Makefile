# SPDX-FileCopyrightText: 2003 Argonne National Laboratory
#
# SPDX-License-Identifier: EPICS

TOP=../..

include $(TOP)/configure/CONFIG
#----------------------------------------
#  ADD MACRO DEFINITIONS AFTER THIS LINE
#=============================

#=============================
# Build the IOC application

PROD_IOC = areadetector_camera
# areadetector_camera.dbd will be created and installed
DBD += areadetector_camera.dbd

# areadetector_camera.dbd will be made up from these files:
areadetector_camera_DBD += base.dbd

# Include dbd files from all support applications:
#areadetector_camera_DBD += xxx.dbd
# asyn driver support
areadetector_camera_DBD += asyn.dbd

# areaDetector core and plugins
areadetector_camera_DBD += ADSupport.dbd
areadetector_camera_DBD += NDPluginSupport.dbd

# NDDriverStdArrays driver
areadetector_camera_DBD += NDDriverStdArraysSupport.dbd

areadetector_camera_DBD += busyRecord.dbd
areadetector_camera_DBD += busySupport.dbd

# Add all the support libraries needed by this IOC
#areadetector_camera_LIBS += xxx
# areaDetector libraries
areadetector_camera_LIBS += NDDriverStdArrays
areadetector_camera_LIBS += NDPlugin
areadetector_camera_LIBS += ADBase
areadetector_camera_LIBS += busy
# asyn support
areadetector_camera_LIBS += asyn

# areadetector_camera_registerRecordDeviceDriver.cpp derives from areadetector_camera.dbd
areadetector_camera_SRCS += areadetector_camera_registerRecordDeviceDriver.cpp

# Build the main IOC entry point on workstation OSs.
areadetector_camera_SRCS_DEFAULT += areadetector_cameraMain.cpp
areadetector_camera_SRCS_vxWorks += -nil-

# Add support from base/src/vxWorks if needed
#areadetector_camera_OBJS_vxWorks += $(EPICS_BASE_BIN)/vxComLibrary

# Finally link to the EPICS Base libraries
areadetector_camera_LIBS += $(EPICS_BASE_IOC_LIBS)

#===========================

include $(TOP)/configure/RULES
#----------------------------------------
#  ADD RULES AFTER THIS LINE

