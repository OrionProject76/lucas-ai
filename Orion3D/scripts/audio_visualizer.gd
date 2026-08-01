extends Node

var spectrum: AudioEffectSpectrumAnalyzerInstance
var bus_idx: int = 0
var effect_idx: int = -1

func _ready():
    bus_idx = AudioServer.get_bus_index("Master")
    var effect = AudioEffectSpectrumAnalyzer.new()
    effect.buffer_length = 0.1
    effect.fft_size = AudioEffectSpectrumAnalyzer.FFT_SIZE_2048
    effect_idx = AudioServer.add_bus_effect(bus_idx, effect)
    spectrum = AudioServer.get_bus_effect_instance(bus_idx, effect_idx)
    print("AudioVisualizer initialise")

func get_band_energy(low_freq: float, high_freq: float) -> float:
    if spectrum:
        return spectrum.get_magnitude_for_frequency_range(low_freq, high_freq).length()
    return 0.0

func get_speech_intensity() -> float:
    return get_band_energy(300, 3000) * 10.0
