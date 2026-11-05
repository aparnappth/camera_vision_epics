# SPDX-FileCopyrightText: 1998 Argonne National Laboratory
#
# SPDX-License-Identifier: EPICS

TOP=../..
include $(TOP)/configure/CONFIG
#----------------------------------------
#  ADD MACRO DEFINITIONS AFTER THIS LINE

#----------------------------------------------------
# Create and install (or just install) into <top>/db
# databases, templates, substitutions like this
#DB += xxx.db
# Standard areaDetector database templates
# ADCore R3-14 and NDDriverStdArrays R1-3

DB += ADBase.template
DB += NDArrayBase.template
DB += NDDriverStdArrays.template
DB += NDPluginBase.template
DB += NDStdArrays.template
DB += NDROI.template
DB += NDStats.template
# Custom RGB analysis plugin
DB += NDPluginRGB.template
# Vision processing records
DB += vision.db

#----------------------------------------------------
# If <anyname>.db template is not named <anyname>*.template add
# <anyname>_template = <templatename>

include $(TOP)/configure/RULES
#----------------------------------------
#  ADD RULES AFTER THIS LINE

