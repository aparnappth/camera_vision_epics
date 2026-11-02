# EPICS Environment Setup on Raspberry Pi

This document describes the installation and configuration of EPICS Base and the support modules used by the StreamDevice and areaDetector camera IOCs on a Raspberry Pi Zero 2 W.

The StreamDevice implementation uses an asyn TCP/IP connection to a Python camera server. The separate areaDetector experiment uses NDDriverStdArrays to accept image arrays from Python and NDPluginStdArrays to publish them for Phoebus. Both use the same EPICS Base and asyn installation.

For application-specific IOC configuration and testing, see [StreamDevice Camera IOC](streamdevice_ioc.md). The areaDetector IOC configuration is documented separately in [areaDetector Camera IOC](areadetector_ioc.md).

## 1. Development Environment

### Hardware

- Raspberry Pi Zero 2 W
- Sony IMX219 8 MP CSI camera
- Network connection for SSH access

### Software

| Component | Version |
|---|---|
| Operating system | Raspberry Pi OS 13 (Trixie), 32-bit |
| Target architecture | `linux-arm` |
| EPICS Base | R7.0.10 |
| asyn | R4-46 |
| StreamDevice | 2.8.26 |
| ADCore | R3-14 |
| NDDriverStdArrays | R1-3 |
| busy | R1-7-4 |
| libxml2 | 2.9.14 |
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
│           ├── StreamDevice/
│           ├── ADCore/
│           ├── NDDriverStdArrays/
│           └── busy/
│
└── hobby/
    └── camera/
        └── camera_vision_epics/
```

This separation allows EPICS Base and support modules to be reused by other projects.

The camera project contains its own IOC source files and copies of the required areaDetector database templates, but does not contain the external EPICS Base or support-module source trees.

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

## 6. Shared Support-Module Configuration (`RELEASE.local`)

Support modules use EPICS RELEASE files to locate their dependencies. For example, the asyn source contains:

```text
configure/RELEASE
```

This file defines paths to EPICS Base and optional support modules.

To keep module paths consistent, the installation uses a shared configuration file in the parent support directory:

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
ADCORE=$(SUPPORT)/ADCore
NDDRIVERSTDARRAYS=$(SUPPORT)/NDDriverStdArrays
BUSY=$(SUPPORT)/busy
AUTOSAVE=
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
| `ADCORE` | areaDetector core module location |
| `NDDRIVERSTDARRAYS` | Channel Access waveform-to-NDArray driver location |
| `BUSY` | EPICS busy record-support module location |
| `AUTOSAVE` | Optional autosave support; left unset for the busy build |
| `CALC` | Optional calculation support |
| `PCRE` | Optional regular-expression support |

The empty `CALC`, `PCRE`, and `AUTOSAVE` definitions indicate that these optional dependencies are not configured in this installation. Entries for modules not yet installed are paths for subsequent build steps; they do not install the modules themselves.

The asyn, StreamDevice and busy builds use their RELEASE include mechanisms to read the shared configuration. ADCore and NDDriverStdArrays are explicitly connected to it in Section 9.4 and Section 10.


## 7. Install asyn

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

The asyn source reads dependency locations through its EPICS RELEASE configuration. The shared `RELEASE.local` defined in Section 6 supplies the local paths and overrides upstream example paths.

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


## 8. Install StreamDevice

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


## 9. Install ADCore

ADCore provides NDArray handling and standard processing plugins for the areaDetector experiment. The new IOC uses the existing EPICS Base and asyn installation rather than a second EPICS environment. Frames are acquired by Picamera2 in Python and sent to NDDriverStdArrays; ADCore does not directly control the IMX219 in this implementation.

### 8.1 Check the Raspberry Pi build environment

The tested Pi Zero 2 W runs 32-bit Raspberry Pi OS 13 (Trixie), reports `armv7l` from `uname -m`, and uses EPICS architecture `linux-arm`:

```bash
cat /etc/os-release
uname -m
~/projects/epics/base/startup/EpicsHostArch
free -h
df -h ~/projects/epics
```

During development the Pi reported about 425 MiB of usable RAM and ample disk space. Use a single compilation job (`make -j1`) for these C++ modules to reduce peak memory pressure. The verified toolchain included GCC/G++ 14.2.0 and GNU Make 4.4.1. The installed libcamera version was 0.7.2; libcamera is used by Picamera2, not linked into NDDriverStdArrays.

### 8.2 Install the libxml2 development files

ADCore links against libxml2. On this Pi the initial `pkg-config` check failed because the development files were not installed. Install them:

```bash
sudo apt update
sudo apt install libxml2-dev
pkg-config --modversion libxml-2.0
pkg-config --cflags --libs libxml-2.0
```

The tested installation returned version `2.9.14` and `-I/usr/include/libxml2 -lxml2`. Verify the header if needed:

```bash
ls /usr/include/libxml2/libxml/parser.h
```

### 8.3 Clone ADCore and NDDriverStdArrays source

Install the modules **outside** the camera project repository, alongside asyn and StreamDevice:

```bash
cd ~/projects/epics/support/modules
git clone --branch R3-14 --depth 1 https://github.com/areaDetector/ADCore.git ADCore
git clone --branch R1-3 --depth 1 https://github.com/areaDetector/NDDriverStdArrays.git NDDriverStdArrays
```

`ADCore` supplies the NDArray infrastructure and processing plugins. `NDDriverStdArrays` receives image arrays from EPICS Channel Access clients and converts them to NDArrays; it depends on ADCore. These are separate modules, not a direct libcamera/IMX219 areaDetector driver.

### 8.4 Connect the modules to the shared RELEASE.local

The shared `RELEASE.local` from Section 6 contains the following module paths:

```makefile
ADCORE=$(SUPPORT)/ADCore
NDDRIVERSTDARRAYS=$(SUPPORT)/NDDriverStdArrays
```

Both cloned modules use a `configure/RELEASE` file that can include a module-local `configure/RELEASE.local`. For **each** module, create that local file with:

```makefile
include $(TOP)/../RELEASE.local
```

From the support directory:

```bash
printf '%s\n' 'include $(TOP)/../RELEASE.local' > ADCore/configure/RELEASE.local
printf '%s\n' 'include $(TOP)/../RELEASE.local' > NDDriverStdArrays/configure/RELEASE.local
```

`$(TOP)` is the module root during the EPICS build, so `$(TOP)/../RELEASE.local` resolves to the shared configuration in `modules/`. Do not replace the upstream `configure/CONFIG` files. Verify that ADCore resolves the paths:

```bash
cd ~/projects/epics/support/modules/ADCore
make -s -f configure/CONFIG TOP=. -p 2>/dev/null | grep -E '^(EPICS_BASE|ASYN|ADCORE) *='
```

### 8.5 Configure and build ADCore

ADCore has optional support for PVAccess, HDF5, JPEG, TIFF, NetCDF, GraphicsMagick and other features. For the verified Channel Access waveform experiment, no optional file-writing or PVAccess plugin was required. The standard `NDPluginStdArrays` plugin is included in the normal ADCore plugin build.

The build was configured to use system libxml2. Add these settings to `ADCore/configure/CONFIG_SITE`:

```makefile
XML2_EXTERNAL = YES
XML2_INCLUDE = /usr/include/libxml2
```

The existing `CONFIG` file includes `CONFIG_SITE`; this is why these settings take effect. Verify and build:

```bash
cd ~/projects/epics/support/modules/ADCore
make -s -f configure/CONFIG TOP=. -p 2>/dev/null | grep -E '^(XML2_EXTERNAL|XML2_INCLUDE) *='
make -j1
ls -l lib/linux-arm/libADBase.so
ls -l lib/linux-arm/libNDPlugin.so
```

The two libraries were generated successfully on the Pi. `libADBase.so` supplies the core detector classes, and `libNDPlugin.so` includes `NDPluginStdArrays`. This verifies the libraries' presence; IOC operation is tested separately.


## 10. Build NDDriverStdArrays

NDDriverStdArrays accepts Channel Access waveform arrays and converts them into NDArrays for ADCore plugins. It depends on ADCore, so build ADCore first.

### 9.1 Compile and verify

With ADCore available through the shared configuration:

```bash
cd ~/projects/epics/support/modules/NDDriverStdArrays
make -s -f configure/CONFIG TOP=. -p 2>/dev/null | grep -E '^(EPICS_BASE|ASYN|ADCORE) *='
make -j1
ls -l lib/linux-arm/libNDDriverStdArrays.so
```

The library was successfully built. Its IOC-shell registration command is `NDDriverStdArraysConfig`, with five arguments: port name, maximum buffers, maximum memory, thread priority and stack size. The project's IOC uses it to create the `STDARRAYS` asyn port; the ADCore plugin is configured separately.


## 11. Install busy Record Support

The areaDetector database templates use the EPICS `busy` record type, which is supplied by a separate support module.

### 10.1 Clone, configure and build

The first IOC startup failed while loading the standard areaDetector templates with `Record type 'busy' ... not found`. The templates use `busy` records (including `AcquireBusy` and `PreAllocBuffers`), which are not part of EPICS Base. Install the busy module:

```bash
cd ~/projects/epics/support/modules
git clone --branch R1-7-4 --depth 1 https://github.com/epics-modules/busy.git busy
```

The upstream busy `configure/RELEASE` contains example paths but also includes `$(TOP)/../RELEASE.local`. Add the following to the shared file, leaving its existing entries intact:

```makefile
BUSY=$(SUPPORT)/busy
AUTOSAVE=
```

`AUTOSAVE` was left empty because the busy module's bundled test application references it, but the camera IOC does not require autosave for this experiment. Verify and build:

```bash
cd ~/projects/epics/support/modules/busy
make -s -f configure/CONFIG TOP=. -p 2>/dev/null | grep -E '^(EPICS_BASE|ASYN|BUSY|AUTOSAVE) *='
make -j1
ls -l lib/linux-arm/libbusy.so
ls -l dbd/busyRecord.dbd
ls -l dbd/busySupport.dbd
```

**Both `busyRecord.dbd` and `busySupport.dbd` are important.** Adding only `busyRecord.dbd` allowed the IOC to recognize the record type but produced a second startup error: the `busy` record's `asynInt32` device support was unavailable. `busySupport.dbd` supplies the `device(busy,INST_IO,asynBusyInt32,"asynInt32")` registration. The areaDetector IOC therefore includes both DBDs and links `libbusy.so`. Do not replace the upstream `busy` records with `bo` records merely to avoid this dependency.


## 12. Verify the Complete EPICS Environment

After installation, the shared environment should contain all modules needed by the two IOCs:

```text
~/projects/epics/
├── base/
│   ├── bin/linux-arm/
│   ├── lib/linux-arm/
│   └── dbd/
└── support/
    └── modules/
        ├── RELEASE.local
        ├── asyn/
        ├── StreamDevice/
        ├── ADCore/
        ├── NDDriverStdArrays/
        └── busy/
```

Verify the EPICS tools and installed libraries:

```bash
which caget
which makeBaseApp.pl
ls ~/projects/epics/support/modules/asyn/lib/linux-arm/libasyn.so
ls ~/projects/epics/support/modules/StreamDevice/lib/linux-arm/libstream.so
ls ~/projects/epics/support/modules/ADCore/lib/linux-arm/libADBase.so
ls ~/projects/epics/support/modules/ADCore/lib/linux-arm/libNDPlugin.so
ls ~/projects/epics/support/modules/NDDriverStdArrays/lib/linux-arm/libNDDriverStdArrays.so
ls ~/projects/epics/support/modules/busy/lib/linux-arm/libbusy.so
ls ~/projects/epics/support/modules/busy/dbd/busyRecord.dbd
ls ~/projects/epics/support/modules/busy/dbd/busySupport.dbd
```

These checks establish that the build outputs exist; they do not replace starting and testing each IOC. The StreamDevice IOC and areaDetector IOC have separate application-level instructions linked below.

## 13. Building Project IOCs Against the Modules

The EPICS environment is shared, but individual IOCs must still declare their dependencies.

For the StreamDevice camera IOC, the important files are:

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

Detailed StreamDevice configuration is documented in [StreamDevice Camera IOC](streamdevice_ioc.md). The separate areaDetector IOC links against `NDDriverStdArrays`, `NDPlugin`, `ADBase`, `busy` and `asyn`, and includes `busyRecord.dbd` and `busySupport.dbd` in addition to the areaDetector and asyn definitions. See [areaDetector Camera IOC](areadetector_ioc.md).

## 14. Rebuilding After Dependency Changes

EPICS does not automatically detect every change made to external support modules.

If EPICS Base or a support module is rebuilt, upgraded, or moved to another location, applications depending on it may also need to be rebuilt.

Before rebuilding, verify that the application's `configure/RELEASE` file points to the correct dependency locations.

For an ordinary build, run from the corresponding IOC root directory:

```bash
make -j1
```

The `-j1` option limits compilation to one job, reducing memory usage on the Raspberry Pi Zero 2 W.

If a dependency has changed and a complete rebuild is required, run:

```bash
make rebuild
```

This applies to both the StreamDevice camera IOC and the areaDetector camera IOC.

For the areaDetector implementation, dependencies should be built in the appropriate order: EPICS Base and asyn first, followed by ADCore and NDDriverStdArrays. The busy support module must also be available before rebuilding the areaDetector IOC.

Rebuilding an IOC does not automatically rebuild its external support modules. Those modules must be rebuilt separately when necessary.

## 15. Installation Checklist

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
- [ ] `libxml2-dev` installed and `pkg-config` check passes
- [ ] ADCore R3-14 built (`libADBase.so`, `libNDPlugin.so`)
- [ ] NDDriverStdArrays R1-3 built (`libNDDriverStdArrays.so`)
- [ ] busy R1-7-4 built (`libbusy.so`, busy DBD files)
- [ ] Shared `RELEASE.local` includes `ADCORE`, `NDDRIVERSTDARRAYS`, `BUSY`
- [ ] areaDetector IOC dependencies configured separately

## 16. References

- [EPICS Documentation](https://docs.epics-controls.org/)
- [EPICS Base Repository](https://github.com/epics-base/epics-base)
- [asynDriver Repository](https://github.com/epics-modules/asyn)
- [StreamDevice Repository](https://github.com/paulscherrerinstitute/StreamDevice)
- [StreamDevice Documentation](https://paulscherrerinstitute.github.io/StreamDevice/)
- [ADCore Repository](https://github.com/areaDetector/ADCore)
- [NDDriverStdArrays Repository](https://github.com/areaDetector/NDDriverStdArrays)
- [EPICS busy Repository](https://github.com/epics-modules/busy)

---

**Next:** [StreamDevice Camera IOC](streamdevice_ioc.md) describes the conventional TCP/StreamDevice implementation. [areaDetector Camera IOC](areadetector_ioc.md) describes the separate image-array IOC and Picamera2/Phoebus experiment.
