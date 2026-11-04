
#ifndef NDPluginRGB_H
#define NDPluginRGB_H

#include <cstddef>
#include "NDPluginDriver.h"

// ==========================================
// Frame validation parameters
// ==========================================

#define NDRGBValidFrameString   "RGB_VALID_FRAME"
#define NDRGBValidCountString   "RGB_VALID_COUNT"
#define NDRGBInvalidCountString "RGB_INVALID_COUNT"

// ==========================================
// RGB channel statistics
// ==========================================

#define NDRGBRedMeanString   "RGB_RED_MEAN"
#define NDRGBGreenMeanString "RGB_GREEN_MEAN"
#define NDRGBBlueMeanString  "RGB_BLUE_MEAN"

// ==========================================
// HSV colour segmentation measurements
// ==========================================

#define NDRGBRedCountString     "RGB_RED_COUNT"
#define NDRGBYellowCountString  "RGB_YELLOW_COUNT"
#define NDRGBGreenCountString   "RGB_GREEN_COUNT"
#define NDRGBColoredCountString "RGB_COLORED_COUNT"

#define NDRGBColorCountsString "RGB_COLOR_COUNTS"


class NDPluginRGB : public NDPluginDriver
{
public:
    NDPluginRGB(
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
    );

    void processCallbacks(NDArray *pArray) override;

private:
    // Frame validation
    int NDRGBValidFrame;
    int NDRGBValidCount;
    int NDRGBInvalidCount;

    // RGB means
    int NDRGBRedMean;
    int NDRGBGreenMean;
    int NDRGBBlueMean;

    // HSV segmentation results
    int NDRGBRedCount;
    int NDRGBYellowCount;
    int NDRGBGreenCount;
    int NDRGBColoredCount;
    int NDRGBColorCounts;


    // Internal counters
    int validCount_;
    int invalidCount_;
};


// IOC configuration command
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
);

#endif

