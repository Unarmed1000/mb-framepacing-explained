#!/usr/bin/env python3
"""Generate the upscaler artifact videos: the render scale videos' scene (generate_render_scale_video.py) scaled up by a simple
temporal upscaler of our own, set up to show the artifacts temporal upscalers are known for. It is not DLSS or FSR: it shows how
the artifacts come about, more plainly than they show in those.

The upscaler works the way the page's diagram describes. Every frame renders at the render scale with the camera shifted by a
different fraction of a pixel (a Halton sequence), and writes each pixel's motion since the last frame and its depth. At the
output resolution it then moves the last output (the history) along the motion vectors, drops it where something else lay there
last frame (the depth differs: the pixel was uncovered), clamps it to the range of colours around the pixel in the new frame
(though not all the way: TRUST), and blends the new frame's nearest sample in (BLEND). No anti-aliasing runs before it: like DLSS
and FSR 2, it does the anti-aliasing. TRUST and BLEND are set per artifact, exaggerated so the artifact is plain to see.

Every clip is a split frame, cut across the middle: above the line the scene as it should look, rendered at the output
resolution, below it through the upscaler, with the artifact.
  ghosting: a cube crossing the frame, alone on a plain background, trailing old frames behind it. (Made by the cube writing no
            motion vectors or depth, as particles often do not, so its history stays where it was.)
  disocclusion: a cube crossing a fine checkerboard wall; the wall it uncovers starts again from the render resolution, blurred
            and blocky, and sharpens over the next frames.
  blur: a cube that holds still, moves across, holds and moves back; while it moves the history is resampled every frame, and
            it softens; when it stops it sharpens again.
  flicker: a still wall of thin, slightly tilted lines, finer than the render resolution holds; the upscaler rebuilds them from
            the jittered frames and drops what the current frame does not show, so they shimmer and form moiré bands.
  transparent: a framed glass pane sliding slowly back and forth in front of a brick wall; like most see-through objects it
            writes no motion, so the upscaler moves its history with the wall behind it (not at all): the wall stays sharp
            through the glass, while the pane's frame and highlights smear.

Every clip loops: it renders the clip twice and keeps the second pass, so the history at the start is the one at the end.

Run from the repository's .venv:
  python tools/frame_pacing_video/generate_upscaler_artifacts.py [--artifact ghosting|disocclusion|blur|flicker|transparent] [--scale S] [--output FILE] [--ffmpeg PATH]
"""

# argparse sets the attributes of Arguments (the typed command line) after construction
# pyright: reportUninitializedInstanceVariable=false

import argparse
import math
import random
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import moderngl
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "timing_diagrams"))

from generate_render_scale_video import (  # noqa: E402
    ANISOTROPY,
    BACKGROUND_VERTEX_SHADER,
    CAMERA,
    CUBE_FACES,
    CUBE_VERTICES,
    DEFAULT_OUTPUT_DIR,
    FPS,
    GROUND,
    HORIZON,
    LIGHT,
    OCTA_FACES,
    OCTA_VERTICES,
    OUTPUT_H,
    OUTPUT_W,
    SKY,
    Colour,
    brick_texture,
    checker_texture,
    grained,
    mesh,
    normalised,
    open_context,
    rotation,
)
from generate_videos import find_ffmpeg  # noqa: E402

FRAMES = 240  # 4 s
# The most of a new sample blended in, when it lands on the output pixel's centre: the less, the longer an uncovered area takes
# to sharpen
BLEND = {"ghosting": 0.25, "disocclusion": 0.2, "blur": 0.08, "flicker": 0.7, "transparent": 0.1}
# How much of the history is kept as it was rather than clamped, per artifact: real upscalers clamp less than all the way, to keep
# detail and avoid flicker, and that is where old colours survive; the clips exaggerate it so the artifact is plain to see
TRUST = {"ghosting": 0.95, "disocclusion": 0.9, "blur": 0.0, "flicker": 0.0, "transparent": 0.8}
# The artifacts shown over the sky and ground; the others show the object alone, on a plain background
SKY_ARTIFACTS: frozenset[str] = frozenset()
PLAIN = (28, 33, 41)
# The artifacts shown over a checkerboard wall, and the size of its squares in output pixels
CHECKER: dict[str, float] = {}
CHECKER_COLOURS = ((58, 64, 74), (178, 186, 196))
# The artifacts shown in front of a brick wall, its colour, and the size of a brick texture's tile in output pixels
WALL_ARTIFACTS = frozenset({"disocclusion", "transparent"})
WALL_COLOUR = (150, 118, 104)
WALL_TILE = 200.0
# The artifacts shown over a wall of thin lines: their spacing and width in output pixels, and their tilt in degrees
LINES = {"flicker": (5.0, 1.5, 4.0)}
LINE_COLOUR = (220, 226, 232)
FAR = 1000.0  # the depth of the background, and of what writes none
# How far apart, in output pixels, the four samples are that the history is read with where the image moves: moving history is
# resampled every frame, which blurs it; a wider reading exaggerates that for the blur clip (0: one plain bilinear sample)
RESAMPLE = {"ghosting": 0.0, "disocclusion": 0.0, "blur": 1.0, "flicker": 0.0, "transparent": 0.8}
# How narrowly a new sample counts: its distance to the output pixel is scaled by this before weighting (1: in render pixels,
# so a sample counts across a whole render pixel; the output's pixels per render pixel: only for the output pixels next to it,
# which rebuilds the full resolution over the jittered frames)
SAMPLE_SCALE = {"disocclusion": 4.0}
# The blend where the image does not move, so the blur clip's cube is sharp again as soon as it stops (the others: BLEND)
STILL_BLEND = {"blur": 0.4}
JITTER_PHASES = 16  # a whole number of times in the clip, so the jitter loops with it
# The render scale per artifact: a quarter where the history has to be far sharper than a single frame
SCALE = {"ghosting": 0.5, "disocclusion": 0.25, "blur": 0.5, "flicker": 0.5, "transparent": 0.5}

OBJECT_VERTEX_SHADER = """
#version 330
uniform mat3 rotation;
uniform mat3 previous_rotation;
uniform vec2 centre;           // pixels, from the top left
uniform vec2 previous_centre;
uniform float unit;            // pixels per object unit at the object's centre
uniform vec2 viewport;         // pixels
uniform float camera;
uniform vec2 jitter;           // pixels, OpenGL's axes (y up)
in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;
out vec3 normal;
out vec2 uv;
out vec3 current;   // this frame's and the last frame's position on the screen, times the depth: linear across a triangle,
out vec3 previous;  // so the fragment shader divides them back
vec3 project(mat3 turn, vec2 middle) {
    vec3 p = turn * in_position;
    float depth = camera + p.z;
    vec2 screen = middle + p.xy * unit * camera / depth;
    vec2 ndc = vec2(screen.x / viewport.x * 2.0 - 1.0, 1.0 - screen.y / viewport.y * 2.0);
    return vec3(ndc * depth, depth);
}
void main() {
    current = project(rotation, centre);
    previous = project(previous_rotation, previous_centre);
    float z = (rotation * in_position).z;
    gl_Position = vec4(current.xy + jitter / viewport * 2.0 * current.z, z / 2.0 * current.z, current.z);
    normal = rotation * in_normal;
    uv = in_uv;
}
"""

OBJECT_FRAGMENT_SHADER = """
#version 330
uniform vec3 light;
uniform vec3 colour;
uniform bool textured;
uniform float opacity;
uniform bool writes_motion;  // and its depth
uniform sampler2D surface;
uniform float lod_bias;  // sharper mipmaps at a lower render resolution, as temporal upscalers ask for
in vec3 normal;
in vec2 uv;
in vec3 current;
in vec3 previous;
layout(location = 0) out vec4 fragment;
layout(location = 1) out vec2 motion;  // since the last frame, in texture coordinates
layout(location = 2) out float depth;  // the distance, for the upscaler's check
void main() {
    // Lit on both sides, for the flat pane; a closed object shows only its outsides
    float brightness = 0.38 + 0.62 * abs(dot(normalize(normal), light));
    vec4 base = textured ? texture(surface, uv, lod_bias) : vec4(colour, 1.0);
    fragment = vec4(base.rgb * brightness, base.a * opacity);
    motion = writes_motion ? (current.xy / current.z - previous.xy / previous.z) * 0.5 : vec2(0.0);
    depth = writes_motion ? current.z : 1000.0;
}
"""

BACKGROUND_FRAGMENT_SHADER = """
#version 330
uniform vec3 sky_top;
uniform vec3 sky_bottom;
uniform vec3 ground_top;
uniform vec3 ground_bottom;
uniform float horizon;
uniform float cell;        // the checkerboard's squares in output pixels; none when 0
uniform vec3 check_dark;
uniform vec3 check_light;
uniform vec3 lines;        // spacing and width in output pixels, tilt in radians; none when the spacing is 0
uniform vec3 line_colour;
uniform vec2 jitter;       // pixels, OpenGL's axes
uniform float to_output;   // output pixels per pixel of this frame
uniform bool wall;         // a brick wall instead
uniform sampler2D wall_texture;
uniform float wall_tile;   // output pixels
uniform float lod_bias;
in float down;
layout(location = 0) out vec4 fragment;
layout(location = 1) out vec2 motion;
layout(location = 2) out float depth;
void main() {
    vec3 colour = down < horizon
        ? mix(sky_top, sky_bottom, down)
        : mix(ground_top, ground_bottom, (down - horizon) / (1.0 - horizon));
    if (cell > 0.0) {
        vec2 square = floor((gl_FragCoord.xy - jitter) * to_output / cell);
        colour = mod(square.x + square.y, 2.0) < 1.0 ? check_dark : check_light;
    }
    if (wall) {
        colour = texture(wall_texture, (gl_FragCoord.xy - jitter) * to_output / wall_tile, lod_bias).rgb;
    }
    if (lines.x > 0.0) {
        vec2 at = (gl_FragCoord.xy - jitter) * to_output;
        float across = at.x * cos(lines.z) + at.y * sin(lines.z);
        float off = abs(mod(across, lines.x) - 0.5 * lines.x);  // from the middle of the nearest line
        // The share of this pixel (to_output output pixels wide) the line covers
        float cover = clamp((0.5 * lines.y + 0.5 * to_output - off) / to_output, 0.0, 1.0) * min(1.0, lines.y / to_output);
        colour = mix(colour, line_colour, cover);
    }
    fragment = vec4(colour, 1.0);
    motion = vec2(0.0);
    depth = 1000.0;
}
"""

RESOLVE_SHADER = """
#version 330
uniform sampler2D colour;   // this frame, at the render resolution, jittered
uniform sampler2D motion;
uniform sampler2D history;  // the last output
uniform sampler2D depth;
uniform sampler2D previous_depth;
uniform vec2 low_size;
uniform vec2 out_size;
uniform vec2 jitter;        // render pixels, OpenGL's axes
uniform bool has_history;
uniform float blend;
uniform float trust;       // how much of the history is kept unclamped
uniform float resample;    // output pixels between the history's four samples where it moves
uniform float still_blend; // the blend where it does not move
uniform float sample_scale; // how narrowly a new sample counts
out vec4 fragment;
void main() {
    vec2 uv = gl_FragCoord.xy / out_size;
    vec2 p = uv * low_size;  // this output pixel's centre, in render pixels
    // The render pixel whose jittered sample lies nearest, and how near
    vec2 k = floor(p + jitter);
    vec2 d = k + 0.5 - jitter - p;
    ivec2 texel = clamp(ivec2(k), ivec2(0), ivec2(low_size) - 1);
    vec3 sample_ = texelFetch(colour, texel, 0).rgb;
    float weight = exp(-2.0 * dot(d, d) * sample_scale * sample_scale);
    // The colours around it in this frame: the history is clamped into their range
    vec3 low = sample_;
    vec3 high = sample_;
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec3 c = texelFetch(colour, clamp(texel + ivec2(x, y), ivec2(0), ivec2(low_size) - 1), 0).rgb;
            low = min(low, c);
            high = max(high, c);
        }
    }
    vec2 unjittered = uv + jitter / low_size;
    vec2 previous = uv - texture(motion, unjittered).rg;
    bool inside = all(greaterThanEqual(previous, vec2(0.0))) && all(lessThanEqual(previous, vec2(1.0)));
    // Uncovered: something nearer lay around the history's place last frame than what is here now (the nearest of 3 x 3, so
    // the edges are caught too)
    ivec2 last = ivec2(low_size) - 1;
    float here = texelFetch(depth, clamp(ivec2(unjittered * low_size), ivec2(0), last), 0).r;
    ivec2 there = ivec2(previous * low_size);
    float before = here;
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            before = min(before, texelFetch(previous_depth, clamp(there + ivec2(x, y), ivec2(0), last), 0).r);
        }
    }
    bool uncovered = here - before > 0.1 * before;
    if (!has_history || !inside || uncovered) {
        fragment = vec4(texture(colour, unjittered).rgb, 1.0);
        return;
    }
    vec3 old = texture(history, previous).rgb;
    bool moves = any(greaterThan(abs(previous - uv) * out_size, vec2(0.01)));
    if (resample > 0.0 && moves) {
        vec2 o = 0.5 * resample / out_size;
        old = 0.25 * (texture(history, previous + vec2(-o.x, -o.y)).rgb + texture(history, previous + vec2(o.x, -o.y)).rgb
                    + texture(history, previous + vec2(-o.x, o.y)).rgb + texture(history, previous + vec2(o.x, o.y)).rgb);
    }
    vec3 kept = mix(clamp(old, low, high), old, trust);
    fragment = vec4(mix(kept, sample_, (moves ? blend : still_blend) * weight), 1.0);
}
"""


PANE_VERTICES: tuple[tuple[float, float, float], ...] = ((-1.4, -1.0, 0.0), (1.4, -1.0, 0.0), (1.4, 1.0, 0.0), (-1.4, 1.0, 0.0))
PANE_FACES = ((0, 1, 2, 3),)


def wall_texture() -> Image.Image:
    """A brick wall that tiles without seams: the brick cut at the edge is drawn on both sides in the same shade."""
    size, rows, per_row = 256, 8, 4
    generator = random.Random("wall")
    image = Image.new("RGB", (size, size), (round(WALL_COLOUR[0] * 0.55), round(WALL_COLOUR[1] * 0.55), round(WALL_COLOUR[2] * 0.55)))
    draw = ImageDraw.Draw(image)
    brick_w, row_h = size / per_row, size / rows
    for row in range(rows):
        for index in range(per_row):
            x = index * brick_w - brick_w / 2 * (row % 2)
            shade = generator.uniform(0.88, 1.08)
            fill = tuple(min(255, round(c * shade)) for c in WALL_COLOUR)
            for wrap in (0, size):
                draw.rectangle([x + wrap + 3, row * row_h + 3, x + wrap + brick_w - 3, (row + 1) * row_h - 3], fill=fill)
    return grained(image, generator)


def pane_texture() -> Image.Image:
    """A pane of glass: a light frame, a faintly blue see-through middle, and two bright diagonal highlights (RGBA)."""
    size, frame = 256, 16
    image = Image.new("RGBA", (size, size), (200, 225, 255, 50))
    draw = ImageDraw.Draw(image)
    for offset, width in ((70, 14), (110, 6)):
        draw.line([(offset, size), (offset + size // 2, 0)], fill=(240, 248, 255, 140), width=width)
    draw.rectangle([0, 0, size - 1, size - 1], outline=(232, 236, 240, 255), width=frame)
    return image


@dataclass(frozen=True)
class Thing:
    """One object at one frame: its mesh, look, place (a fraction of the frame), size and turn, and whether it writes motion."""

    shape: str
    texture: str | None
    colour: Colour
    x: float
    y: float
    size: float
    angles: tuple[float, float]
    writes_motion: bool = True
    opacity: float = 1.0


def halton(index: int, base: int) -> float:
    result, fraction = 0.0, 1.0
    while index:
        fraction /= base
        result += fraction * (index % base)
        index //= base
    return result


def jitter(frame: int) -> tuple[float, float]:
    """The camera's shift this frame, in render pixels: Halton (2, 3), centred on the pixel."""
    phase = frame % JITTER_PHASES + 1
    return (halton(phase, 2) - 0.5, halton(phase, 3) - 0.5)


def scene(artifact: str, frame: int, correct: bool) -> list[Thing]:
    """The objects at `frame` of the clip: the render scale videos' three, and what the artifact needs; `correct` is the half
    above the line."""
    across = (frame % FRAMES) / FRAMES
    if artifact == "transparent":
        # One glass pane sliding slowly back and forth in front of the wall, cut by the line through its middle; it writes no
        # motion
        x = 0.5 - 0.22 * math.cos(2 * math.pi * across)
        return [Thing("pane", "pane", (255, 255, 255), x, 0.5, 1.2, (0.15, 0.35), False)]
    if artifact == "flicker":
        return []  # the wall of lines alone
    if artifact == "blur":
        # Hold at a quarter, move to three quarters, hold, move back: a quarter of the clip each, eased
        phase = (frame % FRAMES) / FRAMES
        moving = min(1.0, max(0.0, (phase - 0.25) * 4)) if phase < 0.75 else 1 - (phase - 0.75) * 4
        x = 0.25 + 0.5 * (3 * moving**2 - 2 * moving**3)
        return [Thing("cube", "bricks", (214, 104, 82), x, 0.5, 0.9, (0.5, 0.6))]
    if artifact == "disocclusion":
        # One cube across the checkerboard wall, cut by the line through its middle
        return [Thing("cube", "bricks", (214, 104, 82), -0.1 + 1.2 * across, 0.5, 0.8, (0.5, 0.6))]
    if artifact == "ghosting":
        # One cube across the frame once per clip, off screen at both ends, in its own half; below it writes no motion
        return [Thing("cube", "bricks", (214, 104, 82), -0.1 + 1.2 * across, 0.25 if correct else 0.75, 0.55, (0.5, 0.6), correct)]
    turn = 2 * math.pi * across
    return [
        Thing("cube", "bricks", (214, 104, 82), 0.2, 0.52, 1.0, (0.5 + turn, 2 * turn)),
        Thing("octahedron", "checker", (120, 190, 110), 0.5, 0.5, 1.5, (turn, -2 * turn)),
        Thing("cube", "bricks", (100, 150, 220), 0.8, 0.52, 0.85, (2 * turn, 0.3 + turn)),
    ]


class TemporalRenderer:
    """The scene rendered jittered at the render resolution with its motion, and the temporal upscale to the output."""

    def __init__(self, scale: float) -> None:
        self.ctx: moderngl.Context = open_context(330)
        self.low: tuple[int, int] = (round(OUTPUT_W * scale), round(OUTPUT_H * scale))
        self.objects: moderngl.Program = self.ctx.program(vertex_shader=OBJECT_VERTEX_SHADER, fragment_shader=OBJECT_FRAGMENT_SHADER)
        self.background: moderngl.Program = self.ctx.program(vertex_shader=BACKGROUND_VERTEX_SHADER, fragment_shader=BACKGROUND_FRAGMENT_SHADER)
        self.resolve: moderngl.Program = self.ctx.program(vertex_shader=BACKGROUND_VERTEX_SHADER, fragment_shader=RESOLVE_SHADER)
        quad = self.ctx.buffer(struct.pack("8f", -1, -1, 1, -1, -1, 1, 1, 1))
        self.background_quad: moderngl.VertexArray = self.ctx.vertex_array(self.background, [(quad, "2f", "in_position")])  # pyright: ignore[reportUnknownMemberType]
        self.resolve_quad: moderngl.VertexArray = self.ctx.vertex_array(self.resolve, [(quad, "2f", "in_position")])  # pyright: ignore[reportUnknownMemberType]
        self.meshes: dict[str, moderngl.VertexArray] = {
            name: self.ctx.vertex_array(self.objects, [(self.ctx.buffer(mesh(vertices, faces)), "3f 3f 2f", "in_position", "in_normal", "in_uv")])  # pyright: ignore[reportUnknownMemberType]
            for name, (vertices, faces) in {
                "cube": (CUBE_VERTICES, CUBE_FACES),
                "octahedron": (OCTA_VERTICES, OCTA_FACES),
                "pane": (PANE_VERTICES, PANE_FACES),
            }.items()
        }
        self.textures: dict[tuple[str, Colour], moderngl.Texture] = {}
        self.colour: moderngl.Texture = self.ctx.texture(self.low, 4)
        self.motion: moderngl.Texture = self.ctx.texture(self.low, 2, dtype="f4")
        for texture in (self.colour, self.motion):
            texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
            texture.repeat_x = texture.repeat_y = False
        depth_buffer = self.ctx.depth_renderbuffer(self.low)
        # This frame's depth and the last frame's, swapped each frame with the history
        self.depths: list[moderngl.Texture] = [self.ctx.texture(self.low, 1, dtype="f4") for _ in range(2)]
        self.frames: list[moderngl.Framebuffer] = [
            self.ctx.framebuffer(color_attachments=[self.colour, self.motion, depth], depth_attachment=depth_buffer) for depth in self.depths
        ]
        # The same scene at the output resolution, as it should look
        self.native: moderngl.Framebuffer = self.ctx.framebuffer(
            color_attachments=[
                self.ctx.texture((OUTPUT_W, OUTPUT_H), 4),
                self.ctx.texture((OUTPUT_W, OUTPUT_H), 2, dtype="f4"),
                self.ctx.texture((OUTPUT_W, OUTPUT_H), 1, dtype="f4"),
            ],
            depth_attachment=self.ctx.depth_renderbuffer((OUTPUT_W, OUTPUT_H)),
        )
        # The history: two textures the upscaler swaps between
        self.histories: list[moderngl.Texture] = [self.ctx.texture((OUTPUT_W, OUTPUT_H), 4, dtype="f2") for _ in range(2)]
        for texture in self.histories:
            texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
            texture.repeat_x = texture.repeat_y = False
        self.outputs: list[moderngl.Framebuffer] = [self.ctx.framebuffer(color_attachments=[texture]) for texture in self.histories]
        self.current: int = 0
        self.has_history: bool = False

    def texture(self, kind: str, colour: Colour) -> moderngl.Texture:
        key = (kind, colour)
        if key not in self.textures:
            textures = {"pane": pane_texture, "wall": wall_texture}
            image = textures[kind]() if kind in textures else brick_texture(colour) if kind == "bricks" else checker_texture(colour)
            texture = self.ctx.texture(image.size, len(image.getbands()), image.tobytes(), alignment=1)
            texture.build_mipmaps()
            texture.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            texture.anisotropy = ANISOTROPY
            self.textures[key] = texture
        return self.textures[key]

    def draw(
        self,
        things: list[Thing],
        before: list[Thing],
        shift: tuple[float, float],
        sky: bool,
        cell: float,
        native: bool = False,
        lines: tuple[float, float, float] = (0.0, 0.0, 0.0),
        wall: bool = False,
    ) -> None:
        """This frame at the render resolution (or the output's, `native`), shifted by `shift` render pixels, with each
        object's motion since `before` and its depth, over the `sky` and ground, a checkerboard of `cell` output pixels, or a
        plain background."""
        target = self.native if native else self.frames[1 - self.current]
        width, height = (OUTPUT_W, OUTPUT_H) if native else self.low
        target.use()
        # Clearing sets every attachment, the motion too, so it clears to no motion and the background is drawn: the sky and
        # ground, or one plain colour
        target.clear(0.0, 0.0, 0.0, 0.0)
        self.ctx.disable(moderngl.DEPTH_TEST)
        colours = (*SKY, *GROUND) if sky else (PLAIN,) * 4
        for name, value in zip(("sky_top", "sky_bottom", "ground_top", "ground_bottom"), colours, strict=True):
            self.background[name].value = tuple(c / 255 for c in value)  # pyright: ignore[reportAttributeAccessIssue]
        self.background["horizon"].value = HORIZON  # pyright: ignore[reportAttributeAccessIssue]
        self.background["cell"].value = cell  # pyright: ignore[reportAttributeAccessIssue]
        self.background["check_dark"].value = tuple(c / 255 for c in CHECKER_COLOURS[0])  # pyright: ignore[reportAttributeAccessIssue]
        self.background["check_light"].value = tuple(c / 255 for c in CHECKER_COLOURS[1])  # pyright: ignore[reportAttributeAccessIssue]
        self.background["jitter"].value = shift  # pyright: ignore[reportAttributeAccessIssue]
        self.background["lines"].value = (lines[0], lines[1], math.radians(lines[2]))  # pyright: ignore[reportAttributeAccessIssue]
        self.background["line_colour"].value = tuple(c / 255 for c in LINE_COLOUR)  # pyright: ignore[reportAttributeAccessIssue]
        self.background["to_output"].value = OUTPUT_W / width  # pyright: ignore[reportAttributeAccessIssue]
        self.background["wall"].value = wall  # pyright: ignore[reportAttributeAccessIssue]
        # The mip bias DLSS and FSR ask for: log2 of the render resolution over the output's, so a frame at the render
        # resolution samples the textures as sharply as the output would, and the jittered frames add up to that detail
        lod_bias = math.log2(width / OUTPUT_W)
        self.background["lod_bias"].value = lod_bias  # pyright: ignore[reportAttributeAccessIssue]
        self.objects["lod_bias"].value = lod_bias  # pyright: ignore[reportAttributeAccessIssue]
        self.background["wall_tile"].value = WALL_TILE  # pyright: ignore[reportAttributeAccessIssue]
        self.texture("wall", WALL_COLOUR).use(location=5)
        self.background["wall_texture"].value = 5  # pyright: ignore[reportAttributeAccessIssue]
        self.background_quad.render(moderngl.TRIANGLE_STRIP)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.objects["viewport"].value = (width, height)  # pyright: ignore[reportAttributeAccessIssue]
        self.objects["camera"].value = CAMERA  # pyright: ignore[reportAttributeAccessIssue]
        self.objects["light"].value = normalised(LIGHT)  # pyright: ignore[reportAttributeAccessIssue]
        self.objects["jitter"].value = shift  # pyright: ignore[reportAttributeAccessIssue]
        unit = 0.2 * height
        for thing, last in zip(things, before, strict=True):
            self.objects["rotation"].value = rotation(*thing.angles)  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["previous_rotation"].value = rotation(*last.angles)  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["centre"].value = (thing.x * width, thing.y * height)  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["previous_centre"].value = (last.x * width, last.y * height)  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["unit"].value = unit * thing.size  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["colour"].value = tuple(c / 255 for c in thing.colour)  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["textured"].value = thing.texture is not None  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["writes_motion"].value = thing.writes_motion  # pyright: ignore[reportAttributeAccessIssue]
            self.objects["opacity"].value = thing.opacity  # pyright: ignore[reportAttributeAccessIssue]
            if thing.texture is not None:
                self.texture(thing.texture, thing.colour).use(location=0)
                self.objects["surface"].value = 0  # pyright: ignore[reportAttributeAccessIssue]
            if thing.texture == "pane":
                # Blended over what is behind, by the texture's alpha; the motion and depth it writes are none and far, so
                # blending them with the background's keeps them as they were
                self.ctx.enable(moderngl.BLEND)
                self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            self.meshes[thing.shape].render(moderngl.TRIANGLES)
            self.ctx.disable(moderngl.BLEND)

    def upscale(self, shift: tuple[float, float], trust: float, blend: float, resample: float, still_blend: float, sample_scale: float) -> Image.Image:
        """The temporal upscale of the frame just drawn into the next history, read back as the output frame."""
        current = self.current
        previous, target = self.histories[current], self.outputs[1 - current]
        target.use()
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.colour.use(location=0)
        self.motion.use(location=1)
        previous.use(location=2)
        self.depths[1 - current].use(location=3)
        self.depths[current].use(location=4)
        for name, value in (("colour", 0), ("motion", 1), ("history", 2), ("depth", 3), ("previous_depth", 4)):
            self.resolve[name].value = value  # pyright: ignore[reportAttributeAccessIssue]
        self.resolve["low_size"].value = self.low  # pyright: ignore[reportAttributeAccessIssue]
        self.resolve["out_size"].value = (OUTPUT_W, OUTPUT_H)  # pyright: ignore[reportAttributeAccessIssue]
        self.resolve["jitter"].value = shift  # pyright: ignore[reportAttributeAccessIssue]
        self.resolve["has_history"].value = self.has_history  # pyright: ignore[reportAttributeAccessIssue]
        self.resolve["blend"].value = blend  # pyright: ignore[reportAttributeAccessIssue]
        self.resolve["trust"].value = trust  # pyright: ignore[reportAttributeAccessIssue]
        self.resolve["resample"].value = resample  # pyright: ignore[reportAttributeAccessIssue]
        self.resolve["still_blend"].value = still_blend  # pyright: ignore[reportAttributeAccessIssue]
        self.resolve["sample_scale"].value = sample_scale  # pyright: ignore[reportAttributeAccessIssue]
        self.resolve_quad.render(moderngl.TRIANGLE_STRIP)
        self.current = 1 - current
        self.has_history = True
        pixels = target.read(components=3, alignment=1)
        return Image.frombytes("RGB", (OUTPUT_W, OUTPUT_H), pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM)

    def step(self, artifact: str, frame: int) -> Image.Image:
        """The frame through the upscaler, with the artifact."""
        shift = jitter(frame)
        things, before = scene(artifact, frame, False), scene(artifact, frame - 1, False)
        self.draw(
            things,
            before,
            shift,
            artifact in SKY_ARTIFACTS,
            CHECKER.get(artifact, 0.0),
            lines=LINES.get(artifact, (0.0, 0.0, 0.0)),
            wall=artifact in WALL_ARTIFACTS,
        )
        blend = BLEND[artifact]
        return self.upscale(shift, TRUST[artifact], blend, RESAMPLE[artifact], STILL_BLEND.get(artifact, blend), SAMPLE_SCALE.get(artifact, 1.0))

    def correct(self, artifact: str, frame: int) -> Image.Image:
        """The frame as it should look: rendered at the output resolution."""
        things, before = scene(artifact, frame, True), scene(artifact, frame - 1, True)
        self.draw(
            things,
            before,
            (0.0, 0.0),
            artifact in SKY_ARTIFACTS,
            CHECKER.get(artifact, 0.0),
            True,
            LINES.get(artifact, (0.0, 0.0, 0.0)),
            artifact in WALL_ARTIFACTS,
        )
        pixels = self.native.read(components=3, alignment=1)
        return Image.frombytes("RGB", (OUTPUT_W, OUTPUT_H), pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def label(frame: Image.Image, top: int, title: str, sub: str) -> None:
    draw = ImageDraw.Draw(frame)
    font = ImageFont.load_default(size=18)
    small = ImageFont.load_default(size=13)
    width = max(draw.textlength(title, font=font), draw.textlength(sub, font=small)) + 24
    draw.rounded_rectangle([16, top, 16 + width, top + 58], radius=8, fill=(18, 21, 25))
    draw.text((28, top + 6), title, fill=(230, 237, 243), font=font)
    draw.text((28, top + 32), sub, fill=(139, 148, 158), font=small)


LABELS = {
    "ghosting": (("As it should look", "the moving cube"), ("Ghosting", "old frames trail behind the moving cube")),
    "transparent": (
        ("As it should look", "a glass pane in front of a wall"),
        ("Soft transparent edges", "the glass smears; the wall behind it stays sharp"),
    ),
    "flicker": (("As it should look", "a still wall of thin lines"), ("Flicker", "the thin lines shimmer and form moire bands")),
    "blur": (("As it should look", "the cube, still and moving"), ("Blur in motion", "the cube softens while it moves")),
    "disocclusion": (("As it should look", "the wall behind the moving cube"), ("Disocclusion", "the wall it uncovers is blurred and blocky at first")),
}


def frames(artifact: str, scale: float) -> list[bytes]:
    """The clip: rendered twice through each half's upscaler, the second pass kept, split across the middle."""
    renderer = TemporalRenderer(scale)
    half = OUTPUT_H // 2
    (title_above, sub_above), (title_below, sub_below) = LABELS[artifact]
    out: list[bytes] = []
    for index in range(2 * FRAMES):
        wrong = renderer.step(artifact, index)
        if index < FRAMES:
            continue
        frame = renderer.correct(artifact, index)
        frame.paste(wrong.crop((0, half, OUTPUT_W, OUTPUT_H)), (0, half))
        ImageDraw.Draw(frame).line([(0, half), (OUTPUT_W, half)], fill=(230, 237, 243), width=2)
        label(frame, 14, title_above, sub_above)
        label(frame, OUTPUT_H - 14 - 58, title_below, sub_below)
        out.append(frame.tobytes())
    return out


class Arguments(argparse.Namespace):
    artifact: str
    scale: float | None
    output: Path | None
    ffmpeg: str | None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an upscaler artifact video (H.264, for the web page).")
    _ = parser.add_argument("--artifact", choices=tuple(LABELS), default="ghosting", help="the artifact to show (default: ghosting)")
    _ = parser.add_argument("--scale", type=float, default=None, help="the render scale per axis (default: the artifact's, SCALE)")
    _ = parser.add_argument("--output", type=Path, default=None, help=f"the video file (default: {DEFAULT_OUTPUT_DIR}/upscaler-ARTIFACT.mp4)")
    _ = parser.add_argument("--ffmpeg", default=None, help="FFmpeg executable or its folder (default: MB_FFMPEG, local.toml, then PATH)")
    args = parser.parse_args(namespace=Arguments())
    ffmpeg = find_ffmpeg(args.ffmpeg).path
    output = args.output or DEFAULT_OUTPUT_DIR / f"upscaler-{args.artifact}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    video = frames(args.artifact, args.scale or SCALE[args.artifact])
    command = [
        str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUTPUT_W}x{OUTPUT_H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", "12", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output),
    ]  # fmt: skip
    _ = subprocess.run(command, input=b"".join(video), check=True)
    print(f"{output}: {len(video)} frames, {len(video) / FPS:g} s")


if __name__ == "__main__":
    main()
