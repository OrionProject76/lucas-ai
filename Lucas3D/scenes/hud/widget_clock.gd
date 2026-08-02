extends VBoxContainer

@onready var time_label: Label = $Time
@onready var date_label: Label = $Date

func _ready():
    _update_time()

func _process(_delta):
    _update_time()

func _update_time():
    var now = Time.get_datetime_dict_from_system()
    time_label.text = "%02d:%02d:%02d" % [now["hour"], now["minute"], now["second"]]
    var months = ["Jan", "Fev", "Mar", "Avr", "Mai", "Jun", "Jul", "Aou", "Sep", "Oct", "Nov", "Dec"]
    date_label.text = "%02d %s %d" % [now["day"], months[now["month"] - 1], now["year"]]
