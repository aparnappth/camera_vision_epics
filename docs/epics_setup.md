# EPICS Environment Setup on Raspberry Pi

This document describes the installation and configuration of EPICS Base, asyn and StreamDevice on a Raspberry Pi Zero 2 W.

It provides the software environment required for the conventional StreamDevice-based camera IOC developed in this project.

For IOC configuration, Python communication and testing, see [StreamDevice Camera IOC](streamdevice_ioc.md).

## 1. Development Environment

### Hardware

- Raspberry Pi Zero 2 W
- Sony IMX219 8 MP CSI camera
- Network connection for SSH access

### Software

| Component | Version |
|---|---|
| Operating system | 32-bit Raspberry Pi OS |
| Target architecture | `linux-arm` |
| EPICS Base | R7.0.10 |
| asyn | R4-46 |
| StreamDevice | 2.8.26 |
| Python | Python 3 |
| libcamera | 0.7.2 |

The versions listed above were used during development. Other versions may require adjustments to the build configuration.

## 2. Directory Organization

The EPICS environment is installed separately from the camera project.

```text
~/projects/
├── epics/
│   ├── base/
│   └── support/
│       └── modules/
│           ├── RELEASE.local
│           ├── asyn/
│           └── StreamDevice/
│
└── hobby/
    └── camera/
        └── camera_vision_epics/
```

This separation allows EPICS Base and support modules to be reused by other projects.

The camera project contains its own IOC source files but does not include copies of EPICS Base, asyn or StreamDevice.

## 3. System Preparation

Update the package index:

```bash
sudo apt update
```

Install common development tools:

```bash
sudo apt install git build-essential perl python3 pkg-config
```

These are basic prerequisites. A fresh EPICS Base installation may also require additional development packages, depending on the operating system and enabled EPICS features.

In particular, check the EPICS Base build documentation for the required readline and other system development libraries.

### Verify the Raspberry Pi architecture

```bash
uname -m
```

On the 32-bit Raspberry Pi installation used for this project, the EPICS target architecture is:

```text
linux-arm
```

EPICS determines its host architecture using its build configuration. Do not assume that every Raspberry Pi uses `linux-arm`; 64-bit installations generally use a different architecture.

## 4. Install EPICS Base

### 4.1 Create the installation directory

```bash
mkdir -p ~/projects/epics
cd ~/projects/epics
```

### 4.2 Clone EPICS Base

```bash
git clone --recursive -b R7.0.10 https://github.com/epics-base/epics-base.git base
```

This downloads the EPICS Base source code and checks out release R7.0.10.

Using a release tag helps make the installation reproducible.

### 4.3 Check the architecture

```bash
cd base
```

Run:

```bash
./startup/EpicsHostArch
```

The expected result for this installation is:

```text
linux-arm
```

### 4.4 Build EPICS Base

```bash
make -j2
```

The `-j2` option allows two parallel build jobs.

This was chosen to limit memory usage on the Raspberry Pi Zero 2 W.

If compilation fails because of missing development dependencies, install the packages identified by the error and rebuild.

### 4.5 Verify the installation

```bash
ls bin/linux-arm
```

The directory should contain EPICS executables, including Channel Access tools.

For example:

```text
caget
caput
camonitor
makeBaseApp.pl
```

## 5. Configure the EPICS Environment

To make EPICS commands available from any working directory, add the EPICS Base executable directory to the shell's `PATH`.

Open:

```bash
nano ~/.bashrc
```

Add:

```bash
# EPICS Base
export EPICS_BASE="$HOME/projects/epics/base"
export PATH="$EPICS_BASE/bin/linux-arm:$PATH"
```

Save and apply:

```bash
source ~/.bashrc
```

Verify:

```bash
which caget
```

Expected path:

```text
/home/aparna/projects/epics/base/bin/linux-arm/caget
```

Also verify:

```bash
which makeBaseApp.pl
```

The environment is now configured for EPICS development.

## 6. Install asyn

asyn is an EPICS support module providing communication interfaces for hardware drivers and asynchronous operations.

In this project, asyn provides the TCP/IP communication interface used by StreamDevice.

### 6.1 Create the support directory

```bash
mkdir -p ~/projects/epics/support/modules
cd ~/projects/epics/support/modules
```

### 6.2 Clone asyn

```bash
git clone --recursive -b R4-46 https://github.com/epics-modules/asyn.git asyn
```

### 6.3 Configure dependencies

The asyn source contains:

```text
configure/RELEASE
```

This file defines paths to EPICS Base and optional support modules.

The project uses a shared configuration file in the parent support directory:

```text
~/projects/epics/support/modules/RELEASE.local
```

Create it:

```bash
nano ~/projects/epics/support/modules/RELEASE.local
```

Add:

```makefile
SUPPORT=/home/aparna/projects/epics/support/modules
EPICS_BASE=/home/aparna/projects/epics/base
ASYN=$(SUPPORT)/asyn
STREAM=$(SUPPORT)/StreamDevice
CALC=
PCRE=
```

**Important:** Replace the absolute paths with the corresponding paths on your own system.

The variables have the following purposes:

| Variable | Purpose |
|---|---|
| `SUPPORT` | Parent directory containing EPICS support modules |
| `EPICS_BASE` | EPICS Base installation |
| `ASYN` | asyn module location |
| `STREAM` | StreamDevice module location |
| `CALC` | Optional calculation support |
| `PCRE` | Optional regular-expression support |

The empty `CALC` and `PCRE` definitions indicate that those optional dependencies are not configured for this project.

The asyn `configure/RELEASE` file includes the parent `RELEASE.local`, allowing these definitions to override its example installation paths.

### 6.4 Build asyn

```bash
cd ~/projects/epics/support/modules/asyn
make -j2
```

### 6.5 Verify the build

```bash
ls lib/linux-arm
```

The compiled libraries should include:

```text
libasyn.so
libasyn.a
```

The installed headers should include:

```text
include/asynPortDriver.h
```

Although `asynPortDriver` was investigated during development, the current camera implementation uses StreamDevice rather than a custom C++ asyn driver.

## 7. Install StreamDevice

StreamDevice is an EPICS device-support module that maps EPICS record processing to instrument command/response protocols.

It uses `.proto` files to describe the commands sent to an instrument and the expected responses.

### 7.1 Clone StreamDevice

```bash
cd ~/projects/epics/support/modules
```

```bash
git clone --recursive -b 2.8.26 https://github.com/paulscherrerinstitute/StreamDevice.git StreamDevice
```

### 7.2 Configure dependencies

The StreamDevice source contains:

```text
configure/RELEASE
```

This file defines dependencies such as:

```makefile
ASYN=$(SUPPORT)/asyn4-36
CALC=$(SUPPORT)/calc-3-7
PCRE=$(SUPPORT)/pcre-7-2
```

These are example paths from the source distribution.

The file also includes:

```makefile
-include $(TOP)/../RELEASE.local
```

This allows StreamDevice to read the shared configuration created in Section 6.

Consequently, the build can locate the installed EPICS Base and asyn modules without requiring the example paths to exist.

The shared configuration also leaves CALC and PCRE unconfigured.

### 7.3 Build StreamDevice

```bash
cd ~/projects/epics/support/modules/StreamDevice
make -j2
```

### 7.4 Verify the StreamDevice library

```bash
ls lib/linux-arm
```

The relevant library files are:

```text
libstream.so
libstream.a
```

The StreamDevice installation also provides database-definition files, including:

```text
dbd/stream.dbd
```

These are used when building the camera IOC.

### 7.5 Build issue encountered during development

During the original installation, the StreamDevice library compiled and installed successfully, but the bundled example IOC (`streamApp`) failed during linking.

The error was:

```text
undefined reference to `pvar_func_vxi11RegisterCommands'
```

The missing registration is associated with asyn's VXI-11 instrument communication support.

The project does not use VXI-11. It uses asyn's ordinary TCP/IP interface.

The original example IOC was left unchanged.

The custom camera IOC subsequently compiled and linked successfully using `libstream.so` and `libasyn.so`.

**Reproducibility note:** This means the StreamDevice installation was sufficient for the project's IOC, but the full upstream example build was not completely successful. A fresh installation should not treat this example-IOC linker failure as resolved. If it occurs, consult [Troubleshooting](troubleshooting.md) and verify the required StreamDevice library separately.

## 8. Verify the EPICS Environment

After installation, the expected structure is:

```text
~/projects/epics/
├── base/
│   ├── bin/linux-arm/
│   ├── lib/linux-arm/
│   └── dbd/
│
└── support/
    └── modules/
        ├── RELEASE.local
        ├── asyn/
        │   ├── include/
        │   ├── lib/linux-arm/
        │   └── dbd/
        │
        └── StreamDevice/
            ├── lib/linux-arm/
            └── dbd/
```

Verify the important components:

```bash
which caget
```

```bash
ls ~/projects/epics/support/modules/asyn/lib/linux-arm/libasyn.so
```

```bash
ls ~/projects/epics/support/modules/StreamDevice/lib/linux-arm/libstream.so
```

If all three checks succeed, the main software dependencies required by our conventional camera IOC are available.

## 9. Building an EPICS IOC Against These Modules

The EPICS environment is shared, but individual IOCs must still declare their dependencies.

For our camera IOC, the important files are:

```text
configure/RELEASE
streamdevice_cameraApp/src/Makefile
```

The `RELEASE` file tells EPICS where the dependencies are installed.

The application Makefile specifies which database definitions and libraries the IOC uses.

The camera IOC links against:

```makefile
streamdevice_camera_LIBS += stream
streamdevice_camera_LIBS += asyn
```

along with the EPICS Base IOC libraries.

It also includes the database definitions needed for StreamDevice and the asyn TCP/IP port driver.

Detailed configuration is documented in [StreamDevice Camera IOC](streamdevice_ioc.md).

## 10. Rebuilding After Dependency Changes

EPICS does not automatically detect every change made to external support modules.

If EPICS Base, asyn or StreamDevice is rebuilt or its installation path changes, dependent IOCs may also need to be rebuilt.

For the camera IOC, run from its root directory:

```bash
make rebuild
```

Before rebuilding, verify that `configure/RELEASE` points to the correct dependency locations.

## 11. Installation Checklist

- [ ] Raspberry Pi OS and development tools available
- [ ] EPICS Base R7.0.10 cloned and built
- [ ] EPICS executable directory added to `PATH`
- [ ] `caget` and `makeBaseApp.pl` available
- [ ] asyn R4-46 cloned and built
- [ ] Shared `RELEASE.local` configured
- [ ] StreamDevice 2.8.26 library built
- [ ] `libasyn.so` available
- [ ] `libstream.so` available
- [ ] Dependency paths verified

## 12. References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [EPICS Base Repository](https://github.com/epics-base/epics-base)
- [asynDriver Repository](https://github.com/epics-modules/asyn)
- [StreamDevice Repository](https://github.com/paulscherrerinstitute/StreamDevice)
- [StreamDevice Documentation](https://paulscherrerinstitute.github.io/StreamDevice/)

---

**Next:** [StreamDevice Camera IOC](streamdevice_ioc.md) explains how to build the conventional IOC, configure the Python TCP interface, and test EPICS communication locally and remotely.
