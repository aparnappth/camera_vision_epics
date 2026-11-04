
#include "NDPluginRGB.h"

#include "iocsh.h"
#include "epicsExport.h"
#include "asynDriver.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>

// ==========================================
// HSV conversion
// ==========================================

// Convert an 8-bit RGB pixel to HSV.
//
// H, S and V use a 0-255 scale, approximately
// matching Pillow's HSV representation.
//
// Thresholds are taken from the existing
// vision/led_monitor.py implementation.

struct HSVPixel
{
    int h;
    int s;
    int v;
};

static HSVPixel rgbToHSV(
    epicsUInt8 red,
    epicsUInt8 green,
    epicsUInt8 blue
)
{
    const double r = red / 255.0;
    const double g = green / 255.0;
    const double b = blue / 255.0;

    const double maximum = std::max({r, g, b});
    const double minimum = std::min({r, g, b});
    const double delta = maximum - minimum;

    double hue = 0.0;
    double saturation = 0.0;
    const double value = maximum;

    if (maximum > 0.0) {
        saturation = delta / maximum;
    }

    if (delta > 0.0) {
        if (maximum == r) {
            hue = (g - b) / delta;
        }
        else if (maximum == g) {
            hue = 2.0 + (b - r) / delta;
        }
        else {
            hue = 4.0 + (r - g) / delta;
        }

        hue /= 6.0;

        if (hue < 0.0) {
            hue += 1.0;
        }
    }

    HSVPixel hsv;

    hsv.h = static_cast<int>(hue * 255.0);
    hsv.s = static_cast<int>(saturation * 255.0);
    hsv.v = static_cast<int>(value * 255.0);

    return hsv;
}


// ==========================================
// Constructor
// ==========================================

NDPluginRGB::NDPluginRGB(
    const char *portName,
    int queueSize,
    int blockingCallbacks,
    const char *NDArrayPort,
    int NDArrayAddr,
    int maxBuffers,
    size_t maxMemory,
    int priority,
    int stackSize,
    int maxThreads
)
    : NDPluginDriver(
          portName,
          queueSize,
          blockingCallbacks,
          NDArrayPort,
          NDArrayAddr,
          1,
          maxBuffers,
          maxMemory,

          // Supported asyn interfaces
          asynInt32Mask |
              asynInt32ArrayMask |
              asynFloat64Mask |
              asynGenericPointerMask,

          // Supported interrupt interfaces
          asynInt32Mask |
              asynInt32ArrayMask |
              asynFloat64Mask |
              asynGenericPointerMask,

          ASYN_MULTIDEVICE,
          1,
          priority,
          stackSize,
          maxThreads
      ),
      validCount_(0),
      invalidCount_(0)
{
    // ======================================
    // Register frame-validation parameters
    // ======================================

    createParam(
        NDRGBValidFrameString,
        asynParamInt32,
        &NDRGBValidFrame
    );

    createParam(
        NDRGBValidCountString,
        asynParamInt32,
        &NDRGBValidCount
    );

    createParam(
        NDRGBInvalidCountString,
        asynParamInt32,
        &NDRGBInvalidCount
    );

    // ======================================
    // Register RGB mean parameters
    // ======================================

    createParam(
        NDRGBRedMeanString,
        asynParamFloat64,
        &NDRGBRedMean
    );

    createParam(
        NDRGBGreenMeanString,
        asynParamFloat64,
        &NDRGBGreenMean
    );

    createParam(
        NDRGBBlueMeanString,
        asynParamFloat64,
        &NDRGBBlueMean
    );

    // ======================================
    // Register HSV colour-count parameters
    // ======================================

    createParam(
        NDRGBRedCountString,
        asynParamInt32,
        &NDRGBRedCount
    );

    createParam(
        NDRGBYellowCountString,
        asynParamInt32,
        &NDRGBYellowCount
    );

    createParam(
        NDRGBGreenCountString,
        asynParamInt32,
        &NDRGBGreenCount
    );

    createParam(
        NDRGBColoredCountString,
        asynParamInt32,
        &NDRGBColoredCount
    );

    // Combined counts from one image frame
    createParam(
        NDRGBColorCountsString,
        asynParamInt32Array,
        &NDRGBColorCounts
    );

    // ======================================
    // Initialize parameters
    // ======================================

    setIntegerParam(NDRGBValidFrame, 0);
    setIntegerParam(NDRGBValidCount, 0);
    setIntegerParam(NDRGBInvalidCount, 0);

    setDoubleParam(NDRGBRedMean, 0.0);
    setDoubleParam(NDRGBGreenMean, 0.0);
    setDoubleParam(NDRGBBlueMean, 0.0);

    setIntegerParam(NDRGBRedCount, 0);
    setIntegerParam(NDRGBYellowCount, 0);
    setIntegerParam(NDRGBGreenCount, 0);
    setIntegerParam(NDRGBColoredCount, 0);

    setStringParam(
        NDPluginDriverPluginType,
        "NDPluginRGB"
    );

    // Connect to upstream NDArray source
    connectToArrayPort();

    callParamCallbacks();
}


// ==========================================
// NDArray processing
// ==========================================

void NDPluginRGB::processCallbacks(NDArray *pArray)
{
    NDArrayInfo arrayInfo;

    // Called with the plugin mutex held.
    NDPluginDriver::beginProcessCallbacks(pArray);

    pArray->getInfo(&arrayInfo);

    bool valid = true;

    // ======================================
    // Validate RGB1 image format
    // ======================================

    if (pArray->ndims != 3) {
        valid = false;
    }

    if (pArray->dataType != NDUInt8) {
        valid = false;
    }

    if (arrayInfo.colorMode != NDColorModeRGB1) {
        valid = false;
    }

    if (pArray->ndims == 3 &&
        pArray->dims[0].size != 3) {
        valid = false;
    }

    if (pArray->pData == nullptr) {
        valid = false;
    }

    size_t nPixels = 0;

    if (valid) {
        const size_t width = pArray->dims[1].size;
        const size_t height = pArray->dims[2].size;

        if (width == 0 ||
            height == 0 ||
            width > std::numeric_limits<size_t>::max() / height) {
            valid = false;
        }
        else {
            nPixels = width * height;

            if (nPixels >
                    std::numeric_limits<size_t>::max() / 3 ||
                arrayInfo.nElements != 3 * nPixels ||
                nPixels > static_cast<size_t>(
                    std::numeric_limits<epicsInt32>::max()
                )) {
                valid = false;
            }
        }
    }

    // Combined counts for the current frame.
    // Initialized to zero for invalid frames.
    epicsInt32 colorCounts[3] = {0, 0, 0};

    // ======================================
    // RGB statistics and HSV segmentation
    // ======================================

    if (valid) {

        const epicsUInt8 *pixels =
            static_cast<const epicsUInt8 *>(
                pArray->pData
            );

        double redTotal = 0.0;
        double greenTotal = 0.0;
        double blueTotal = 0.0;

        epicsInt32 redCount = 0;
        epicsInt32 yellowCount = 0;
        epicsInt32 greenCount = 0;

        for (size_t i = 0; i < nPixels; ++i) {

            const size_t index = 3 * i;

            const epicsUInt8 red = pixels[index];
            const epicsUInt8 green = pixels[index + 1];
            const epicsUInt8 blue = pixels[index + 2];

            // Accumulate channel intensities
            redTotal += red;
            greenTotal += green;
            blueTotal += blue;

            // Convert pixel to HSV
            const HSVPixel hsv =
                rgbToHSV(red, green, blue);

            const bool brightColoured =
                (hsv.s > 100) &&
                (hsv.v > 100);

            if (!brightColoured) {
                continue;
            }

            if (hsv.h < 15 || hsv.h > 240) {
                ++redCount;
            }
            else if (hsv.h >= 25 && hsv.h <= 50) {
                ++yellowCount;
            }
            else if (hsv.h >= 55 && hsv.h <= 115) {
                ++greenCount;
            }
        }

        // ==================================
        // RGB channel means
        // ==================================

        setDoubleParam(
            NDRGBRedMean,
            redTotal / nPixels
        );

        setDoubleParam(
            NDRGBGreenMean,
            greenTotal / nPixels
        );

        setDoubleParam(
            NDRGBBlueMean,
            blueTotal / nPixels
        );

        // ==================================
        // Individual colour counts
        // ==================================

        const epicsInt32 coloredCount =
            redCount + yellowCount + greenCount;

        setIntegerParam(NDRGBRedCount, redCount);
        setIntegerParam(NDRGBYellowCount, yellowCount);
        setIntegerParam(NDRGBGreenCount, greenCount);
        setIntegerParam(NDRGBColoredCount, coloredCount);

        // ==================================
        // Combined frame-consistent counts
        // ==================================

        colorCounts[0] = redCount;
        colorCounts[1] = yellowCount;
        colorCounts[2] = greenCount;

        ++validCount_;

        setIntegerParam(NDRGBValidFrame, 1);

    }
    else {

        // ==================================
        // Invalid frame handling
        // ==================================

        ++invalidCount_;

        setIntegerParam(NDRGBValidFrame, 0);

        // Clear scalar measurements
        setDoubleParam(NDRGBRedMean, 0.0);
        setDoubleParam(NDRGBGreenMean, 0.0);
        setDoubleParam(NDRGBBlueMean, 0.0);

        setIntegerParam(NDRGBRedCount, 0);
        setIntegerParam(NDRGBYellowCount, 0);
        setIntegerParam(NDRGBGreenCount, 0);
        setIntegerParam(NDRGBColoredCount, 0);
    }

    // ======================================
    // Publish frame counters
    // ======================================

    setIntegerParam(NDRGBValidCount, validCount_);
    setIntegerParam(NDRGBInvalidCount, invalidCount_);

    // Publish scalar parameter updates.
    callParamCallbacks();

    // ======================================
    // Publish the complete count array
    // ======================================

    // One callback contains all three counts
    // from the same processed NDArray.
    doCallbacksInt32Array(
        colorCounts,
        3,
        NDRGBColorCounts,
        0
    );

    // Measurement-only plugin:
    // Do not call endProcessCallbacks()
    // with the incoming NDArray.
    // Do not manually release pArray.
}


// ==========================================
// IOC configuration command
// ==========================================

extern "C" int NDRGBConfigure(
    const char *portName,
    int queueSize,
    int blockingCallbacks,
    const char *NDArrayPort,
    int NDArrayAddr,
    int maxBuffers,
    size_t maxMemory,
    int priority,
    int stackSize,
    int maxThreads
)
{
    NDPluginRGB *pPlugin = new NDPluginRGB(
        portName,
        queueSize,
        blockingCallbacks,
        NDArrayPort,
        NDArrayAddr,
        maxBuffers,
        maxMemory,
        priority,
        stackSize,
        maxThreads
    );

    return pPlugin->start();
}


// ==========================================
// IOC-shell registration
// ==========================================

static const iocshArg arg0 = {
    "portName", iocshArgString
};

static const iocshArg arg1 = {
    "queueSize", iocshArgInt
};

static const iocshArg arg2 = {
    "blockingCallbacks", iocshArgInt
};

static const iocshArg arg3 = {
    "NDArrayPort", iocshArgString
};

static const iocshArg arg4 = {
    "NDArrayAddr", iocshArgInt
};

static const iocshArg arg5 = {
    "maxBuffers", iocshArgInt
};

static const iocshArg arg6 = {
    "maxMemory", iocshArgInt
};

static const iocshArg arg7 = {
    "priority", iocshArgInt
};

static const iocshArg arg8 = {
    "stackSize", iocshArgInt
};

static const iocshArg arg9 = {
    "maxThreads", iocshArgInt
};

static const iocshArg * const args[] = {
    &arg0, &arg1, &arg2, &arg3, &arg4,
    &arg5, &arg6, &arg7, &arg8, &arg9
};

static const iocshFuncDef funcDef = {
    "NDRGBConfigure",
    10,
    args
};

static void configCall(const iocshArgBuf *args)
{
    NDRGBConfigure(
        args[0].sval,
        args[1].ival,
        args[2].ival,
        args[3].sval,
        args[4].ival,
        args[5].ival,
        args[6].ival,
        args[7].ival,
        args[8].ival,
        args[9].ival
    );
}

extern "C" void NDRGBRegister(void)
{
    iocshRegister(&funcDef, configCall);
}

extern "C" {
    epicsExportRegistrar(NDRGBRegister);
}

