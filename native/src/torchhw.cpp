// torchhw: native helper for RetroTorch (Python for S60 1.4.5).
//
// Gives Python the light hardware that PyS60 itself does not expose:
//   * HWRM Light (CHWRMLight): display backlight, keypad light and any
//     extra light targets the phone reports, with intensity and blinking.
//   * ECam (CCamera): the camera's LED flash. A continuous "video light"
//     is what makes a real torch; several ways of switching it on are
//     tried, because phones differ.
//
// Two builds come from this file:
//   torchhw.pyd      S60 3rd Edition FP2: HWRM lights + ECam camera.
//   torchhw_fp1.pyd  S60 3rd Edition FP1 (defined TORCHHW_FP1): HWRM lights
//                    only. FP1 ECam (Symbian OS 9.2) has no New2L, no
//                    MCameraObserver2 and no CCameraAdvancedSettings, and the
//                    FP1 phones that have a camera light at all (N82) use a
//                    xenon tube, which cannot be held on. Linking those APIs
//                    into the module would stop it loading on FP1, taking the
//                    keypad and extra lights down with it, so this build
//                    leaves the camera out and Python uses PyS60's own camera
//                    module for photo-flash bursts there.
//
// Everything runs in the Python thread. Camera callbacks arrive through
// the active scheduler while Python waits (e32.ao_sleep / Ao_lock), and
// only update plain state that Python polls with cam_state(): no Python
// code is ever called from a callback.

#include <e32base.h>
#include <e32std.h>
#include <hwrmlight.h>
#ifndef TORCHHW_FP1
#include <ecam.h>
#include <ecamadvancedsettings.h>
#include <fbs.h>
#endif

#include "Python.h"
#include "symbian_python_ext_util.h"

// --------------------------------------------------------------- log
// A short text log Python can read with torchhw.log() (and write to the
// app's log file), so phone-only behaviour can be diagnosed afterwards.

static char g_log[2048];
static int g_loglen = 0;

static void Log(const char* msg, TInt a = 0, TInt b = 0)
{
    TBuf8<160> line;
    line.Copy(TPtrC8((const TUint8*)msg));
    line.Append(' ');
    line.AppendNum(a);
    line.Append(' ');
    line.AppendNum(b);
    line.Append('\n');
    TInt n = line.Length();
    if (g_loglen + n >= (TInt)sizeof(g_log)) {
        // keep the newest half
        TInt keep = g_loglen / 2;
        Mem::Copy(g_log, g_log + g_loglen - keep, keep);
        g_loglen = keep;
    }
    Mem::Copy(g_log + g_loglen, line.Ptr(), n);
    g_loglen += n;
}

// --------------------------------------------------------------- lights

static CHWRMLight* g_light = NULL;

static TInt LightInit()
{
    if (g_light)
        return KErrNone;
    TRAPD(err, g_light = CHWRMLight::NewL());
    Log("light init", err, g_light ? g_light->SupportedTargets() : -1);
    return err;
}

// --------------------------------------------------------------- camera

#ifndef TORCHHW_FP1

enum TCamState {
    ECamClosed = 0,
    ECamReserving = 1,
    ECamPoweringOn = 2,
    ECamReady = 3,
    ECamFailed = 4
};

NONSHARABLE_CLASS(CTorchCamera) : public CBase, public MCameraObserver, public MCameraObserver2
{
public:
    CTorchCamera() : iCam(NULL), iAdv(NULL), iState(ECamClosed), iErr(KErrNone), iApi(0),
                     iVf(EFalse), iFrames(0), iVideo(0) {}
    ~CTorchCamera() { Close(); }

    // api 2: CCamera::New2L (MCameraObserver2, extended flash modes visible)
    // api 1: CCamera::NewL (MCameraObserver, the classic API PyS60 uses)
    TInt Open(TInt aIndex, TInt aApi)
    {
        Close();
        iApi = aApi;
        TInt err = KErrNone;
        if (aApi == 2) {
            TRAP(err, iCam = CCamera::New2L(*this, aIndex, 0));
        } else {
            TRAP(err, iCam = CCamera::NewL(*(MCameraObserver*)this, aIndex));
        }
        Log("cam new (api,err)", aApi, err);
        if (err != KErrNone) {
            iCam = NULL;
            iState = ECamFailed;
            iErr = err;
            return err;
        }
        iState = ECamReserving;
        iErr = KErrNone;
        iCam->Reserve();
        return KErrNone;
    }

    void Close()
    {
        if (iAdv) {
            delete iAdv;
            iAdv = NULL;
        }
        if (iCam) {
            if (iVideo == 2)
                iCam->StopVideoCapture();
            iVideo = 0;
            if (iVf)
                iCam->StopViewFinder();
            iVf = EFalse;
            if (iState == ECamReady)
                iCam->PowerOff();
            iCam->Release();
            delete iCam;
            iCam = NULL;
        }
        iState = ECamClosed;
    }

    // ---- MCameraObserver (classic)
    void ReserveComplete(TInt aError) { Reserved(aError); }
    void PowerOnComplete(TInt aError) { PoweredOn(aError); }
    void ViewFinderFrameReady(CFbsBitmap& /*aFrame*/) { iFrames++; }
    void ImageReady(CFbsBitmap* /*aBitmap*/, HBufC8* aData, TInt /*aError*/) { delete aData; }
    void FrameBufferReady(MFrameBuffer* aBuf, TInt /*aError*/) { if (aBuf) aBuf->Release(); }

    // ---- MCameraObserver2
    void HandleEvent(const TECAMEvent& aEvent)
    {
        TInt uid = aEvent.iEventType.iUid;
        if (aEvent.iEventType == KUidECamEventReserveComplete) {
            Reserved(aEvent.iErrorCode);
        } else if (aEvent.iEventType == KUidECamEventPowerOnComplete) {
            PoweredOn(aEvent.iErrorCode);
        } else if (aEvent.iEventType == KUidECamEventCameraNoLongerReserved) {
            Log("cam lost (taken by another app)", uid, aEvent.iErrorCode);
            iState = ECamFailed;
            iErr = KErrInUse;
        } else {
            Log("cam event", uid, aEvent.iErrorCode);
        }
    }
    void ViewFinderReady(MCameraBuffer& aBuf, TInt /*aError*/) { iFrames++; aBuf.Release(); }
    void ImageBufferReady(MCameraBuffer& aBuf, TInt /*aError*/) { aBuf.Release(); }
    void VideoBufferReady(MCameraBuffer& aBuf, TInt /*aError*/) { aBuf.Release(); }

    void Reserved(TInt aError)
    {
        Log("cam reserved", aError);
        if (aError != KErrNone) {
            iState = ECamFailed;
            iErr = aError;
            return;
        }
        iState = ECamPoweringOn;
        iCam->PowerOn();
    }

    void PoweredOn(TInt aError)
    {
        Log("cam powered on", aError);
        if (aError != KErrNone) {
            iState = ECamFailed;
            iErr = aError;
            return;
        }
        iState = ECamReady;
        if (iApi == 2) {
            TRAPD(err, iAdv = CCamera::CCameraAdvancedSettings::NewL(*iCam));
            Log("cam adv settings", err, iAdv ? 1 : 0);
            if (err != KErrNone)
                iAdv = NULL;
        }
    }

    // flash modes the camera reports (TCameraInfo), and the advanced
    // settings' list when that interface exists
    TInt InfoModes()
    {
        if (!iCam)
            return 0;
        TCameraInfo info;
        iCam->CameraInfo(info);
        return (TInt)info.iFlashModesSupported;
    }

    TInt AdvModes()
    {
        if (!iAdv)
            return -1;
        return iAdv->SupportedFlashModes();
    }

    // method 0: CCamera::SetFlashL
    // method 1: CCameraAdvancedSettings::SetFlashMode
    TInt SetFlash(TInt aMode, TInt aMethod)
    {
        if (!iCam || iState != ECamReady)
            return KErrNotReady;
        TInt err = KErrNone;
        if (aMethod == 1) {
            if (!iAdv)
                return KErrNotSupported;
            iAdv->SetFlashMode((CCamera::TFlash)aMode);
        } else {
            TRAP(err, iCam->SetFlashL((CCamera::TFlash)aMode));
        }
        Log("cam set flash (mode,err)", aMode, err);
        return err;
    }

    TInt Flash()
    {
        if (!iCam)
            return -1;
        if (iAdv)
            return iAdv->FlashMode();
        return iCam->Flash();
    }

    // Some phones light the LED only while the camera streams frames.
    TInt Viewfinder(TBool aOn)
    {
        if (!iCam || iState != ECamReady)
            return KErrNotReady;
        TInt err = KErrNone;
        if (aOn && !iVf) {
            TSize size(80, 60);
            TRAP(err, iCam->StartViewFinderBitmapsL(size));
            if (err == KErrNone)
                iVf = ETrue;
        } else if (!aOn && iVf) {
            iCam->StopViewFinder();
            iVf = EFalse;
        }
        Log("cam viewfinder (on,err)", aOn, err);
        return err;
    }

    // Video mode: Nokia's camera app lights the LED as a "video light" only in
    // video mode. aLevel 0 = off, 1 = video capture prepared, 2 = also started.
    TInt Video(TInt aLevel)
    {
        if (!iCam || iState != ECamReady)
            return KErrNotReady;
        TInt err = KErrNone;
        if (aLevel == 0) {
            if (iVideo == 2)
                iCam->StopVideoCapture();
            iVideo = 0;
            Log("cam video off");
            return KErrNone;
        }
        TCameraInfo info;
        iCam->CameraInfo(info);
        TUint32 formats = info.iVideoFrameFormatsSupported;
        TUint32 bit = 1;
        while (bit && !(formats & bit))
            bit <<= 1;
        Log("cam video formats (mask,sizes)", (TInt)formats, info.iNumVideoFrameSizesSupported);
        if (!bit || info.iNumVideoFrameSizesSupported <= 0)
            return KErrNotSupported;
        if (iVideo == 0) {
            // the last size index is the smallest on Nokia phones
            TInt size = info.iNumVideoFrameSizesSupported - 1;
            TRAP(err, iCam->PrepareVideoCaptureL((CCamera::TFormat)bit, size, 0, 2, 1));
            Log("cam video prepare (format,err)", (TInt)bit, err);
            if (err != KErrNone)
                return err;
            iVideo = 1;
        }
        if (aLevel == 2 && iVideo == 1) {
            iCam->StartVideoCapture();
            iVideo = 2;
            Log("cam video started");
        }
        return KErrNone;
    }

    CCamera* iCam;
    CCamera::CCameraAdvancedSettings* iAdv;
    TInt iState;
    TInt iErr;
    TInt iApi;
    TBool iVf;
    TInt iFrames;
    TInt iVideo;
};

static CTorchCamera* g_cam = NULL;

#endif  // TORCHHW_FP1: no camera at all (see the top of the file)

// Which camera APIs this build can use: bit 0 = CCamera::NewL (classic),
// bit 1 = CCamera::New2L (FP2, extended flash modes). 0 = no camera code.
static TInt CamApiMask()
{
#ifdef TORCHHW_FP1
    return 0;
#else
    return 3;
#endif
}

// --------------------------------------------------------------- Python

static PyObject* py_version(PyObject* /*self*/, PyObject* /*args*/)
{
    return Py_BuildValue("i", 3);
}

// cam_apis() -> bit mask of camera APIs this build supports (see above)
static PyObject* py_cam_apis(PyObject* /*self*/, PyObject* /*args*/)
{
    return Py_BuildValue("i", CamApiMask());
}

static PyObject* py_log(PyObject* /*self*/, PyObject* /*args*/)
{
    PyObject* r = Py_BuildValue("s#", g_log, g_loglen);
    g_loglen = 0;
    return r;
}

// light_targets() -> bit mask of CHWRMLight targets, or a negative error
static PyObject* py_light_targets(PyObject* /*self*/, PyObject* /*args*/)
{
    TInt err = LightInit();
    if (err != KErrNone)
        return Py_BuildValue("i", err);
    return Py_BuildValue("i", g_light->SupportedTargets());
}

// light_on(targets, intensity=0, duration_ms=0, fade=0) -> error code
// intensity 0 = the phone's default, 1..100 otherwise; duration 0 = forever
static PyObject* py_light_on(PyObject* /*self*/, PyObject* args)
{
    int target, intensity = 0, duration = 0, fade = 0;
    if (!PyArg_ParseTuple(args, "i|iii", &target, &intensity, &duration, &fade))
        return NULL;
    TInt err = LightInit();
    if (err == KErrNone) {
        if (intensity <= 0)
            intensity = KHWRMDefaultIntensity;
        TBool f = EFalse;
        if (fade)
            f = ETrue;
        TRAP(err, g_light->LightOnL(target, duration, intensity, f));
    }
    return Py_BuildValue("i", err);
}

// light_off(targets, fade=0) -> error code
static PyObject* py_light_off(PyObject* /*self*/, PyObject* args)
{
    int target, fade = 0;
    if (!PyArg_ParseTuple(args, "i|i", &target, &fade))
        return NULL;
    TInt err = LightInit();
    if (err == KErrNone) {
        TBool f = EFalse;
        if (fade)
            f = ETrue;
        TRAP(err, g_light->LightOffL(target, KHWRMInfiniteDuration, f));
    }
    return Py_BuildValue("i", err);
}

// light_blink(targets, on_ms, off_ms, intensity=0, duration_ms=0) -> error code
static PyObject* py_light_blink(PyObject* /*self*/, PyObject* args)
{
    int target, on_ms, off_ms, intensity = 0, duration = 0;
    if (!PyArg_ParseTuple(args, "iii|ii", &target, &on_ms, &off_ms, &intensity, &duration))
        return NULL;
    TInt err = LightInit();
    if (err == KErrNone) {
        if (intensity <= 0)
            intensity = KHWRMDefaultIntensity;
        TRAP(err, g_light->LightBlinkL(target, duration, on_ms, off_ms, intensity));
    }
    return Py_BuildValue("i", err);
}

// light_status(target) -> 0 unknown, 1 on, 2 off, 3 blinking
static PyObject* py_light_status(PyObject* /*self*/, PyObject* args)
{
    int target;
    if (!PyArg_ParseTuple(args, "i", &target))
        return NULL;
    if (LightInit() != KErrNone)
        return Py_BuildValue("i", 0);
    return Py_BuildValue("i", (int)g_light->LightStatus(target));
}

// light_reserve(targets, reserve=1) -> error code. A reserved target keeps
// our setting even while other apps are in front.
static PyObject* py_light_reserve(PyObject* /*self*/, PyObject* args)
{
    int target, on = 1;
    if (!PyArg_ParseTuple(args, "i|i", &target, &on))
        return NULL;
    TInt err = LightInit();
    if (err == KErrNone) {
        if (on) {
            TRAP(err, g_light->ReserveLightL(target, ETrue, EFalse));
        } else {
            g_light->ReleaseLight(target);
        }
    }
    Log("light reserve (target,err)", target, err);
    return Py_BuildValue("i", err);
}

static PyObject* py_cam_count(PyObject* /*self*/, PyObject* /*args*/)
{
#ifdef TORCHHW_FP1
    return Py_BuildValue("i", 0);
#else
    return Py_BuildValue("i", CCamera::CamerasAvailable());
#endif
}

// cam_open(index=0, api=2) -> error code; then poll cam_state()
static PyObject* py_cam_open(PyObject* /*self*/, PyObject* args)
{
#ifdef TORCHHW_FP1
    (void)args;
    return Py_BuildValue("i", KErrNotSupported);
#else
    int index = 0, api = 2;
    if (!PyArg_ParseTuple(args, "|ii", &index, &api))
        return NULL;
    if (!(CamApiMask() & (1 << (api - 1))))
        return Py_BuildValue("i", KErrNotSupported);
    if (!g_cam) {
        g_cam = new CTorchCamera;
        if (!g_cam)
            return Py_BuildValue("i", KErrNoMemory);
    }
    return Py_BuildValue("i", g_cam->Open(index, api));
#endif
}

// cam_state() -> (state, error, info_flash_modes, adv_flash_modes, frames)
static PyObject* py_cam_state(PyObject* /*self*/, PyObject* /*args*/)
{
#ifdef TORCHHW_FP1
    return Py_BuildValue("(iiiii)", 0, 0, 0, -1, 0);
#else
    if (!g_cam)
        return Py_BuildValue("(iiiii)", ECamClosed, 0, 0, -1, 0);
    return Py_BuildValue("(iiiii)", g_cam->iState, g_cam->iErr, g_cam->InfoModes(),
                         g_cam->AdvModes(), g_cam->iFrames);
#endif
}

// cam_flash(mode, method=0) -> error code (mode: CCamera::TFlash bits)
static PyObject* py_cam_flash(PyObject* /*self*/, PyObject* args)
{
#ifdef TORCHHW_FP1
    (void)args;
    return Py_BuildValue("i", KErrNotSupported);
#else
    int mode, method = 0;
    if (!PyArg_ParseTuple(args, "i|i", &mode, &method))
        return NULL;
    if (!g_cam)
        return Py_BuildValue("i", KErrNotReady);
    return Py_BuildValue("i", g_cam->SetFlash(mode, method));
#endif
}

static PyObject* py_cam_flash_mode(PyObject* /*self*/, PyObject* /*args*/)
{
#ifdef TORCHHW_FP1
    return Py_BuildValue("i", -1);
#else
    if (!g_cam)
        return Py_BuildValue("i", -1);
    return Py_BuildValue("i", g_cam->Flash());
#endif
}

// cam_viewfinder(on) -> error code
static PyObject* py_cam_viewfinder(PyObject* /*self*/, PyObject* args)
{
#ifdef TORCHHW_FP1
    (void)args;
    return Py_BuildValue("i", KErrNotSupported);
#else
    int on;
    if (!PyArg_ParseTuple(args, "i", &on))
        return NULL;
    if (!g_cam)
        return Py_BuildValue("i", KErrNotReady);
    TBool b = EFalse;
    if (on)
        b = ETrue;
    return Py_BuildValue("i", g_cam->Viewfinder(b));
#endif
}

// cam_video(level) -> error code; 0 off, 1 prepared, 2 recording frames
static PyObject* py_cam_video(PyObject* /*self*/, PyObject* args)
{
#ifdef TORCHHW_FP1
    (void)args;
    return Py_BuildValue("i", KErrNotSupported);
#else
    int level;
    if (!PyArg_ParseTuple(args, "i", &level))
        return NULL;
    if (!g_cam)
        return Py_BuildValue("i", KErrNotReady);
    return Py_BuildValue("i", g_cam->Video(level));
#endif
}

static PyObject* py_cam_close(PyObject* /*self*/, PyObject* /*args*/)
{
#ifndef TORCHHW_FP1
    if (g_cam)
        g_cam->Close();
#endif
    Log("cam closed");
    Py_INCREF(Py_None);
    return Py_None;
}

// close() frees everything (the app calls it on exit)
static PyObject* py_close(PyObject* /*self*/, PyObject* /*args*/)
{
#ifndef TORCHHW_FP1
    if (g_cam) {
        delete g_cam;
        g_cam = NULL;
    }
#endif
    if (g_light) {
        delete g_light;
        g_light = NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

static const PyMethodDef torchhw_methods[] = {
    {"version", (PyCFunction)py_version, METH_VARARGS, NULL},
    {"cam_apis", (PyCFunction)py_cam_apis, METH_VARARGS, NULL},
    {"log", (PyCFunction)py_log, METH_VARARGS, NULL},
    {"light_targets", (PyCFunction)py_light_targets, METH_VARARGS, NULL},
    {"light_on", (PyCFunction)py_light_on, METH_VARARGS, NULL},
    {"light_off", (PyCFunction)py_light_off, METH_VARARGS, NULL},
    {"light_blink", (PyCFunction)py_light_blink, METH_VARARGS, NULL},
    {"light_status", (PyCFunction)py_light_status, METH_VARARGS, NULL},
    {"light_reserve", (PyCFunction)py_light_reserve, METH_VARARGS, NULL},
    {"cam_count", (PyCFunction)py_cam_count, METH_VARARGS, NULL},
    {"cam_open", (PyCFunction)py_cam_open, METH_VARARGS, NULL},
    {"cam_state", (PyCFunction)py_cam_state, METH_VARARGS, NULL},
    {"cam_flash", (PyCFunction)py_cam_flash, METH_VARARGS, NULL},
    {"cam_flash_mode", (PyCFunction)py_cam_flash_mode, METH_VARARGS, NULL},
    {"cam_viewfinder", (PyCFunction)py_cam_viewfinder, METH_VARARGS, NULL},
    {"cam_video", (PyCFunction)py_cam_video, METH_VARARGS, NULL},
    {"cam_close", (PyCFunction)py_cam_close, METH_VARARGS, NULL},
    {"close", (PyCFunction)py_close, METH_VARARGS, NULL},
    {NULL, NULL, 0, NULL}
};

extern "C" {
DL_EXPORT(void) inittorchhw(void)
{
    Py_InitModule("torchhw", (PyMethodDef*)torchhw_methods);
}
}
