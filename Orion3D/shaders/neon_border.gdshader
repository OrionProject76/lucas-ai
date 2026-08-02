shader_type canvas_item;

// ⚠️ NE PAS UTILISER TEXTURE_PIXEL_SIZE ICI.
// Ces shaders sont appliqués à des ColorRect, qui n'ont AUCUNE texture :
// TEXTURE_PIXEL_SIZE y vaut (1,1). « border_width * TEXTURE_PIXEL_SIZE.x »
// donnait donc 3.0, et smoothstep(3.0, 0.0, dist) avec dist <= 0.5 rend
// 1 PARTOUT — la « bordure » remplissait tout le rectangle en cyan
// opaque. C'était la cause du fond opaque plein écran, et donc de
// l'impossibilité de voir le bureau à travers la fenêtre.
// Les épaisseurs sont désormais exprimées en fraction de la taille du
// rectangle : indépendant de la résolution, et borné par construction.

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
    float w = border_width * 0.002;
    float border = smoothstep(w, 0.0, dist);
    float glow = smoothstep(w * 4.0, 0.0, dist) * glow_strength * pulse;
    float inner = smoothstep(corner_radius * 0.002, 0.0, dist) * 0.15;
    vec3 final_color = inner_glow.rgb * inner + border_color.rgb * (border + glow);
    float final_alpha = max(inner * inner_glow.a, (border + glow * 0.4) * border_color.a);
    COLOR = vec4(final_color, final_alpha);
}
