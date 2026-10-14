import io
import os
import math
import struct
import wave
import winsound
from typing import List, Tuple

class AudioEngine:
    """
    Synthesizes crisp, studio-grade sound effects in-memory using 44.1kHz PCM WAV:
    - match_detected: ascending celebration chime
    - start: crisp upward blip
    - stop: soft downward blip
    - save: subtle mechanical tick
    
    Plays asynchronously via Windows winmm (winsound.SND_MEMORY) in daemon threads
    with zero external dependencies and zero audio lag.
    """
    _instance = None
    _enabled = True
    _volume = 0.6  # 0.0 to 1.0

    def __init__(self):
        self._sound_cache = {}
        self._pregenerate_sounds()

    @classmethod
    def get(cls) -> "AudioEngine":
        if cls._instance is None:
            cls._instance = AudioEngine()
        return cls._instance

    @classmethod
    def set_enabled(cls, enabled: bool):
        cls._enabled = enabled

    @classmethod
    def is_enabled(cls) -> bool:
        return cls._enabled

    @classmethod
    def set_volume(cls, volume: float):
        """Set volume level between 0.0 and 1.0 (clamped) and re-synthesize waveforms."""
        cls._volume = max(0.0, min(1.0, float(volume)))
        inst = cls.get()
        inst._pregenerate_sounds()

    @classmethod
    def get_volume(cls) -> float:
        return cls._volume

    def _generate_wave(self, notes: List[Tuple[float, float, float, float]]) -> bytes:
        """
        Synthesizes notes into a 44100Hz, 16-bit Mono WAV.
        Each note tuple: (freq_hz, start_sec, duration_sec, amplitude)
        Adds subtle warm 2nd harmonic (warmth) and smooth exponential decay.
        """
        sample_rate = 44100
        total_duration = max(start + dur for _, start, dur, _ in notes) + 0.02
        total_samples = int(sample_rate * total_duration)
        samples = [0.0] * total_samples

        for freq, start, dur, amp in notes:
            start_idx = int(start * sample_rate)
            num_samples = int(dur * sample_rate)
            for i in range(num_samples):
                idx = start_idx + i
                if idx >= total_samples:
                    break
                t = i / sample_rate
                # Smooth 10ms bell attack, gentle exponential decay
                attack = min(1.0, i / (0.010 * sample_rate))
                decay = math.exp(-6.5 * (t / dur))
                env = attack * decay
                # Fundamental sine + gentle octave overtone for warm acoustic timbre
                val = (math.sin(2.0 * math.pi * freq * t) * 0.85 +
                       math.sin(2.0 * math.pi * (freq * 2.0) * t) * 0.15) * amp * env
                samples[idx] += val

        # Normalize and convert to 16-bit signed PCM with perceptual auditory scaling.
        if self._volume <= 0.0:
            scale_factor = 0.0
        else:
            scale_factor = float(self._volume) ** 1.7

        max_val = max((abs(s) for s in samples), default=1.0)
        norm_factor = (32760.0 * scale_factor) / max(max_val, 1e-6)

        raw_data = bytearray()
        for s in samples:
            val = int(max(-32768, min(32767, s * norm_factor)))
            raw_data.extend(struct.pack("<h", val))

        # Pack into WAV container in memory
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(raw_data)

        return buffer.getvalue()

    def _pregenerate_sounds(self):
        """
        Synthesizes and caches ONLY the 4 permitted system sound events:
        - Short, calm, soothing acoustic chimes (all under 0.35s).
        1. match_detected: gentle two-tone glass chime (E5 -> A5)
        2. start: subtle upward acoustic soft blip
        3. stop: soft descending warm tone
        4. save: gentle wooden chime droplet
        """
        self._sound_cache.clear()

        # 1. Match Completed / Detected (Calm, soothing 2-tone chime ~0.35s)
        self._sound_cache["match_detected"] = self._generate_wave([
            (659.25, 0.00, 0.20, 0.45),  # E5 (warm bell)
            (880.00, 0.08, 0.26, 0.55),  # A5 (harmonic resolution)
        ])

        # 2. Start Automation (Calm upward acoustic ping ~0.16s)
        self._sound_cache["start"] = self._generate_wave([
            (523.25, 0.00, 0.10, 0.40),  # C5
            (659.25, 0.05, 0.12, 0.50),  # E5
        ])

        # 3. Stop Automation (Soft downward warm tone ~0.16s)
        self._sound_cache["stop"] = self._generate_wave([
            (659.25, 0.00, 0.09, 0.45),  # E5
            (440.00, 0.04, 0.12, 0.40),  # A4
        ])

        # 4. Save Settings (Gentle wooden drop ~0.10s)
        self._sound_cache["save"] = self._generate_wave([
            (880.00, 0.00, 0.10, 0.45),  # A5
        ])

    def play(self, sound_name: str):
        # Strictly allowed sound events only
        if not self._enabled or self._volume <= 0.0:
            return

        wav_bytes = self._sound_cache.get(sound_name)
        if not wav_bytes:
            return

        try:
            # On Windows, SND_ASYNC with SND_MEMORY is restricted by PlaySound; writing to a temporary file allows 100% single-threaded native SND_ASYNC
            temp_wav = os.path.join(WORKSPACE_DIR, "assets", f"_{sound_name}.wav")
            if not os.path.exists(temp_wav):
                with open(temp_wav, "wb") as f:
                    f.write(wav_bytes)
            winsound.PlaySound(
                temp_wav,
                winsound.SND_FILENAME | winsound.SND_ASYNC
            )
        except Exception as e:
            try:
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            except Exception:
                pass

# Global shortcut helper
def play_sound(sound_name: str):
    AudioEngine.get().play(sound_name)

