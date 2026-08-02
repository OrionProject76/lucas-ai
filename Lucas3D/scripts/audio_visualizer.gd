extends Node

var spectrum: AudioEffectSpectrumAnalyzerInstance
var bus_idx: int = 0
var effect_idx: int = -1

func _ready():
    bus_idx = AudioServer.get_bus_index("Master")
    var effect = AudioEffectSpectrumAnalyzer.new()
    effect.buffer_length = 0.1
    effect.fft_size = AudioEffectSpectrumAnalyzer.FFT_SIZE_2048
    # ⚠️ add_bus_effect() ne rend RIEN en Godot 4 — il rendait l'index
    # en Godot 3. L'affecter était une erreur de compilation qui
    # empêchait le projet ENTIER de démarrer. L'index utile est celui
    # du dernier effet ajouté.
    AudioServer.add_bus_effect(bus_idx, effect)
    effect_idx = AudioServer.get_bus_effect_count(bus_idx) - 1
    spectrum = AudioServer.get_bus_effect_instance(bus_idx, effect_idx)
    print("AudioVisualizer initialise")

func get_band_energy(low_freq: float, high_freq: float) -> float:
    if spectrum:
        return spectrum.get_magnitude_for_frequency_range(low_freq, high_freq).length()
    return 0.0

func get_speech_intensity() -> float:
    return get_band_energy(300, 3000) * 10.0
