import numpy as np
import sounddevice as sd
SR = 44100


def glissando(start_freq, end_freq, duration_ms):
    duration = duration_ms / 1000.0
    t = np.linspace(0, duration, int(SR * duration), endpoint=False)

    # Linear frequency sweep
    freq = np.linspace(start_freq, end_freq, len(t))

    # Integrate frequency to phase
    phase = 2 * np.pi * np.cumsum(freq) / SR

    return np.sin(phase).astype(np.float32)


def red_alert():
    cpu_factor = 3
    adj = max(1, 72 // cpu_factor)  # = 24

    duration = 20 * adj  # 480 ms

    sound = []

    for _ in range(5):
        sound.append(glissando(80, 2000, duration))
        sound.append(glissando(2000, 80, duration))

    sound = 0.4 * np.concatenate(sound)

    sd.play(sound, SR)
    sd.wait()


if __name__ == "__main__":
    red_alert()