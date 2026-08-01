shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_always;

uniform vec4 base_color : source_color = vec4(0.0, 0.6, 1.0, 0.2);
uniform vec4 glow_color : source_color = vec4(0.0, 1.0, 1.0, 1.0);
uniform vec4 rim_color : source_color = vec4(0.3, 0.95, 1.0, 1.0);
uniform float scanline_count : hint_range(0.0, 300.0) = 150.0;
uniform float scanline_speed : hint_range(0.0, 30.0) = 4.0;
uniform float fresnel_power : hint_range(0.0, 15.0) = 2.0;
uniform float glitch_intensity : hint_range(0.0, 2.0) = 0.12;
uniform float time_scale : hint_range(0.0, 10.0) = 2.0;
uniform float pulse_speed : hint_range(0.0, 20.0) = 3.0;
uniform float wireframe_intensity : hint_range(0.0, 5.0) = 1.0;

varying vec3 world_pos;
varying vec3 world_normal;
varying vec3 barycentric;

float rand(vec2 co){
    return fract(sin(dot(co.xy, vec2(12.9898, 78.233))) * 43758.5453);
}

void vertex() {
    world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
    int index = VERTEX_ID % 3;
    if (index == 0) barycentric = vec3(1.0, 0.0, 0.0);
    else if (index == 1) barycentric = vec3(0.0, 1.0, 0.0);
    else barycentric = vec3(0.0, 0.0, 1.0);
}

void fragment() {
    float time = TIME * time_scale;
    vec3 view_dir = normalize(CAMERA_POSITION_WORLD - world_pos);
    float fresnel = pow(1.0 - abs(dot(view_dir, world_normal)), fresnel_power);

    float scanline = sin(world_pos.y * scanline_count + time * scanline_speed);
    scanline = smoothstep(0.0, 0.15, scanline);

    float h_scan = sin(world_pos.x * scanline_count * 0.7 + time * scanline_speed * 0.8);
    h_scan = smoothstep(0.0, 0.12, h_scan);

    float glitch = rand(vec2(floor(time * 20.0), world_pos.y)) * glitch_intensity;
    float glitch2 = rand(vec2(floor(time * 12.0), world_pos.x)) * glitch_intensity * 0.6;

    float pulse = sin(time * pulse_speed) * 0.5 + 0.5;
    float pulse2 = cos(time * pulse_speed * 0.7) * 0.3 + 0.7;

    vec3 deltas = fwidth(barycentric);
    vec3 wires = smoothstep(deltas * 1.2, deltas, barycentric);
    float wire = 1.0 - min(min(wires.x, wires.y), wires.z);

    vec3 color = mix(base_color.rgb, glow_color.rgb, fresnel * 1.5 + glitch + glitch2);
    color += glow_color.rgb * scanline * 0.8;
    color += rim_color.rgb * h_scan * 0.6;
    color += glow_color.rgb * pulse * 0.4;
    color += glow_color.rgb * wire * wireframe_intensity;
    color += vec3(0.0, 0.4, 0.6) * pulse2 * 0.3;

    float alpha = base_color.a;
    alpha += fresnel * 0.8;
    alpha += scanline * 0.3;
    alpha += wire * 0.5;
    alpha += glitch * 0.2;
    alpha = clamp(alpha, 0.0, 0.95);

    ALBEDO = color;
    ALPHA = alpha;
    EMISSION = color * (3.0 + pulse * 2.0);
}
