extends VBoxContainer

@onready var bars_container: HBoxContainer = $Bars
var bar_count: int = 16
var bars: Array[ColorRect] = []

func _ready():
    for i in range(bar_count):
        var bar = ColorRect.new()
        bar.custom_minimum_size = Vector2(8, 10)
        bar.color = Color(0, 0.8, 1)
        bar.size_flags_vertical = 3
        bars_container.add_child(bar)
        bars.append(bar)

func _process(_delta):
    if not AudioVisualizer:
        return
    for i in range(bar_count):
        var freq_low = 80 + i * 200
        var freq_high = freq_low + 200
        var energy = AudioVisualizer.get_band_energy(freq_low, freq_high)
        var target_height = 10 + energy * 200
        bars[i].custom_minimum_size.y = lerp(bars[i].custom_minimum_size.y, target_height, 0.3)
        var hue = 0.5 + (i / float(bar_count)) * 0.2
        bars[i].color = Color.from_hsv(hue, 0.8, 1.0)
