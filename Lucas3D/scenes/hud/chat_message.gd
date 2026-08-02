extends HBoxContainer

@onready var icon: Label = $Icon
@onready var text_label: RichTextLabel = $Text

func set_message(text: String, from_lucas: bool):
    if from_lucas:
        icon.text = "O"
        text_label.modulate = Color(0, 1, 1)
        text_label.text = "[color=#00ffff]" + text + "[/color]"
    else:
        icon.text = "U"
        text_label.modulate = Color(1, 1, 1)
        text_label.text = text
