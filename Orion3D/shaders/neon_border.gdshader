shader_type canvas_item;

uniform vec4 border_color : source_color = vec4(0.0, 1.0, 1.0, 1.0);
uniform vec4 inner_glow : source_color = vec4(0.0, 0.4, 0.6, 0.3);
uniform float border_width : hint_range(0.0, 20.0) = 2.5;
uniform float glow_strength : hint_range(0.0, 8.0) = 2.0;
uniform float pulse_speed : hint_range(0.0, 5.0) = 1.5;
uniform float corner_radius : hint_range(0.0, 100.0) = 12.0;
uniform bool animated = true;

void fragment() {
    vec2 uv = UV;
    float time = TIME * pulse_speed;
    float pulse = animated ? sin(time) * 0.3 + 0.7 : 1.0;
    float dx = min(uv.x, 1.0 - uv.x);
    float dy = min(uv.y, 1.0 - uv.y);
    float dist = min(dx, dy);
    float border = smoothstep(border_width * TEXTURE_PIXEL_SIZE.x, 0.0, dist);
    float glow = smoothstep(border_width * TEXTURE_PIXEL_SIZE.x * 4.0, 0.0, dist) * glow_strength * pulse;
    float inner = smoothstep(corner_radius * TEXTURE_PIXEL_SIZE.x, 0.0, dist) * 0.15;
    vec3 final_color = inner_glow.rgb * inner + border_color.rgb * (border + glow);
    float final_alpha = max(inner * inner_glow.a, (border + glow * 0.4) * border_color.a);
    COLOR = vec4(final_color, final_alpha);
}
