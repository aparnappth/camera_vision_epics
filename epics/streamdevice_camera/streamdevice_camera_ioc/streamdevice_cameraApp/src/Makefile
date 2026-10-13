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

PROD_IOC = streamdevice_camera
# streamdevice_camera.dbd will be created and installed
DBD += streamdevice_camera.dbd

# streamdevice_camera.dbd will be made up from these files:
streamdevice_camera_DBD += base.dbd
streamdevice_camera_DBD += asyn.dbd
streamdevice_camera_DBD += drvAsynIPPort.dbd
streamdevice_camera_DBD += stream.dbd
# Register the PVAccess server for EPICS database records
streamdevice_camera_DBD += PVAServerRegister.dbd
# Register the QSRV provider for EPICS database records
streamdevice_camera_DBD += qsrv.dbd

# Include dbd files from all support applications:
#streamdevice_camera_DBD += xxx.dbd

# Add all the support libraries needed by this IOC
#streamdevice_camera_LIBS += xxx

# streamdevice_camera_registerRecordDeviceDriver.cpp derives from streamdevice_camera.dbd
streamdevice_camera_SRCS += streamdevice_camera_registerRecordDeviceDriver.cpp

# Build the main IOC entry point on workstation OSs.
streamdevice_camera_SRCS_DEFAULT += streamdevice_cameraMain.cpp
streamdevice_camera_SRCS_vxWorks += -nil-

# Add support from base/src/vxWorks if needed
#streamdevice_camera_OBJS_vxWorks += $(EPICS_BASE_BIN)/vxComLibrary

# Finally link to the EPICS Base libraries
streamdevice_camera_LIBS += $(EPICS_BASE_IOC_LIBS)
streamdevice_camera_LIBS += stream
streamdevice_camera_LIBS += asyn


# PVAccess server support
streamdevice_camera_LIBS += qsrv
streamdevice_camera_LIBS += pvAccessIOC
streamdevice_camera_LIBS += pvAccess
streamdevice_camera_LIBS += pvData

#===========================

include $(TOP)/configure/RULES
#----------------------------------------
#  ADD RULES AFTER THIS LINE

