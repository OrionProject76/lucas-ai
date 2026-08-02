extends VBoxContainer

@onready var cpu_bar: ProgressBar = $CPU/Bar
@onready var cpu_val: Label = $CPU/Value
@onready var ram_bar: ProgressBar = $RAM/Bar
@onready var ram_val: Label = $RAM/Value
@onready var gpu_bar: ProgressBar = $GPU/Bar
@onready var gpu_val: Label = $GPU/Value

func _ready():
    Global.system_data_updated.connect(_on_update)

func _on_update(cpu: float, ram: float, gpu: float):
    cpu_bar.value = cpu
    cpu_val.text = "%.0f%%" % cpu
    ram_bar.value = ram
    ram_val.text = "%.0f%%" % ram
    gpu_bar.value = gpu
    gpu_val.text = "%.0f%%" % gpu
    cpu_bar.modulate = _get_color(cpu)
    ram_bar.modulate = _get_color(ram)
    gpu_bar.modulate = _get_color(gpu)

func _get_color(value: float) -> Color:
    if value < 50:
        return Color(0, 1, 0.5)
    elif value < 80:
        return Color(1, 0.8, 0)
    else:
        return Color(1, 0.2, 0.2)
