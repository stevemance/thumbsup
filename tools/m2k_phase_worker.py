#!/opt/labctl/venv/bin/python3
"""ADALM2000 worker for tools/telem_truth.py (runs under the labctl venv, which has libm2k).

Wiring: M2K analog CH2 (+2/-2) across two weapon motor phase wires.
Protocol on stdin: 'CAP <out.npy>' captures CH2 free-running and prints
'DONE <freq_hz> <vpp> <vrms> <snr>'; freq is the commutation fundamental,
so eRPM = freq * 60.  'QUIT' exits."""
import sys, libm2k, numpy as np
RATE, N = 1_000_000, 500_000
ctx = libm2k.m2kOpen(); ctx.calibrateADC(); ctx.setTimeout(8000)
ain = ctx.getAnalogIn(); ain.reset()
ain.enableChannel(0, True); ain.enableChannel(1, True)
ain.setSampleRate(RATE); ain.setRange(1, libm2k.PLUS_MINUS_25V)
trig = ain.getTrigger()
for ch in (0, 1): trig.setAnalogMode(ch, libm2k.ALWAYS)
print("READY", flush=True)
for line in sys.stdin:
    p = line.split()
    if not p or p[0] == "QUIT": break
    try:
        ain.startAcquisition(N); d = ain.getSamples(N); ain.stopAcquisition()
        x = np.asarray(d[1], dtype=float); np.save(p[1], x)
        # PWM (~24 kHz) is far above the commutation fundamental; low-pass by block-averaging to 20 kHz.
        k = 50; y = x[: len(x) // k * k].reshape(-1, k).mean(axis=1); fs = RATE / k
        y = y - y.mean(); w = np.hanning(len(y))
        spec = np.abs(np.fft.rfft(y * w)); f = np.fft.rfftfreq(len(y), 1 / fs)
        band = (f > 20) & (f < 5000)
        i = np.argmax(spec * band)
        # parabolic interpolation for sub-bin accuracy
        if 0 < i < len(spec) - 1:
            a, b, c = spec[i - 1], spec[i], spec[i + 1]; off = 0.5 * (a - c) / (a - 2 * b + c)
        else: off = 0
        fpk = (i + off) * (f[1] - f[0])
        snr = spec[i] / (np.median(spec[band]) + 1e-9)
        print(f"DONE {fpk:.2f} {x.max()-x.min():.2f} {np.sqrt(np.mean((x-x.mean())**2)):.3f} {snr:.1f}", flush=True)
    except Exception as e:
        try: ain.stopAcquisition()
        except Exception: pass
        print(f"ERR {e}", flush=True)
libm2k.contextClose(ctx)
