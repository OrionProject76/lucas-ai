shader_type canvas_item;

// ⚠️ Même piège que neon_border : TEXTURE_PIXEL_SIZE vaut (1,1) sur un
// ColorRect. La grille se calculait donc sur des coordonnées écrasées et
// couvrait tout. SCREEN_PIXEL_SIZE est valide ici et vaut exactement
// 1/taille du viewport — ce ColorRect couvre l'écran entier.

uniform vec4 grid_color : source_color = vec4(0.0, 0.5, 0.7, 0.1);
uniform vec4 accent_color : source_color = vec4(0.0, 0.9, 1.0, 0.2);
uniform float grid_size : hint_range(10.0, 200.0) = 60.0;
uniform float line_width : hint_range(0.5, 5.0) = 1.0;
uniform float speed : hint_range(0.0, 5.0) = 0.5;
uniform float fade_distance : hint_range(0.0, 1.0) = 0.3;

void fragment() {
    vec2 uv = UV;
    float time = TIME * speed;
    vec2 grid_uv = uv / SCREEN_PIXEL_SIZE;
    grid_uv.y += time * 30.0;
    float x_grid = abs(fract(grid_uv.x / grid_size) - 0.5) * 2.0;
    float y_grid = abs(fract(grid_uv.y / grid_size) - 0.5) * 2.0;
    float x_line = smoothstep(line_width, 0.0, (1.0 - x_grid) * grid_size);
    float y_line = smoothstep(line_width, 0.0, (1.0 - y_grid) * grid_size);
    float grid = max(x_line, y_line);
    float center_dist = distance(uv, vec2(0.5));
    float center_fade = smoothstep(0.0, fade_distance, center_dist);
    float edge_fade = smoothstep(0.0, 0.15, min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y)));
    vec3 color = mix(grid_color.rgb, accent_color.rgb, x_line * y_line);
    float alpha = grid * center_fade * edge_fade * grid_color.a;
    COLOR = vec4(color, alpha);
}
